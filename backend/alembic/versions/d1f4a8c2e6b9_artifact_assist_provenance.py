"""artifact_assists + coding_entries.coder: AI-assist provenance channel

Revision ID: d1f4a8c2e6b9
Revises: c8f1b04e7a29
Create Date: 2026-09-07 00:00:00.000000

Closes GAP-4 in
``documentation/research/qualitative-coding-landscape-and-expansion.md``
(avenues B1 and C2): the editor overhaul made the human the author of
every artifact (``origin=edited``, no model, no prompt) and, as a side
effect, erased the record of where the AI actually helped. That decision
about ``origin``/``model``/``system_prompt`` is correct and untouched by
this revision -- see ``versioning_models.ArtifactAssist``'s docstring for
why a SIBLING channel is the fix rather than overloading those columns.

Two independent additions:

1. ``coding_entries.coder``/``coder_model`` (B1) -- per-quote attribution.
   ``server_default='human'`` because every entry that exists today was
   written by a human edit or an already-reviewed-and-accepted AI recode
   indistinguishable from one; there is no way to reconstruct which rows
   started life as an AI proposal after the fact (the proposal/accept
   state was never persisted -- that's GAP-4), so backfilling anything
   other than the conservative default would be inventing history. Per
   CLAUDE.md's early-prototyping rule, no backfill script is written.

2. ``artifact_assists`` (C2) -- one row per assistant run that
   contributed to a version: model, prompts, and accept/dismiss counts.
   Starts empty; there is nothing to backfill since this provenance was
   never captured before.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d1f4a8c2e6b9"
down_revision: Union[str, Sequence[str], None] = "c8f1b04e7a29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "coding_entries",
        sa.Column("coder", sa.String(), nullable=False, server_default="human"),
    )
    op.add_column(
        "coding_entries",
        sa.Column("coder_model", sa.String(), nullable=True),
    )
    op.create_index("idx_coding_entries_file_id_coder", "coding_entries", ["file_id", "coder"])

    op.create_table(
        "artifact_assists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_instructions", sa.Text(), nullable=True),
        sa.Column("prompt_meta", sa.JSON(), nullable=True),
        sa.Column("proposed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dismissed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_refs", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["artifact_versions.id"], ondelete="CASCADE"),
        # SET NULL rather than CASCADE: deleting the job row (which the
        # runner never does today, but ``jobs.py`` has no retention
        # policy specified) must not erase the assist record it produced.
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_artifact_assists_file_id", "artifact_assists", ["file_id"])
    op.create_index("idx_artifact_assists_version_id", "artifact_assists", ["version_id"])


def downgrade() -> None:
    op.drop_index("idx_artifact_assists_version_id", table_name="artifact_assists")
    op.drop_index("idx_artifact_assists_file_id", table_name="artifact_assists")
    op.drop_table("artifact_assists")

    op.drop_index("idx_coding_entries_file_id_coder", table_name="coding_entries")
    op.drop_column("coding_entries", "coder_model")
    op.drop_column("coding_entries", "coder")
