"""Tests for quote bank routes (QC-008).

Covers:
- GET /api/coding/{ref}/quotes (pagination, filters: code, coder, q,
  starred_only, version_no)
- PUT /api/coding/{ref}/quotes/{entry_id}/star (owner-scoped, idempotent,
  survives the quote being re-saved)
- PATCH /api/coding/{ref}/quotes/{entry_id}/notes (versioned note edit)
- Exact offsets & source context inspection
- Multi-user starring isolation
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import File, get_async_db
from backend.app.main import app as fastapi_app
from backend.app.services import version_service
from backend.app.storage_models import CodingEntry, Submission
from backend.app.versioning_models import ORIGIN_EDITED



def _auth_headers(make_token, sub="1"):
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


@pytest.fixture()
def db_session_factory(async_sqlite_engine, monkeypatch):
    SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)

    async def _get_async_db():
        async with SessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_async_db] = _get_async_db
    try:
        yield SessionLocal
    finally:
        fastapi_app.dependency_overrides.pop(get_async_db, None)


async def _make_user(SessionLocal, email: str = "user1@test.com"):
    from backend.app.database import User
    async with SessionLocal() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

async def _setup_test_coding(SessionLocal, email: str = "user1@test.com"):
    user = await _make_user(SessionLocal, email=email)
    user_id = user.id
    async with SessionLocal() as session:
        file_rec = File(
            user_id=user_id,
            filename="Test Coding",
            schemaname="proj_quotebanktest",
            file_type="coding",
        )
        session.add(file_rec)
        await session.flush()

        # Seed v1
        await version_service.commit_coding_version(
            session,
            file_id=file_rec.id,
            author_user_id=user_id,
            origin=ORIGIN_EDITED,
        )

        # Seed submissions
        sub1 = Submission(
            file_id=file_rec.id,
            id="sub_1",
            title="Post About AI Ethics",
            selftext="Qualitative coding requires careful evidence extraction and rigorous review.",
            author="researcher1",
            subreddit="qualitative",
            word_count=10,
        )
        sub2 = Submission(
            file_id=file_rec.id,
            id="sub_2",
            title="Second Post",
            selftext="Artificial intelligence models can suggest initial tags, but humans decide.",
            author="researcher2",
            subreddit="datascience",
            word_count=11,
        )
        session.add_all([sub1, sub2])
        await session.flush()

        # Seed entries
        e1 = CodingEntry(
            file_id=file_rec.id,
            row_type="submission",
            post_id="sub_1",
            code="Rigorous Review",
            code_uid="uid_rigor",
            quote="careful evidence extraction",
            start_offset=27,
            end_offset=54,
            notes="Key methodological excerpt",
            coder="human",
            valid_from=1,
            valid_to=None,
        )
        e2 = CodingEntry(
            file_id=file_rec.id,
            row_type="submission",
            post_id="sub_2",
            code="AI Assistance",
            code_uid="uid_ai",
            quote="Artificial intelligence models can suggest initial tags",
            start_offset=0,
            end_offset=55,
            notes=None,
            coder="ai",
            coder_model="gpt-4o",
            valid_from=1,
            valid_to=None,
        )
        session.add_all([e1, e2])
        await session.commit()
        await session.refresh(file_rec)
        await session.refresh(e1)
        await session.refresh(e2)
        return user, file_rec, e1, e2


class TestQuoteBankRoutes:
    @pytest.mark.asyncio
    async def test_list_quotes_all_and_filtering(self, client, make_token, db_session_factory):
        user, file_rec, e1, e2 = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        

        # 1. Fetch all quotes
        resp = client.get(f"/api/coding/{file_rec.schemaname}/quotes", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["quotes"]) == 2
        # Quotes carry exact offsets and source text
        q1 = next(q for q in data["quotes"] if q["id"] == e1.id)
        assert q1["quote"] == "careful evidence extraction"
        assert q1["start_offset"] == 27
        assert q1["end_offset"] == 54
        assert q1["coder"] == "human"
        assert q1["starred"] is False
        assert q1["title"] == "Post About AI Ethics"
        assert "careful evidence extraction" in q1["content"]

        # 2. Filter by coder: 'ai'
        resp_ai = client.get(
            f"/api/coding/{file_rec.schemaname}/quotes?coder=ai", headers=headers
        )
        assert resp_ai.status_code == 200
        assert resp_ai.json()["total"] == 1
        assert resp_ai.json()["quotes"][0]["id"] == e2.id

        # 3. Filter by code: 'Rigorous Review'
        resp_code = client.get(
            f"/api/coding/{file_rec.schemaname}/quotes?code=Rigorous%20Review", headers=headers
        )
        assert resp_code.status_code == 200
        assert resp_code.json()["total"] == 1
        assert resp_code.json()["quotes"][0]["id"] == e1.id

        # 4. Filter by search query q: 'suggest'
        resp_q = client.get(
            f"/api/coding/{file_rec.schemaname}/quotes?q=suggest", headers=headers
        )
        assert resp_q.status_code == 200
        assert resp_q.json()["total"] == 1
        assert resp_q.json()["quotes"][0]["id"] == e2.id

    @pytest.mark.asyncio
    async def test_star_and_unstar_with_user_isolation(
        self, client, make_token, db_session_factory
    ):
        user, file_rec, e1, _ = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        

        # Star e1 for user 1
        star_resp = client.put(
            f"/api/coding/{file_rec.schemaname}/quotes/{e1.id}/star",
            headers=headers,
            json={"starred": True},
        )
        assert star_resp.status_code == 200
        assert star_resp.json() == {"entry_id": e1.id, "starred": True}

        # Verify starred in list
        list_resp = client.get(
            f"/api/coding/{file_rec.schemaname}/quotes?starred_only=true",
            headers=headers,
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1
        assert list_resp.json()["quotes"][0]["id"] == e1.id
        assert list_resp.json()["quotes"][0]["starred"] is True

        # Unstar e1
        unstar_resp = client.put(
            f"/api/coding/{file_rec.schemaname}/quotes/{e1.id}/star",
            headers=headers,
            json={"starred": False},
        )
        assert unstar_resp.status_code == 200
        assert unstar_resp.json() == {"entry_id": e1.id, "starred": False}

        # Verify empty starred list
        list_resp2 = client.get(
            f"/api/coding/{file_rec.schemaname}/quotes?starred_only=true",
            headers=headers,
        )
        assert list_resp2.status_code == 200
        assert list_resp2.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_note_edit_mints_a_version_and_keeps_history(
        self, client, make_token, db_session_factory
    ):
        user, file_rec, e1, _ = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        base = f"/api/coding/{file_rec.schemaname}/quotes"

        patch_resp = client.patch(
            f"{base}/{e1.id}/notes", headers=headers, json={"notes": "  Updated note for chapter 3  "},
        )
        assert patch_resp.status_code == 200
        body = patch_resp.json()
        assert body["notes"] == "Updated note for chapter 3"
        new_id = body["entry_id"]
        assert new_id != e1.id

        live = client.get(base, headers=headers).json()
        q1 = next(q for q in live["quotes"] if q["id"] == new_id)
        assert q1["notes"] == "Updated note for chapter 3"
        assert live["total"] == 2

        old = client.get(f"{base}?version_no=1", headers=headers).json()
        q1_old = next(q for q in old["quotes"] if q["id"] == e1.id)
        assert q1_old["notes"] == "Key methodological excerpt"

    @pytest.mark.asyncio
    async def test_note_on_a_closed_entry_is_rejected(self, client, make_token, db_session_factory):
        user, file_rec, e1, _ = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        base = f"/api/coding/{file_rec.schemaname}/quotes"

        client.patch(f"{base}/{e1.id}/notes", headers=headers, json={"notes": "v2"})
        resp = client.patch(f"{base}/{e1.id}/notes", headers=headers, json={"notes": "stale"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_star_survives_a_note_edit(self, client, make_token, db_session_factory):
        user, file_rec, e1, _ = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        base = f"/api/coding/{file_rec.schemaname}/quotes"

        client.put(f"{base}/{e1.id}/star", headers=headers, json={"starred": True})
        new_id = client.patch(
            f"{base}/{e1.id}/notes", headers=headers, json={"notes": "re-saved"},
        ).json()["entry_id"]

        starred = client.get(f"{base}?starred_only=true", headers=headers).json()
        assert starred["total"] == 1
        assert starred["quotes"][0]["id"] == new_id

    @pytest.mark.asyncio
    async def test_starring_twice_is_idempotent(self, client, make_token, db_session_factory):
        user, file_rec, e1, _ = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        url = f"/api/coding/{file_rec.schemaname}/quotes/{e1.id}/star"

        assert client.put(url, headers=headers, json={"starred": True}).status_code == 200
        assert client.put(url, headers=headers, json={"starred": True}).status_code == 200
        starred = client.get(
            f"/api/coding/{file_rec.schemaname}/quotes?starred_only=true", headers=headers,
        ).json()
        assert starred["total"] == 1

    @pytest.mark.asyncio
    async def test_entry_from_another_file_is_404(self, client, make_token, db_session_factory):
        user, file_rec, e1, _ = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        async with db_session_factory() as session:
            other = File(user_id=user.id, filename="Other", schemaname="proj_otherfile", file_type="coding")
            session.add(other)
            await session.commit()

        resp = client.put(
            f"/api/coding/proj_otherfile/quotes/{e1.id}/star", headers=headers, json={"starred": True},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_pagination(self, client, make_token, db_session_factory):
        user, file_rec, e1, e2 = await _setup_test_coding(db_session_factory)
        headers = _auth_headers(make_token, sub=str(user.id))
        base = f"/api/coding/{file_rec.schemaname}/quotes"

        page1 = client.get(f"{base}?limit=1&offset=0", headers=headers).json()
        page2 = client.get(f"{base}?limit=1&offset=1", headers=headers).json()
        assert page1["total"] == page2["total"] == 2
        assert [q["id"] for q in page1["quotes"]] == [e1.id]
        assert [q["id"] for q in page2["quotes"]] == [e2.id]

    @pytest.mark.asyncio
    async def test_starred_status_is_owner_scoped_across_users(
        self, client, make_token, db_session_factory
    ):
        # User 1 owns file
        user1, file_rec, e1, _ = await _setup_test_coding(db_session_factory, email="user_a@test.com")
        user2 = await _make_user(db_session_factory, email="user_b@test.com")

        headers1 = _auth_headers(make_token, sub=str(user1.id))
        headers2 = _auth_headers(make_token, sub=str(user2.id))

        # User 1 stars e1
        resp = client.put(
            f"/api/coding/{file_rec.schemaname}/quotes/{e1.id}/star",
            headers=headers1,
            json={"starred": True},
        )
        assert resp.status_code == 200

        # User 1 sees it as starred
        list1 = client.get(f"/api/coding/{file_rec.schemaname}/quotes", headers=headers1).json()
        assert list1["quotes"][0]["starred"] is True

        # User 2 accessing the file (if given permission, or directly via repo check)
        from backend.app.repositories import coding_repo
        async with db_session_factory() as session:
            # Check list_quote_bank for user2
            quotes_u2, _ = await coding_repo.list_quote_bank(
                session, file_rec.id, user_id=user2.id
            )
            assert quotes_u2[0]["starred"] is False
