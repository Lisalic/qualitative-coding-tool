"""unique index on lower(users.email)

Revision ID: b8d4f2a6c1e7
Revises: a7c3e5f19b20
Create Date: 2026-10-02 00:00:00.000000

Emails are case-insensitive account identifiers: login, register and
forgot-password all look users up by ``lower(email)``. This index makes
that lookup indexed and stops Foo@x.com and foo@x.com from both registering.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d4f2a6c1e7'
down_revision: Union[str, Sequence[str], None] = 'a7c3e5f19b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('uq_users_email_lower', 'users', [sa.text('lower(email)')], unique=True)


def downgrade() -> None:
    op.drop_index('uq_users_email_lower', table_name='users')
