"""Document attachments (PDF/DOCX/TXT) on messages

Revision ID: c4f8a2d6e1b9
Revises: b7e3d1a9c2f5
Create Date: 2026-09-29 18:00:00.000000

Adds nullable columns only; existing messages (text and image) are untouched.
The document file itself lives on disk in DOCUMENT_STORAGE_DIR.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f8a2d6e1b9'
down_revision: Union[str, Sequence[str], None] = 'b7e3d1a9c2f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('document_key', sa.String(), nullable=True))
    op.add_column('messages', sa.Column('document_name', sa.String(), nullable=True))
    op.add_column('messages', sa.Column('document_mime_type', sa.String(), nullable=True))
    op.add_column('messages', sa.Column('document_size_bytes', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('document_text', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('document_text_status', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('messages') as batch:
        batch.drop_column('document_text_status')
        batch.drop_column('document_text')
        batch.drop_column('document_size_bytes')
        batch.drop_column('document_mime_type')
        batch.drop_column('document_name')
        batch.drop_column('document_key')
