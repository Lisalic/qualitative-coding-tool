"""add jobs.accounting and jobs.salvaged_output columns

Revision ID: e8a2b3c4d5f6
Revises: d1f4a8c2e6b9
Create Date: 2026-09-12 00:00:00.000000

Adds ``jobs.accounting`` and ``jobs.salvaged_output`` columns to the
``jobs`` table, matching the ORM schema added in commit 1162008 for
QC-005 (usage/accounting tracking) and QC-006 (partial job output salvage).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8a2b3c4d5f6'
down_revision: Union[str, Sequence[str], None] = 'd1f4a8c2e6b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('accounting', sa.JSON(), nullable=True))
    op.add_column('jobs', sa.Column('salvaged_output', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'salvaged_output')
    op.drop_column('jobs', 'accounting')
