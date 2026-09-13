"""Route tests for /api/comparison/codebooks and /api/comparison/codings.

Validates deterministic computed comparisons:
- 401 unauthenticated rejected.
- 404 unowned files rejected.
- 200 computed codebook diff without model/API key.
- 200 computed coding diff without model/API key.
- Route-level directional reversibility.
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


async def _make_user(session_factory, email: str = "comp_test@example.com") -> User:
    async with session_factory() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_file(session_factory, user_id: int, filename: str, file_type: str) -> File:
    async with session_factory() as session:
        file_rec = File(
            user_id=user_id,
            filename=filename,
            schemaname=filename.replace(".", "_"),
            file_type=file_type,
        )
        session.add(file_rec)
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


def test_comparison_unauthenticated_rejected(client):
    resp = client.get("/api/comparison/codebooks?file_a=1&file_b=2")
    assert resp.status_code == 401

    resp = client.get("/api/comparison/codings?file_a=1&file_b=2")
    assert resp.status_code == 401


async def test_comparison_unowned_rejected(client, session_factory, make_token):
    u1 = await _make_user(session_factory, "u1_comp@example.com")
    u2 = await _make_user(session_factory, "u2_comp@example.com")
    f1 = await _make_file(session_factory, u1.id, "cb1.csv", "codebook")
    f2 = await _make_file(session_factory, u1.id, "cb2.csv", "codebook")

    resp = client.get(
        f"/api/comparison/codebooks?file_a={f1.id}&file_b={f2.id}",
        cookies={"access_token": make_token(sub=str(u2.id))},
    )
    assert resp.status_code == 404


async def test_computed_codebook_comparison_route(client, session_factory, make_token):
    u = await _make_user(session_factory, "cb_user@example.com")
    f1 = await _make_file(session_factory, u.id, "cb_a.csv", "codebook")
    f2 = await _make_file(session_factory, u.id, "cb_b.csv", "codebook")

    codes_a = [
        {"position": 1, "code_uid": "c1", "family_uid": "f1", "family_name": "Fam", "name": "Code 1", "body": "Body A"}
    ]
    codes_b = [
        {"position": 1, "code_uid": "c1", "family_uid": "f1", "family_name": "Fam", "name": "Code 1", "body": "Body B (redefined)"}
    ]

    async with session_factory() as session:
        await version_service.commit_codebook_version(
            session, file_id=f1.id, author_user_id=u.id, codes=codes_a, origin="manual"
        )
        await version_service.commit_codebook_version(
            session, file_id=f2.id, author_user_id=u.id, codes=codes_b, origin="manual"
        )
        await session.commit()

    resp = client.get(
        f"/api/comparison/codebooks?file_a={f1.id}&file_b={f2.id}",
        cookies={"access_token": make_token(sub=str(u.id))},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_a"]["id"] == f1.id
    assert data["file_b"]["id"] == f2.id
    assert len(data["redefined"]) == 1
    assert data["redefined"][0]["from"]["body"] == "Body A"
    assert data["redefined"][0]["to"]["body"] == "Body B (redefined)"


async def test_computed_coding_comparison_route_and_reversibility(client, session_factory, make_token):
    u = await _make_user(session_factory, "coding_user@example.com")
    f1 = await _make_file(session_factory, u.id, "coding_a.csv", "coding")
    f2 = await _make_file(session_factory, u.id, "coding_b.csv", "coding")

    async with session_factory() as session:
        await version_service.commit_coding_version(session, file_id=f1.id, author_user_id=u.id, origin="manual")
        await version_service.commit_coding_version(session, file_id=f2.id, author_user_id=u.id, origin="manual")

        e1 = CodingEntry(file_id=f1.id, row_type="sub", post_id="p1", code="C1", code_uid="u1", quote="q", start_offset=0, end_offset=1, valid_from=1)
        e2 = CodingEntry(file_id=f2.id, row_type="sub", post_id="p1", code="C2", code_uid="u2", quote="q", start_offset=0, end_offset=1, valid_from=1)
        session.add_all([e1, e2])
        await session.commit()

    # Diff A -> B
    resp_ab = client.get(
        f"/api/comparison/codings?file_a={f1.id}&file_b={f2.id}",
        cookies={"access_token": make_token(sub=str(u.id))},
    )
    assert resp_ab.status_code == 200
    data_ab = resp_ab.json()
    assert data_ab["rows_recoded"] == 1
    assert len(data_ab["applied"]) == 1
    assert len(data_ab["removed"]) == 1

    # Diff B -> A (Reverse)
    resp_ba = client.get(
        f"/api/comparison/codings?file_a={f2.id}&file_b={f1.id}",
        cookies={"access_token": make_token(sub=str(u.id))},
    )
    assert resp_ba.status_code == 200
    data_ba = resp_ba.json()
    assert data_ba["rows_recoded"] == 1
    assert data_ab["applied"][0]["code_uid"] == data_ba["removed"][0]["code_uid"]
    assert data_ab["removed"][0]["code_uid"] == data_ba["applied"][0]["code_uid"]
