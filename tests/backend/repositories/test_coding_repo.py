from backend.app.database import File
from backend.app.repositories.coding_repo import (
    bulk_insert_coding_entries,
    code_frequency,
    get_coding_entries,
)

from .conftest import make_user


async def _make_file(session, user, schemaname: str = "coding_a") -> File:
    f = File(user_id=user.id, filename=f"{schemaname}.txt", schemaname=schemaname, file_type="coding")
    session.add(f)
    await session.commit()
    return f


class TestBulkInsertCodingEntries:
    async def test_inserts_entries(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            entries = [
                {"post_id": "p1", "code": "CODE_A", "evidence": "quote 1"},
                {"post_id": "p1", "code": "CODE_B", "evidence": "quote 2"},
                {"post_id": "p2", "code": "CODE_A", "evidence": "quote 3"},
            ]
            n = await bulk_insert_coding_entries(session, f.id, entries)
            await session.commit()
            assert n == 3

    async def test_empty_entries_is_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            n = await bulk_insert_coding_entries(session, f.id, [])
            assert n == 0

    async def test_missing_evidence_defaults_to_none(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [{"post_id": "p1", "code": "CODE_A"}])
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert entries[0].evidence is None


class TestGetCodingEntries:
    async def test_all_entries_for_file(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [
                    {"post_id": "p1", "code": "CODE_A", "evidence": "e1"},
                    {"post_id": "p2", "code": "CODE_B", "evidence": "e2"},
                ],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert {(e.post_id, e.code) for e in entries} == {("p1", "CODE_A"), ("p2", "CODE_B")}

    async def test_filtered_by_code(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [
                    {"post_id": "p1", "code": "CODE_A", "evidence": "e1"},
                    {"post_id": "p2", "code": "CODE_B", "evidence": "e2"},
                    {"post_id": "p3", "code": "CODE_A", "evidence": "e3"},
                ],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id, code="CODE_A")
            assert {e.post_id for e in entries} == {"p1", "p3"}

    async def test_scoped_to_file_id(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f1 = await _make_file(session, user, "coding_a")
            f2 = await _make_file(session, user, "coding_b")
            await bulk_insert_coding_entries(session, f1.id, [{"post_id": "p1", "code": "CODE_A", "evidence": "e1"}])
            await bulk_insert_coding_entries(session, f2.id, [{"post_id": "p1", "code": "CODE_X", "evidence": "e2"}])
            await session.commit()

            entries = await get_coding_entries(session, f1.id)
            assert len(entries) == 1
            assert entries[0].code == "CODE_A"


class TestCodeFrequency:
    async def test_counts_grouped_and_ordered_desc(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [
                    {"post_id": "p1", "code": "CODE_A", "evidence": "e1"},
                    {"post_id": "p2", "code": "CODE_A", "evidence": "e2"},
                    {"post_id": "p3", "code": "CODE_A", "evidence": "e3"},
                    {"post_id": "p1", "code": "CODE_B", "evidence": "e4"},
                ],
            )
            await session.commit()

            freq = await code_frequency(session, f.id)
            assert freq[0] == ("CODE_A", 3)
            assert freq[1] == ("CODE_B", 1)

    async def test_empty_returns_empty_list(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            freq = await code_frequency(session, f.id)
            assert freq == []
