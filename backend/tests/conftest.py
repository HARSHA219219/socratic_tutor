"""Test setup: isolated temp SQLite DB (built via Alembic migrations), temp image dir, fake LLM."""
import json
import os
import re
import sys
import tempfile
import uuid
from typing import Optional
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
_TMP = Path(tempfile.mkdtemp(prefix="socratic-tests-"))

# Must be set before the app (and its settings/engine) is imported. Never touches the real DB.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["IMAGE_STORAGE_DIR"] = str(_TMP / "images")
os.environ["DOCUMENT_STORAGE_DIR"] = str(_TMP / "documents")
os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


command.upgrade(alembic_config(), "head")

from app.main import app  # noqa: E402
from app.services import llm_service  # noqa: E402
from app.core import security  # noqa: E402


class FakeCompletions:
    def __init__(self):
        self.calls = []
        # Hint planner reply: None = default plan below; a dict or raw string overrides it
        self.plan_override = None
        # Checkpoint summary reply: None = default JSON; a string overrides it
        self.checkpoint_override = None
        # Streaming: every stream handed out, and an optional failure after N words
        self.streams = []
        self.stream_fail_after = None
        # Image descriptions: returned text, or raise when image_summary_fail is True
        self.image_summary = "A labelled diagram of a plant cell; the nucleus is circled in red."
        self.image_summary_fail = False

    def _plan(self, kwargs) -> str:
        override = self.plan_override
        if isinstance(override, list):  # one entry per planner call
            override = override.pop(0) if override else None
        if isinstance(override, str):
            return override
        level = int(re.search(r"<CurrentHintLevel>\s*(\d+)", kwargs["messages"][1]["content"]).group(1))
        plan = {
            "question_depth": "moderate", "student_level": "developing", "student_state": "stuck",
            "misconceptions": [], "learning_goal": "Understand the idea.", "recommended_hint_count": 3,
            "current_hint_level": level, "next_hint": f"Planner hint {level}",
            "hint_purpose": "Point toward the key idea.", "should_allow_answer_button": True,
        }
        plan.update(override or {})
        return json.dumps(plan)

    def _checkpoint(self) -> str:
        return json.dumps({
            "topic": "Photosynthesis", "learning_objective": "Explain how plants make food.",
            "student_knowledge": ["Plants need sunlight"], "student_attempts": ["Guessed plants eat soil"],
            "correct_understanding": [], "misconceptions": ["Plants get food from soil"],
            "hints_given": [], "answers_revealed": [], "attachments": [],
            "unresolved_questions": ["Where does the glucose come from?"],
            "next_tutoring_action": "Ask what gas plants take in.", "continuation_notes": "Student is curious.",
        })

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("response_format") and kwargs["messages"][0]["content"].startswith("You are creating a learning-state checkpoint"):
            content = self.checkpoint_override if self.checkpoint_override is not None else self._checkpoint()
        elif kwargs.get("response_format"):
            content = self._plan(kwargs)
        elif str(kwargs["messages"][0]["content"]).startswith("You write short, factual descriptions of images"):
            if self.image_summary_fail:
                raise RuntimeError("vision model unavailable")
            content = self.image_summary
        elif kwargs.get("max_tokens") == 16:
            content = "Photosynthesis Basics"
        else:
            content = "What do you notice first?"
        if kwargs.get("stream"):
            stream = FakeStream(content, fail_after=self.stream_fail_after)
            self.streams.append(stream)
            return stream
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeStream:
    """Mimics the OpenAI SDK's AsyncStream of chat.completion.chunk objects."""

    def __init__(self, content: str, fail_after: Optional[int] = None):
        words = re.findall(r"\s*\S+\s*", content)
        # Include chunks the consumer must skip safely: no choices, and an empty delta
        self._chunks = [SimpleNamespace(choices=[])] + [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))])
        ] + [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=w))]) for w in words]
        self.fail_after = fail_after
        self.sent_words = 0
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        chunk = self._chunks.pop(0)
        if chunk.choices and chunk.choices[0].delta.content:
            if self.fail_after is not None and self.sent_words >= self.fail_after:
                raise RuntimeError("upstream exploded (secret details)")
            self.sent_words += 1
        return chunk

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeCompletions()
    monkeypatch.setattr(llm_service, "client", SimpleNamespace(chat=SimpleNamespace(completions=fake)))
    return fake


@pytest.fixture
def client(fake_llm):
    security.login_limiter.clear()
    security.recovery_limiter.clear()
    security.admin_limiter.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_student(client):
    def _make(username=None, password="correct-horse-1", name="Test Student"):
        suffix = uuid.uuid4().hex[:8]
        body = {"name": name, "roll_no": f"R{suffix}", "username": username or f"user_{suffix}", "password": password}
        res = client.post("/api/students/signup", json=body)
        assert res.status_code == 200, res.text
        data = res.json()
        data["headers"] = {"Authorization": f"Bearer {data['access_token']}"}
        data["password"] = password
        return data

    return _make


@pytest.fixture
def admin_headers():
    token = security.create_access_token({"sub": settings.ADMIN_USERNAME})
    return {"Authorization": f"Bearer {token}"}
