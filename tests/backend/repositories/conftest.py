"""Shared helpers for repository tests -- builds directly on the
``async_sqlite_engine`` fixture from ``tests/conftest.py`` (same
``async_sessionmaker(async_sqlite_engine, expire_on_commit=False)``
pattern already used in ``tests/backend/test_databasemanager.py``), just
factored out to avoid repeating it in every test file.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import User


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def make_user(session, email: str = "a@b.com") -> User:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    return user
