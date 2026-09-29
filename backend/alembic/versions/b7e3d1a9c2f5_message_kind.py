"""Message kind for hint ladder / direct answer turns

Revision ID: b7e3d1a9c2f5
Revises: a1c9e2f4b7d3
Create Date: 2026-09-29 12:00:00.000000

Adds a nullable column only; existing messages keep kind = NULL (normal messages).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e3d1a9c2f5'
down_revision: Union[str, Sequence[str], None] = 'a1c9e2f4b7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('kind', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('messages') as batch:
        batch.drop_column('kind')
