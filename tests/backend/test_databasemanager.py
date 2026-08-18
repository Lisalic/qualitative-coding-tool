"""Tests for backend/app/databasemanager.py.

Repositories take a session by constructor injection, so these run
against a real (in-memory SQLite) session via the shared `db_session`
fixture -- no Postgres needed, and no need to hand-mock SQLAlchemy's
query API.

The sync `DatabaseManager`/`ProjectRepository`/`UserRepository`/
`ProjectTableRepository` classes (and their tests) were removed in the
refactor's cleanup stage: every route was converted to async across
Stages 1-9, leaving zero remaining call sites for the sync classes.
Only the async repositories remain.
"""

import pytest

from backend.app.database import User
from backend.app.databasemanager import (
    AsyncProjectRepository,
    AsyncProjectTableRepository,
    AsyncUserRepository,
)


# ---------------------------------------------------------------------------
# Async repositories
# ---------------------------------------------------------------------------


class TestAsyncUserRepository:
    async def test_create_and_get_by_email(self, async_sqlite_engine) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            repo = AsyncUserRepository(session)
            user = await repo.create(email="a@b.com", hashed_password="hash")
            await session.commit()
            assert user.password == "hash"

            found = await repo.get_by_email("a@b.com")
            assert found is not None
            assert found.email == "a@b.com"

    async def test_get_by_email_not_found(self, async_sqlite_engine) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            repo = AsyncUserRepository(session)
            assert await repo.get_by_email("nobody@nowhere.com") is None


class TestAsyncProjectRepository:
    async def test_create_rename_and_list(self, async_sqlite_engine) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            user = User(email="a@b.com", password="hash")
            session.add(user)
            await session.commit()

            repo = AsyncProjectRepository(session)
            proj = await repo.create(user_id=user.id, projectname="P1")
            await session.commit()

            renamed = await repo.rename_project(proj.id, "P2")
            assert renamed is True

            all_projects = await repo.get_all_for_user(user.id)
            assert len(all_projects) == 1
            assert all_projects[0].projectname == "P2"

    async def test_rename_missing_returns_false(self, async_sqlite_engine) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            repo = AsyncProjectRepository(session)
            assert await repo.rename_project(999999, "x") is False


class TestAsyncProjectTableRepository:
    async def test_neither_id_raises_value_error(self, async_sqlite_engine) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            repo = AsyncProjectTableRepository(session)
            with pytest.raises(ValueError, match="Either project_id or file_id"):
                await repo.add_table_metadata()

    async def test_project_id_branch_is_a_no_op(self, async_sqlite_engine) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)
        async with SessionLocal() as session:
            repo = AsyncProjectTableRepository(session)
            assert await repo.add_table_metadata(project_id=1) is None
