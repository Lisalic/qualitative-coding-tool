"""field-level codebook deltas for compacted versions

Revision ID: a4d7f931c8e5
Revises: f2b6c8e0a913
Create Date: 2026-08-27 00:00:00.000001

``f2b6c8e0a913`` stopped a coding-only save from copying the whole
codebook snapshot forward, but a genuine codebook EDIT (a real
``commit_codebook_version`` call -- ``save_project_codebook``, apply-
codebook, ``save_coding_codebook``) still materializes a full
``codebook_codes`` row set every single time, forever. A codebook edited
repeatedly over a long history still grows ``codebook_codes`` linearly
with the number of edits, the same shape of problem ``f2b6c8e0a913``
fixed for coding saves, just on a slower clock.

This revision adds ``artifact_versions.codes_delta`` (JSON, nullable).
Combined with the already-added ``codes_materialized``,
``version_service`` now keeps only v1, the 3 most recent versions of any
file, and every 10th version ("keyframe") fully materialized; every
other version is compacted to a field-level delta
(``core/codebook_delta.py::encode_delta``) computed directly against its
nearest still-materialized ancestor, and reconstructed on read by
``version_service.read_codes`` via ``apply_delta``. See
``versioning_models.ArtifactVersion.codes_materialized``'s docstring for
the full policy and the reasoning for a single direct delta per
compacted version rather than a chain of consecutive ones.

**No backfill.** Existing rows are already fully materialized (the
previous revision's ``server_default=true``), which is what makes them
valid anchors -- ``codes_delta`` stays ``NULL`` for all of them, exactly
like a real materialized version created after this revision. Nothing
about existing data needs to change; only future compaction (which only
starts kicking in once a file accumulates more than
``LATEST_MATERIALIZED_WINDOW`` + a keyframe's worth of versions) uses the
new column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a4d7f931c8e5"
down_revision: Union[str, Sequence[str], None] = "f2b6c8e0a913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("artifact_versions", sa.Column("codes_delta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("artifact_versions", "codes_delta")
