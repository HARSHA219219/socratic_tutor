"""Smoke test against a running server (uvicorn on :8000). Creates a throwaway account."""
import uuid
import requests

BASE = "http://127.0.0.1:8000/api"
suffix = uuid.uuid4().hex[:6]

# Create student account
res = requests.post(f"{BASE}/students/signup", json={
    "name": "Test User", "roll_no": f"smoke-{suffix}", "username": f"smoke_{suffix}", "password": "smoke-pass-123",
})
auth = res.json()
print("Signup:", res.status_code, auth.get("student"))
headers = {"Authorization": f"Bearer {auth['access_token']}"}

# Create session
res = requests.post(f"{BASE}/sessions/", json={}, headers=headers)
session = res.json()
print("Session:", session)

# Send chat
res = requests.post(f"{BASE}/chat/", json={"session_id": session["id"], "message": "what is ai?"}, headers=headers)
chat_res = res.json()
print("Chat Response:", chat_res.get("session_title"), "|", chat_res.get("response"))
