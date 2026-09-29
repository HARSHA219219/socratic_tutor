"""Multiple attachments per message, context-budget limits, and image descriptions reused in later turns."""
import json
import sqlite3
import tempfile
from pathlib import Path

from alembic import command

from app.core.config import settings
from tests.conftest import alembic_config
from tests.test_documents import make_pdf

PNG_A = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PNG_B = b"\x89PNG\r\n\x1a\n" + b"\x01" * 64
SUMMARY = "A labelled diagram of a plant cell; the nucleus is circled in red."


def new_session(client, headers):
    return client.post("/api/sessions/", json={}, headers=headers).json()["id"]


def upload(client, headers, sid, files, message="", stream=False):
    path = "/api/chat/stream/attachments" if stream else "/api/chat/attachments"
    return client.post(path, data={"session_id": sid, "message": message},
                       files=[("files", f) for f in files], headers=headers)


def tutor_calls(fake_llm):
    return [
        c for c in fake_llm.calls
        if not c.get("response_format") and c.get("max_tokens") != 16
        and not str(c["messages"][0]["content"]).startswith("You write short, factual descriptions")
    ]


def image_parts(messages):
    return [p for m in messages if isinstance(m["content"], list) for p in m["content"] if p["type"] == "image_url"]


def stored_files():
    dirs = [Path(settings.IMAGE_STORAGE_DIR), Path(settings.DOCUMENT_STORAGE_DIR)]
    return {p.name for d in dirs if d.exists() for p in d.iterdir()}


def test_mixed_attachments_are_saved_sent_and_reloaded(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    files = [
        ("leaf.png", PNG_A, "image/png"),
        ("cell.png", PNG_B, "image/png"),
        ("notes.txt", b"Chlorophyll absorbs light.", "text/plain"),
        ("../../worksheet.pdf", make_pdf("Photosynthesis worksheet"), "application/pdf"),
    ]
    res = upload(client, h, sid, files, message="Compare these")
    assert res.status_code == 200, res.text
    atts = res.json()["user_message"]["attachments"]
    assert [a["kind"] for a in atts] == ["image", "image", "document", "document"]
    assert [a["position"] for a in atts] == [0, 1, 2, 3]
    assert [a["name"] for a in atts] == ["leaf.png", "cell.png", "notes.txt", "worksheet.pdf"]
    assert "extracted_text" not in atts[2]  # text stays server-side
    # Legacy fields mirror the first image / document
    user = res.json()["user_message"]
    assert user["image_mime_type"] == "image/png" and user["document_name"] == "notes.txt"

    # The tutor saw every attachment: 2 labelled images + both documents' text
    sent = tutor_calls(fake_llm)[0]["messages"][-1]["content"]
    assert sent[0]["type"] == "text" and sent[0]["text"].startswith("Compare these")
    assert "Chlorophyll absorbs light." in sent[0]["text"] and "Photosynthesis worksheet" in sent[0]["text"]
    assert len(image_parts([{"content": sent}])) == 2
    labels = [p["text"] for p in sent if p["type"] == "text"][1:]
    assert labels == ['[Above: Image #1 ("leaf.png")]', '[Above: Image #2 ("cell.png")]']

    # Survives reload, including the descriptions written after the reply
    history = client.get(f"/api/chat/session/{sid}", headers=h).json()
    reloaded = history[0]["attachments"]
    assert [a["name"] for a in reloaded] == ["leaf.png", "cell.png", "notes.txt", "worksheet.pdf"]
    assert [a["summary_status"] for a in reloaded[:2]] == ["ok", "ok"]
    assert reloaded[0]["image_summary"] == SUMMARY
    assert reloaded[2]["summary_status"] is None  # documents are not described


def test_count_total_size_and_context_limits(client, make_student, monkeypatch):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)

    too_many = [(f"n{i}.txt", b"hello", "text/plain") for i in range(settings.MAX_ATTACHMENTS_PER_MESSAGE + 1)]
    res = upload(client, h, sid, too_many)
    assert res.status_code == 400 and "up to 5 files" in res.json()["detail"]

    monkeypatch.setattr(settings, "MAX_TOTAL_ATTACHMENT_BYTES", 100)
    res = upload(client, h, sid, [("a.png", PNG_A, "image/png"), ("b.png", PNG_B, "image/png")])
    assert res.status_code == 413 and "too large together" in res.json()["detail"]
    monkeypatch.setattr(settings, "MAX_TOTAL_ATTACHMENT_BYTES", 20 * 1024 * 1024)

    # Attachment content above ATTACHMENT_CONTEXT_PERCENT of the budget is rejected, not dropped
    monkeypatch.setattr(settings, "CONTEXT_TOKEN_BUDGET", 2000)  # cap = 900 tokens < one image (1100)
    res = upload(client, h, sid, [("a.png", PNG_A, "image/png")])
    assert res.status_code == 413
    detail = res.json()["detail"]
    assert "too large for the tutor to read together" in detail and '"a.png" ~1,100' in detail
    # The single-file endpoints apply the same budget
    res = client.post("/api/chat/image", data={"session_id": sid}, files={"image": ("a.png", PNG_A, "image/png")}, headers=h)
    assert res.status_code == 413

    assert client.get(f"/api/chat/session/{sid}", headers=h).json() == []


def test_one_invalid_file_rejects_the_whole_message(client, make_student):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    before = stored_files()
    res = upload(client, h, sid, [
        ("ok.png", PNG_A, "image/png"),
        ("virus.exe", b"MZ\x90\x00binary", "application/octet-stream"),
    ])
    assert res.status_code == 400
    assert res.json()["detail"].startswith('"virus.exe": Unsupported file type. You can attach images')
    oversized_doc = upload(client, h, sid, [("big.txt", b"a" * (settings.MAX_DOCUMENT_BYTES + 1), "text/plain")])
    assert oversized_doc.status_code == 413
    assert stored_files() == before  # nothing written to disk
    assert client.get(f"/api/chat/session/{sid}", headers=h).json() == []


def test_streaming_multiple_attachments(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    res = upload(client, h, sid, [("a.png", PNG_A, "image/png"), ("q.txt", b"What is 2+2?", "text/plain")],
                 message="Help", stream=True)
    assert res.status_code == 200
    events = [json.loads(b[6:]) for b in res.text.split("\n\n") if b.startswith("data: {")]
    assert events[0]["type"] == "start" and len(events[0]["user_message"]["attachments"]) == 2
    assert events[-1]["type"] == "complete"
    streamed = [c for c in fake_llm.calls if c.get("stream")][-1]["messages"][-1]["content"]
    assert len(image_parts([{"content": streamed}])) == 1 and "What is 2+2?" in streamed[0]["text"]
    # The description was written in the background after the stream
    history = client.get(f"/api/chat/session/{sid}", headers=h).json()
    assert history[0]["attachments"][0]["image_summary"] == SUMMARY


def test_later_turns_reuse_the_description_instead_of_the_image(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    upload(client, h, sid, [("cell.png", PNG_A, "image/png")], message="What is this?")
    client.post("/api/chat/", json={"session_id": sid, "message": "What should I focus on?"}, headers=h)

    prompt = tutor_calls(fake_llm)[-1]["messages"]
    assert image_parts(prompt) == []  # original not re-sent
    earlier = prompt[1]["content"]
    assert isinstance(earlier, str) and earlier.startswith("What is this?")
    assert 'Image #1 ("cell.png") was shared earlier' in earlier and SUMMARY in earlier
    assert "the image itself is not attached now" in earlier


def test_asking_to_recheck_resends_the_original(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    upload(client, h, sid, [("first.png", PNG_A, "image/png"), ("second.png", PNG_B, "image/png")], message="Two pics")

    client.post("/api/chat/", json={"session_id": sid, "message": "Please look at the image again"}, headers=h)
    assert len(image_parts(tutor_calls(fake_llm)[-1]["messages"])) == 2  # latest image message re-sent

    client.post("/api/chat/", json={"session_id": sid, "message": "Can you re-check image 2?"}, headers=h)
    prompt = tutor_calls(fake_llm)[-1]["messages"]
    assert len(image_parts(prompt)) == 1
    texts = [p["text"] for m in prompt if isinstance(m["content"], list) for p in m["content"] if p["type"] == "text"]
    assert '[Above: Image #2 ("second.png")]' in texts
    assert 'Image #1 ("first.png") was shared earlier' in texts[0]  # #1 still as its description


def test_failed_description_falls_back_to_the_original(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    fake_llm.image_summary_fail = True
    upload(client, h, sid, [("cell.png", PNG_A, "image/png")], message="What is this?")
    history = client.get(f"/api/chat/session/{sid}", headers=h).json()
    assert history[0]["attachments"][0]["summary_status"] == "failed"
    assert history[0]["attachments"][0]["image_summary"] is None

    client.post("/api/chat/", json={"session_id": sid, "message": "And now?"}, headers=h)
    prompt = tutor_calls(fake_llm)[-1]["messages"]
    assert len(image_parts(prompt)) == 1  # previous behavior: the image itself
    assert "Description written" not in json.dumps(prompt)  # never claims an analysis that didn't happen


def test_attachment_download_is_owner_or_admin_only(client, make_student, admin_headers):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    res = upload(client, h, sid, [("a.png", PNG_A, "image/png"), ("n.txt", b"notes", "text/plain")])
    img_id, doc_id = [a["id"] for a in res.json()["user_message"]["attachments"]]

    own = client.get(f"/api/attachments/{img_id}", headers=h)
    assert own.status_code == 200 and own.content == PNG_A and own.headers["content-type"] == "image/png"
    doc = client.get(f"/api/attachments/{doc_id}", headers=h)
    assert doc.content == b"notes" and "attachment" in doc.headers["content-disposition"]
    assert client.get(f"/api/attachments/{img_id}").status_code == 401
    assert client.get(f"/api/attachments/{img_id}", headers=make_student()["headers"]).status_code == 404
    assert client.get(f"/api/attachments/{img_id}", headers=admin_headers).status_code == 200
    assert client.get("/api/attachments/../../etc/passwd", headers=admin_headers).status_code == 404

    # Admin conversation view lists every attachment
    logs = client.get(f"/api/admin/students/{s['student']['id']}/sessions/{sid}", headers=admin_headers).json()
    assert [a["name"] for a in logs[0]["attachments"]] == ["a.png", "n.txt"]


def test_single_file_endpoints_also_create_attachment_rows(client, make_student):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    res = client.post("/api/chat/image", data={"session_id": sid, "message": "hi"},
                      files={"image": ("photo.jpeg", b"\xff\xd8\xff" + b"\x00" * 40, "image/jpeg")}, headers=h)
    assert res.status_code == 200
    atts = res.json()["user_message"]["attachments"]
    assert len(atts) == 1 and atts[0]["kind"] == "image" and atts[0]["name"] == "photo.jpeg"


def test_migration_backfills_existing_image_and_document_messages(monkeypatch):
    db_path = Path(tempfile.mkdtemp()) / "before_attachments.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    cfg = alembic_config()
    command.upgrade(cfg, "e3a7c9d1f4b2")  # just before message_attachments
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO students (id, name, roll_no, username) VALUES ('s1', 'Ravi', 'r1', 'ravi')")
    con.execute("INSERT INTO sessions (id, student_id) VALUES ('sess1', 's1')")
    con.execute("INSERT INTO messages (id, session_id, role, content) VALUES ('m1', 'sess1', 'user', 'plain')")
    con.execute("INSERT INTO messages (id, session_id, role, content, image_key, image_mime_type, image_size_bytes, "
                "document_key, document_name, document_mime_type, document_size_bytes, document_text, document_text_status) "
                "VALUES ('m2', 'sess1', 'user', 'both', 'aaa.png', 'image/png', 10, 'bbb.txt', 'n.txt', 'text/plain', 5, 'hello', 'ok')")
    con.commit()
    con.close()

    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT message_id, position, kind, storage_key, name, extracted_text FROM message_attachments "
                       "ORDER BY position").fetchall()
    assert rows == [("m2", 0, "image", "aaa.png", "image.png", None), ("m2", 1, "document", "bbb.txt", "n.txt", "hello")]
    assert con.execute("SELECT image_key, document_key FROM messages WHERE id='m2'").fetchone() == ("aaa.png", "bbb.txt")
    con.close()

    command.downgrade(cfg, "e3a7c9d1f4b2")
    con = sqlite3.connect(db_path)
    assert "message_attachments" not in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert con.execute("SELECT count(*) FROM messages").fetchone() == (2,)
    con.close()
