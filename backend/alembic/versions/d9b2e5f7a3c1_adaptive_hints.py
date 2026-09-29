"""Adaptive hint ladder metadata on messages

Revision ID: d9b2e5f7a3c1
Revises: c4f8a2d6e1b9
Create Date: 2026-09-30 10:00:00.000000

Adds nullable columns only. Hints saved earlier keep NULL and are treated as a 3-step ladder.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9b2e5f7a3c1'
down_revision: Union[str, Sequence[str], None] = 'c4f8a2d6e1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('hint_total', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('hint_allow_answer', sa.Boolean(), nullable=True))
    op.add_column('messages', sa.Column('hint_assessment', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('messages') as batch:
        batch.drop_column('hint_assessment')
        batch.drop_column('hint_allow_answer')
        batch.drop_column('hint_total')
