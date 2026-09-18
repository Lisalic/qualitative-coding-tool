"""row_memos: user-authored analytic memos on a row

Revision ID: c8f1b04e7a29
Revises: b3e9a1f4c2d6
Create Date: 2026-09-02 00:00:00.000000

Adds ``row_memos``, closing GAP-4 in
``documentation/research/qualitative-coding-landscape-and-expansion.md``:
until now the only place a researcher could write down an observation
was ``coding_entries.notes`` (added by ``7c2e4a9f1d3b``), which
annotates a single coded *quote* and therefore only exists once a
codebook has been generated and applied. A memo attaches to the row
itself and is available from the moment data is imported.

Scoped by ``file_id`` like every other table in ``storage_models.py``,
so a memo belongs to one artifact's copy of a row. Memos are copied
forward alongside rows (``repositories/memo_repo.py``), which is what
makes a memo written while filtering still visible when that row is
opened inside the resulting ``filtered_data`` artifact.

``row_type`` is part of the uniqueness key for the same reason it is on
``coding_entries`` (see ``3fb52f406a4c``): submission and comment ids
share one bare-string namespace once their Reddit fullname prefixes are
stripped at import, so ``(file_id, row_id)`` alone would merge a post's
memo with a same-id comment's.

Deliberately no ``valid_from``/``valid_to``: unlike
``submissions``/``comments``/``coding_entries``, a memo is commentary
about an artifact rather than artifact content, so it is not what a
version diff describes and it is not range-versioned. ``updated_at``
carries the recency signal instead. See ``storage_models.py::RowMemo``.

There is nothing to backfill -- the table starts empty.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8f1b04e7a29"
down_revision: Union[str, Sequence[str], None] = "b3e9a1f4c2d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "row_memos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("row_type", sa.String(), nullable=False),
        sa.Column("row_id", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # SET NULL rather than CASCADE: deleting a user must not silently
        # erase memos on artifacts, mirroring
        # ``artifact_versions.author_user_id``.
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "row_type", "row_id", name="uq_row_memos_file_row"),
    )
    op.create_index("idx_row_memos_file_row", "row_memos", ["file_id", "row_type", "row_id"])


def downgrade() -> None:
    op.drop_index("idx_row_memos_file_row", table_name="row_memos")
    op.drop_table("row_memos")
