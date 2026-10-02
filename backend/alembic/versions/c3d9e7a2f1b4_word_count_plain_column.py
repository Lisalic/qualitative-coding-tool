"""make word_count a plain column filled by the app

Revision ID: c3d9e7a2f1b4
Revises: b8d4f2a6c1e7
Create Date: 2026-10-02 00:00:00.000000

``a1e6f2c9b3d7`` declared ``submissions.word_count``/``comments.word_count``
as ``GENERATED ALWAYS AS (...) STORED``, but every write path
(``raw_data_repo.bulk_insert_*``, ``copy_rows_by_id``/``copy_all_rows``)
sets ``word_count`` explicitly -- the ORM and the SQLite unit tests model it
as a plain ``Integer`` -- so on a database built by migrations Postgres
rejected every upload and row copy with "cannot insert a non-DEFAULT value
into column word_count". ``DROP EXPRESSION`` keeps the stored values and
turns the column into a plain integer that ``raw_data_repo._word_count``
fills in. ``IF EXISTS`` makes this a no-op on a database whose column was
already plain (one first built by ``create_all``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d9e7a2f1b4'
down_revision: Union[str, Sequence[str], None] = 'b8d4f2a6c1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SUBMISSIONS_WORD_COUNT_EXPR = (
    "CASE WHEN COALESCE(TRIM(title || ' ' || selftext), '') = '' THEN 0 "
    "ELSE array_length(string_to_array(regexp_replace(TRIM(title || ' ' || selftext), '\\s+', ' ', 'g'), ' '), 1) "
    "END"
)
_COMMENTS_WORD_COUNT_EXPR = (
    "CASE WHEN COALESCE(TRIM(body), '') = '' THEN 0 "
    "ELSE array_length(string_to_array(regexp_replace(TRIM(body), '\\s+', ' ', 'g'), ' '), 1) "
    "END"
)


def upgrade() -> None:
    op.execute("ALTER TABLE submissions ALTER COLUMN word_count DROP EXPRESSION IF EXISTS")
    op.execute("ALTER TABLE comments ALTER COLUMN word_count DROP EXPRESSION IF EXISTS")


def downgrade() -> None:
    for table, expr in (
        ('submissions', _SUBMISSIONS_WORD_COUNT_EXPR),
        ('comments', _COMMENTS_WORD_COUNT_EXPR),
    ):
        op.drop_index(f'idx_{table}_file_id_word_count', table_name=table)
        op.drop_column(table, 'word_count')
        op.add_column(table, sa.Column('word_count', sa.Integer(), sa.Computed(expr, persisted=True), nullable=True))
        op.create_index(f'idx_{table}_file_id_word_count', table, ['file_id', 'word_count'])
