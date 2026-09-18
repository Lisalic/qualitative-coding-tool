"""Tests for ``repositories/memo_repo.py``.

Pins the two decisions that are easy to regress: a blank body *deletes*
the memo rather than storing an empty one (which is what lets "has a
memo" stay a row-exists test everywhere downstream), and memos copy
forward with exactly the rows they were asked about -- never more.
"""

from sqlalchemy import select

from backend.app.database import File
from backend.app.repositories.memo_repo import (
    copy_all_memos,
    copy_memos_by_id,
    delete_memos_for_file,
    get_memo,
    list_memos,
    upsert_memo,
)
from backend.app.storage_models import RowMemo

from .conftest import make_user


async def _make_file(session, user, schemaname: str, file_type: str = "raw_data") -> File:
    f = File(user_id=user.id, filename=f"{schemaname}.zst", schemaname=schemaname, file_type=file_type)
    session.add(f)
    await session.commit()
    return f


async def _memo(session, file_id: int, row_type: str, row_id: str, body: str, user_id: int) -> None:
    await upsert_memo(
        session, file_id=file_id, row_type=row_type, row_id=row_id, body=body, author_user_id=user_id
    )
    await session.commit()


class TestUpsertMemo:
    async def test_creates_then_updates_in_place(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")

            await _memo(session, f.id, "submission", "s1", "first thought", user.id)
            await _memo(session, f.id, "submission", "s1", "second thought", user.id)

            rows = (await session.execute(select(RowMemo).where(RowMemo.file_id == f.id))).scalars().all()
            assert len(rows) == 1, "one memo per row, not an append-only thread"
            assert rows[0].body == "second thought"
            assert rows[0].author_user_id == user.id

    async def test_blank_body_deletes_rather_than_storing_empty(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")

            await _memo(session, f.id, "submission", "s1", "something", user.id)
            result = await upsert_memo(
                session, file_id=f.id, row_type="submission", row_id="s1", body="   ", author_user_id=user.id
            )
            await session.commit()

            assert result is None
            assert await get_memo(session, file_id=f.id, row_type="submission", row_id="s1") is None

    async def test_blank_body_on_a_row_with_no_memo_is_a_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")

            assert await upsert_memo(
                session, file_id=f.id, row_type="submission", row_id="s1", body="", author_user_id=user.id
            ) is None
            assert await list_memos(session, f.id) == []

    async def test_body_is_stripped(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")

            await _memo(session, f.id, "submission", "s1", "  padded  ", user.id)
            memo = await get_memo(session, file_id=f.id, row_type="submission", row_id="s1")
            assert memo.body == "padded"

    async def test_row_type_is_part_of_the_identity(self, session_factory) -> None:
        """A post and a comment can share a bare id once their Reddit
        fullname prefixes are stripped at import -- their memos must not
        merge. Same reasoning as ``coding_entries.row_type``.
        """
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")

            await _memo(session, f.id, "submission", "shared", "about the post", user.id)
            await _memo(session, f.id, "comment", "shared", "about the comment", user.id)

            post = await get_memo(session, file_id=f.id, row_type="submission", row_id="shared")
            comment = await get_memo(session, file_id=f.id, row_type="comment", row_id="shared")
            assert post.body == "about the post"
            assert comment.body == "about the comment"

    async def test_memos_are_scoped_per_file(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            a = await _make_file(session, user, "proj_a")
            b = await _make_file(session, user, "proj_b")

            await _memo(session, a.id, "submission", "s1", "in a", user.id)
            await _memo(session, b.id, "submission", "s1", "in b", user.id)

            assert (await get_memo(session, file_id=a.id, row_type="submission", row_id="s1")).body == "in a"
            assert (await get_memo(session, file_id=b.id, row_type="submission", row_id="s1")).body == "in b"


class TestListMemos:
    async def test_returns_only_this_files_memos(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            a = await _make_file(session, user, "proj_a")
            b = await _make_file(session, user, "proj_b")

            await _memo(session, a.id, "submission", "s1", "one", user.id)
            await _memo(session, a.id, "comment", "c1", "two", user.id)
            await _memo(session, b.id, "submission", "s9", "elsewhere", user.id)

            memos = await list_memos(session, a.id)
            assert [(m.row_type, m.row_id) for m in memos] == [("comment", "c1"), ("submission", "s1")]

    async def test_empty_file_returns_empty_list(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user, "proj_a")
            assert await list_memos(session, f.id) == []


class TestCopyMemosById:
    async def test_copies_only_the_named_rows(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            src = await _make_file(session, user, "proj_src")
            tgt = await _make_file(session, user, "proj_tgt", file_type="filtered_data")

            for row_id in ("s1", "s2", "s3"):
                await _memo(session, src.id, "submission", row_id, f"note {row_id}", user.id)
            await _memo(session, src.id, "comment", "c1", "note c1", user.id)
            await _memo(session, src.id, "comment", "c2", "note c2", user.id)

            copied = await copy_memos_by_id(
                session,
                source_file_id=src.id,
                target_file_id=tgt.id,
                submission_ids=["s1", "s3"],
                comment_ids=["c2"],
            )
            await session.commit()

            assert copied == 3
            assert [(m.row_type, m.row_id, m.body) for m in await list_memos(session, tgt.id)] == [
                ("comment", "c2", "note c2"),
                ("submission", "s1", "note s1"),
                ("submission", "s3", "note s3"),
            ]

    async def test_leaves_the_source_untouched(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            src = await _make_file(session, user, "proj_src")
            tgt = await _make_file(session, user, "proj_tgt", file_type="filtered_data")

            await _memo(session, src.id, "submission", "s1", "note", user.id)
            await copy_memos_by_id(
                session, source_file_id=src.id, target_file_id=tgt.id, submission_ids=["s1"]
            )
            await session.commit()

            assert len(await list_memos(session, src.id)) == 1

    async def test_ids_with_no_memo_copy_nothing(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            src = await _make_file(session, user, "proj_src")
            tgt = await _make_file(session, user, "proj_tgt", file_type="filtered_data")

            await _memo(session, src.id, "submission", "s1", "note", user.id)
            copied = await copy_memos_by_id(
                session, source_file_id=src.id, target_file_id=tgt.id, submission_ids=["s2", "s3"]
            )
            await session.commit()

            assert copied == 0
            assert await list_memos(session, tgt.id) == []

    async def test_empty_id_lists_are_a_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            src = await _make_file(session, user, "proj_src")
            tgt = await _make_file(session, user, "proj_tgt", file_type="filtered_data")

            await _memo(session, src.id, "submission", "s1", "note", user.id)
            assert await copy_memos_by_id(session, source_file_id=src.id, target_file_id=tgt.id) == 0


class TestCopyAllMemos:
    async def test_copies_every_memo(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            src = await _make_file(session, user, "proj_src")
            tgt = await _make_file(session, user, "proj_tgt", file_type="filtered_data")

            await _memo(session, src.id, "submission", "s1", "one", user.id)
            await _memo(session, src.id, "comment", "c1", "two", user.id)

            copied = await copy_all_memos(session, source_file_id=src.id, target_file_id=tgt.id)
            await session.commit()

            assert copied == 2
            assert len(await list_memos(session, tgt.id)) == 2

    async def test_source_with_no_memos_is_a_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            src = await _make_file(session, user, "proj_src")
            tgt = await _make_file(session, user, "proj_tgt", file_type="filtered_data")
            assert await copy_all_memos(session, source_file_id=src.id, target_file_id=tgt.id) == 0


class TestDeleteMemosForFile:
    async def test_removes_only_that_files_memos(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            a = await _make_file(session, user, "proj_a")
            b = await _make_file(session, user, "proj_b")

            await _memo(session, a.id, "submission", "s1", "in a", user.id)
            await _memo(session, b.id, "submission", "s1", "in b", user.id)

            await delete_memos_for_file(session, a.id)
            await session.commit()

            assert await list_memos(session, a.id) == []
            assert len(await list_memos(session, b.id)) == 1
