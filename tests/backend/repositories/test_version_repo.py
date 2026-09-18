"""Tests for backend/app/repositories/version_repo.py -- ``latest_materialized_version``,
the anchor lookup ``version_service.read_codes`` uses to resolve a
coding version that inherits its codebook snapshot rather than owning
one (see ``versioning_models.ArtifactVersion.codes_materialized``'s
docstring for why).
"""

from backend.app.database import File
from backend.app.repositories.version_repo import create_version, latest_materialized_version

from .conftest import make_user


async def _make_file(session, user, schemaname: str = "proj_a") -> File:
    f = File(user_id=user.id, filename=f"{schemaname}.txt", schemaname=schemaname, file_type="coding")
    session.add(f)
    await session.commit()
    return f


class TestLatestMaterializedVersion:
    async def test_returns_none_for_a_file_with_no_versions(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            result = await latest_materialized_version(session, f.id, at_or_before=1)
            assert result is None

    async def test_v1_is_its_own_anchor(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            v1 = await create_version(
                session, file_id=f.id, version_no=1, parent_version_id=None,
                author_user_id=user.id, origin="generated", sealed_at=None,
            )
            await session.commit()

            result = await latest_materialized_version(session, f.id, at_or_before=1)
            assert result.id == v1.id

    async def test_skips_over_unmaterialized_versions_to_the_nearest_earlier_anchor(
        self, session_factory
    ) -> None:
        # v1 materialized, v2/v3/v4 unmaterialized (row-only saves) -- the
        # anchor for any of v2/v3/v4 must be v1, not the nearest version.
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            v1 = await create_version(
                session, file_id=f.id, version_no=1, parent_version_id=None,
                author_user_id=user.id, origin="generated", sealed_at=None,
            )
            for n in (2, 3, 4):
                v = await create_version(
                    session, file_id=f.id, version_no=n, parent_version_id=v1.id,
                    author_user_id=user.id, origin="edited", sealed_at=None,
                )
                v.codes_materialized = False
            await session.commit()

            for n in (2, 3, 4):
                result = await latest_materialized_version(session, f.id, at_or_before=n)
                assert result.id == v1.id, f"anchor for v{n} should be v1"

    async def test_finds_the_most_recent_materialized_version_not_just_v1(
        self, session_factory
    ) -> None:
        # v1 materialized, v2 materialized (a real codebook edit), v3/v4
        # unmaterialized -- the anchor for v3/v4 must be v2, the MOST
        # RECENT materialized version, not v1.
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            v1 = await create_version(
                session, file_id=f.id, version_no=1, parent_version_id=None,
                author_user_id=user.id, origin="generated", sealed_at=None,
            )
            v2 = await create_version(
                session, file_id=f.id, version_no=2, parent_version_id=v1.id,
                author_user_id=user.id, origin="edited", sealed_at=None,
            )
            for n in (3, 4):
                v = await create_version(
                    session, file_id=f.id, version_no=n, parent_version_id=v2.id,
                    author_user_id=user.id, origin="edited", sealed_at=None,
                )
                v.codes_materialized = False
            await session.commit()

            for n in (3, 4):
                result = await latest_materialized_version(session, f.id, at_or_before=n)
                assert result.id == v2.id, f"anchor for v{n} should be v2, not v1"

    async def test_existing_rows_default_to_materialized(self, session_factory) -> None:
        # server_default=true: create_version doesn't pass codes_materialized
        # at all, matching every pre-existing version in the real database.
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            v1 = await create_version(
                session, file_id=f.id, version_no=1, parent_version_id=None,
                author_user_id=user.id, origin="generated", sealed_at=None,
            )
            await session.commit()
            await session.refresh(v1)
            assert v1.codes_materialized is True
