"""Admin password change + recovery-code reset (mirrors the student flow)."""
import asyncio

from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.domain import AppConfig

ADMIN = settings.ADMIN_USERNAME


def login(client, password):
    return client.post("/api/admin/login", data={"username": ADMIN, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _stored(key):
    async def get():
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(AppConfig).where(AppConfig.config_key == key))).scalars().first()
            return row.config_value if row else None
    return asyncio.run(get())


def test_admin_full_password_lifecycle(client):
    # Starts on the .env default password
    first = login(client, "admin123")
    assert first.status_code == 200
    headers = auth(first.json()["access_token"])

    # Wrong username and wrong password give the same message
    bad_user = client.post("/api/admin/login", data={"username": "nobody", "password": "admin123"})
    bad_pw = login(client, "wrong-password")
    assert bad_user.status_code == bad_pw.status_code == 401
    assert bad_user.json()["detail"] == bad_pw.json()["detail"]

    # No recovery code yet; generating one needs the current password
    assert client.get("/api/admin/security", headers=headers).json()["has_recovery_code"] is False
    assert client.post("/api/admin/security/recovery-code", json={"current_password": "nope"}, headers=headers).status_code == 400
    gen = client.post("/api/admin/security/recovery-code", json={"current_password": "admin123"}, headers=headers)
    assert gen.status_code == 200
    code = gen.json()["recovery_code"]
    assert code not in (_stored("ADMIN_RECOVERY_CODE_HASH") or "")

    # Change password while signed in
    changed = client.post("/api/admin/security/password",
                          json={"current_password": "admin123", "new_password": "instructor-pass-1"}, headers=headers)
    assert changed.status_code == 200
    assert login(client, "admin123").status_code == 401
    assert login(client, "instructor-pass-1").status_code == 200
    assert _stored("ADMIN_PASSWORD_HASH") != "instructor-pass-1"

    # Forgot password: username + recovery code
    wrong = client.post("/api/admin/recover/verify", json={"username": ADMIN, "recovery_code": "AAAAA-AAAAA"})
    wrong_user = client.post("/api/admin/recover/verify", json={"username": "nobody", "recovery_code": code})
    assert wrong.status_code == wrong_user.status_code == 400
    assert wrong.json()["detail"] == wrong_user.json()["detail"]

    ok = client.post("/api/admin/recover/verify", json={"username": ADMIN, "recovery_code": code})
    assert ok.status_code == 200
    token = ok.json()["reset_token"]
    # A reset token is not an admin session token
    assert client.get("/api/admin/students", headers=auth(token)).status_code == 401

    reset = client.post("/api/admin/recover/reset", json={"reset_token": token, "new_password": "recovered-pass-2"})
    assert reset.status_code == 200
    new_code = reset.json()["recovery_code"]
    assert new_code != code
    assert client.get("/api/admin/students", headers=auth(reset.json()["access_token"])).status_code == 200

    # Old code and used token are dead; new password works
    assert client.post("/api/admin/recover/verify", json={"username": ADMIN, "recovery_code": code}).status_code == 400
    assert client.post("/api/admin/recover/reset", json={"reset_token": token, "new_password": "again-pass-3"}).status_code == 400
    assert login(client, "instructor-pass-1").status_code == 401
    assert login(client, "recovered-pass-2").status_code == 200


def test_admin_recovery_rate_limited(client):
    for _ in range(5):
        assert client.post("/api/admin/recover/verify", json={"username": ADMIN, "recovery_code": "WRONG"}).status_code == 400
    assert client.post("/api/admin/recover/verify", json={"username": ADMIN, "recovery_code": "WRONG"}).status_code == 429


def test_student_token_cannot_use_admin_security(client, make_student):
    s = make_student()
    assert client.get("/api/admin/security", headers=s["headers"]).status_code == 401
    security.admin_limiter.clear()
