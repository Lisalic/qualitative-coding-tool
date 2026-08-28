"""stop copying a coding artifact's codebook snapshot on every save

Revision ID: f2b6c8e0a913
Revises: e7a3d1c9b482
Create Date: 2026-08-27 00:00:00.000001

``version_service.commit_coding_version`` used to call
``version_repo.copy_codes`` on every single coding save -- including a
plain row-only edit (``save_coding_rows``, an AI recode) that never
touches the codebook at all -- producing a byte-identical ~44 kB
``codebook_codes`` snapshot per save. 100 row-edits meant 100 copies of
the same ~18 codes: 4.4 MB for content nobody changed.

This revision adds one column, ``artifact_versions.codes_materialized``
(default ``True``). A coding version born from a row-only edit is now
stamped ``False`` instead of copying anything, and
``version_service.read_codes`` resolves it by looking up the nearest
earlier version with ``codes_materialized = True`` -- one indexed query,
not a replay, since there's no delta representation to replay here (see
``versioning_models.ArtifactVersion``'s docstring for the full reasoning
and the O(1)-regardless-of-run-length argument).

**No backfill needed.** Every version that exists today is fully
materialized -- it already has its own ``codebook_codes`` rows -- so
``server_default=true`` is exactly the right value for all of them: a
materialized version is trivially a valid anchor. Nothing about existing
data changes; only future coding saves stop over-copying.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2b6c8e0a913"
down_revision: Union[str, Sequence[str], None] = "e7a3d1c9b482"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "artifact_versions",
        sa.Column("codes_materialized", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("artifact_versions", "codes_materialized")
