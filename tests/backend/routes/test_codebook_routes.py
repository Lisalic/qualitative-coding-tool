"""Tests for backend/app/api/codebook_routes.py -- GET /api/list-codebooks,
GET /api/codebook, PUT /api/codebook/{ref}, POST /api/codebook/{ref}/import.

These run against the in-memory async SQLite database
(``override_async_db``) rather than a mocked sync ``engine``. The
AI/job-kickoff routes in this module (generate-codebook, compare-codebooks)
are covered separately in ``test_ai_and_raw_sql_routes.py`` at the
validation/auth-guard/202-shape boundary; their full job-handler behavior is
covered by ``tests/backend/services/test_codebook_service.py``.
"""

import pytest

from backend.app.services import version_service

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


_ONE_CODE = [
    {
        "code_uid": "u1", "family_uid": "f1", "family_name": "F", "name": "C", "body": "content",
        "position": 0,
    }
]


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

    async def test_excludes_comparisons_and_other_types_sorted_by_name(
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
        assert names == ["Zeta"]  # comparison and raw_data excluded

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

    async def test_matches_by_schemaname_and_reads_codes(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(
            session_factory,
            user.id,
            filename="cb",
            schemaname="proj_a",
            file_type="codebook",
        )
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated",
                codes=_ONE_CODE, system_prompt="sys", user_instructions="usr",
                prompt_meta={"rendered_chars": 1234, "rendered_sha256": "abc", "batches": 2},
            )
            await session.commit()

        resp = client.get(
            "/api/codebook?codebook_id=proj_a", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["codes"][0]["name"] == "C"
        assert body["codes"][0]["code_uid"] == "u1"
        assert body["systemprompt"] == "sys"
        assert body["instructions"] == "usr"
        assert body["prompt_meta"]["rendered_chars"] == 1234

    async def test_matches_by_integer_file_id(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, filename="cb", schemaname="proj_a", file_type="codebook")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated", codes=_ONE_CODE,
            )
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
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=owner.id, origin="generated", codes=_ONE_CODE,
            )
            await session.commit()

        resp = client.get(
            "/api/codebook?codebook_id=proj_a", cookies={"access_token": make_token(sub=str(other.id))}
        )
        assert resp.status_code == 404


class TestSaveProjectCodebook:
    def test_requires_auth(self, client) -> None:
        resp = client.put("/api/codebook/proj_a", json={"codes": _ONE_CODE})
        assert resp.status_code == 401

    async def test_happy_path_updates_content_and_display_name(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, filename="cb", schemaname="proj_a", file_type="codebook")

        resp = client.put(
            "/api/codebook/proj_a",
            json={"codes": _ONE_CODE, "display_name": "renamed"},
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "renamed"

        async with session_factory() as session:
            codes = await version_service.read_codes(session, file_rec.id)
        assert [c.name for c in codes] == ["C"]

    async def test_unowned_schema_returns_404(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner@b.com")
        other = await _make_user(session_factory, "other@b.com")
        await _make_file(session_factory, owner.id, filename="cb", schemaname="proj_a", file_type="codebook")

        resp = client.put(
            "/api/codebook/proj_a",
            json={"codes": _ONE_CODE},
            cookies={"access_token": make_token(sub=str(other.id))},
        )
        assert resp.status_code == 404

    async def test_code_without_uid_or_is_new_is_rejected(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id, filename="cb", schemaname="proj_a", file_type="codebook")

        bad_code = {"family_uid": "f1", "family_name": "F", "name": "C", "body": "x"}
        resp = client.put(
            "/api/codebook/proj_a",
            json={"codes": [bad_code]},
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 400


class TestDuplicateCodebook:
    def test_requires_auth(self, client) -> None:
        resp = client.post("/api/codebook/proj_a/duplicate", json={"display_name": "n"})
        assert resp.status_code == 401

    async def test_no_owned_source_returns_404(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        resp = client.post(
            "/api/codebook/proj_missing/duplicate",
            json={"display_name": "n"},
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 404

    async def test_forks_codes_and_lineage(self, client, session_factory, make_token) -> None:
        from backend.app.repositories import version_repo

        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_dup")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated", codes=_ONE_CODE,
            )
            await session.commit()

        resp = client.post(
            "/api/codebook/proj_dup/duplicate",
            json={"display_name": "dup"},
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "dup"
        new_file_id = int(body["id"])
        assert new_file_id != file_rec.id

        async with session_factory() as session:
            codes = await version_service.read_codes(session, new_file_id)
            assert [c.code_uid for c in codes] == ["u1"]
            edges = await version_repo.list_parent_edges(session, new_file_id)
            assert [e.parent_file_id for e in edges] == [file_rec.id]
            assert edges[0].relation == "forked_from"

    async def test_from_version_no_forks_that_version_not_head(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_dup_v")
        renamed = [{**_ONE_CODE[0], "name": "Renamed"}]
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated", codes=_ONE_CODE,
            )
            await session.commit()
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited", codes=renamed,
            )
            await session.commit()

        resp = client.post(
            "/api/codebook/proj_dup_v/duplicate",
            json={"display_name": "from-v1", "from_version_no": 1},
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        new_file_id = int(resp.json()["id"])

        async with session_factory() as session:
            codes = await version_service.read_codes(session, new_file_id)
            assert [c.name for c in codes] == ["C"]
