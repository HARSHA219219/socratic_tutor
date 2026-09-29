"""Conversation checkpoints: manual summaries, continuing from them, and the automatic window summary."""
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.domain import ConversationCheckpoint


def new_session(client, headers):
    return client.post("/api/sessions/", json={}, headers=headers).json()["id"]


def send(client, headers, sid, message):
    res = client.post("/api/chat/", json={"session_id": sid, "message": message}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def checkpoint_calls(fake_llm):
    return [c for c in fake_llm.calls
            if c.get("response_format") and c["messages"][0]["content"].startswith("You are creating a learning-state")]


def tutor_calls(fake_llm):
    return [c for c in fake_llm.calls if not c.get("response_format") and c.get("max_tokens") != 16]


def test_create_checkpoint_summarizes_only_through_selected_message(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    first = send(client, h, sid, "How do plants make food? FIRST-QUESTION")
    send(client, h, sid, "Do they eat soil? SECOND-QUESTION")

    res = client.post("/api/checkpoints/", json={"session_id": sid, "message_id": first["assistant_message"]["id"]}, headers=h)
    assert res.status_code == 200, res.text
    cp = res.json()
    assert cp["source"] == "manual"
    assert cp["message_id"] == first["assistant_message"]["id"]
    assert cp["summary"]["topic"] == "Photosynthesis"
    assert cp["summary"]["misconceptions"] == ["Plants get food from soil"]
    assert cp["summary_token_count"] > 0

    transcript = checkpoint_calls(fake_llm)[-1]["messages"][1]["content"]
    assert "FIRST-QUESTION" in transcript and "SECOND-QUESTION" not in transcript
    assert "Tutor: What do you notice first?" in transcript

    listed = client.get(f"/api/checkpoints/session/{sid}", headers=h).json()
    assert [c["id"] for c in listed] == [cp["id"]]
    assert client.get(f"/api/checkpoints/{cp['id']}", headers=h).json()["summary"]["topic"] == "Photosynthesis"


def test_transcript_includes_hints_answers_and_attachments(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, "What is 7 x 8?")
    client.post("/api/chat/", json={"session_id": sid, "mode": "hint"}, headers=h)
    client.post("/api/chat/", json={"session_id": sid, "mode": "answer"}, headers=h)
    client.post("/api/chat/document", data={"session_id": sid, "message": "my notes"},
                files={"document": ("notes.txt", b"Multiplication is repeated addition.")}, headers=h)
    last = client.get(f"/api/chat/session/{sid}", headers=h).json()[-1]
    res = client.post("/api/checkpoints/", json={"session_id": sid, "message_id": last["id"]}, headers=h)
    assert res.status_code == 200
    transcript = checkpoint_calls(fake_llm)[-1]["messages"][1]["content"]
    assert "Tutor (hint 1 of 3)" in transcript
    assert "Student (pressed 'Show answer')" in transcript and "Tutor (full answer revealed)" in transcript
    assert '[Attached document: "notes.txt"' in transcript and "repeated addition" in transcript


def test_checkpoint_ownership_and_validation(client, make_student):
    a, b = make_student(), make_student()
    sid_a = new_session(client, a["headers"])
    reply_a = send(client, a["headers"], sid_a, "Question A")["assistant_message"]["id"]
    sid_b = new_session(client, b["headers"])
    reply_b = send(client, b["headers"], sid_b, "Question B")["assistant_message"]["id"]

    # Another student's session
    assert client.post("/api/checkpoints/", json={"session_id": sid_a, "message_id": reply_a}, headers=b["headers"]).status_code == 404
    # A message from a different session
    res = client.post("/api/checkpoints/", json={"session_id": sid_b, "message_id": reply_a}, headers=b["headers"])
    assert res.status_code == 400
    assert client.post("/api/checkpoints/", json={"session_id": sid_b, "message_id": "nope"}, headers=b["headers"]).status_code == 400

    cp = client.post("/api/checkpoints/", json={"session_id": sid_a, "message_id": reply_a}, headers=a["headers"]).json()
    # Retrieval requires auth and ownership
    assert client.get(f"/api/checkpoints/{cp['id']}").status_code == 401
    assert client.get(f"/api/checkpoints/{cp['id']}", headers=b["headers"]).status_code == 404
    assert client.get(f"/api/checkpoints/session/{sid_a}", headers=b["headers"]).status_code == 404
    assert client.post(f"/api/checkpoints/{cp['id']}/continue", headers=b["headers"]).status_code == 404
    assert reply_b  # b's own session untouched


def test_bad_model_output_is_a_clear_error(client, make_student, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    reply = send(client, s["headers"], sid, "Hi")["assistant_message"]["id"]
    fake_llm.checkpoint_override = "not json at all"
    res = client.post("/api/checkpoints/", json={"session_id": sid, "message_id": reply}, headers=s["headers"])
    assert res.status_code == 400 and "summary could not be generated" in res.json()["detail"]
    assert client.get(f"/api/checkpoints/session/{sid}", headers=s["headers"]).json() == []


def test_continue_from_checkpoint_creates_new_session(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    reply = send(client, h, sid, "How do plants make food?")["assistant_message"]["id"]
    cp = client.post("/api/checkpoints/", json={"session_id": sid, "message_id": reply}, headers=h).json()

    res = client.post(f"/api/checkpoints/{cp['id']}/continue", headers=h)
    assert res.status_code == 200
    new = res.json()
    assert new["id"] != sid
    assert new["title"].endswith("(continued)") and new["title"].startswith("Photosynthesis Basics")

    msgs = client.get(f"/api/chat/session/{new['id']}", headers=h).json()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "system" and msgs[0]["kind"] == "checkpoint_context"
    assert "Trusted tutor context" in msgs[0]["content"] and "Topic: Photosynthesis" in msgs[0]["content"]

    # The next tutor call in the new session carries the context as a system message
    send(client, h, new["id"], "So where does the glucose come from?")
    sent = tutor_calls(fake_llm)[-1]["messages"]
    assert sent[1]["role"] == "system" and "Topic: Photosynthesis" in sent[1]["content"]
    assert sent[-1]["content"] == "So where does the glucose come from?"


def _checkpoints(sid):
    async def q():
        async with AsyncSessionLocal() as db:
            rows = await db.execute(select(ConversationCheckpoint).where(ConversationCheckpoint.session_id == sid))
            return rows.scalars().all()
    return asyncio.run(q())


def test_automatic_checkpoint_when_prompt_nears_budget(client, make_student, fake_llm, monkeypatch):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    first = send(client, h, sid, "Explain photosynthesis " + "please " * 40)
    monkeypatch.setattr(settings, "CONTEXT_TOKEN_BUDGET", 150)  # tiny budget forces summarizing

    send(client, h, sid, "What about the light reactions?")
    autos = [c for c in _checkpoints(sid) if c.source == "automatic"]
    assert len(autos) == 1 and autos[0].message_id == first["assistant_message"]["id"]

    sent = tutor_calls(fake_llm)[-1]["messages"]
    assert "Trusted tutor context" in sent[1]["content"]
    assert sent[-1] == {"role": "user", "content": "What about the light reactions?"}
    assert not any("please please" in str(m["content"]) for m in sent)  # old turn replaced by the summary


def test_automatic_checkpoint_is_not_duplicated(client, make_student, fake_llm, monkeypatch):
    from app.services.llm_service import ensure_automatic_checkpoint, _load_history

    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, "First question")
    send(client, h, sid, "Second question")

    async def twice():
        async with AsyncSessionLocal() as db:
            history = await _load_history(db, sid)
            a = await ensure_automatic_checkpoint(db, sid, history)
            b = await ensure_automatic_checkpoint(db, sid, history)
            return a[0].id, b[0].id
    first_id, second_id = asyncio.run(twice())
    assert first_id == second_id
    assert len([c for c in _checkpoints(sid) if c.source == "automatic"]) == 1
    assert len(checkpoint_calls(fake_llm)) == 1


def test_latest_student_message_is_never_dropped(client, make_student, fake_llm, monkeypatch):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    monkeypatch.setattr(settings, "CONTEXT_TOKEN_BUDGET", 20)  # smaller than the message itself
    latest = "A very long new question " * 30
    send(client, h, sid, latest)
    sent = tutor_calls(fake_llm)[-1]["messages"]
    assert sent[-1] == {"role": "user", "content": latest}
    assert sent[0]["role"] == "system"


def test_summary_disabled_sends_full_history(client, make_student, fake_llm, monkeypatch):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, "Question one " * 20)
    monkeypatch.setattr(settings, "CONTEXT_TOKEN_BUDGET", 50)
    monkeypatch.setattr(settings, "SUMMARY_ENABLED", False)
    send(client, h, sid, "Question two")
    assert _checkpoints(sid) == []
    assert len(tutor_calls(fake_llm)[-1]["messages"]) == 4  # system + 3 turns, nothing dropped
