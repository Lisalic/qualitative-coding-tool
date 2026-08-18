"""Unit tests for backend/app/services/file_service.py.

`delete_database`/`delete_row`/`move_rows` run straight against an
in-memory async SQLite session (`async_sqlite_engine` from
`tests/conftest.py`) -- pure ORM operations on the fixed tables, no
Postgres-only SQL involved.

`upload_zst`/`merge_databases` involve either real `.zst` streaming or
raw SQL reads from old dynamic Postgres schemas (`to_regclass`, quoted
dynamic schema names) that SQLite can't run -- those are mocked at the
`stream_zst_to_postgres` / `_fetch_dynamic_rows` / `_drop_dynamic_schema`
boundary here for fast, deterministic unit coverage. Real end-to-end
coverage of the dynamic-schema read/drop path is intentionally left to
the opt-in integration suite (`tests/backend/integration/`), since it
needs a real Postgres to create the throwaway dynamic schemas in the
first place.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import File, FileDependency, FileTable, User
from backend.app.services import file_service
from backend.app.storage_models import ArtifactContent, Comment, CodingEntry, Submission


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session, email: str = "a@b.com") -> User:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    return user


async def _make_file(session, user_id, schemaname, filename="f", file_type="raw_data") -> File:
    f = File(user_id=user_id, filename=filename, schemaname=schemaname, file_type=file_type)
    session.add(f)
    await session.commit()
    return f


def _submission(file_id, row_id, **overrides):
    defaults = dict(
        file_id=file_id, id=row_id, subreddit="s", title="t", selftext="body",
        author="a", created_utc=1, score=1, num_comments=0, word_count=1,
    )
    defaults.update(overrides)
    return Submission(**defaults)


def _comment(file_id, row_id, **overrides):
    defaults = dict(
        file_id=file_id, id=row_id, subreddit="s", body="body", author="a",
        created_utc=1, score=1, link_id="l", parent_id="p", word_count=1,
    )
    defaults.update(overrides)
    return Comment(**defaults)


# ---------------------------------------------------------------------------
# delete_database
# ---------------------------------------------------------------------------


class TestDeleteDatabase:
    async def test_deletes_file_and_all_fixed_table_rows(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            f = await _make_file(session, user.id, "proj_a")
            other = await _make_file(session, user.id, "proj_other")

            session.add(_submission(f.id, "s1"))
            session.add(_comment(f.id, "c1"))
            session.add(ArtifactContent(file_id=f.id, content="x"))
            session.add(CodingEntry(file_id=f.id, post_id="p1", code="code1", evidence="e"))
            session.add(FileTable(file_id=f.id, tablename="submissions", row_count=1))
            session.add(FileDependency(child_file_id=f.id, parent_file_id=other.id))
            await session.commit()

            filename = await file_service.delete_database(session, user.id, "proj_a")
            assert filename == "f"

            assert (await session.execute(select(File).where(File.id == f.id))).scalar_one_or_none() is None
            assert (await session.execute(select(Submission).where(Submission.file_id == f.id))).scalars().all() == []
            assert (await session.execute(select(Comment).where(Comment.file_id == f.id))).scalars().all() == []
            assert (
                await session.execute(select(ArtifactContent).where(ArtifactContent.file_id == f.id))
            ).scalars().all() == []
            assert (await session.execute(select(CodingEntry).where(CodingEntry.file_id == f.id))).scalars().all() == []
            assert (await session.execute(select(FileTable).where(FileTable.file_id == f.id))).scalars().all() == []
            assert (
                await session.execute(select(FileDependency).where(FileDependency.child_file_id == f.id))
            ).scalars().all() == []
            # The unrelated file this one depended on must survive.
            assert (await session.execute(select(File).where(File.id == other.id))).scalar_one_or_none() is not None

    async def test_missing_file_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await file_service.delete_database(session, user.id, "proj_missing")

    async def test_someone_elses_file_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            await _make_file(session, owner.id, "proj_a")

            with pytest.raises(NotFoundError):
                await file_service.delete_database(session, other.id, "proj_a")


# ---------------------------------------------------------------------------
# delete_row
# ---------------------------------------------------------------------------


class TestDeleteRow:
    async def test_deletes_matching_row_and_updates_row_count(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            f = await _make_file(session, user.id, "proj_a")
            session.add_all([_submission(f.id, "s1"), _submission(f.id, "s2")])
            await session.commit()

            deleted = await file_service.delete_row(
                session, user.id, schemaname="proj_a", table="submissions", row_id="s1"
            )
            assert deleted == 1

            remaining = (
                await session.execute(select(Submission).where(Submission.file_id == f.id))
            ).scalars().all()
            assert [r.id for r in remaining] == ["s2"]

            ft = (
                await session.execute(
                    select(FileTable).where(FileTable.file_id == f.id, FileTable.tablename == "submissions")
                )
            ).scalar_one()
            assert ft.row_count == 1

    async def test_deletes_zero_for_missing_row(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, "proj_a")

            deleted = await file_service.delete_row(
                session, user.id, schemaname="proj_a", table="submissions", row_id="nonexistent"
            )
            assert deleted == 0

    async def test_not_owned_raises_forbidden(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ForbiddenError):
                await file_service.delete_row(
                    session, user.id, schemaname="proj_missing", table="submissions", row_id="s1"
                )

    async def test_db_suffix_stripped(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            f = await _make_file(session, user.id, "proj_a")
            session.add(_submission(f.id, "s1"))
            await session.commit()

            deleted = await file_service.delete_row(
                session, user.id, schemaname="proj_a.db", table="submissions", row_id="s1"
            )
            assert deleted == 1


# ---------------------------------------------------------------------------
# move_rows
# ---------------------------------------------------------------------------


class TestMoveRows:
    async def test_moves_rows_between_owned_files(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            src = await _make_file(session, user.id, "proj_src")
            tgt = await _make_file(session, user.id, "proj_tgt")
            session.add_all([
                _submission(src.id, "keep", selftext="stays"),
                _submission(src.id, "move", selftext="moves"),
            ])
            await session.commit()

            moved = await file_service.move_rows(
                session, user.id,
                source_schema="proj_src", target_schema="proj_tgt",
                table="submissions", row_ids=["move"],
            )
            assert moved == 1

            src_rows = (await session.execute(select(Submission).where(Submission.file_id == src.id))).scalars().all()
            assert [r.id for r in src_rows] == ["keep"]

            tgt_rows = (await session.execute(select(Submission).where(Submission.file_id == tgt.id))).scalars().all()
            assert len(tgt_rows) == 1
            assert tgt_rows[0].id == "move"
            assert tgt_rows[0].selftext == "moves"

            src_ft = (
                await session.execute(
                    select(FileTable).where(FileTable.file_id == src.id, FileTable.tablename == "submissions")
                )
            ).scalar_one()
            tgt_ft = (
                await session.execute(
                    select(FileTable).where(FileTable.file_id == tgt.id, FileTable.tablename == "submissions")
                )
            ).scalar_one()
            assert src_ft.row_count == 1
            assert tgt_ft.row_count == 1

    async def test_moves_comments(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            src = await _make_file(session, user.id, "proj_src")
            tgt = await _make_file(session, user.id, "proj_tgt")
            session.add(_comment(src.id, "c1", body="hello"))
            await session.commit()

            moved = await file_service.move_rows(
                session, user.id,
                source_schema="proj_src", target_schema="proj_tgt",
                table="comments", row_ids=["c1"],
            )
            assert moved == 1
            tgt_rows = (await session.execute(select(Comment).where(Comment.file_id == tgt.id))).scalars().all()
            assert tgt_rows[0].body == "hello"

    async def test_no_matching_rows_returns_zero(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, "proj_src")
            await _make_file(session, user.id, "proj_tgt")

            moved = await file_service.move_rows(
                session, user.id,
                source_schema="proj_src", target_schema="proj_tgt",
                table="submissions", row_ids=["nonexistent"],
            )
            assert moved == 0

    async def test_source_not_owned_raises_forbidden(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, "proj_tgt")
            with pytest.raises(ForbiddenError):
                await file_service.move_rows(
                    session, user.id,
                    source_schema="proj_missing", target_schema="proj_tgt",
                    table="submissions", row_ids=["1"],
                )

    async def test_target_not_owned_raises_forbidden(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, "proj_src")
            with pytest.raises(ForbiddenError):
                await file_service.move_rows(
                    session, user.id,
                    source_schema="proj_src", target_schema="proj_missing",
                    table="submissions", row_ids=["1"],
                )


# ---------------------------------------------------------------------------
# upload_zst -- mocked at the streaming / dynamic-schema-read boundary
# ---------------------------------------------------------------------------


class TestUploadZst:
    async def test_happy_path_copies_streamed_rows_into_fixed_tables(
        self, session_factory, monkeypatch
    ) -> None:
        def _fake_stream(tmp_path, schema_name, data_type, subreddit_filter, batch_size):
            assert schema_name.startswith("proj_")
            assert data_type == "submissions"
            return {"submissions": 2, "comments": 0}

        async def _fake_fetch(session, schemaname, table, columns):
            assert table == "submissions"
            return [
                {"id": "a", "subreddit": "s", "title": "t1", "selftext": "x", "author": "u",
                 "created_utc": 1, "score": 1, "num_comments": 0},
                {"id": "b", "subreddit": "s", "title": "t2", "selftext": "y", "author": "u",
                 "created_utc": 2, "score": 2, "num_comments": 0},
            ]

        dropped = []

        async def _fake_drop(session, schemaname):
            dropped.append(schemaname)

        monkeypatch.setattr(file_service, "stream_zst_to_postgres", _fake_stream)
        monkeypatch.setattr(file_service, "_fetch_dynamic_rows", _fake_fetch)
        monkeypatch.setattr(file_service, "_drop_dynamic_schema", _fake_drop)

        async with session_factory() as session:
            user = await _make_user(session)

            file_rec, result = await file_service.upload_zst(
                session, user.id,
                file_content=b"irrelevant-bytes",
                filename="dump.zst",
                data_type="submissions",
                subreddits=None,
                name="My Upload",
                description="desc",
                project_id=None,
            )

            assert file_rec.filename == "My Upload"
            assert file_rec.file_type == "raw_data"
            assert result["inserted_counts"] == {"submissions": 2, "comments": 0}
            assert result["schema_name"] == file_rec.schemaname
            assert dropped == [file_rec.schemaname]

            rows = (await session.execute(select(Submission).where(Submission.file_id == file_rec.id))).scalars().all()
            assert sorted(r.id for r in rows) == ["a", "b"]

            ft = (
                await session.execute(
                    select(FileTable).where(FileTable.file_id == file_rec.id, FileTable.tablename == "submissions")
                )
            ).scalar_one()
            assert ft.row_count == 2

    async def test_default_name_strips_zst_suffix(self, session_factory, monkeypatch) -> None:
        async def _fake_fetch(*args, **kwargs):
            return []

        async def _fake_drop(*args, **kwargs):
            return None

        monkeypatch.setattr(
            file_service, "stream_zst_to_postgres",
            lambda *a, **k: {"submissions": 0, "comments": 0},
        )
        monkeypatch.setattr(file_service, "_fetch_dynamic_rows", _fake_fetch)
        monkeypatch.setattr(file_service, "_drop_dynamic_schema", _fake_drop)

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec, _result = await file_service.upload_zst(
                session, user.id,
                file_content=b"x",
                filename="reddit-dump.zst",
                data_type="submissions",
                subreddits=None,
                name=None,
                description=None,
                project_id=None,
            )
            assert file_rec.filename == "reddit-dump"

    async def test_project_not_found_raises(self, session_factory, monkeypatch) -> None:
        monkeypatch.setattr(
            file_service, "stream_zst_to_postgres",
            lambda *a, **k: {"submissions": 0, "comments": 0},
        )

        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await file_service.upload_zst(
                    session, user.id,
                    file_content=b"x",
                    filename="x.zst",
                    data_type="submissions",
                    subreddits=None,
                    name="n",
                    description=None,
                    project_id=999999,
                )


# ---------------------------------------------------------------------------
# merge_databases -- mocked at the dynamic-schema-read boundary
# ---------------------------------------------------------------------------


class TestMergeDatabases:
    def _patch_sources(self, monkeypatch, sources: dict[str, dict[str, list[dict]]]):
        async def _fake_read(session, schema_src):
            return sources.get(schema_src, {"submissions": [], "comments": []})

        monkeypatch.setattr(file_service, "_read_source_tables", _fake_read)

    async def test_merges_two_sources_with_id_dedup(self, session_factory, monkeypatch) -> None:
        self._patch_sources(monkeypatch, {
            "proj_a": {
                "submissions": [
                    {"id": "1", "subreddit": "s", "title": "t1", "selftext": "x", "author": "u",
                     "created_utc": 1, "score": 1, "num_comments": 0},
                ],
                "comments": [],
            },
            "proj_b": {
                "submissions": [
                    # Duplicate id "1" (must be dropped -- already copied from proj_a) ...
                    {"id": "1", "subreddit": "s", "title": "dup", "selftext": "x", "author": "u",
                     "created_utc": 1, "score": 1, "num_comments": 0},
                    # ... plus a genuinely new row.
                    {"id": "2", "subreddit": "s", "title": "t2", "selftext": "y", "author": "u",
                     "created_utc": 2, "score": 2, "num_comments": 0},
                ],
                "comments": [],
            },
        })

        async with session_factory() as session:
            user = await _make_user(session)
            parent_a = await _make_file(session, user.id, "proj_a", filename="A")
            parent_b = await _make_file(session, user.id, "proj_b", filename="B")

            file_rec, result = await file_service.merge_databases(
                session, user.id,
                source_schemas=["proj_a", "proj_b"],
                name="Merged",
                description=None,
                project_id=None,
            )

            assert result["file_migrated"] is True
            assert file_rec.filename == "Merged"

            rows = (await session.execute(select(Submission).where(Submission.file_id == file_rec.id))).scalars().all()
            assert sorted(r.id for r in rows) == ["1", "2"]
            # The surviving "1" row keeps proj_a's content (first writer wins).
            assert next(r for r in rows if r.id == "1").title == "t1"

            deps = (
                await session.execute(select(FileDependency).where(FileDependency.child_file_id == file_rec.id))
            ).scalars().all()
            # Both sources have an owned File row, so both are linked as parents.
            assert {d.parent_file_id for d in deps} == {parent_a.id, parent_b.id}

    async def test_no_rows_returns_not_migrated_without_creating_file(
        self, session_factory, monkeypatch
    ) -> None:
        self._patch_sources(monkeypatch, {})

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec, result = await file_service.merge_databases(
                session, user.id,
                source_schemas=["proj_empty"],
                name="Merged",
                description=None,
                project_id=None,
            )
            assert file_rec is None
            assert result["file_migrated"] is False
            assert result["total_submissions"] == 0

            count = (await session.execute(select(File).where(File.filename == "Merged")))
            assert count.scalar_one_or_none() is None

    async def test_blank_name_raises_validation_error(self, session_factory) -> None:
        from backend.app.core.exceptions import ValidationAppError

        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await file_service.merge_databases(
                    session, user.id,
                    source_schemas=[],
                    name="   ",
                    description=None,
                    project_id=None,
                )

    async def test_duplicate_name_raises_validation_error(self, session_factory) -> None:
        from backend.app.core.exceptions import ValidationAppError

        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, "proj_existing", filename="Taken")

            with pytest.raises(ValidationAppError):
                await file_service.merge_databases(
                    session, user.id,
                    source_schemas=[],
                    name="Taken",
                    description=None,
                    project_id=None,
                )
