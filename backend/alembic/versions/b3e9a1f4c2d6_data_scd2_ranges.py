"""submissions/comments: SCD-2 revision ranges, surrogate PK

Revision ID: b3e9a1f4c2d6
Revises: a4d7f931c8e5
Create Date: 2026-08-28 00:00:00.000000

Adds ``valid_from``/``valid_to`` range columns to ``submissions`` and
``comments``, mirroring ``coding_entries``'s existing SCD-2 shape (see
``storage_models.py::CodingEntry``'s docstring): a row is live iff
``valid_to IS NULL``, live *as of* version ``v`` iff ``valid_from <= v
AND (valid_to IS NULL OR valid_to >= v)``. Backs real version history
for raw/filtered data -- ``file_service.delete_rows``/``move_rows`` now
close a row's range instead of hard-deleting it, and each mutation
mints a real ``artifact_versions`` row via
``version_service.commit_data_version``.

The primary key also changes shape, from composite ``(file_id, id)`` to
a surrogate ``pk``: with soft-delete, a row moved out of a file and
later moved back in produces two rows sharing the same ``(file_id,
id)`` (one closed, one live), which the old composite PK can no longer
represent. ``coding_entries`` already made this exact PK-shape change
(see ``9a1c3e7f5b2d``) for the same reason.

A partial unique index ``(file_id, id) WHERE valid_to IS NULL``
preserves "at most one LIVE row per id" without constraining the
now-permitted historical duplicates.

``word_count`` stays untouched: it is a real ``GENERATED ALWAYS AS
(...) STORED`` column (added by ``a1e6f2c9b3d7``) and is not part of
either table's primary key, so swapping the PK out from under it does
not require regenerating it.

Backfill: every pre-existing row is, by definition, still live and was
live from the beginning of that file's history -- ``valid_from``'s
``server_default='1'`` and ``valid_to``'s default ``NULL`` are already
the correct backfilled values, so no data migration step is needed
beyond adding the columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3e9a1f4c2d6"
down_revision: Union[str, Sequence[str], None] = "a4d7f931c8e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _upgrade_table(table: str) -> None:
    op.add_column(table, sa.Column("valid_from", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(table, sa.Column("valid_to", sa.Integer(), nullable=True))

    # Surrogate PK: add as SERIAL (NOT NULL + its own sequence in one
    # statement -- ALTER TABLE ADD COLUMN can't express SQLAlchemy's
    # `autoincrement=True` the way CREATE TABLE can), drop the old
    # composite PK, promote the new column. Plain `Integer`/`SERIAL`
    # (not `BigInteger`/`BIGSERIAL`) to match this column's ORM type in
    # `storage_models.py` -- also matches every other surrogate PK in
    # this project (`File.id`, `ArtifactVersion.id`, `CodingEntry.id`),
    # and SQLite's ROWID-alias autoincrement (used by the test suite)
    # only kicks in for a column declared exactly `INTEGER`, not
    # `BIGINT` -- a `BigInteger` PK silently fails to autogenerate under
    # SQLite even though it works fine under Postgres.
    op.execute(f'ALTER TABLE "{table}" ADD COLUMN pk SERIAL')
    op.drop_constraint(f"{table}_pkey", table, type_="primary")
    op.create_primary_key(f"{table}_pkey", table, ["pk"])

    op.create_index(f"idx_{table}_live", table, ["file_id", "valid_to"])
    op.create_index(
        f"uq_{table}_file_id_id_live", table, ["file_id", "id"],
        unique=True, postgresql_where=sa.text("valid_to IS NULL"),
    )


def _downgrade_table(table: str) -> None:
    op.drop_index(f"uq_{table}_file_id_id_live", table_name=table)
    op.drop_index(f"idx_{table}_live", table_name=table)

    op.drop_constraint(f"{table}_pkey", table, type_="primary")
    op.drop_column(table, "pk")
    op.create_primary_key(f"{table}_pkey", table, ["file_id", "id"])

    op.drop_column(table, "valid_to")
    op.drop_column(table, "valid_from")


def upgrade() -> None:
    _upgrade_table("submissions")
    _upgrade_table("comments")


def downgrade() -> None:
    # Downgrading with more than one live-per-id-per-file duplicate
    # present (created by a soft-move after this revision) would violate
    # the old composite PK -- an operator restoring the old shape from a
    # database that has taken advantage of the new one must first
    # collapse history to current live rows. Not handled here (per this
    # project's early-prototyping/no-legacy-compat stance); this
    # downgrade is only guaranteed clean immediately after upgrading.
    _downgrade_table("comments")
    _downgrade_table("submissions")
