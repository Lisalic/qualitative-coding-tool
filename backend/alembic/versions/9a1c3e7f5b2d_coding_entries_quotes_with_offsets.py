"""coding_entries: one row per quote, with start/end offsets

Revision ID: 9a1c3e7f5b2d
Revises: 7c2e4a9f1d3b
Create Date: 2026-08-26 00:00:00.000000

Replaces the free-text ``evidence`` column (an AI's raw, unverified
``"quote a"§"quote b"`` string for one (item, code) pair) with one row per
individual quote, each carrying the exact ``start_offset``/``end_offset``
into the item's own body text (``Submission.selftext``/``Comment.body``)
that the quote was resolved to (see ``backend/app/core/evidence_match.py``).

This is what makes View Coding's highlighting exact by construction: the
frontend used to re-search for each evidence snippet in the rendered text
at render time (``content.indexOf``, with a regex fallback) -- fragile,
and the direct cause of an earlier highlighting bug. Storing the resolved
offsets removes that search entirely.

Per CLAUDE.md's early-prototyping rule (no legacy compatibility, no
production data worth preserving), this drops and recreates the table
outright rather than attempting to backfill ``evidence`` strings into
quotes+offsets -- a merged, possibly-approximate evidence string cannot be
split back into individually-verified, exactly-offset quotes without
re-running the classifier. Existing coding artifacts keep their codebook
snapshot and their own rows; only their coding is lost. Re-run Apply
Codebook (or Recode with AI) to repopulate it.

The primary key also changes shape: it's now a surrogate ``id`` rather
than ``(file_id, row_type, post_id, code)``, since one code can now be
supported by more than one quote (more than one row).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1c3e7f5b2d'
down_revision: Union[str, Sequence[str], None] = '7c2e4a9f1d3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('coding_entries')
    op.create_table(
        'coding_entries',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('row_type', sa.String(), nullable=False, server_default='submission'),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('quote', sa.Text(), nullable=False),
        sa.Column('start_offset', sa.Integer(), nullable=False),
        sa.Column('end_offset', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_index('idx_coding_entries_file_id_code', 'coding_entries', ['file_id', 'code'])
    op.create_index('idx_coding_entries_file_id_row', 'coding_entries', ['file_id', 'row_type', 'post_id'])


def downgrade() -> None:
    op.drop_table('coding_entries')
    op.create_table(
        'coding_entries',
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('row_type', sa.String(), primary_key=True, server_default='submission'),
        sa.Column('post_id', sa.String(), primary_key=True),
        sa.Column('code', sa.String(), primary_key=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_index('idx_coding_entries_file_id_code', 'coding_entries', ['file_id', 'code'])
