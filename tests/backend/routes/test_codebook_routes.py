"""Tests for backend/app/api/codebook_routes.py -- GET /api/list-codebooks,
GET /api/codebook, GET /api/parse-codebook, POST /api/save-file-codebook/.

Stage 7 moved this module fully onto the async ORM + fixed
``artifact_content`` table (``repositories/artifact_content_repo.py``), so
these run against the in-memory async SQLite database
(``override_async_db``) rather than a mocked sync ``engine``. The
AI/job-kickoff routes in this module (generate-codebook, compare-codebooks)
are covered separately in ``test_ai_and_raw_sql_routes.py`` at the
validation/auth-guard/202-shape boundary; their full job-handler behavior is
covered by ``tests/backend/services/test_codebook_service.py``.
"""

import pytest

from backend.app.repositories import artifact_content_repo

pytestmark = pytest.mark.usefixtures("override_async_db")


async def _make_user(session_factory, email: str = "a@b.com"):
    from backend.app.database import User

    async with session_factory() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_file(session_factory, user_id: int, **kwargs):
    from backend.app.database import File

    defaults = dict(filename="cb", schemaname="proj_a", file_type="codebook")
    defaults.update(kwargs)
    async with session_factory() as session:
        file_rec = File(user_id=user_id, **defaults)
        session.add(file_rec)
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


@pytest.fixture()
def session_factory(async_sqlite_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


class TestListCodebooks:
    def test_requires_auth(self, client) -> None:
        # Regression test: this endpoint used to return every user's
        # codebooks with no auth check at all.
        resp = client.get("/api/list-codebooks")
        assert resp.status_code == 401

    def test_empty_list(self, client, auth_cookies) -> None:
        resp = client.get("/api/list-codebooks", cookies=auth_cookies)
        assert resp.status_code == 200
        assert resp.json() == {"codebooks": []}

    async def test_lists_codebook_and_comparison_types_sorted_by_name(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id, filename="Zeta", schemaname="proj_z", file_type="codebook")
        await _make_file(
            session_factory, user.id, filename="Alpha", schemaname="cmp_a", file_type="codebook_comparison"
        )
        await _make_file(session_factory, user.id, filename="Other", schemaname="proj_o", file_type="raw_data")

        resp = client.get(
            "/api/list-codebooks", cookies={"access_token": make_token(sub=str(user.id))}
        )
        names = [c["name"] for c in resp.json()["codebooks"]]
        assert names == ["Alpha", "Zeta"]  # sorted, raw_data excluded

    async def test_scoped_to_owner_not_all_users(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner@b.com")
        other = await _make_user(session_factory, "other@b.com")
        await _make_file(session_factory, owner.id, filename="Mine", schemaname="proj_m", file_type="codebook")
        await _make_file(session_factory, other.id, filename="NotMine", schemaname="proj_n", file_type="codebook")

        resp = client.get(
            "/api/list-codebooks", cookies={"access_token": make_token(sub=str(owner.id))}
        )
        names = [c["name"] for c in resp.json()["codebooks"]]
        assert names == ["Mine"]


class TestGetCodebook:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/codebook")
        assert resp.status_code == 401

    def test_no_id_and_no_files_returns_404(self, client, auth_cookies) -> None:
        resp = client.get("/api/codebook", cookies=auth_cookies)
        assert resp.status_code == 404
        assert resp.json()["error"] == "No codebook file found"

    def test_unmatched_id_returns_404(self, client, auth_cookies) -> None:
        resp = client.get("/api/codebook?codebook_id=nonexistent", cookies=auth_cookies)
        assert resp.status_code == 404

    async def test_matches_by_schemaname_and_reads_content(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(
            session_factory,
            user.id,
            filename="cb",
            schemaname="proj_a",
            file_type="codebook",
            systemprompt="sys",
            userprompt="usr",
        )
        async with session_factory() as session:
            await artifact_content_repo.write_content(session, file_rec.id, "codebook text content")
            await session.commit()

        resp = client.get(
            "/api/codebook?codebook_id=proj_a", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["codebook"] == "codebook text content"
        assert body["systemprompt"] == "sys"
        assert body["userprompt"] == "usr"

    async def test_matches_by_integer_file_id(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, filename="cb", schemaname="proj_a", file_type="codebook")
        async with session_factory() as session:
            await artifact_content_repo.write_content(session, file_rec.id, "content")
            await session.commit()

        resp = client.get(
            f"/api/codebook?codebook_id={file_rec.id}",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200

    async def test_content_missing_in_file_returns_404(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id, filename="cb", schemaname="proj_a", file_type="codebook")

        resp = client.get(
            "/api/codebook?codebook_id=proj_a", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "Codebook content not found in file"

    async def test_cannot_read_another_users_codebook(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner@b.com")
        other = await _make_user(session_factory, "other@b.com")
        file_rec = await _make_file(
            session_factory, owner.id, filename="cb", schemaname="proj_a", file_type="codebook"
        )
        async with session_factory() as session:
            await artifact_content_repo.write_content(session, file_rec.id, "secret content")
            await session.commit()

        resp = client.get(
            "/api/codebook?codebook_id=proj_a", cookies={"access_token": make_token(sub=str(other.id))}
        )
        assert resp.status_code == 404


class TestParseCodebook:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/parse-codebook?codebook_id=nonexistent")
        assert resp.status_code == 401

    def test_no_matching_file_returns_404(self, client, auth_cookies) -> None:
        resp = client.get("/api/parse-codebook?codebook_id=nonexistent", cookies=auth_cookies)
        assert resp.status_code == 404

    async def test_parses_raw_content_into_json_structure(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, filename="cb", schemaname="proj_a", file_type="codebook")
        raw = "### Code Family: F\n#### Code Name: C\ncontent"
        async with session_factory() as session:
            await artifact_content_repo.write_content(session, file_rec.id, raw)
            await session.commit()

        resp = client.get(
            "/api/parse-codebook?codebook_id=proj_a", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        parsed = resp.json()["parsed"]
        assert parsed[0]["family_name"] == "F"
        assert parsed[0]["codes"][0]["code_name"] == "C"


class TestSaveProjectCodebook:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/save-file-codebook/", data={"schema_name": "proj_a", "content": "x"}
        )
        assert resp.status_code == 401

    async def test_happy_path_updates_content_and_display_name(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, filename="cb", schemaname="proj_a", file_type="codebook")

        resp = client.post(
            "/api/save-file-codebook/",
            data={"schema_name": "proj_a", "content": "updated text", "display_name": "renamed"},
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "renamed"

        async with session_factory() as session:
            content = await artifact_content_repo.read_content(session, file_rec.id)
        assert content == "updated text"

    async def test_unowned_schema_returns_404(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner@b.com")
        other = await _make_user(session_factory, "other@b.com")
        await _make_file(session_factory, owner.id, filename="cb", schemaname="proj_a", file_type="codebook")

        resp = client.post(
            "/api/save-file-codebook/",
            data={"schema_name": "proj_a", "content": "x"},
            cookies={"access_token": make_token(sub=str(other.id))},
        )
        assert resp.status_code == 404
