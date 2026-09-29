import asyncio
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.domain import Message, AppConfig
from app.services.llm_service import build_llm_messages

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32


def new_session(client, headers):
    res = client.post("/api/sessions/", json={}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_endpoints_require_student_auth(client):
    assert client.post("/api/sessions/", json={}).status_code == 401
    assert client.post("/api/chat/", json={"session_id": "x", "message": "hi"}).status_code == 401


def test_text_chat_persists_history_and_names_chat(client, make_student, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    res = client.post("/api/chat/", json={"session_id": sid, "message": "How do plants make food?"}, headers=s["headers"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["response"] == "What do you notice first?"
    assert body["session_title"] == "Photosynthesis Basics"
    # The new user message is sent once (no duplicate at the end of the history)
    tutor_call = fake_llm.calls[0]
    assert [m["role"] for m in tutor_call["messages"]] == ["system", "user"]

    client.post("/api/chat/", json={"session_id": sid, "message": "Using sunlight?"}, headers=s["headers"])
    history = client.get(f"/api/chat/session/{sid}", headers=s["headers"]).json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert history[0]["image_mime_type"] is None
    sessions = client.get(f"/api/sessions/student/{s['student']['id']}", headers=s["headers"]).json()
    assert sessions[0]["title"] == "Photosynthesis Basics"
    # Title is generated only once
    assert sum(1 for c in fake_llm.calls if c.get("max_tokens") == 16) == 1


def test_student_cannot_read_other_students_session(client, make_student):
    a, b = make_student(), make_student()
    sid = new_session(client, a["headers"])
    assert client.get(f"/api/chat/session/{sid}", headers=b["headers"]).status_code == 404
    assert client.post("/api/chat/", json={"session_id": sid, "message": "hi"}, headers=b["headers"]).status_code == 404
    assert client.get(f"/api/sessions/student/{a['student']['id']}", headers=b["headers"]).status_code == 403


def test_image_upload_storage_and_retrieval(client, make_student, admin_headers, fake_llm):
    s = make_student()
    sid = new_session(client, s["headers"])
    res = client.post(
        "/api/chat/image",
        data={"session_id": sid, "message": "What is this diagram?"},
        files={"image": ("anything.txt", PNG, "application/octet-stream")},  # filename/type ignored
        headers=s["headers"],
    )
    assert res.status_code == 200, res.text
    user_msg = res.json()["user_message"]
    assert user_msg["image_mime_type"] == "image/png"
    assert user_msg["image_size_bytes"] == len(PNG)

    # Multimodal request went to the configured vision model
    tutor_call = fake_llm.calls[0]
    last = tutor_call["messages"][-1]
    assert last["content"][0] == {"type": "text", "text": "What is this diagram?"}
    assert last["content"][1]["type"] == "image_url"
    assert last["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")

    async def stored():
        async with AsyncSessionLocal() as db:
            msg = (await db.execute(select(Message).where(Message.id == user_msg["id"]))).scalars().first()
            vision = (await db.execute(select(AppConfig).where(AppConfig.config_key == "VISION_MODEL"))).scalars().first()
            return msg, vision
    msg, vision = asyncio.run(stored())
    assert tutor_call["model"] == vision.config_value
    # File on disk, only a reference in SQLite
    path = Path(settings.IMAGE_STORAGE_DIR) / msg.image_key
    assert path.read_bytes() == PNG
    assert msg.image_key.endswith(".png") and "anything" not in msg.image_key

    # Survives reload: history still points at the image
    history = client.get(f"/api/chat/session/{sid}", headers=s["headers"]).json()
    assert history[0]["image_mime_type"] == "image/png"

    url = f"/api/images/{user_msg['id']}"
    own = client.get(url, headers=s["headers"])
    assert own.status_code == 200 and own.content == PNG and own.headers["content-type"] == "image/png"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=make_student()["headers"]).status_code == 404
    assert client.get(url, headers=admin_headers).status_code == 200

    # Admin conversation log includes image metadata
    logs = client.get(f"/api/admin/students/{s['student']['id']}/sessions/{sid}", headers=admin_headers).json()
    assert logs[0]["image_mime_type"] == "image/png"


def test_image_only_message_and_webp(client, make_student):
    s = make_student()
    sid = new_session(client, s["headers"])
    res = client.post("/api/chat/image", data={"session_id": sid}, files={"image": ("x.webp", WEBP, "image/webp")}, headers=s["headers"])
    assert res.status_code == 200, res.text
    assert res.json()["user_message"]["content"] == ""
    assert res.json()["session_title"] == "Image question"


def test_rejects_fake_and_oversized_images(client, make_student, monkeypatch):
    s = make_student()
    sid = new_session(client, s["headers"])
    fake = client.post("/api/chat/image", data={"session_id": sid},
                       files={"image": ("photo.png", b"<?php echo 1; ?>", "image/png")}, headers=s["headers"])
    assert fake.status_code == 400 and "Unsupported" in fake.json()["detail"]

    monkeypatch.setattr(settings, "MAX_IMAGE_BYTES", 100)
    big = client.post("/api/chat/image", data={"session_id": sid},
                      files={"image": ("big.png", PNG + b"\x00" * 200, "image/png")}, headers=s["headers"])
    assert big.status_code == 413
    # Nothing was saved for rejected uploads
    assert client.get(f"/api/chat/session/{sid}", headers=s["headers"]).json() == []


def test_build_llm_messages_caps_history_images():
    def msg(i, role="user", image=False):
        return SimpleNamespace(id=str(i), role=role, content=f"m{i}",
                               image_key=f"{i}.png" if image else None, image_mime_type="image/png" if image else None)

    async def loader(key, mime):
        return f"data:{mime};base64,AAAA"

    history = [msg(1, image=True), msg(2, "assistant"), msg(3, image=True), msg(4, "assistant"), msg(5, image=True)]
    messages, has_images = asyncio.run(build_llm_messages("sys", history, loader, max_images=2))
    assert has_images
    assert messages[0] == {"role": "system", "content": "sys"}
    assert isinstance(messages[1]["content"], str) and "attached an image earlier" in messages[1]["content"]
    assert isinstance(messages[3]["content"], list) and isinstance(messages[5]["content"], list)

    text_only, has_images = asyncio.run(build_llm_messages("sys", [msg(1), msg(2, "assistant")], loader))
    assert not has_images and text_only[1] == {"role": "user", "content": "m1"}
