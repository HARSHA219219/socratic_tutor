"""Student accounts (username/password/recovery code), message images, session titles

Revision ID: a1c9e2f4b7d3
Revises: 782c42faa2b1
Create Date: 2026-09-27 12:00:00.000000

Existing data is preserved: every existing student gets a generated, unique
username (student_<roll_no>) and no password. Such "legacy" students claim
their account (and keep their chat history) by signing up with their original
name + roll number, at which point they choose their own username/password.
"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c9e2f4b7d3'
down_revision: Union[str, Sequence[str], None] = '782c42faa2b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_username(roll_no: str, student_id: str) -> str:
    base = re.sub(r"[^a-z0-9]", "", (roll_no or "").lower())[:20] or student_id.replace("-", "")[:8]
    return f"student_{base}"


def upgrade() -> None:
    bind = op.get_bind()

    # --- students: add nullable columns, backfill, then enforce NOT NULL ---
    op.add_column('students', sa.Column('username', sa.String(), nullable=True))
    op.add_column('students', sa.Column('password_hash', sa.String(), nullable=True))
    op.add_column('students', sa.Column('recovery_code_hash', sa.String(), nullable=True))

    rows = bind.execute(sa.text("SELECT id, roll_no FROM students ORDER BY created_at, id")).fetchall()
    taken: set[str] = set()
    for student_id, roll_no in rows:
        candidate = _legacy_username(roll_no, student_id)
        unique, n = candidate, 2
        while unique.lower() in taken:
            unique = f"{candidate}_{n}"
            n += 1
        taken.add(unique.lower())
        bind.execute(
            sa.text("UPDATE students SET username = :u WHERE id = :id"),
            {"u": unique, "id": student_id},
        )

    with op.batch_alter_table('students') as batch:
        batch.alter_column('username', existing_type=sa.String(), nullable=False)
    op.create_index(
        'ix_students_username_lower', 'students', [sa.text('lower(username)')], unique=True
    )

    # --- sessions: auto-generated chat title ---
    op.add_column('sessions', sa.Column('title', sa.String(), nullable=True))

    # --- messages: optional image reference + metadata (file itself lives on disk) ---
    op.add_column('messages', sa.Column('image_key', sa.String(), nullable=True))
    op.add_column('messages', sa.Column('image_mime_type', sa.String(), nullable=True))
    op.add_column('messages', sa.Column('image_size_bytes', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('messages') as batch:
        batch.drop_column('image_size_bytes')
        batch.drop_column('image_mime_type')
        batch.drop_column('image_key')
    with op.batch_alter_table('sessions') as batch:
        batch.drop_column('title')
    op.drop_index('ix_students_username_lower', table_name='students')
    with op.batch_alter_table('students') as batch:
        batch.drop_column('recovery_code_hash')
        batch.drop_column('password_hash')
        batch.drop_column('username')
