"""add jobs table

Revision ID: 8b0a568ce28c
Revises:
Create Date: 2026-08-17 14:25:45.291827

Note: submissions/comments/artifact_content/coding_entries already exist
in the target database (created by an earlier, uncommitted session via
Base.metadata.create_all -- verified their live structure exactly
matches backend/app/storage_models.py) so autogenerate correctly found
no diff for them; only `jobs` is actually new here. Unrelated
pre-existing drift the autogenerate diff also surfaced (a stray
`project_tables` table, several TEXT/String column-type mismatches, a
missing project_files FK) is left untouched -- out of scope for this
migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b0a568ce28c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_type', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('error_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('jobs')
