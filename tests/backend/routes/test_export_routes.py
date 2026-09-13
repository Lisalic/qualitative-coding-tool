"""Unit tests for backend/app/api/export_routes.py.

Validates export endpoints (/api/export/{file_id}/...), ensuring authentication,
owner scoping, HTTP headers, and Content-Disposition attachments.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import File, User
from backend.app.services import version_service
from backend.app.storage_models import CodingEntry, RowMemo

pytestmark = pytest.mark.usefixtures("override_async_db")


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session_factory, email: str = "export_route_test@example.com") -> User:
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


def test_export_unauthenticated_rejected(client):
    resp = client.get("/api/export/999/codebook")
    assert resp.status_code == 401


async def test_export_unowned_file_rejected(client, session_factory, make_token):
    user_a = await _make_user(session_factory, "user_a@example.com")
    user_b = await _make_user(session_factory, "user_b@example.com")
    file_a = await _make_file(session_factory, user_a.id, "cb.csv", "codebook")

    resp = client.get(
        f"/api/export/{file_a.id}/codebook",
        cookies={"access_token": make_token(sub=str(user_b.id))},
    )
    assert resp.status_code == 404


async def test_export_codebook_route_csv_and_json(client, session_factory, make_token):
    user = await _make_user(session_factory, "user_cb@example.com")
    file_rec = await _make_file(session_factory, user.id, "my_cb.csv", "codebook")
    code = {
        "code_uid": "u1",
        "name": "Theme Alpha",
        "position": 1,
        "family_uid": "",
        "family_name": "",
        "body": "",
    }
    async with session_factory() as session:
        await version_service.commit_codebook_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual", codes=[code]
        )
        await session.commit()

    # CSV
    resp_csv = client.get(
        f"/api/export/{file_rec.id}/codebook?format=csv",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert 'attachment; filename="my_cb_v1_codebook.csv"' in resp_csv.headers["content-disposition"]
    assert "Theme Alpha" in resp_csv.text

    # JSON
    resp_json = client.get(
        f"/api/export/{file_rec.id}/codebook?format=json",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_json.status_code == 200
    assert "application/json" in resp_json.headers["content-type"]
    assert 'attachment; filename="my_cb_v1_codebook.json"' in resp_json.headers["content-disposition"]
    data = resp_json.json()
    assert data["codes"][0]["name"] == "Theme Alpha"


async def test_export_coding_route_csv_and_json(client, session_factory, make_token):
    user = await _make_user(session_factory, "user_coding@example.com")
    file_rec = await _make_file(session_factory, user.id, "my_coding.csv", "coding")
    async with session_factory() as session:
        await version_service.commit_coding_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual"
        )
        entry = CodingEntry(
            file_id=file_rec.id,
            row_type="submission",
            post_id="p1",
            code="Code1",
            code_uid="u1",
            quote="Quoted evidence",
            start_offset=0,
            end_offset=15,
            notes="",
            coder="human",
            valid_from=1,
            valid_to=None,
        )
        session.add(entry)
        await session.commit()

    resp = client.get(
        f"/api/export/{file_rec.id}/coding?format=csv",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp.status_code == 200
    assert "Quoted evidence" in resp.text
    assert 'attachment; filename="my_coding_v1_coding.csv"' in resp.headers["content-disposition"]

    resp_j = client.get(
        f"/api/export/{file_rec.id}/coding?format=json",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_j.status_code == 200
    assert resp_j.json()["entries"][0]["quote"] == "Quoted evidence"


async def test_export_memos_and_summary_routes(client, session_factory, make_token):
    user = await _make_user(session_factory, "user_memo@example.com")
    file_rec = await _make_file(session_factory, user.id, "my_data.csv", "coding")
    async with session_factory() as session:
        await version_service.commit_coding_version(
            session, file_id=file_rec.id, author_user_id=user.id, origin="manual"
        )
        memo = RowMemo(
            file_id=file_rec.id,
            row_type="submission",
            row_id="p1",
            body="Noteworthy post memo",
            author_user_id=user.id,
        )
        entry = CodingEntry(
            file_id=file_rec.id,
            row_type="submission",
            post_id="p1",
            code="Code1",
            code_uid="u1",
            quote="quote",
            start_offset=0,
            end_offset=5,
            valid_from=1,
            valid_to=None,
        )
        session.add_all([memo, entry])
        await session.commit()

    # Memos
    resp_m = client.get(
        f"/api/export/{file_rec.id}/memos?format=csv",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_m.status_code == 200
    assert "Noteworthy post memo" in resp_m.text

    # Summary
    resp_s = client.get(
        f"/api/export/{file_rec.id}/summary?format=json",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_s.status_code == 200
    assert resp_s.json()["summary"][0]["code"] == "Code1"

    # Summary with version_no
    resp_sv = client.get(
        f"/api/export/{file_rec.id}/summary?format=json&version_no=1",
        cookies={"access_token": make_token(sub=str(user.id))},
    )
    assert resp_sv.status_code == 200
    assert resp_sv.json()["version_no"] == 1
    assert 'attachment; filename="my_data_v1_summary.json"' in resp_sv.headers["content-disposition"]
