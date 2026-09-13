"""Unit tests for backend/app/api/coverage_routes.py.

Validates the /api/coding/{file_id}/coverage endpoint:
- Rejects unauthenticated requests (401).
- Rejects unowned files (404).
- Computes head-version coverage metrics.
- Computes historical version coverage metrics via SCD-2.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import File, User
from backend.app.services import version_service
from backend.app.storage_models import CodingEntry

pytestmark = pytest.mark.usefixtures("override_async_db")


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session_factory, email: str = "coverage_test@example.com") -> User:
    async with session_factory() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_file(session_factory, user_id: int, filename: str) -> File:
    async with session_factory() as session:
        file_rec = File(
            user_id=user_id,
            filename=filename,
            schemaname=filename.replace(".", "_"),
            file_type="coding",
        )
        session.add(file_rec)
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


def test_coverage_unauthenticated_rejected(client):
    resp = client.get("/api/coding/999/coverage")
    assert resp.status_code == 401


async def test_coverage_unowned_file_rejected(client, session_factory, make_token):
    u1 = await _make_user(session_factory, "u1@example.com")
    u2 = await _make_user(session_factory, "u2@example.com")
    f1 = await _make_file(session_factory, u1.id, "my_coding.csv")

    resp = client.get(
        f"/api/coding/{f1.id}/coverage",
        cookies={"access_token": make_token(sub=str(u2.id))},
    )
    assert resp.status_code == 404


async def test_coverage_head_and_historical(client, session_factory, make_token):
    u = await _make_user(session_factory, "cov_user@example.com")
    f = await _make_file(session_factory, u.id, "test_cov.csv")

    # V1: 1 code, 1 entry
    async with session_factory() as session:
        await version_service.commit_coding_version(
            session, file_id=f.id, author_user_id=u.id, origin="manual"
        )
        e1 = CodingEntry(
            file_id=f.id,
            row_type="submission",
            post_id="p1",
            code="Code1",
            code_uid="u1",
            quote="q1",
            start_offset=0,
            end_offset=2,
            valid_from=1,
            valid_to=None,
        )
        session.add(e1)
        await session.commit()

    # Query head coverage
    resp = client.get(
        f"/api/coding/{f.id}/coverage",
        cookies={"access_token": make_token(sub=str(u.id))},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_id"] == f.id
    assert data["total_entries"] == 1
    assert data["coded_rows"] == 1
    assert "notice" in data

    # Query historical coverage (version_no=1)
    resp_hist = client.get(
        f"/api/coding/{f.id}/coverage?version_no=1",
        cookies={"access_token": make_token(sub=str(u.id))},
    )
    assert resp_hist.status_code == 200
    assert resp_hist.json()["version_no"] == 1
