"""artifact version spine (finalize: drop legacy storage)

Revision ID: d4f97a2c6e1b
Revises: c2e58b41d7af
Create Date: 2026-08-26 00:00:00.000001

Second half of the artifact-version-spine cutover -- see
``c2e58b41d7af``'s module docstring for the full three-step story
(additive migration -> ``backend/scripts/backfill_codebook_codes.py`` ->
this revision). This one has nothing left to invent: it just enforces
the constraints the previous revision left nullable on purpose, and
deletes what nothing reads through the old path any more (every service
call site was rewritten onto ``version_service.py``/``version_repo.py``
in the same application change that ships this migration -- per
CLAUDE.md's early-prototyping rule, there is no dual-read period, no
back-compat shim, and no reason to keep the old columns/tables around
once the app stops reading them).

**Operator note:** if this revision is run on a database that has real
``coding_entries`` rows and the backfill script was skipped, the ``ALTER
COLUMN code_uid SET NOT NULL`` below will fail loudly with a constraint
violation naming the offending rows -- which is the intended failure
mode (state it loudly, don't silently truncate data) rather than a
silent success that leaves ``code_uid`` NULL somewhere the app now
assumes it never is. Run the backfill script first.

Downgrade recreates ``file_dependencies``, ``artifact_content``, and
``files.systemprompt``/``userprompt`` structurally (empty, per the
precedent ``9a1c3e7f5b2d`` already set for this same table) -- their
content lives in ``artifact_versions``/``codebook_codes`` now, and a
typed, version-pinned, multi-role edge or a per-code row set cannot be
projected back onto an untyped ``(child, parent)`` pair or a single blob
without inventing information that no longer exists in a recoverable
form.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f97a2c6e1b'
down_revision: Union[str, Sequence[str], None] = 'c2e58b41d7af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE coding_entries SET valid_from = 1 WHERE valid_from IS NULL"))
    op.alter_column('coding_entries', 'code_uid', nullable=False)
    op.alter_column('coding_entries', 'valid_from', nullable=False)

    op.drop_table('file_dependencies')
    op.drop_table('artifact_content')

    op.drop_column('files', 'systemprompt')
    op.drop_column('files', 'userprompt')


def downgrade() -> None:
    op.add_column('files', sa.Column('systemprompt', sa.String(), nullable=True))
    op.add_column('files', sa.Column('userprompt', sa.String(), nullable=True))

    op.create_table(
        'artifact_content',
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('file_id'),
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

    op.alter_column('coding_entries', 'valid_from', nullable=True)
    op.alter_column('coding_entries', 'code_uid', nullable=True)
