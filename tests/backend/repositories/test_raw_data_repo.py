from sqlalchemy import select

from backend.app.database import File
from backend.app.repositories.raw_data_repo import (
    bulk_insert_comments,
    bulk_insert_submissions,
    copy_rows_by_id,
    sample_comments,
    sample_submissions,
)
from backend.app.storage_models import Comment, Submission

from .conftest import make_user


async def _make_file(session, user, schemaname: str, file_type: str = "raw_data") -> File:
    f = File(user_id=user.id, filename=f"{schemaname}.zst", schemaname=schemaname, file_type=file_type)
    session.add(f)
    await session.commit()
    return f


class TestBulkInsertSubmissions:
    async def test_inserts_rows_and_computes_word_count(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")

            rows = [
                {"id": "s1", "subreddit": "r1", "title": "Hello world", "selftext": "this is a test", "author": "u1", "created_utc": 100, "score": 1, "num_comments": 0},
                {"id": "s2", "subreddit": "r1", "title": "", "selftext": "", "author": "u2", "created_utc": 200, "score": 2, "num_comments": 1},
            ]
            n = await bulk_insert_submissions(session, f.id, rows)
            await session.commit()
            assert n == 2

            result = await session.execute(select(Submission).where(Submission.file_id == f.id).order_by(Submission.id))
            saved = result.scalars().all()
            assert len(saved) == 2
            # "Hello world" + "this is a test" -> 6 tokens
            assert saved[0].word_count == 6
            assert saved[1].word_count == 0

    async def test_empty_rows_is_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")
            n = await bulk_insert_submissions(session, f.id, [])
            assert n == 0


class TestBulkInsertComments:
    async def test_inserts_rows_and_computes_word_count(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")

            rows = [
                {"id": "c1", "subreddit": "r1", "body": "one two three", "author": "u1", "created_utc": 100, "score": 1, "link_id": "l1", "parent_id": "p1"},
                {"id": "c2", "subreddit": "r1", "body": "   ", "author": "u2", "created_utc": 200, "score": 2, "link_id": "l1", "parent_id": "p1"},
            ]
            n = await bulk_insert_comments(session, f.id, rows)
            await session.commit()
            assert n == 2

            result = await session.execute(select(Comment).where(Comment.file_id == f.id).order_by(Comment.id))
            saved = result.scalars().all()
            assert saved[0].word_count == 3
            assert saved[1].word_count == 0

    async def test_empty_rows_is_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")
            n = await bulk_insert_comments(session, f.id, [])
            assert n == 0


class TestSampleSubmissions:
    async def test_samples_ceil_percentage(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")
            rows = [
                {"id": f"s{i}", "subreddit": "r", "title": "t", "selftext": "x", "author": "a", "created_utc": i, "score": 0, "num_comments": 0}
                for i in range(10)
            ]
            await bulk_insert_submissions(session, f.id, rows)
            await session.commit()

            # ceil(10 * 25 / 100) == 3
            sampled = await sample_submissions(session, f.id, 25)
            assert len(sampled) == 3

    async def test_zero_percentage_returns_empty(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")
            rows = [{"id": "s1", "subreddit": "r", "title": "t", "selftext": "x", "author": "a", "created_utc": 1, "score": 0, "num_comments": 0}]
            await bulk_insert_submissions(session, f.id, rows)
            await session.commit()

            sampled = await sample_submissions(session, f.id, 0)
            assert sampled == []

    async def test_no_rows_returns_empty(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")
            sampled = await sample_submissions(session, f.id, 100)
            assert sampled == []


class TestSampleComments:
    async def test_samples_ceil_percentage(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")
            rows = [
                {"id": f"c{i}", "subreddit": "r", "body": "x", "author": "a", "created_utc": i, "score": 0, "link_id": "l", "parent_id": "p"}
                for i in range(10)
            ]
            await bulk_insert_comments(session, f.id, rows)
            await session.commit()

            sampled = await sample_comments(session, f.id, 25)
            assert len(sampled) == 3


class TestCopyRowsById:
    async def test_copies_selected_submissions_and_comments(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "proj_source")
            target = await _make_file(session, user, "proj_target", file_type="filtered_data")

            sub_rows = [
                {"id": f"s{i}", "subreddit": "r", "title": f"t{i}", "selftext": "x", "author": "a", "created_utc": i, "score": 0, "num_comments": 0}
                for i in range(5)
            ]
            comm_rows = [
                {"id": f"c{i}", "subreddit": "r", "body": f"b{i}", "author": "a", "created_utc": i, "score": 0, "link_id": "l", "parent_id": "p"}
                for i in range(5)
            ]
            await bulk_insert_submissions(session, source.id, sub_rows)
            await bulk_insert_comments(session, source.id, comm_rows)
            await session.commit()

            counts = await copy_rows_by_id(
                session,
                source_file_id=source.id,
                target_file_id=target.id,
                submission_ids=["s0", "s2", "s4"],
                comment_ids=["c1", "c3"],
            )
            await session.commit()

            assert counts == {"submissions": 3, "comments": 2}

            result = await session.execute(select(Submission).where(Submission.file_id == target.id).order_by(Submission.id))
            copied_subs = result.scalars().all()
            assert [s.id for s in copied_subs] == ["s0", "s2", "s4"]
            assert [s.title for s in copied_subs] == ["t0", "t2", "t4"]

            result = await session.execute(select(Comment).where(Comment.file_id == target.id).order_by(Comment.id))
            copied_comments = result.scalars().all()
            assert [c.id for c in copied_comments] == ["c1", "c3"]

            # Source rows are untouched.
            result = await session.execute(select(Submission).where(Submission.file_id == source.id))
            assert len(result.scalars().all()) == 5

    async def test_skips_branch_when_id_list_is_none(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "proj_source")
            target = await _make_file(session, user, "proj_target", file_type="filtered_data")

            await bulk_insert_submissions(
                session,
                source.id,
                [{"id": "s1", "subreddit": "r", "title": "t", "selftext": "x", "author": "a", "created_utc": 1, "score": 0, "num_comments": 0}],
            )
            await session.commit()

            counts = await copy_rows_by_id(
                session,
                source_file_id=source.id,
                target_file_id=target.id,
                submission_ids=None,
                comment_ids=None,
            )
            assert counts == {"submissions": 0, "comments": 0}

            result = await session.execute(select(Submission).where(Submission.file_id == target.id))
            assert result.scalars().all() == []

    async def test_empty_id_list_is_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "proj_source")
            target = await _make_file(session, user, "proj_target", file_type="filtered_data")

            counts = await copy_rows_by_id(
                session,
                source_file_id=source.id,
                target_file_id=target.id,
                submission_ids=[],
                comment_ids=[],
            )
            assert counts == {"submissions": 0, "comments": 0}
