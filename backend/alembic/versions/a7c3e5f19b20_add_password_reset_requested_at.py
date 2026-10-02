"""add users.password_reset_requested_at

Revision ID: a7c3e5f19b20
Revises: f4c8b2a1e0d3
Create Date: 2026-10-01 00:00:00.000000

Per-account cooldown for password-reset emails. Reset tokens themselves
are stateless signed tokens (see ``backend/app/services/auth_service.py``),
so this timestamp is the only state the feature needs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e5f19b20'
down_revision: Union[str, Sequence[str], None] = 'f4c8b2a1e0d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('password_reset_requested_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'password_reset_requested_at')
