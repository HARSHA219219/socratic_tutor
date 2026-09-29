import asyncio
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.database import AsyncSessionLocal
from app.models.domain import Student


def run(coro):
    return asyncio.run(coro)


async def _get_student(student_id):
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(Student).where(Student.id == student_id))).scalars().first()


def test_signup_returns_token_and_one_time_recovery_code(client, make_student):
    data = make_student()
    assert data["recovery_code"] and len(data["recovery_code"]) == 23
    assert data["student"]["username"].startswith("user_")
    stored = run(_get_student(data["student"]["id"]))
    # Only hashes are stored
    assert stored.password_hash and stored.password_hash != data["password"]
    assert stored.recovery_code_hash and data["recovery_code"] not in stored.recovery_code_hash
    assert client.get("/api/students/me", headers=data["headers"]).json()["id"] == data["student"]["id"]


def test_username_unique_case_insensitive(client, make_student):
    name = f"Ravi{uuid.uuid4().hex[:6]}"
    make_student(username=name)
    res = client.post("/api/students/signup", json={
        "name": "Other", "roll_no": uuid.uuid4().hex[:8], "username": name.lower(), "password": "password-123",
    })
    assert res.status_code == 409
    assert "already taken" in res.json()["detail"]


def test_database_enforces_case_insensitive_unique_username():
    async def insert_pair():
        async with AsyncSessionLocal() as db:
            db.add(Student(name="A", roll_no=uuid.uuid4().hex, username="DupeUser"))
            await db.commit()
            db.add(Student(name="B", roll_no=uuid.uuid4().hex, username="dupeuser"))
            await db.commit()
    with pytest.raises(IntegrityError):
        run(insert_pair())


@pytest.mark.parametrize("bad", ["ab", "has space", "x" * 31, "rävi"])
def test_invalid_usernames_rejected(client, bad):
    res = client.post("/api/students/signup", json={"name": "N", "roll_no": "1", "username": bad, "password": "password-123"})
    assert res.status_code == 422


def test_login_success_and_generic_failure(client, make_student):
    data = make_student()
    uname = data["student"]["username"]
    ok = client.post("/api/students/login", json={"username": uname.upper(), "password": data["password"]})
    assert ok.status_code == 200
    wrong_pw = client.post("/api/students/login", json={"username": uname, "password": "nope-nope-1"})
    no_user = client.post("/api/students/login", json={"username": "ghost_user_zz", "password": "nope-nope-1"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["detail"] == no_user.json()["detail"]


def test_legacy_student_claims_account_and_keeps_history(client):
    sid, roll = str(uuid.uuid4()), f"L{uuid.uuid4().hex[:6]}"

    async def seed():
        async with AsyncSessionLocal() as db:
            await db.execute(text("INSERT INTO students (id, name, roll_no, username) VALUES (:i, 'Old Timer', :r, :u)"),
                             {"i": sid, "r": roll, "u": f"student_{roll.lower()}"})
            await db.execute(text("INSERT INTO sessions (id, student_id) VALUES ('legacy-sess-' || :i, :i)"), {"i": sid})
            await db.execute(text("INSERT INTO messages (id, session_id, role, content) "
                                  "VALUES (:m, 'legacy-sess-' || :i, 'user', 'old question')"),
                             {"m": str(uuid.uuid4()), "i": sid})
            await db.commit()
    run(seed())

    wrong_name = client.post("/api/students/signup", json={"name": "Someone Else", "roll_no": roll, "username": f"c{roll}", "password": "password-123"})
    assert wrong_name.status_code == 400

    res = client.post("/api/students/signup", json={"name": "Old Timer", "roll_no": roll, "username": f"claim_{roll}", "password": "password-123"})
    assert res.status_code == 200
    assert res.json()["student"]["id"] == sid
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    msgs = client.get(f"/api/chat/session/legacy-sess-{sid}", headers=headers).json()
    assert msgs[0]["content"] == "old question"

    again = client.post("/api/students/signup", json={"name": "Old Timer", "roll_no": roll, "username": f"x{roll}", "password": "password-123"})
    assert again.status_code == 409


def test_password_recovery_flow_rotates_code(client, make_student):
    data = make_student()
    uname, old_code = data["student"]["username"], data["recovery_code"]

    bad = client.post("/api/students/recover/verify", json={"username": uname, "recovery_code": "AAAAA-AAAAA-AAAAA-AAAAA"})
    ghost = client.post("/api/students/recover/verify", json={"username": "no_such_user_q", "recovery_code": old_code})
    assert bad.status_code == ghost.status_code == 400
    assert bad.json()["detail"] == ghost.json()["detail"]

    # Code is accepted case/format-insensitively
    ok = client.post("/api/students/recover/verify", json={"username": uname, "recovery_code": old_code.lower().replace("-", " ")})
    assert ok.status_code == 200
    reset_token = ok.json()["reset_token"]

    reset = client.post("/api/students/recover/reset", json={"reset_token": reset_token, "new_password": "brand-new-pass"})
    assert reset.status_code == 200
    new_code = reset.json()["recovery_code"]
    assert new_code and new_code != old_code

    # Old code and the used reset token are both dead
    assert client.post("/api/students/recover/verify", json={"username": uname, "recovery_code": old_code}).status_code == 400
    assert client.post("/api/students/recover/reset", json={"reset_token": reset_token, "new_password": "another-pass-1"}).status_code == 400
    assert client.post("/api/students/login", json={"username": uname, "password": data["password"]}).status_code == 401
    assert client.post("/api/students/login", json={"username": uname, "password": "brand-new-pass"}).status_code == 200


def test_recovery_attempts_are_rate_limited(client, make_student):
    data = make_student()
    uname = data["student"]["username"]
    for _ in range(5):
        r = client.post("/api/students/recover/verify", json={"username": uname, "recovery_code": "WRONG-WRONG"})
        assert r.status_code == 400
    blocked = client.post("/api/students/recover/verify", json={"username": uname, "recovery_code": data["recovery_code"]})
    assert blocked.status_code == 429


def test_student_token_cannot_access_admin(client, make_student):
    data = make_student()
    assert client.get("/api/admin/students", headers=data["headers"]).status_code == 401


def test_cors_origins_setting(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CORS_ORIGINS", " https://a.example.com/ , https://b.example.com ")
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]
    monkeypatch.setattr(settings, "CORS_ORIGINS", "")
    assert settings.cors_origins == ["*"]
