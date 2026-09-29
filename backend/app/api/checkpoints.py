from datetime import datetime, timezone
from typing import List
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_student_id
from app.db.database import get_db
from app.models.domain import ConversationCheckpoint, Message, Session
from app.schemas.domain import CheckpointCreate, CheckpointResponse, SessionResponse
from app.services.llm_service import (
    CHECKPOINT_CONTEXT_KIND, CheckpointError, format_checkpoint_context, generate_conversation_checkpoint,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _own_session(db: AsyncSession, session_id: str, student_id: str) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalars().first()
    # Same 404 for "missing" and "someone else's" so ids can't be probed
    if not session or session.student_id != student_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _own_checkpoint(db: AsyncSession, checkpoint_id: str, student_id: str) -> tuple[ConversationCheckpoint, Session]:
    result = await db.execute(
        select(ConversationCheckpoint, Session)
        .join(Session, Session.id == ConversationCheckpoint.session_id)
        .where(ConversationCheckpoint.id == checkpoint_id)
    )
    row = result.first()
    if not row or row[1].student_id != student_id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return row[0], row[1]


@router.post("/", response_model=CheckpointResponse)
async def create_checkpoint(
    data: CheckpointCreate,
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    await _own_session(db, data.session_id, student_id)
    msg = await db.get(Message, data.message_id)
    if not msg or msg.session_id != data.session_id:
        raise HTTPException(status_code=400, detail="That message is not part of this conversation.")
    try:
        summary_text, tokens = await generate_conversation_checkpoint(db, data.session_id, data.message_id)
    except CheckpointError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Checkpoint generation failed: {e}")
        raise HTTPException(status_code=502, detail="Could not create the summary right now. Please try again.")
    checkpoint = ConversationCheckpoint(
        session_id=data.session_id, message_id=data.message_id, summary_text=summary_text,
        summary_token_count=tokens, source="manual",
    )
    db.add(checkpoint)
    await db.commit()
    await db.refresh(checkpoint)
    return checkpoint


@router.get("/session/{session_id}", response_model=List[CheckpointResponse])
async def list_session_checkpoints(
    session_id: str,
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    await _own_session(db, session_id, student_id)
    result = await db.execute(
        select(ConversationCheckpoint)
        .where(ConversationCheckpoint.session_id == session_id)
        .order_by(ConversationCheckpoint.created_at.asc())
    )
    return result.scalars().all()


@router.get("/{checkpoint_id}", response_model=CheckpointResponse)
async def get_checkpoint(
    checkpoint_id: str,
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    checkpoint, _ = await _own_checkpoint(db, checkpoint_id, student_id)
    return checkpoint


@router.post("/{checkpoint_id}/continue", response_model=SessionResponse)
async def continue_from_checkpoint(
    checkpoint_id: str,
    student_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    checkpoint, original = await _own_checkpoint(db, checkpoint_id, student_id)
    try:
        summary = json.loads(checkpoint.summary_text)
    except ValueError:
        summary = {}
    base = original.title or (summary.get("topic") if summary.get("topic") not in (None, "unknown") else None) or "Chat"
    title = f"{base[:48]} (continued)"

    new_session = Session(student_id=student_id, title=title)
    db.add(new_session)
    await db.flush()
    # Trusted tutor context for the model; the chat UI shows it as a "continued from checkpoint" card
    db.add(Message(
        session_id=new_session.id, role="system", kind=CHECKPOINT_CONTEXT_KIND,
        content=format_checkpoint_context(summary) if summary else checkpoint.summary_text,
        timestamp=_now(),
    ))
    await db.commit()
    await db.refresh(new_session)
    return new_session
