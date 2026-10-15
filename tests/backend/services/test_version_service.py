"""Tests for backend/app/services/version_service.py's codebook-snapshot
compaction scheme: which versions stay materialized (v1 / latest-3 /
every-Kth keyframe), how a compacted version's codes are reconstructed
via core/codebook_delta.py, and that reconstruction is byte-exact
regardless of how many compacted versions sit in between. See
ArtifactVersion.codes_materialized's docstring for the full policy.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import File, User
from backend.app.repositories import version_repo
from backend.app.services import version_service
from backend.app.services.version_service import KEYFRAME_INTERVAL, LATEST_MATERIALIZED_WINDOW


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture()
async def session(SessionLocal):
    async with SessionLocal() as s:
        yield s


@pytest.fixture()
async def user_id(session) -> int:
    user = User(email="version-service-test@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


async def _make_file(session, owner_id: int, *, file_type: str = "codebook", schemaname: str = "proj_a") -> File:
    f = File(user_id=owner_id, filename="f", schemaname=schemaname, file_type=file_type)
    session.add(f)
    await session.flush()
    return f


def _codes_at(i: int) -> list[dict]:
    """One code per call, content genuinely different every time (so
    commit_codebook_version's no-op suppression never fires) -- a single
    family, single code, `definition` carries the step number.
    """
    return [
        {
            "code_uid": "u1", "family_uid": "f1", "family_name": "F", "name": "C",
            "body": f"Definition: step {i}", "definition": f"step {i}",
            "inclusion": None, "exclusion": None, "keywords": None, "example": None,
            "position": 0,
        }
    ]


class TestMaterializationScheme:
    async def test_25_versions_keeps_exactly_v1_keyframes_and_latest3(self, session, user_id) -> None:
        assert (KEYFRAME_INTERVAL, LATEST_MATERIALIZED_WINDOW) == (10, 3)
        f = await _make_file(session, user_id, schemaname="proj_25")
        for i in range(1, 26):
            await version_service.commit_codebook_version(
                session, file_id=f.id, author_user_id=user_id, origin="edited" if i > 1 else "generated",
                codes=_codes_at(i),
            )
            await session.commit()

        head = await version_repo.head_version(session, f.id)
        assert head.version_no == 25

        expected_materialized = {1, 10, 20, 23, 24, 25}
        for n in range(1, 26):
            v = await version_repo.get_version_by_no(session, f.id, n)
            assert v.codes_materialized == (n in expected_materialized), f"v{n} materialized mismatch"
            if n not in expected_materialized:
                assert v.codes_delta is not None, f"v{n} should have a stored delta"
                rows = await version_repo.list_codes(session, v.id)
                assert rows == [], f"v{n} should have no codebook_codes rows of its own"

    async def test_every_version_reconstructs_to_its_own_exact_content(self, session, user_id) -> None:
        f = await _make_file(session, user_id, schemaname="proj_25b")
        for i in range(1, 26):
            await version_service.commit_codebook_version(
                session, file_id=f.id, author_user_id=user_id, origin="edited" if i > 1 else "generated",
                codes=_codes_at(i),
            )
            await session.commit()

        for i in range(1, 26):
            codes = await version_service.read_codes(session, f.id, version_no=i)
            assert [c.definition for c in codes] == [f"step {i}"], f"v{i} reconstructed wrong content"

    async def test_zero_code_version_reconstructs_as_empty(self, session, user_id) -> None:
        f = await _make_file(session, user_id, schemaname="proj_empty_v")
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="generated", codes=_codes_at(1),
        )
        await session.commit()
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="edited", codes=[],
        )
        await session.commit()

        codes = await version_service.read_codes(session, f.id, version_no=2)
        assert codes == []

    async def test_reconstructed_objects_are_not_tracked_by_the_session(self, session, user_id) -> None:
        f = await _make_file(session, user_id, schemaname="proj_untracked")
        for i in range(1, 8):  # v1..v7 -- v2..v4 get compacted by the time v7 commits
            await version_service.commit_codebook_version(
                session, file_id=f.id, author_user_id=user_id, origin="edited" if i > 1 else "generated",
                codes=_codes_at(i),
            )
            await session.commit()

        v2 = await version_repo.get_version_by_no(session, f.id, 2)
        assert v2.codes_materialized is False, "test setup assumption: v2 should be compacted by v7"

        codes = await version_service.read_codes(session, f.id, version_no=2)
        assert len(codes) == 1
        for code in codes:
            assert code not in session.new
            assert code not in session.dirty


class TestKeyframeForcesMaterializationOnRowOnlyEdit:
    async def test_row_only_edit_landing_on_a_keyframe_boundary_is_materialized(
        self, session, user_id
    ) -> None:
        f = await _make_file(session, user_id, file_type="coding", schemaname="proj_kf_coding")
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="generated", codes=_codes_at(1),
        )
        await session.commit()

        for _ in range(8):  # v2..v9, row-only, all unmaterialized
            await version_service.commit_coding_version(session, file_id=f.id, author_user_id=user_id, origin="edited")
            await session.commit()

        # v10: still a row-only edit, but lands on the keyframe boundary.
        v10 = await version_service.commit_coding_version(session, file_id=f.id, author_user_id=user_id, origin="edited")
        await session.commit()

        assert v10.version_no == 10
        assert v10.codes_materialized is True
        rows = await version_repo.list_codes(session, v10.id)
        assert [r.definition for r in rows] == ["step 1"]  # unchanged content, but now owns real rows

        for n in range(2, 10):
            v = await version_repo.get_version_by_no(session, f.id, n)
            assert v.codes_materialized is False, f"v{n} should still be a plain unmaterialized inherit"
            assert v.codes_delta is None, f"v{n} is a row-only edit -- nothing to delta-encode"

    async def test_read_codes_resolves_correctly_across_a_keyframe(self, session, user_id) -> None:
        f = await _make_file(session, user_id, file_type="coding", schemaname="proj_kf_read")
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="generated", codes=_codes_at(1),
        )
        await session.commit()
        for _ in range(10):  # v2..v11
            await version_service.commit_coding_version(session, file_id=f.id, author_user_id=user_id, origin="edited")
            await session.commit()

        for n in (1, 5, 10, 11):
            codes = await version_service.read_codes(session, f.id, version_no=n)
            assert [c.definition for c in codes] == ["step 1"]


class TestChurnCompactsAwayEmptyDeltas:
    async def test_add_then_remove_between_keyframes_nets_out_in_the_delta(self, session, user_id) -> None:
        """A code added at v2 and removed again at v3 (churn entirely
        between v1 and the v10 keyframe) must not linger in v2's or v3's
        stored delta once they're both compacted -- each is diffed
        directly against its own anchor, not chained through each other.
        """
        f = await _make_file(session, user_id, schemaname="proj_churn")
        base = _codes_at(1)
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="generated", codes=base,
        )
        await session.commit()

        with_extra = base + [
            {
                "code_uid": "u2", "family_uid": "f1", "family_name": "F", "name": "Temp",
                "body": "", "definition": None, "inclusion": None, "exclusion": None,
                "keywords": None, "example": None, "position": 1,
            }
        ]
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="edited", codes=with_extra,
        )
        await session.commit()  # v2: added u2

        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="edited", codes=base,
        )
        await session.commit()  # v3: removed u2 again (back to v1's exact content)

        # Advance far enough that v2 gets compacted (candidate at commit
        # v5 is v2; LATEST_MATERIALIZED_WINDOW=3).
        for i in range(4, 6):
            await version_service.commit_codebook_version(
                session, file_id=f.id, author_user_id=user_id, origin="edited", codes=_codes_at(i),
            )
            await session.commit()

        v2 = await version_repo.get_version_by_no(session, f.id, 2)
        assert v2.codes_materialized is False
        # v1 -> v2 is a REAL change (added u2), so the delta must exist and
        # actually add it -- churn only cancels out relative to a FIXED
        # anchor across MULTIPLE versions, not within a single real edit.
        assert v2.codes_delta["added"], "v2 really did add u2 relative to v1"

        codes_v2 = await version_service.read_codes(session, f.id, version_no=2)
        assert {c.code_uid for c in codes_v2} == {"u1", "u2"}
        codes_v3 = await version_service.read_codes(session, f.id, version_no=3)
        assert {c.code_uid for c in codes_v3} == {"u1"}


class TestRowOnlyEditsSurviveCompactionOfTheirAncestor:
    """A row-only coding version owns no codes of its own and inherits
    them from the nearest version that does. Once that version is itself
    compacted (rows deleted, changes kept as a delta), the inheritance
    must resolve through the delta -- it used to jump straight to the
    materialized anchor beneath it and silently drop every edit the
    delta recorded, so the head of a coding artifact read an OLDER
    codebook than the one it had been saved against.
    """

    async def _coding_file_with_edit_then_row_saves(self, session, user_id, *, row_saves: int) -> File:
        f = await _make_file(session, user_id, file_type="coding", schemaname="proj_row_only_compaction")
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="generated", codes=_codes_at(1),
        )
        await session.commit()
        await version_service.commit_codebook_version(  # v2: a real codebook edit
            session, file_id=f.id, author_user_id=user_id, origin="edited", codes=_codes_at(2),
        )
        await session.commit()
        for _ in range(row_saves):  # v3.. : row-only saves
            await version_service.commit_coding_version(session, file_id=f.id, author_user_id=user_id, origin="edited")
            await session.commit()
        return f

    async def test_head_still_reads_the_edit_after_its_version_is_compacted(self, session, user_id) -> None:
        f = await self._coding_file_with_edit_then_row_saves(session, user_id, row_saves=3)  # head = v5

        v2 = await version_repo.get_version_by_no(session, f.id, 2)
        assert v2.codes_materialized is False and v2.codes_delta is not None, "setup: v2 must be compacted by v5"

        for n in (2, 3, 4, 5):
            codes = await version_service.read_codes(session, f.id, version_no=n)
            assert [c.definition for c in codes] == ["step 2"], f"v{n} lost v2's edit"
        head_codes = await version_service.read_codes(session, f.id)
        assert [c.definition for c in head_codes] == ["step 2"]

    async def test_a_keyframe_landing_on_a_row_only_edit_copies_the_right_codes(self, session, user_id) -> None:
        f = await self._coding_file_with_edit_then_row_saves(session, user_id, row_saves=8)  # head = v10 keyframe

        v10 = await version_repo.get_version_by_no(session, f.id, 10)
        assert v10.codes_materialized is True
        assert [r.definition for r in await version_repo.list_codes(session, v10.id)] == ["step 2"]


class TestRowOnlyHeadKeepsNoOpSuppression:
    async def test_resaving_identical_codes_over_a_row_only_head_mints_no_version(self, session, user_id) -> None:
        f = await _make_file(session, user_id, file_type="coding", schemaname="proj_row_only_noop")
        await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="generated", codes=_codes_at(1),
        )
        await session.commit()
        row_only = await version_service.commit_coding_version(session, file_id=f.id, author_user_id=user_id, origin="edited")
        await session.commit()

        same = await version_service.commit_codebook_version(
            session, file_id=f.id, author_user_id=user_id, origin="edited", codes=_codes_at(1),
        )
        await session.commit()

        assert same.id == row_only.id, "identical codes must not mint a new version just because the head was row-only"
