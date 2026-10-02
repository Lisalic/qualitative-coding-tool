"""add starred_quotes table for evidence shortlist

Revision ID: f4c8b2a1e0d3
Revises: e8a2b3c4d5f6
Create Date: 2026-09-13 00:00:00.000000

Adds the ``starred_quotes`` table for QC-008 (Quote bank and evidence shortlist).
Owner-scoped by ``user_id``; a star is keyed on a quote's stable identity
(row + ``code_uid`` + span), not on a ``coding_entries.id``, so it survives
the entry being re-inserted by a later version.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c8b2a1e0d3'
down_revision: Union[str, Sequence[str], None] = 'e8a2b3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'starred_quotes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('row_type', sa.String(), nullable=False),
        sa.Column('post_id', sa.String(), nullable=False),
        sa.Column('code_uid', sa.String(), nullable=False),
        sa.Column('start_offset', sa.Integer(), nullable=False),
        sa.Column('end_offset', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'file_id', 'row_type', 'post_id', 'code_uid', 'start_offset', 'end_offset',
            name='uq_starred_quotes_user_quote',
        ),
    )
    op.create_index('idx_starred_quotes_user_file', 'starred_quotes', ['user_id', 'file_id'])


def downgrade() -> None:
    op.drop_index('idx_starred_quotes_user_file', table_name='starred_quotes')
    op.drop_table('starred_quotes')
