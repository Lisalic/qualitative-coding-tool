"""Unit tests for backend/app/services/content_service.py.

Runs directly against an in-memory async SQLite session (the
``async_sqlite_engine`` fixture from ``tests/conftest.py``), bypassing the
HTTP layer entirely -- ``tests/backend/routes/test_ai_and_raw_sql_routes.py``
covers the route/auth/response-shape behavior on top of this.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import File, User
from backend.app.services import content_service, version_service


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session, email: str = "a@b.com") -> User:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    return user


class TestSaveSummary:
    async def test_happy_path_writes_file_and_content(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await content_service.save_summary(
                session,
                user.id,
                content="summary text",
                name="My Summary",
                description="  a desc  ",
                project_id=None,
            )

            assert file_rec.filename == "My Summary"
            assert file_rec.file_type == "summary"
            assert file_rec.schemaname.startswith("sum_")
            assert file_rec.description == "a desc"

            content = await version_service.read_blob(session, file_rec.id)
            assert content == "summary text"

    async def test_blank_description_normalizes_to_none(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await content_service.save_summary(
                session,
                user.id,
                content="x",
                name="n",
                description="   ",
                project_id=None,
            )
            assert file_rec.description is None

    async def test_links_owned_project(self, session_factory) -> None:
        from backend.app.database import Project

        async with session_factory() as session:
            user = await _make_user(session)
            proj = Project(user_id=user.id, projectname="proj", description=None)
            session.add(proj)
            await session.commit()

            file_rec = await content_service.save_summary(
                session,
                user.id,
                content="x",
                name="n",
                description=None,
                project_id=proj.id,
            )

            await session.refresh(proj, attribute_names=["files"])
            assert [f.id for f in proj.files] == [file_rec.id]

    async def test_project_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await content_service.save_summary(
                    session,
                    user.id,
                    content="x",
                    name="n",
                    description=None,
                    project_id=999999,
                )

    async def test_project_wrong_owner_raises_forbidden(self, session_factory) -> None:
        from backend.app.database import Project

        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            proj = Project(user_id=owner.id, projectname="proj", description=None)
            session.add(proj)
            await session.commit()

            with pytest.raises(ForbiddenError):
                await content_service.save_summary(
                    session,
                    other.id,
                    content="x",
                    name="n",
                    description=None,
                    project_id=proj.id,
                )


class TestGetSummary:
    async def _save(self, session, user_id, **kwargs):
        defaults = dict(content="c", name="n", description=None, project_id=None)
        defaults.update(kwargs)
        return await content_service.save_summary(session, user_id, **defaults)

    async def test_lookup_by_schemaname(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            saved = await self._save(session, user.id, name="s1")
            found = await content_service.get_summary(session, user.id, saved.schemaname)
            assert found.id == saved.id

    async def test_lookup_by_filename(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            saved = await self._save(session, user.id, name="unique-name")
            found = await content_service.get_summary(session, user.id, "unique-name")
            assert found.id == saved.id

    async def test_lookup_by_id(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            saved = await self._save(session, user.id, name="s3")
            found = await content_service.get_summary(session, user.id, str(saved.id))
            assert found.id == saved.id

    async def test_no_id_returns_latest(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await self._save(session, user.id, name="first")
            second = await self._save(session, user.id, name="second")

            found = await content_service.get_summary(session, user.id, None)
            assert found.id == second.id

    async def test_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await content_service.get_summary(session, user.id, "nonexistent")

    async def test_no_summaries_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await content_service.get_summary(session, user.id, None)

    async def test_scoped_to_calling_user(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            saved = await self._save(session, owner.id, name="owners-summary")

            # Another user can't reach it by schemaname/filename/id...
            with pytest.raises(NotFoundError):
                await content_service.get_summary(session, other.id, saved.schemaname)
            with pytest.raises(NotFoundError):
                await content_service.get_summary(session, other.id, "owners-summary")
            with pytest.raises(NotFoundError):
                await content_service.get_summary(session, other.id, str(saved.id))
            # ...nor via the "most recent" fallback.
            with pytest.raises(NotFoundError):
                await content_service.get_summary(session, other.id, None)

    async def test_not_a_summary_file_type_is_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            codebook = File(
                user_id=user.id, filename="cb", schemaname="proj_cb", file_type="codebook"
            )
            session.add(codebook)
            await session.commit()

            with pytest.raises(NotFoundError):
                await content_service.get_summary(session, user.id, codebook.schemaname)
