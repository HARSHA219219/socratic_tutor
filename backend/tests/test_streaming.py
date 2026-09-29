"""Streaming tutor replies (Server-Sent Events) for text, hints, answers, images and documents."""
import asyncio
import json

from sqlalchemy import select

from app.api.chat import StreamTurn, _save_user_message, stream_turn_events
from app.db.database import AsyncSessionLocal
from app.models.domain import Message, Session

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
TUTOR_REPLY = "What do you notice first?"


def new_session(client, headers):
    return client.post("/api/sessions/", json={}, headers=headers).json()["id"]


def parse_sse(text: str) -> list:
    """Events in order; '[DONE]' stays a string, everything else is parsed JSON."""
    events = []
    for block in text.split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.split("\n") if line.startswith("data:"))
        if data:
            events.append(data if data == "[DONE]" else json.loads(data))
    return events


def stream(client, headers, sid, message="", mode="normal"):
    res = client.post("/api/chat/stream", json={"session_id": sid, "message": message, "mode": mode}, headers=headers)
    assert res.status_code == 200, res.text
    return res, parse_sse(res.text)


def assistant_rows(sid):
    async def q():
        async with AsyncSessionLocal() as db:
            rows = await db.execute(select(Message).where(Message.session_id == sid, Message.role == "assistant"))
            return rows.scalars().all()
    return asyncio.run(q())


def stream_calls(fake_llm):
    return [c for c in fake_llm.calls if c.get("stream")]


def test_stream_requires_student_auth(client, make_student):
    s = make_student()
    sid = new_session(client, s["headers"])
    assert client.post("/api/chat/stream", json={"session_id": sid, "message": "hi"}).status_code == 401
    other = make_student()
    assert client.post("/api/chat/stream", json={"session_id": sid, "message": "hi"}, headers=other["headers"]).status_code == 404
    # Validation errors are still normal HTTP errors, before any streaming
    assert client.post("/api/chat/stream", json={"session_id": sid, "message": "  "}, headers=s["headers"]).status_code == 400


def test_normal_message_streams_chunks_and_persists_once(client, make_student, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    res, events = stream(client, s["headers"], sid, "How do plants make food?")

    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["cache-control"] == "no-cache"
    assert res.headers["x-accel-buffering"] == "no"
    assert res.text.endswith("data: [DONE]\n\n")

    types = [e["type"] if isinstance(e, dict) else e for e in events]
    assert types[0] == "start" and types[-2] == "complete" and types[-1] == "[DONE]"
    chunks = [e["text"] for e in events if isinstance(e, dict) and e["type"] == "chunk"]
    assert len(chunks) >= 3 and "".join(chunks) == TUTOR_REPLY

    start, complete = events[0], events[-2]
    assert start["user_message"]["content"] == "How do plants make food?"  # saved before streaming
    assert complete["assistant_message"]["content"] == TUTOR_REPLY
    assert complete["session_title"] == "Photosynthesis Basics"

    rows = assistant_rows(sid)
    assert len(rows) == 1 and rows[0].content == TUTOR_REPLY and rows[0].id == complete["message_id"]
    assert stream_calls(fake_llm)[0]["stream"] is True

    # Non-streaming endpoint still works in the same chat
    assert client.post("/api/chat/", json={"session_id": sid, "message": "And then?"}, headers=s["headers"]).status_code == 200
    assert len(assistant_rows(sid)) == 2


def test_hint_streams_and_keeps_kind(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    stream(client, h, sid, "How do I integrate x*e^x?")
    _, events = stream(client, h, sid, mode="hint")
    types = [e["type"] for e in events if isinstance(e, dict)]
    assert types[:2] == ["start", "user_message"] and types[-1] == "complete"
    chunks = [e["text"] for e in events if isinstance(e, dict) and e["type"] == "chunk"]
    assert len(chunks) >= 2 and "".join(chunks) == "Planner hint 1"
    complete = events[-2]
    assert complete["user_message"]["kind"] == "hint-1" and complete["assistant_message"]["kind"] == "hint-1"
    assert complete["assistant_message"]["hint_total"] == 3

    # Planner failure: the fixed-stage hint streams straight from the model
    fake_llm.plan_override = "not json"
    _, events = stream(client, h, sid, mode="hint")
    complete = events[-2]
    assert complete["assistant_message"]["kind"] == "hint-2"
    assert complete["assistant_message"]["content"] == TUTOR_REPLY
    last = stream_calls(fake_llm)[-1]["messages"][-1]
    assert last["role"] == "system" and "Give me a hint" in last["content"]

    # Hints are exhausted after 3 -> normal HTTP error, not a stream
    stream(client, h, sid, mode="hint")
    assert client.post("/api/chat/stream", json={"session_id": sid, "mode": "hint"}, headers=h).status_code == 400


def test_answer_streams_and_keeps_kind(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    assert client.post("/api/chat/stream", json={"session_id": sid, "mode": "answer"}, headers=h).status_code == 400
    stream(client, h, sid, "Why is the sky blue?")
    _, events = stream(client, h, sid, mode="answer")
    complete = events[-2]
    assert events[0]["user_message"]["kind"] == "answer"
    assert complete["assistant_message"]["kind"] == "answer"
    last = stream_calls(fake_llm)[-1]["messages"][-1]
    assert last["role"] == "system" and "complete, correct answer" in last["content"]


def test_image_stream_uses_vision_model(client, make_student, admin_headers, fake_llm):
    original = client.get("/api/admin/config", headers=admin_headers).json()
    client.put("/api/admin/config", json={**original, "vision_model": "test/vision-model"}, headers=admin_headers)
    try:
        s = make_student()
        sid = new_session(client, s["headers"])
        res = client.post("/api/chat/stream/image", data={"session_id": sid, "message": "What is this?"},
                          files={"image": ("x.png", PNG, "image/png")}, headers=s["headers"])
        assert res.status_code == 200
        events = parse_sse(res.text)
        assert events[0]["user_message"]["image_mime_type"] == "image/png"
        assert events[-2]["type"] == "complete"
        call = stream_calls(fake_llm)[-1]
        assert call["model"] == "test/vision-model"
        assert call["messages"][-1]["content"][1]["type"] == "image_url"
        # Upload validation still happens before streaming
        bad = client.post("/api/chat/stream/image", data={"session_id": sid},
                          files={"image": ("x.png", b"nope", "image/png")}, headers=s["headers"])
        assert bad.status_code == 400
    finally:
        client.put("/api/admin/config", json=original, headers=admin_headers)


def test_document_stream_includes_extracted_text(client, make_student, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    res = client.post("/api/chat/stream/document", data={"session_id": sid, "message": "Summarise"},
                      files={"document": ("notes.txt", b"Mitochondria is the powerhouse of the cell.")},
                      headers=s["headers"])
    assert res.status_code == 200
    events = parse_sse(res.text)
    assert events[0]["user_message"]["document_name"] == "notes.txt"
    assert events[-2]["type"] == "complete"
    sent = stream_calls(fake_llm)[-1]["messages"][-1]["content"]
    assert sent.startswith("Summarise") and "powerhouse of the cell" in sent


def test_upstream_error_sends_error_event_and_saves_nothing(client, make_student, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    fake_llm.stream_fail_after = 2
    res, events = stream(client, s["headers"], sid, "Explain gravity")
    types = [e["type"] if isinstance(e, dict) else e for e in events]
    assert types[0] == "start" and "chunk" in types and types[-2:] == ["error", "[DONE]"]
    assert events[-2]["message"] == "Unable to generate tutor response"
    assert "secret" not in res.text  # internal error details never reach the client
    assert assistant_rows(sid) == []
    # The student's message was saved before streaming and is kept
    history = client.get(f"/api/chat/session/{sid}", headers=s["headers"]).json()
    assert [m["content"] for m in history] == ["Explain gravity"]
    assert fake_llm.streams[-1].closed


def _saved_user_turn(sid, text):
    async def go():
        async with AsyncSessionLocal() as db:
            session = await db.get(Session, sid)
            return (await _save_user_message(db, session, text)).id
    return asyncio.run(go())


def test_client_disconnect_mid_stream_saves_no_reply(client, make_student, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    user_id = _saved_user_turn(sid, "Tell me about atoms")

    async def disconnect_after_first_chunk():
        events = stream_turn_events(StreamTurn(session_id=sid, user_message_id=user_id))
        first = await events.__anext__()   # start
        second = await events.__anext__()  # first chunk
        await events.aclose()              # what Starlette does when the client goes away
        return first, second

    first, second = asyncio.run(disconnect_after_first_chunk())
    assert '"type": "start"' in first and '"type": "chunk"' in second
    assert fake_llm.streams[-1].closed  # upstream stopped
    assert assistant_rows(sid) == []

    # The DB session is healthy afterwards: a normal request in the same chat works
    assert client.post("/api/chat/", json={"session_id": sid, "message": "Again?"}, headers=s["headers"]).status_code == 200
    assert len(assistant_rows(sid)) == 1


def test_disconnect_detected_at_end_saves_no_reply(client, make_student, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    user_id = _saved_user_turn(sid, "Tell me about atoms")

    async def gone():
        return True

    async def consume():
        return [e async for e in stream_turn_events(StreamTurn(session_id=sid, user_message_id=user_id), gone)]

    events = asyncio.run(consume())
    assert not any('"complete"' in e for e in events)
    assert assistant_rows(sid) == []
