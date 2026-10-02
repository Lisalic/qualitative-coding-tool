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
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT lower(trim(email)) AS email, count(*) AS n FROM users "
            "GROUP BY lower(trim(email)) HAVING count(*) > 1"
        )
    ).all()
    if duplicates:
        # Two accounts for one address (Foo@x.com and foo@x.com) can't be
        # merged automatically -- each may own projects. Fail with names
        # rather than a bare constraint error, so they can be resolved by
        # hand (delete or rename one) before this revision applies.
        listed = ", ".join(f"{row.email} ({row.n} accounts)" for row in duplicates)
        raise RuntimeError(f"Cannot add a case-insensitive unique email index; duplicate accounts: {listed}")

    # Store emails the way every auth request now normalizes them.
    bind.execute(sa.text("UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email))"))
    op.create_index('uq_users_email_lower', 'users', [sa.text('lower(email)')], unique=True)


def downgrade() -> None:
    op.drop_index('uq_users_email_lower', table_name='users')
