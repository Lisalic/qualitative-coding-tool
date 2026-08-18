"""Tests for backend/app/databasemanager.py.

Repositories take a session by constructor injection, so these run
against a real (in-memory SQLite) session via the shared `db_session`
fixture -- no Postgres needed, and no need to hand-mock SQLAlchemy's
query API.
"""

import pytest

from backend.app.database import Project, User
from backend.app.databasemanager import (
    AsyncProjectRepository,
    AsyncProjectTableRepository,
    AsyncUserRepository,
    DatabaseManager,
    ProjectRepository,
    ProjectTableRepository,
    UserRepository,
)


# ---------------------------------------------------------------------------
# Sync repositories
# ---------------------------------------------------------------------------


class TestUserRepository:
    def test_create_and_flush(self, db_session) -> None:
        """Confirmed bug: `create` passed `hashed_password=...`, the
        *column* name (`Column("hashed_password", ...)`), not the mapped
        attribute `password` -- raising TypeError on every call. Fixed to
        use the correct keyword.
        """
        repo = UserRepository(db_session)
        user = repo.create(email="a@b.com", hashed_password="hash123")
        assert user.id is not None
        assert user.email == "a@b.com"
        assert user.password == "hash123"

    def test_get_by_email_found(self, db_session) -> None:
        repo = UserRepository(db_session)
        repo.create(email="a@b.com", hashed_password="hash")
        db_session.commit()
        found = repo.get_by_email("a@b.com")
        assert found is not None
        assert found.email == "a@b.com"

    def test_get_by_email_not_found(self, db_session) -> None:
        repo = UserRepository(db_session)
        assert repo.get_by_email("nobody@nowhere.com") is None


class TestProjectRepository:
    def _make_user(self, db_session) -> User:
        user = User(email="owner@x.com", password="hash")
        db_session.add(user)
        db_session.commit()
        return user

    def test_create_and_get_all_for_user(self, db_session) -> None:
        user = self._make_user(db_session)
        repo = ProjectRepository(db_session)
        repo.create(user_id=user.id, projectname="P1")
        db_session.commit()
        projects = repo.get_all_for_user(user.id)
        assert len(projects) == 1
        assert projects[0].projectname == "P1"

    def test_get_all_for_user_empty(self, db_session) -> None:
        repo = ProjectRepository(db_session)
        assert repo.get_all_for_user(999) == []

    def test_rename_project_existing_returns_true(self, db_session) -> None:
        user = self._make_user(db_session)
        proj = Project(user_id=user.id, projectname="Old")
        db_session.add(proj)
        db_session.commit()

        repo = ProjectRepository(db_session)
        result = repo.rename_project(proj.id, "New")
        assert result is True
        assert proj.projectname == "New"

    def test_rename_project_missing_returns_false(self, db_session) -> None:
        repo = ProjectRepository(db_session)
        assert repo.rename_project(999999, "New") is False


class TestProjectTableRepository:
    def test_project_id_branch_is_a_no_op(self, db_session) -> None:
        repo = ProjectTableRepository(db_session)
        assert repo.add_table_metadata(project_id=1, table_name="t", row_count=5) is None

    def test_file_id_branch_creates_file_table_row(self, db_session) -> None:
        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        from backend.app.database import File

        f = File(user_id=user.id, filename="f.zst", schemaname="proj_x")
        db_session.add(f)
        db_session.commit()

        repo = ProjectTableRepository(db_session)
        ft = repo.add_table_metadata(file_id=f.id, table_name="submissions", row_count=10)
        assert ft is not None
        assert ft.tablename == "submissions"
        assert ft.row_count == 10

    def test_neither_id_raises_value_error(self, db_session) -> None:
        repo = ProjectTableRepository(db_session)
        with pytest.raises(ValueError, match="Either project_id or file_id"):
            repo.add_table_metadata()

    def test_project_id_takes_precedence_over_file_id(self, db_session) -> None:
        # When both are given, the project_id branch's early return wins.
        repo = ProjectTableRepository(db_session)
        assert repo.add_table_metadata(project_id=1, file_id=2) is None


class TestDatabaseManagerContextManager:
    def test_commits_on_clean_exit(self, sqlite_engine, monkeypatch) -> None:
        from sqlalchemy.orm import sessionmaker

        monkeypatch.setattr(
            "backend.app.databasemanager.SessionLocal",
            sessionmaker(bind=sqlite_engine, expire_on_commit=False),
        )
        with DatabaseManager() as dm:
            dm.users.create(email="a@b.com", hashed_password="hash")

        # A fresh session must see the committed row.
        Session = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
        with Session() as verify:
            assert verify.query(User).filter_by(email="a@b.com").first() is not None

    def test_rolls_back_on_exception(self, sqlite_engine, monkeypatch) -> None:
        from sqlalchemy.orm import sessionmaker

        monkeypatch.setattr(
            "backend.app.databasemanager.SessionLocal",
            sessionmaker(bind=sqlite_engine, expire_on_commit=False),
        )
        with pytest.raises(RuntimeError):
            with DatabaseManager() as dm:
                dm.users.create(email="rollback@x.com", hashed_password="hash")
                raise RuntimeError("boom")

        Session = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
        with Session() as verify:
            assert verify.query(User).filter_by(email="rollback@x.com").first() is None

    def test_file_tables_is_an_alias_for_project_tables(self, sqlite_engine, monkeypatch) -> None:
        from sqlalchemy.orm import sessionmaker

        monkeypatch.setattr(
            "backend.app.databasemanager.SessionLocal",
            sessionmaker(bind=sqlite_engine, expire_on_commit=False),
        )
        with DatabaseManager() as dm:
            assert dm.file_tables is dm.project_tables


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
