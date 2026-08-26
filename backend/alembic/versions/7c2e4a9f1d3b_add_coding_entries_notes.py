"""add coding_entries.notes

Revision ID: 7c2e4a9f1d3b
Revises: 3fb52f406a4c
Create Date: 2026-08-23 00:00:00.000000

Part of the coding-artifact overhaul (see CLAUDE.md's "Core artifact
model"): a coding artifact now owns its own codebook snapshot, its own
copy of every sampled post/comment, and its coding -- with
``coding_entries`` as the sole source of truth for the coding part (no
more parallel ``artifact_content`` DSL blob to keep in sync). The
frontend's editor (``frontend/src/lib/codingUtils.js``'s old
``formatCodingData``/``parseCodingData``) already round-tripped an
optional ``NOTES:`` line per code/evidence entry, but the server-side
parse (``codebook_apply.py::_extract_structured_records``) never carried
it through to storage -- this column closes that gap.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c2e4a9f1d3b'
down_revision: Union[str, Sequence[str], None] = '3fb52f406a4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coding_entries', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('coding_entries', 'notes')
