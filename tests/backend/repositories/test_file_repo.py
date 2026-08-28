from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker
import pytest

from backend.app.core.exceptions import NotFoundError
from backend.app.database import File, FileTable, User
from backend.app.repositories.file_repo import (
    filter_owned_ids,
    get_owned_file,
    list_files_with_tables,
    resolve_file_id,
)

from .conftest import make_user


class TestResolveFileId:
    async def test_resolve_by_schemaname(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = File(user_id=user.id, filename="f.zst", schemaname="proj_abc", file_type="raw_data")
            session.add(f)
            await session.commit()

            file_id = await resolve_file_id(session, "proj_abc", user.id)
            assert file_id == f.id

    async def test_resolve_by_filename(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = File(user_id=user.id, filename="data.zst", schemaname="proj_xyz", file_type="raw_data")
            session.add(f)
            await session.commit()

            file_id = await resolve_file_id(session, "data.zst", user.id)
            assert file_id == f.id

    async def test_resolve_by_numeric_id(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = File(user_id=user.id, filename="data.zst", schemaname="proj_xyz", file_type="raw_data")
            session.add(f)
            await session.commit()

            file_id = await resolve_file_id(session, str(f.id), user.id)
            assert file_id == f.id

    async def test_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            with pytest.raises(NotFoundError):
                await resolve_file_id(session, "nope", user.id)

    async def test_non_numeric_ref_with_no_match_raises_not_found(self, session_factory) -> None:
        # A ref that doesn't match schemaname/filename and doesn't parse as
        # an int must still raise NotFoundError, not ValueError.
        async with session_factory() as session:
            user = await make_user(session)
            with pytest.raises(NotFoundError):
                await resolve_file_id(session, "totally-not-a-ref", user.id)

    async def test_scoped_to_owner(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await make_user(session, "owner@x.com")
            other = await make_user(session, "other@x.com")

            f = File(user_id=owner.id, filename="data.zst", schemaname="proj_owned", file_type="raw_data")
            session.add(f)
            await session.commit()

            with pytest.raises(NotFoundError):
                await resolve_file_id(session, "proj_owned", other.id)

            # But the owner can still resolve it.
            file_id = await resolve_file_id(session, "proj_owned", owner.id)
            assert file_id == f.id

    async def test_file_types_filter(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = File(user_id=user.id, filename="data.zst", schemaname="proj_a", file_type="raw_data")
            session.add(f)
            await session.commit()

            with pytest.raises(NotFoundError):
                await resolve_file_id(session, "proj_a", user.id, file_types=("codebook",))

            file_id = await resolve_file_id(session, "proj_a", user.id, file_types=("raw_data", "codebook"))
            assert file_id == f.id


class TestGetOwnedFile:
    async def test_returns_full_row(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = File(user_id=user.id, filename="data.zst", schemaname="proj_a", file_type="raw_data")
            session.add(f)
            await session.commit()

            found = await get_owned_file(session, "proj_a", user.id)
            assert found.id == f.id
            assert found.filename == "data.zst"

    async def test_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            with pytest.raises(NotFoundError):
                await get_owned_file(session, "nope", user.id)

    async def test_other_users_file_is_not_found(self, session_factory) -> None:
        # Deliberate: ownership is baked into the query, so "belongs to
        # someone else" and "doesn't exist" both surface as NotFoundError,
        # not ForbiddenError -- see the docstring in file_repo.py.
        async with session_factory() as session:
            owner = await make_user(session, "owner@x.com")
            other = await make_user(session, "other@x.com")

            f = File(user_id=owner.id, filename="data.zst", schemaname="proj_owned", file_type="raw_data")
            session.add(f)
            await session.commit()

            with pytest.raises(NotFoundError):
                await get_owned_file(session, "proj_owned", other.id)


class TestListFilesWithTables:
    async def test_returns_only_user_files(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await make_user(session, "owner@x.com")
            other = await make_user(session, "other@x.com")

            f1 = File(user_id=owner.id, filename="a.zst", schemaname="proj_a", file_type="raw_data")
            f2 = File(user_id=other.id, filename="b.zst", schemaname="proj_b", file_type="raw_data")
            session.add_all([f1, f2])
            await session.commit()

            files = await list_files_with_tables(session, owner.id)
            assert [f.id for f in files] == [f1.id]

    async def test_relationships_are_populated(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = File(user_id=user.id, filename="a.zst", schemaname="proj_a", file_type="raw_data")
            session.add(f)
            await session.commit()
            session.add(FileTable(file_id=f.id, tablename="submissions", row_count=5))
            await session.commit()

            files = await list_files_with_tables(session, user.id)
            assert len(files) == 1
            assert files[0].tables[0].tablename == "submissions"
            assert files[0].tables[0].row_count == 5

    async def test_query_count_constant_regardless_of_file_count(self, async_sqlite_engine) -> None:
        """N+1 regression test: a small and a large file set must issue the
        same number of SQL statements to load files + tables.
        """
        SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)

        async def _populate(n_files: int, email: str) -> int:
            async with SessionLocal() as session:
                user = await make_user(session, email)
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

        async def _count_queries(user_id: int) -> int:
            counter = {"n": 0}

            def _before_cursor_execute(*args, **kwargs):
                counter["n"] += 1

            sync_engine = async_sqlite_engine.sync_engine
            event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
            try:
                async with SessionLocal() as session:
                    files = await list_files_with_tables(session, user_id)
                    for f in files:
                        list(f.tables)
            finally:
                event.remove(sync_engine, "before_cursor_execute", _before_cursor_execute)
            return counter["n"]

        small_user_id = await _populate(2, "small@x.com")
        small_count = await _count_queries(small_user_id)

        large_user_id = await _populate(25, "large@x.com")
        large_count = await _count_queries(large_user_id)

        assert small_count == large_count
        # Sanity: it really did do more than one query per relationship
        # (files, tables), not zero.
        assert small_count >= 2


class TestFilterOwnedIds:
    async def test_returns_only_owned_ids(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await make_user(session, "owner@x.com")
            other = await make_user(session, "other@x.com")

            f1 = File(user_id=owner.id, filename="a.zst", schemaname="proj_a", file_type="raw_data")
            f2 = File(user_id=other.id, filename="b.zst", schemaname="proj_b", file_type="raw_data")
            session.add_all([f1, f2])
            await session.commit()

            owned = await filter_owned_ids(session, {f1.id, f2.id, 999999}, owner.id)
            assert owned == {f1.id}

    async def test_empty_input_returns_empty_set(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            assert await filter_owned_ids(session, set(), user.id) == set()
