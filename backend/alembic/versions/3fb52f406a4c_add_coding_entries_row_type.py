"""add coding_entries.row_type

Revision ID: 3fb52f406a4c
Revises: 5445e278056d
Create Date: 2026-08-23 00:00:00.000000

Distinguishes a coded post from a coded comment. Before this, a
``coding_entries.post_id`` was assumed to always be a submission id --
but Apply Codebook samples both ``submissions`` and ``comments``
(``coding_service.py::_assemble_posts_content``) and flattened both into
the same ``POST_ID`` label with no marker, so a comment could be coded
but never resolved back to its text (``data_service.get_post_contents``
only ever queried ``Submission``). Submission and comment ids share one
bare-string namespace (both strip their Reddit fullname prefix at
import), so without this column a genuine id collision between the two
tables would silently merge into one ``coding_entries`` row.

Backfills every existing row to ``'submission'`` -- the only value any
row written before this column existed could have meant, since the
comment-aware assembly path this migration accompanies did not exist
yet. The primary key widens from ``(file_id, post_id, code)`` to
``(file_id, row_type, post_id, code)`` so a post and a comment that
happen to share an id in the same file no longer collide.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fb52f406a4c'
down_revision: Union[str, Sequence[str], None] = '5445e278056d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'coding_entries',
        sa.Column('row_type', sa.String(), nullable=False, server_default='submission'),
    )
    op.drop_constraint('coding_entries_pkey', 'coding_entries', type_='primary')
    op.create_primary_key(
        'coding_entries_pkey',
        'coding_entries',
        ['file_id', 'row_type', 'post_id', 'code'],
    )


def downgrade() -> None:
    op.drop_constraint('coding_entries_pkey', 'coding_entries', type_='primary')
    op.create_primary_key(
        'coding_entries_pkey',
        'coding_entries',
        ['file_id', 'post_id', 'code'],
    )
    op.drop_column('coding_entries', 'row_type')
