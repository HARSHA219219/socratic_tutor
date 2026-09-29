from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import AsyncIterator, Awaitable, Callable, List, Literal, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from dataclasses import dataclass
import asyncio
import logging
import re

from app.core.config import settings
from app.core.security import get_current_student_id
from app.db.database import AsyncSessionLocal, get_db
from app.models.domain import Session, Message, MessageAttachment
from app.schemas.domain import MessageResponse
from app.services.llm_service import generate_tutor_response, generate_session_title, stream_tutor_response
from app.services.hint_planner import plan_next_hint, suggested_level, hint_level, hint_total
import json
from app.services.attachment_service import (
    AttachmentError, PreparedAttachment, check_context_budget, delete_stored, prepare_document, prepare_image,
    read_uploads, store_attachments, summarize_message_images,
)

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    session_id: str
    message: str = ""
    # "hint" climbs the hint ladder one step; "answer" asks for the full solution
    mode: Literal["normal", "hint", "answer"] = "normal"

# Fallback hint instructions, used only if the adaptive hint planner fails.
# Keyed by stage: 1 = first hint, 2 = middle hints, 3 = final hint.
HINT_INSTRUCTIONS = {
    1: ("The student pressed 'Give me a hint' (first hint: a nudge). Reply with a gentle nudge only: "
        "one short guiding question or pointer toward the key idea of their latest question. "
        "Do not name the method, show steps, or reveal the answer. At most 2-3 sentences."),
    2: ("The student pressed 'Give me a hint' again (a bigger hint). Name the relevant concept, "
        "rule or formula and explain how it connects to their problem, but do not solve it or give the answer. "
        "End with a question that invites them to try the next step."),
    3: ("The student pressed 'Give me a hint' again (final hint: a worked step). Work out the first "
        "concrete step of the solution clearly, then ask the student to do the next step themselves. "
        "Do not give the final answer."),
}

ANSWER_INSTRUCTION = (
    "The student explicitly pressed 'Show me the answer'. For this reply only, set the Socratic approach aside: "
    "give the complete, correct answer to their latest question with a clear step-by-step explanation. "
    "Finish with one short question that checks they understood the key idea."
)

def _now() -> datetime:
    # Naive UTC with microseconds: SQLite's CURRENT_TIMESTAMP is only second-precise,
    # which let a question and its reply (or a hint request) tie when ordering.
    return datetime.now(timezone.utc).replace(tzinfo=None)

HINT_REQUEST_TEXT = "Can I have a hint?"
ANSWER_REQUEST_TEXT = "Please show me the full answer."

class ChatResponse(BaseModel):
    session_id: str
    response: str
    session_title: Optional[str] = None
    user_message: Optional[MessageResponse] = None
    assistant_message: Optional[MessageResponse] = None

async def _get_own_session(db: AsyncSession, session_id: str, student_id: str) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalars().first()
    # Same 404 for "missing" and "someone else's" so session ids can't be probed
    if not session or session.student_id != student_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

async def _session_history(db: AsyncSession, session_id: str) -> list[Message]:
    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.timestamp.asc()))
    history = list(result.scalars().all())
    if not any(m.role == "user" and not m.kind for m in history):
        raise HTTPException(status_code=400, detail="Ask a question first, then you can ask for a hint.")
    return history

@dataclass
class HintMeta:
    total: int
    allow_answer: bool = True
    assessment: Optional[dict] = None

async def _save_user_message(
    db: AsyncSession,
    session: Session,
    text: str,
    attachments: Optional[list[PreparedAttachment]] = None,
    kind: Optional[str] = None,
    hint: Optional[HintMeta] = None,
) -> Message:
    """Saves the student's message with all of its (already validated) attachments.
    Files go to disk under random names; SQLite gets one message_attachments row per file.
    If saving fails, files already written are removed again."""
    saved = await store_attachments(attachments) if attachments else []
    try:
        user_msg = Message(session_id=session.id, role="user", content=text, kind=kind, timestamp=_now())
        if hint:
            user_msg.hint_total = hint.total
        first_image = first_doc = None
        for position, (p, key) in enumerate(saved):
            att = MessageAttachment(
                position=position, kind=p.kind, storage_key=key, name=p.name, mime_type=p.mime,
                size_bytes=len(p.data), extracted_text=p.text, text_status=p.text_status,
            )
            user_msg.attachments.append(att)
            if p.kind == "image" and first_image is None:
                first_image = (p, key)
            if p.kind == "document" and first_doc is None:
                first_doc = (p, key)
        # Legacy single-file columns mirror the first image / document (older clients and endpoints)
        if first_image:
            p, key = first_image
            user_msg.image_key, user_msg.image_mime_type, user_msg.image_size_bytes = key, p.mime, len(p.data)
        if first_doc:
            p, key = first_doc
            user_msg.document_key, user_msg.document_name = key, p.name
            user_msg.document_mime_type, user_msg.document_size_bytes = p.mime, len(p.data)
            user_msg.document_text, user_msg.document_text_status = p.text, p.text_status
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)
        return user_msg
    except Exception:
        await db.rollback()
        delete_stored(saved)
        raise

async def _save_reply(
    db: AsyncSession,
    session: Session,
    user_msg: Message,
    reply_text: str,
    hint: Optional[HintMeta] = None,
) -> ChatResponse:
    """Stores exactly one tutor reply (same kind as the request) and names a new chat."""
    kind = user_msg.kind
    tutor_msg = Message(session_id=session.id, role="assistant", content=reply_text, kind=kind, timestamp=_now())
    if hint:
        tutor_msg.hint_total = hint.total
        tutor_msg.hint_allow_answer = hint.allow_answer
        tutor_msg.hint_assessment = json.dumps(hint.assessment) if hint.assessment else None
    db.add(tutor_msg)

    # Name the chat after its first message (ChatGPT-style)
    if not session.title and kind is None:
        title_source = user_msg.content or (f"Help with {user_msg.document_name}" if user_msg.document_name else "")
        session.title = await generate_session_title(db, title_source, bool(user_msg.image_key))
    await db.commit()
    await db.refresh(tutor_msg)

    return ChatResponse(
        session_id=session.id,
        response=reply_text,
        session_title=session.title,
        user_message=MessageResponse.model_validate(user_msg),
        assistant_message=MessageResponse.model_validate(tutor_msg),
    )

async def _handle_chat(
    db: AsyncSession,
    session: Session,
    text: str,
    attachments: Optional[list[PreparedAttachment]] = None,
    kind: Optional[str] = None,
    instruction: Optional[str] = None,
    hint: Optional[HintMeta] = None,
    reply_text: Optional[str] = None,
) -> ChatResponse:
    user_msg = await _save_user_message(db, session, text, attachments, kind, hint)
    try:
        # Generate tutor response (unless it was already produced, e.g. by the hint planner)
        tutor_response_text = reply_text if reply_text is not None else await generate_tutor_response(db, session.id, instruction)
    except Exception as e:
        logger.error(f"Error calling LLM: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to communicate with LLM")
    return await _save_reply(db, session, user_msg, tutor_response_text, hint)

async def _suggested_hint_level(db: AsyncSession, session: Session) -> tuple[list[Message], int]:
    history = await _session_history(db, session.id)
    suggested = suggested_level(history)
    if suggested is None:
        raise HTTPException(
            status_code=400,
            detail="You've used all the hints for this question. Try a step yourself, or reveal the answer.",
        )
    return history, suggested

def _fallback_hint(history: list[Message], suggested: int) -> tuple[str, str, HintMeta]:
    """Fixed-stage hint used when the planner is unavailable: (kind, instruction, meta)."""
    previous = [m for m in history if m.role == "assistant" and hint_level(m.kind)]
    total = hint_total(previous[-1]) if previous and suggested > 1 else 3
    total = max(total, suggested)
    stage = 1 if suggested == 1 else 3 if suggested >= total else 2
    return f"hint-{suggested}", HINT_INSTRUCTIONS[stage], HintMeta(total=total)

async def _handle_hint(db: AsyncSession, session: Session) -> ChatResponse:
    """Adaptive hint: the planner decides how many hints fit this question and writes the next one."""
    history, suggested = await _suggested_hint_level(db, session)

    plan = await plan_next_hint(db, history, suggested)
    if plan:
        meta = HintMeta(total=plan.total, allow_answer=plan.allow_answer, assessment=plan.assessment)
        return await _handle_chat(db, session, HINT_REQUEST_TEXT, kind=f"hint-{plan.level}", hint=meta, reply_text=plan.next_hint)

    # Planner unavailable or returned bad JSON: fixed-stage hint from the normal tutor call
    kind, instruction, meta = _fallback_hint(history, suggested)
    return await _handle_chat(db, session, HINT_REQUEST_TEXT, kind=kind, instruction=instruction, hint=meta)

async def _read_image(image: UploadFile) -> PreparedAttachment:
    # Read at most one byte over the limit so huge uploads are rejected without buffering them
    data = await image.read(settings.MAX_IMAGE_BYTES + 1)
    try:
        prepared = prepare_image(data, image.filename or "")
        check_context_budget([prepared])
    except AttachmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return prepared

async def _read_document(document: UploadFile) -> PreparedAttachment:
    # Read at most one byte over the limit so huge uploads are rejected without buffering them
    data = await document.read(settings.MAX_DOCUMENT_BYTES + 1)
    try:
        # Nothing is saved on failure, so the tutor never "pretends" to have read the file
        prepared = await prepare_document(data, document.filename or "")
        check_context_budget([prepared])
    except AttachmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return prepared

async def _read_attachments(files: List[UploadFile]) -> list[PreparedAttachment]:
    try:
        return await read_uploads(files)
    except AttachmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, student_id: str = Depends(get_current_student_id), db: AsyncSession = Depends(get_db)):
    # Verify session exists and belongs to the signed-in student
    session = await _get_own_session(db, request.session_id, student_id)
    if request.mode == "hint":
        return await _handle_hint(db, session)
    if request.mode == "answer":
        await _session_history(db, session.id)  # same "ask a question first" check
        return await _handle_chat(db, session, ANSWER_REQUEST_TEXT, kind="answer", instruction=ANSWER_INSTRUCTION)
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return await _handle_chat(db, session, request.message)

async def _chat_with_uploads(
    db: AsyncSession, session: Session, text: str, prepared: list[PreparedAttachment], background: BackgroundTasks,
) -> ChatResponse:
    response = await _handle_chat(db, session, text, prepared)
    if any(p.kind == "image" for p in prepared):
        background.add_task(summarize_message_images, response.user_message.id)
    return response

@router.post("/image", response_model=ChatResponse)
async def chat_with_image(
    background: BackgroundTasks,
    session_id: str = Form(...),
    message: str = Form(""),
    image: UploadFile = File(...),
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_own_session(db, session_id, student_id)
    prepared = await _read_image(image)
    return await _chat_with_uploads(db, session, message.strip(), [prepared], background)

@router.post("/document", response_model=ChatResponse)
async def chat_with_document(
    background: BackgroundTasks,
    session_id: str = Form(...),
    message: str = Form(""),
    document: UploadFile = File(...),
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_own_session(db, session_id, student_id)
    prepared = await _read_document(document)
    return await _chat_with_uploads(db, session, message.strip(), [prepared], background)

@router.post("/attachments", response_model=ChatResponse)
async def chat_with_attachments(
    background: BackgroundTasks,
    session_id: str = Form(...),
    message: str = Form(""),
    files: List[UploadFile] = File(...),
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """One message with several files (images and/or PDF, DOCX, TXT documents)."""
    session = await _get_own_session(db, session_id, student_id)
    prepared = await _read_attachments(files)
    return await _chat_with_uploads(db, session, message.strip(), prepared, background)

# =====================================================================
# Streaming (Server-Sent Events)
# =====================================================================

SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
SSE_DONE = "data: [DONE]\n\n"
STREAM_ERROR_MESSAGE = "Unable to generate tutor response"
_WORD_RE = re.compile(r"\s*\S+\s*")

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def _dump(msg: Optional[Message]) -> Optional[dict]:
    return MessageResponse.model_validate(msg).model_dump(mode="json") if msg is not None else None

@dataclass
class StreamTurn:
    """One streamed tutor turn. Validation (and, except for hints, the student's message)
    happens before streaming starts so the usual HTTP errors are still returned."""
    session_id: str
    user_message_id: Optional[str] = None
    instruction: Optional[str] = None
    # Hint mode: the planner runs inside the stream, then the request message is saved
    hint_level: Optional[int] = None

async def stream_turn_events(
    turn: StreamTurn,
    is_disconnected: Optional[Callable[[], Awaitable[bool]]] = None,
) -> AsyncIterator[str]:
    """Yields SSE events: start, (user_message), chunk..., complete | error, then [DONE].

    The tutor reply is stored only after the whole stream arrived, exactly once. If the
    client goes away (generator closed / cancelled) nothing is stored for the reply.
    """
    chunks: list[str] = []
    upstream = None
    # Own DB session: the request-scoped one may be closed while the body is still streaming
    async with AsyncSessionLocal() as db:
        try:
            session = await db.get(Session, turn.session_id)
            user_msg = await db.get(Message, turn.user_message_id) if turn.user_message_id else None
            yield _sse({"type": "start", "session_id": turn.session_id, "user_message": _dump(user_msg)})

            hint_meta: Optional[HintMeta] = None
            instruction = turn.instruction
            prepared_text: Optional[str] = None
            if turn.hint_level is not None:
                history = await _session_history(db, session.id)
                plan = await plan_next_hint(db, history, turn.hint_level)
                if plan:
                    hint_meta = HintMeta(total=plan.total, allow_answer=plan.allow_answer, assessment=plan.assessment)
                    kind, prepared_text = f"hint-{plan.level}", plan.next_hint
                else:
                    kind, instruction, hint_meta = _fallback_hint(history, turn.hint_level)
                user_msg = await _save_user_message(db, session, HINT_REQUEST_TEXT, kind=kind, hint=hint_meta)
                yield _sse({"type": "user_message", "user_message": _dump(user_msg)})

            if prepared_text is not None:
                # The planner returns the whole hint as JSON, so it is sent word by word
                for piece in _WORD_RE.findall(prepared_text):
                    chunks.append(piece)
                    yield _sse({"type": "chunk", "text": piece})
            else:
                upstream = stream_tutor_response(db, session.id, instruction)
                async for piece in upstream:
                    chunks.append(piece)
                    yield _sse({"type": "chunk", "text": piece})

            reply = "".join(chunks)
            if not reply.strip():
                raise RuntimeError("empty tutor response")
            if is_disconnected is not None and await is_disconnected():
                return  # nobody is listening: don't store a reply they never saw
            saved = await _save_reply(db, session, user_msg, reply, hint_meta)
            yield _sse({
                "type": "complete",
                "message_id": saved.assistant_message.id,
                "session_title": saved.session_title,
                "user_message": saved.user_message.model_dump(mode="json"),
                "assistant_message": saved.assistant_message.model_dump(mode="json"),
            })
        except (asyncio.CancelledError, GeneratorExit):
            await db.rollback()
            raise
        except Exception as e:
            logger.error(f"Streaming tutor response failed: {e}")
            await db.rollback()
            yield _sse({"type": "error", "message": STREAM_ERROR_MESSAGE})
        finally:
            if upstream is not None:
                await upstream.aclose()  # stop reading from the model
    yield SSE_DONE

def _sse_response(turn: StreamTurn, request: Request, summarize_images: bool = False) -> StreamingResponse:
    return StreamingResponse(
        stream_turn_events(turn, request.is_disconnected),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
        # After the tutor has seen the originals, describe new images once for later turns
        background=BackgroundTask(summarize_message_images, turn.user_message_id) if summarize_images else None,
    )

@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """Streaming version of POST /api/chat/ (same request body)."""
    session = await _get_own_session(db, body.session_id, student_id)
    if body.mode == "hint":
        _, suggested = await _suggested_hint_level(db, session)
        return _sse_response(StreamTurn(session_id=session.id, hint_level=suggested), request)
    if body.mode == "answer":
        await _session_history(db, session.id)  # same "ask a question first" check
        user_msg = await _save_user_message(db, session, ANSWER_REQUEST_TEXT, kind="answer")
        return _sse_response(StreamTurn(session.id, user_msg.id, ANSWER_INSTRUCTION), request)
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    user_msg = await _save_user_message(db, session, body.message)
    return _sse_response(StreamTurn(session.id, user_msg.id), request)

@router.post("/stream/image")
async def chat_stream_image(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(""),
    image: UploadFile = File(...),
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_own_session(db, session_id, student_id)
    prepared = await _read_image(image)
    user_msg = await _save_user_message(db, session, message.strip(), [prepared])
    return _sse_response(StreamTurn(session.id, user_msg.id), request, summarize_images=True)

@router.post("/stream/document")
async def chat_stream_document(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(""),
    document: UploadFile = File(...),
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_own_session(db, session_id, student_id)
    prepared = await _read_document(document)
    user_msg = await _save_user_message(db, session, message.strip(), [prepared])
    return _sse_response(StreamTurn(session.id, user_msg.id), request)

@router.post("/stream/attachments")
async def chat_stream_attachments(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(""),
    files: List[UploadFile] = File(...),
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """Streaming version of POST /api/chat/attachments."""
    session = await _get_own_session(db, session_id, student_id)
    prepared = await _read_attachments(files)
    user_msg = await _save_user_message(db, session, message.strip(), prepared)
    has_images = any(p.kind == "image" for p in prepared)
    return _sse_response(StreamTurn(session.id, user_msg.id), request, summarize_images=has_images)

@router.get("/session/{session_id}", response_model=List[MessageResponse])
async def get_session_messages(session_id: str, student_id: str = Depends(get_current_student_id), db: AsyncSession = Depends(get_db)):
    await _get_own_session(db, session_id, student_id)
    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.timestamp.asc()))
    return result.scalars().all()
