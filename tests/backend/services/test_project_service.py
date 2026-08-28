"""Unit tests for backend/app/services/project_service.py.

Runs directly against an in-memory async SQLite session (the
``async_sqlite_engine`` fixture from ``tests/conftest.py``), bypassing the
HTTP layer entirely -- ``tests/backend/routes/test_project_routes.py``
covers the route/auth/response-shape behavior on top of this.
"""

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from backend.app.database import File, FileTable, User
from backend.app.repositories import version_repo
from backend.app.services import project_service


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session, email: str = "a@b.com") -> User:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    return user


class TestListFilesForUser:
    async def test_empty_for_new_user(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            rows = await project_service.list_files_for_user(session, user.id)
            assert rows == []

    async def test_default_file_type_is_raw_data(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            session.add(
                File(user_id=user.id, filename="a.zst", schemaname="proj_a", file_type="raw_data")
            )
            session.add(
                File(user_id=user.id, filename="b.txt", schemaname="proj_b", file_type="codebook")
            )
            await session.commit()

            rows = await project_service.list_files_for_user(session, user.id)
            assert [r["schema_name"] for r in rows] == ["proj_a"]

    async def test_codebook_file_type_excludes_comparisons(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            session.add(
                File(user_id=user.id, filename="cb", schemaname="proj_cb", file_type="codebook")
            )
            session.add(
                File(
                    user_id=user.id,
                    filename="cmp",
                    schemaname="cmp_x",
                    file_type="codebook_comparison",
                )
            )
            session.add(
                File(user_id=user.id, filename="raw", schemaname="proj_raw", file_type="raw_data")
            )
            await session.commit()

            rows = await project_service.list_files_for_user(session, user.id, "codebook")
            assert [r["schema_name"] for r in rows] == ["proj_cb"]

    async def test_coding_file_type_excludes_comparisons(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            session.add(
                File(user_id=user.id, filename="c", schemaname="proj_c", file_type="coding")
            )
            session.add(
                File(
                    user_id=user.id, filename="cmp", schemaname="cmp_c", file_type="coding_comparison"
                )
            )
            await session.commit()

            rows = await project_service.list_files_for_user(session, user.id, "coding")
            assert [r["schema_name"] for r in rows] == ["proj_c"]

    async def test_codebook_comparison_file_type_returns_only_comparisons(
        self, session_factory
    ) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            session.add(
                File(user_id=user.id, filename="cb", schemaname="proj_cb", file_type="codebook")
            )
            session.add(
                File(
                    user_id=user.id,
                    filename="cmp",
                    schemaname="cmp_x",
                    file_type="codebook_comparison",
                )
            )
            await session.commit()

            rows = await project_service.list_files_for_user(
                session, user.id, "codebook_comparison"
            )
            assert [r["schema_name"] for r in rows] == ["cmp_x"]

    async def test_scoped_to_owner(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            session.add(
                File(user_id=owner.id, filename="a", schemaname="proj_a", file_type="raw_data")
            )
            session.add(
                File(user_id=other.id, filename="b", schemaname="proj_b", file_type="raw_data")
            )
            await session.commit()

            rows = await project_service.list_files_for_user(session, owner.id)
            assert [r["schema_name"] for r in rows] == ["proj_a"]

    async def test_includes_tables_and_parent_files(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            parent = File(
                user_id=user.id, filename="raw", schemaname="proj_raw", file_type="raw_data"
            )
            session.add(parent)
            await session.commit()

            child = File(
                user_id=user.id, filename="filtered", schemaname="proj_filtered", file_type="raw_data"
            )
            session.add(child)
            await session.commit()
            session.add(FileTable(file_id=child.id, tablename="submissions", row_count=3))
            await session.commit()
            await version_repo.add_edge(
                session, child_file_id=child.id, parent_file_id=parent.id, parent_version_id=None,
                relation="derived_from", role="source_data",
            )
            await session.commit()

            rows = await project_service.list_files_for_user(session, user.id)
            by_schema = {r["schema_name"]: r for r in rows}
            assert by_schema["proj_filtered"]["tables"] == [
                {"table_name": "submissions", "row_count": 3}
            ]
            assert by_schema["proj_filtered"]["parent_files"] == [
                {
                    "id": str(parent.id),
                    "name": "raw",
                    "schema_name": "proj_raw",
                    "type": "raw_data",
                }
            ]


class TestCreateProject:
    async def test_create(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            proj = await project_service.create_project(session, user.id, "My Project", "desc")
            assert proj.id is not None
            assert proj.user_id == user.id
            assert proj.projectname == "My Project"
            assert proj.description == "desc"

    async def test_blank_name_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await project_service.create_project(session, user.id, "   ", None)


class TestUpdateProject:
    async def test_update_happy_path(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            proj = await project_service.create_project(session, user.id, "orig", "orig desc")

            updated = await project_service.update_project(
                session, user.id, proj.id, "renamed", "new desc"
            )
            assert updated.projectname == "renamed"
            assert updated.description == "new desc"

    async def test_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await project_service.update_project(session, user.id, 999999, "x", None)

    async def test_wrong_owner_raises_forbidden(self, session_factory) -> None:
        async with session_factory() as session:
            u1 = await _make_user(session, "u1@x.com")
            u2 = await _make_user(session, "u2@x.com")
            proj = await project_service.create_project(session, u1.id, "orig", None)

            with pytest.raises(ForbiddenError):
                await project_service.update_project(session, u2.id, proj.id, "hijacked", None)

    async def test_blank_name_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            proj = await project_service.create_project(session, user.id, "orig", None)
            with pytest.raises(ValidationAppError):
                await project_service.update_project(session, user.id, proj.id, "  ", None)


class TestListProjectsWithFiles:
    async def test_empty_for_new_user(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            rows = await project_service.list_projects_with_files(session, user.id)
            assert rows == []

    async def test_lists_own_projects_with_files(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            proj = await project_service.create_project(session, user.id, "proj", None)

            from backend.app.database import async_link_file_to_project

            parent = File(user_id=user.id, filename="raw", schemaname="proj_raw", file_type="raw_data")
            session.add(parent)
            await session.commit()

            f = File(user_id=user.id, filename="a", schemaname="proj_a", file_type="raw_data")
            session.add(f)
            await session.commit()
            await version_repo.add_edge(
                session, child_file_id=f.id, parent_file_id=parent.id, parent_version_id=None,
                relation="derived_from", role="source_data",
            )
            await async_link_file_to_project(session, f.id, proj.id)
            await session.commit()

            rows = await project_service.list_projects_with_files(session, user.id)
            assert len(rows) == 1
            assert rows[0]["projectname"] == "proj"
            assert [f["schema_name"] for f in rows[0]["files"]] == ["proj_a"]
            # Now carries the SAME {id, name, schema_name, type} shape as
            # list_files_for_user's parent_files -- unified, no longer two
            # different shapes for the same concept.
            assert rows[0]["files"][0]["parent_files"] == [
                {"id": str(parent.id), "name": "raw", "schema_name": "proj_raw", "type": "raw_data"}
            ]

    async def test_scoped_to_owner(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            await project_service.create_project(session, owner.id, "mine", None)
            await project_service.create_project(session, other.id, "not mine", None)

            rows = await project_service.list_projects_with_files(session, owner.id)
            assert [r["projectname"] for r in rows] == ["mine"]


class TestRenameFile:
    async def test_rename_happy_path(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            f = File(user_id=user.id, filename="orig", schemaname="proj_a", file_type="raw_data")
            session.add(f)
            await session.commit()

            renamed = await project_service.rename_file(
                session, user.id, "proj_a", "new name", "new desc"
            )
            assert renamed.filename == "new name"
            assert renamed.description == "new desc"

    async def test_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await project_service.rename_file(session, user.id, "nope", "x", None)

    async def test_other_users_file_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            session.add(
                File(user_id=owner.id, filename="a", schemaname="proj_a", file_type="raw_data")
            )
            await session.commit()

            with pytest.raises(NotFoundError):
                await project_service.rename_file(session, other.id, "proj_a", "hijacked", None)


class TestNPlusOneRegression:
    """The whole point of Stage 2: my_projects/list_projects used to issue
    2 extra queries *per file*. Both service functions must issue a
    constant number of queries regardless of file count.
    """

    async def _populate(self, session_factory, n_files: int, email: str) -> int:
        async with session_factory() as session:
            user = await _make_user(session, email)
            files = [
                File(
                    user_id=user.id,
                    filename=f"f{i}.zst",
                    schemaname=f"{email}_proj_{i}",
                    file_type="raw_data",
                )
                for i in range(n_files)
            ]
            session.add_all(files)
            await session.commit()
            for i, f in enumerate(files):
                session.add(FileTable(file_id=f.id, tablename="submissions", row_count=i))
            await session.commit()
            return user.id

    async def _count_queries(self, async_sqlite_engine, session_factory, fn, user_id: int) -> int:
        counter = {"n": 0}

        def _before_cursor_execute(*args, **kwargs):
            counter["n"] += 1

        sync_engine = async_sqlite_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
        try:
            async with session_factory() as session:
                await fn(session, user_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _before_cursor_execute)
        return counter["n"]

    async def test_list_files_for_user_query_count_constant(
        self, async_sqlite_engine, session_factory
    ) -> None:
        small_user = await self._populate(session_factory, 2, "small@x.com")
        small_count = await self._count_queries(
            async_sqlite_engine, session_factory, project_service.list_files_for_user, small_user
        )

        large_user = await self._populate(session_factory, 25, "large@x.com")
        large_count = await self._count_queries(
            async_sqlite_engine, session_factory, project_service.list_files_for_user, large_user
        )

        assert small_count == large_count, (
            f"query count grew with file count ({small_count} -> {large_count}); "
            "list_files_for_user reintroduced an N+1"
        )

    async def test_list_projects_with_files_query_count_constant(
        self, async_sqlite_engine, session_factory
    ) -> None:
        async def _populate_with_project(n_files: int, email: str) -> int:
            async with session_factory() as session:
                user = await _make_user(session, email)
                proj = await project_service.create_project(session, user.id, "p", None)
                from backend.app.database import async_link_file_to_project

                for i in range(n_files):
                    f = File(
                        user_id=user.id,
                        filename=f"f{i}.zst",
                        schemaname=f"{email}_proj_{i}",
                        file_type="raw_data",
                    )
                    session.add(f)
                    await session.commit()
                    await async_link_file_to_project(session, f.id, proj.id)
                await session.commit()
                return user.id

        small_user = await _populate_with_project(2, "small2@x.com")
        small_count = await self._count_queries(
            async_sqlite_engine,
            session_factory,
            project_service.list_projects_with_files,
            small_user,
        )

        large_user = await _populate_with_project(25, "large2@x.com")
        large_count = await self._count_queries(
            async_sqlite_engine,
            session_factory,
            project_service.list_projects_with_files,
            large_user,
        )

        assert small_count == large_count, (
            f"query count grew with file count ({small_count} -> {large_count}); "
            "list_projects_with_files reintroduced an N+1"
        )
