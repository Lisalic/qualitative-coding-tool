"""baseline untracked schema

Revision ID: a1e6f2c9b3d7
Revises:
Create Date: 2026-08-26 00:00:00.000000

This is now the ROOT of the chain -- it takes over `down_revision = None`
from `8b0a568ce28c`, which becomes its child. That is not cosmetic:
`8b0a568ce28c` creates `jobs`, whose `user_id` column has
`ForeignKeyConstraint(['user_id'], ['users.id'])` -- and confirmed by
actually running `alembic upgrade head` against a genuinely empty
Postgres database, that statement fails with
`psycopg2.errors.UndefinedTable: relation "users" does not exist`.
`8b0a568ce28c` was only ever run against databases where `users` already
existed via `backend/app/main.py`'s `Base.metadata.create_all` -- exactly
as its own docstring says of `submissions`/`comments`/`artifact_content`/
`coding_entries`, but `users` (and `projects`, `files`, `file_tables`,
`project_files`, `file_dependencies`, `prompts`) were never even
mentioned there, because nothing had yet needed to alter them. No
revision in this project's history has ever been run against a database
that didn't already have the full `create_all` schema underneath it, and
so no migration here has ever been testable end to end.

This revision fixes that by giving every one of those never-migrated
tables a real `op.create_table`, ahead of `8b0a568ce28c` in the chain, so
`alembic upgrade head` against a genuinely empty database now builds a
complete, working schema instead of failing on the second table it tries
to create. It also means `compare_metadata` against `Base.metadata` can
be asserted empty in a test for the first time (see
`tests/backend/integration/test_alembic_migration.py`).

This also makes good on a claim `backend/app/storage_models.py` has been
making since it was written: its module docstring says `word_count` on
`Submission`/`Comment` is "a plain `Integer` for ORM/test purposes... the
real `GENERATED ALWAYS AS (...) STORED` DDL is added by the Alembic
migration that creates these tables against Postgres" -- no such
migration has ever existed; the only place that DDL is written anywhere
in this repository is the legacy per-schema path in
`backend/scripts/import_db.py:71-91`. This revision reproduces that exact
expression as a Postgres-only `sa.Computed(..., persisted=True)` column
(SQLite's `Base.metadata.create_all`, which the default unit test suite
still uses, has never modeled generated-column behavior and continues
not to -- this migration only changes what a real Postgres upgrade
produces).

`file_dependencies` is included here even though the very next revision
after `9a1c3e7f5b2d` (the A10 revision) drops it again. That is
deliberate: this revision's job is to describe the schema that has
ACTUALLY existed since before any of these revisions were written, and
`file_dependencies` genuinely was part of that schema at this point in
history.

**No operator step is needed for any database that already ran this
project's migrations** (every environment running today, including the
Azure deployment). Inserting a new ROOT ahead of the currently-stamped
revision does not change what `alembic_version` holds, and Alembic only
ever applies revisions strictly after the one currently stamped -- an
already-migrated database stamped at `9a1c3e7f5b2d` sees this revision
as already-satisfied history, not as pending work, and `alembic upgrade
head` against it is a no-op. Only a genuinely fresh/empty database (a new
local Postgres, a new CI database) exercises this revision's DDL at all,
which is exactly the case that was broken before.

Pre-existing drift `8b0a568ce28c`'s docstring already flagged (a stray
`project_tables` table, some TEXT/String column-type mismatches, a
missing `project_files` FK) is still left untouched here -- out of scope
for this revision, same as it was there.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1e6f2c9b3d7'
down_revision: Union[str, Sequence[str], None] = None
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
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('projectname', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'files',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('schemaname', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('file_type', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('systemprompt', sa.String(), nullable=True),
        sa.Column('userprompt', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'file_tables',
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('tablename', sa.String(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('file_id', 'tablename'),
    )

    op.create_table(
        'project_files',
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('project_id', 'file_id'),
    )

    op.create_table(
        'file_dependencies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('child_file_id', sa.Integer(), nullable=False),
        sa.Column('parent_file_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['child_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'prompts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('promptname', sa.String(), nullable=False),
        sa.Column('prompt', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'submissions',
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('subreddit', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('selftext', sa.String(), nullable=True),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('created_utc', sa.BigInteger(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('num_comments', sa.Integer(), nullable=True),
        sa.Column(
            'word_count', sa.Integer(),
            sa.Computed(_SUBMISSIONS_WORD_COUNT_EXPR, persisted=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('file_id', 'id'),
    )
    op.create_index('idx_submissions_file_id_word_count', 'submissions', ['file_id', 'word_count'])

    op.create_table(
        'comments',
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('subreddit', sa.String(), nullable=True),
        sa.Column('body', sa.String(), nullable=True),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('created_utc', sa.BigInteger(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('link_id', sa.String(), nullable=True),
        sa.Column('parent_id', sa.String(), nullable=True),
        sa.Column(
            'word_count', sa.Integer(),
            sa.Computed(_COMMENTS_WORD_COUNT_EXPR, persisted=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('file_id', 'id'),
    )
    op.create_index('idx_comments_file_id_word_count', 'comments', ['file_id', 'word_count'])

    op.create_table(
        'artifact_content',
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('file_id'),
    )

    # This is `coding_entries`' shape as it ACTUALLY existed the moment
    # `8b0a568ce28c` first ran against a `create_all`'d database -- i.e.
    # before any of `3fb52f406a4c` (adds row_type, widens the PK),
    # `7c2e4a9f1d3b` (adds notes), or `9a1c3e7f5b2d` (drops/recreates
    # with quote/start_offset/end_offset) had been applied. Those three
    # revisions already know how to evolve this exact starting shape
    # into today's -- reproducing their target shape here instead would
    # make each of them fail with "column already exists" (verified: it
    # does) the first time this chain runs against a fresh database.
    op.create_table(
        'coding_entries',
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('file_id', 'post_id', 'code'),
    )
    op.create_index('idx_coding_entries_file_id_code', 'coding_entries', ['file_id', 'code'])


def downgrade() -> None:
    op.drop_index('idx_coding_entries_file_id_code', table_name='coding_entries')
    op.drop_table('coding_entries')

    op.drop_table('artifact_content')

    op.drop_index('idx_comments_file_id_word_count', table_name='comments')
    op.drop_table('comments')

    op.drop_index('idx_submissions_file_id_word_count', table_name='submissions')
    op.drop_table('submissions')

    op.drop_table('prompts')
    op.drop_table('file_dependencies')
    op.drop_table('project_files')
    op.drop_table('file_tables')
    op.drop_table('files')
    op.drop_table('projects')
    op.drop_table('users')
