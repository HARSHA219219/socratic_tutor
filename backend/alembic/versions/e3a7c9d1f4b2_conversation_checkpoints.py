"""Conversation checkpoints (learning-state summaries)

Revision ID: e3a7c9d1f4b2
Revises: d9b2e5f7a3c1
Create Date: 2026-09-30 12:00:00.000000

Creates a new table only; existing tables and data are untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3a7c9d1f4b2'
down_revision: Union[str, Sequence[str], None] = 'd9b2e5f7a3c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation_checkpoints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('message_id', sa.String(), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('summary_token_count', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversation_checkpoints_session_id', 'conversation_checkpoints', ['session_id'])
    op.create_index('ix_conversation_checkpoints_message_id', 'conversation_checkpoints', ['message_id'])


def downgrade() -> None:
    op.drop_index('ix_conversation_checkpoints_message_id', table_name='conversation_checkpoints')
    op.drop_index('ix_conversation_checkpoints_session_id', table_name='conversation_checkpoints')
    op.drop_table('conversation_checkpoints')
