"""Upgrades a database that holds legacy (pre-account) data and checks nothing is lost."""
import sqlite3
import tempfile
from pathlib import Path

from alembic import command

from app.core.config import settings
from tests.conftest import alembic_config


def test_migration_preserves_data_and_assigns_unique_usernames(monkeypatch):
    db_path = Path(tempfile.mkdtemp()) / "legacy.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    cfg = alembic_config()

    command.upgrade(cfg, "782c42faa2b1")
    con = sqlite3.connect(db_path)
    # "A-1" and "a1" sanitize to the same base username
    con.executemany("INSERT INTO students (id, name, roll_no) VALUES (?, ?, ?)",
                    [("s1", "Ravi", "A-1"), ("s2", "Anu", "a1"), ("s3", "Kiran", "")])
    con.execute("INSERT INTO sessions (id, student_id) VALUES ('sess1', 's1')")
    con.execute("INSERT INTO messages (id, session_id, role, content) VALUES ('m1', 'sess1', 'user', 'hello')")
    con.commit()
    con.close()

    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    rows = dict(con.execute("SELECT id, username FROM students").fetchall())
    assert len({u.lower() for u in rows.values()}) == 3
    assert {rows["s1"], rows["s2"]} == {"student_a1", "student_a1_2"}
    assert rows["s3"].startswith("student_")
    assert con.execute("SELECT content, image_key FROM messages WHERE id='m1'").fetchone() == ("hello", None)
    assert con.execute("SELECT password_hash FROM students WHERE id='s1'").fetchone() == (None,)
    try:
        con.execute("INSERT INTO students (id, name, roll_no, username) VALUES ('s4', 'X', 'x9', 'STUDENT_A1')")
        raise AssertionError("case-insensitive duplicate should fail")
    except sqlite3.IntegrityError:
        pass
    con.close()

    # Downgrade keeps the original rows too
    command.downgrade(cfg, "782c42faa2b1")
    con = sqlite3.connect(db_path)
    assert con.execute("SELECT count(*) FROM students").fetchone() == (3,)
    assert con.execute("SELECT count(*) FROM messages").fetchone() == (1,)
    con.close()


def test_document_migration_preserves_text_and_image_messages(monkeypatch):
    db_path = Path(tempfile.mkdtemp()) / "before_docs.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    cfg = alembic_config()

    command.upgrade(cfg, "b7e3d1a9c2f5")  # state just before document columns
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO students (id, name, roll_no, username) VALUES ('s1', 'Ravi', 'r1', 'ravi')")
    con.execute("INSERT INTO sessions (id, student_id) VALUES ('sess1', 's1')")
    con.execute("INSERT INTO messages (id, session_id, role, content) VALUES ('m1', 'sess1', 'user', 'text only')")
    con.execute("INSERT INTO messages (id, session_id, role, content, image_key, image_mime_type, image_size_bytes) "
                "VALUES ('m2', 'sess1', 'user', 'with image', 'abc.png', 'image/png', 10)")
    con.commit()
    con.close()

    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    cols = {r[1] for r in con.execute("PRAGMA table_info(messages)")}
    assert {"document_key", "document_name", "document_mime_type", "document_size_bytes",
            "document_text", "document_text_status"} <= cols
    assert con.execute("SELECT content, image_key, document_key FROM messages ORDER BY id").fetchall() == [
        ("text only", None, None), ("with image", "abc.png", None),
    ]
    con.close()

    command.downgrade(cfg, "b7e3d1a9c2f5")
    con = sqlite3.connect(db_path)
    assert "document_key" not in {r[1] for r in con.execute("PRAGMA table_info(messages)")}
    assert con.execute("SELECT count(*) FROM messages").fetchone() == (2,)
    con.close()
