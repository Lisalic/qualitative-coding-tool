"""add jobs.progress column

Revision ID: 5445e278056d
Revises: 8b0a568ce28c
Create Date: 2026-08-23 00:00:00.000000

Lets a long-running, multi-batch job handler (filter-data, apply-codebook,
generate-codebook, summarize-coding) push interim progress -- so
``GET /api/jobs/{id}`` can report "N/M batches processed" while a job is
still ``running``, instead of the frontend only learning anything once it
reaches a terminal status.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5445e278056d'
down_revision: Union[str, Sequence[str], None] = '8b0a568ce28c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('progress', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'progress')
