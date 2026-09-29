"""Multiple attachments per message (normalized table) + image summaries

Revision ID: f5c8b3a1d2e7
Revises: e3a7c9d1f4b2
Create Date: 2026-09-30 18:00:00.000000

Creates message_attachments and backfills one row for every existing image and
document message, pointing at the same files on disk. Existing columns and files
are untouched, so older code and the downgrade keep working.
"""
import re
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5c8b3a1d2e7'
down_revision: Union[str, Sequence[str], None] = 'e3a7c9d1f4b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'message_attachments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('message_id', sa.String(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('text_status', sa.String(), nullable=True),
        sa.Column('image_summary', sa.Text(), nullable=True),
        sa.Column('summary_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_message_attachments_message_id', 'message_attachments', ['message_id'])

    bind = op.get_bind()
    attachments = sa.table(
        'message_attachments',
        sa.column('id'), sa.column('message_id'), sa.column('position'), sa.column('kind'),
        sa.column('storage_key'), sa.column('name'), sa.column('mime_type'), sa.column('size_bytes'),
        sa.column('extracted_text'), sa.column('text_status'),
    )
    rows = bind.execute(sa.text(
        "SELECT id, image_key, image_mime_type, image_size_bytes, document_key, document_name, "
        "document_mime_type, document_size_bytes, document_text, document_text_status "
        "FROM messages WHERE image_key IS NOT NULL OR document_key IS NOT NULL"
    )).fetchall()
    new_rows = []
    for (msg_id, image_key, image_mime, image_size, doc_key, doc_name, doc_mime, doc_size, doc_text, doc_status) in rows:
        position = 0
        if image_key:
            ext = (re.search(r"\.(\w+)$", image_key) or [None, "png"])[1]
            new_rows.append({
                "id": str(uuid.uuid4()), "message_id": msg_id, "position": position, "kind": "image",
                "storage_key": image_key, "name": f"image.{ext}", "mime_type": image_mime or "image/png",
                "size_bytes": image_size or 0, "extracted_text": None, "text_status": None,
            })
            position += 1
        if doc_key:
            new_rows.append({
                "id": str(uuid.uuid4()), "message_id": msg_id, "position": position, "kind": "document",
                "storage_key": doc_key, "name": doc_name, "mime_type": doc_mime or "application/octet-stream",
                "size_bytes": doc_size or 0, "extracted_text": doc_text, "text_status": doc_status,
            })
    if new_rows:
        op.bulk_insert(attachments, new_rows)


def downgrade() -> None:
    op.drop_index('ix_message_attachments_message_id', table_name='message_attachments')
    op.drop_table('message_attachments')
