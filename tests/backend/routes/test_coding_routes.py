"""Guard-level (and, where SQLite can carry it, happy-path) tests for
backend/app/api/coding_routes.py.

The coding-artifact overhaul replaces the old blob-backed
`/api/coded-data` / `/api/save-file-coded-data(-duplicate)/` trio with a
REST-ish `/api/coding/{ref}` family: a coding artifact now owns its own
codebook snapshot, its own copy of every sampled post/comment, and its
coding (`coding_entries`, the sole source of truth for the
classification) -- see `backend/app/services/coding_service.py`'s module
docstring. Per CLAUDE.md's early-prototyping rule there is no
compatibility shim for the old routes; they are gone, not deprecated.

`apply-codebook`/`compare-codings`/`summarize-coding` keep their existing
`202 {job_id, status}` kickoff contract, unchanged by this overhaul except
for what their handlers now persist -- see
`tests/backend/services/test_coding_service.py` for that deeper coverage.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.usefixtures("override_db")


def _auth_headers(make_token, sub="1"):
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


@pytest.fixture()
def route_backed_by_sqlite_jobs(async_sqlite_engine, monkeypatch):
    """Point the route's ``get_async_db`` dependency, and every session
    factory a background job handler opens for itself
    (``jobs/service.py``'s and ``coding_service.py``'s own
    ``AsyncSessionLocal``), at the same in-memory SQLite engine -- so a
    job enqueued through the ``TestClient`` actually executes (and can
    read/write its own rows) against the test database instead of the
    real ``DATABASE_URL``.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from backend.app.database import get_async_db
    from backend.app.main import app as fastapi_app

    SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)

    async def _get_async_db():
        async with SessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_async_db] = _get_async_db
    monkeypatch.setattr("backend.app.jobs.service.AsyncSessionLocal", SessionLocal)
    monkeypatch.setattr("backend.app.services.coding_service.AsyncSessionLocal", SessionLocal)
    try:
        yield SessionLocal
    finally:
        fastapi_app.dependency_overrides.pop(get_async_db, None)


async def _make_user(SessionLocal, email: str = "a@b.com"):
    from backend.app.database import User

    async with SessionLocal() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_file(
    SessionLocal,
    user_id: int,
    *,
    file_type: str = "coding",
    schemaname: str | None = None,
    content: str | None = None,
):
    """Insert a ``File`` (optionally with an ``artifact_content`` row --
    a coding file's codebook snapshot, or a coding_comparison's markdown)
    directly via the ORM, owned by ``user_id``.
    """
    import secrets

    from backend.app.database import File
    from backend.app.storage_models import ArtifactContent

    async with SessionLocal() as session:
        file_rec = File(
            user_id=user_id,
            filename="c",
            schemaname=schemaname or f"proj_{secrets.token_hex(4)}",
            file_type=file_type,
        )
        session.add(file_rec)
        await session.flush()
        if content is not None:
            session.add(ArtifactContent(file_id=file_rec.id, content=content))
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


async def _link_dependency(SessionLocal, *, child_file_id: int, parent_file_id: int):
    from backend.app.database import FileDependency

    async with SessionLocal() as session:
        session.add(FileDependency(child_file_id=child_file_id, parent_file_id=parent_file_id))
        await session.commit()


async def _add_submission(SessionLocal, file_id: int, *, sub_id: str, title: str = "T", selftext: str = "S"):
    from backend.app.storage_models import Submission

    async with SessionLocal() as session:
        session.add(Submission(file_id=file_id, id=sub_id, title=title, selftext=selftext, word_count=1))
        await session.commit()


async def _add_comment(SessionLocal, file_id: int, *, comment_id: str, body: str = "B", link_id: str | None = None):
    from backend.app.storage_models import Comment

    async with SessionLocal() as session:
        session.add(Comment(file_id=file_id, id=comment_id, body=body, link_id=link_id, word_count=1))
        await session.commit()


async def _add_coding_entry(
    SessionLocal,
    file_id: int,
    *,
    row_type: str = "submission",
    post_id: str,
    code: str,
    quote: str = "e",
    notes: str | None = None,
):
    from backend.app.storage_models import CodingEntry

    async with SessionLocal() as session:
        session.add(
            CodingEntry(
                file_id=file_id,
                row_type=row_type,
                post_id=post_id,
                code=code,
                quote=quote,
                start_offset=0,
                end_offset=len(quote),
                notes=notes,
            )
        )
        await session.commit()


class TestGetCodingArtifact:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/coding/proj_a")
        assert resp.status_code == 401

    async def test_no_matching_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.get(
            "/api/coding/proj_missing", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 404

    async def test_returns_codebook_snapshot_tree_and_counts(
        self, client, route_backed_by_sqlite_jobs, make_token, monkeypatch
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        coding_file = await _make_file(
            route_backed_by_sqlite_jobs, user.id, schemaname="proj_c", content="# Codebook\n- code A"
        )
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s1")
        await _add_coding_entry(route_backed_by_sqlite_jobs, coding_file.id, post_id="s1", code="A")
        monkeypatch.setattr(
            "backend.app.api.coding_routes.parse_codebook_to_json", MagicMock(return_value="[]")
        )

        resp = client.get("/api/coding/proj_c", headers=_auth_headers(make_token, sub=str(user.id)))
        assert resp.status_code == 200
        body = resp.json()
        assert body["codebook_text"] == "# Codebook\n- code A"
        assert body["codebook_tree"] == []
        assert body["total_rows"] == 1
        assert body["total_coded"] == 1
        assert body["code_frequency"] == [{"code": "A", "count": 1}]
        assert body["file"]["schema_name"] == "proj_c"

    async def test_cannot_read_another_users_file(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        owner = await _make_user(route_backed_by_sqlite_jobs, "owner@x.com")
        other = await _make_user(route_backed_by_sqlite_jobs, "other@x.com")
        file_rec = await _make_file(route_backed_by_sqlite_jobs, owner.id, content="secret")

        resp = client.get(
            f"/api/coding/{file_rec.schemaname}", headers=_auth_headers(make_token, sub=str(other.id))
        )
        assert resp.status_code == 404


class TestListCodingRows:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/coding/proj_a/rows")
        assert resp.status_code == 401

    async def test_no_owned_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.get(
            "/api/coding/proj_missing/rows", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 404

    async def test_lists_every_row_coded_or_not(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        coding_file = await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s1", title="Coded post")
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s2", title="Uncoded post")
        await _add_coding_entry(route_backed_by_sqlite_jobs, coding_file.id, post_id="s1", code="A")

        resp = client.get(
            "/api/coding/proj_c/rows", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        by_item = {row["item_id"]: row for row in body["rows"]}
        assert by_item["t3_s1"]["codes"] == [
            {"code": "A", "quote": "e", "start_offset": 0, "end_offset": 1, "notes": None}
        ]
        assert by_item["t3_s2"]["codes"] == []

    async def test_only_uncoded_filter(self, client, route_backed_by_sqlite_jobs, make_token) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        coding_file = await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s1")
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s2")
        await _add_coding_entry(route_backed_by_sqlite_jobs, coding_file.id, post_id="s1", code="A")

        resp = client.get(
            "/api/coding/proj_c/rows?only=uncoded", headers=_auth_headers(make_token, sub=str(user.id))
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["rows"][0]["item_id"] == "t3_s2"

    async def test_cannot_read_another_users_rows(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        owner = await _make_user(route_backed_by_sqlite_jobs, "owner@x.com")
        other = await _make_user(route_backed_by_sqlite_jobs, "other@x.com")
        coding_file = await _make_file(route_backed_by_sqlite_jobs, owner.id, schemaname="proj_c")

        resp = client.get(
            "/api/coding/proj_c/rows", headers=_auth_headers(make_token, sub=str(other.id))
        )
        assert resp.status_code == 404


class TestGetCodingText:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/coding/proj_a/text")
        assert resp.status_code == 401

    async def test_no_owned_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.get(
            "/api/coding/proj_missing/text", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 404

    async def test_renders_canonical_text_from_coding_entries(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        coding_file = await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")
        await _add_coding_entry(route_backed_by_sqlite_jobs, coding_file.id, post_id="s1", code="A", quote="ev")

        resp = client.get(
            "/api/coding/proj_c/text", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 200
        text = resp.json()["text"]
        assert "POST_ID: t3_s1" in text
        assert "CODE: A" in text
        assert "EVIDENCE: ev" in text

    async def test_empty_when_nothing_coded(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")
        resp = client.get(
            "/api/coding/proj_c/text", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == ""


class TestSaveCodingCodebook:
    def test_requires_auth(self, client) -> None:
        resp = client.put("/api/coding/proj_a/codebook", json={"content": "x"})
        assert resp.status_code == 401

    async def test_no_owned_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.put(
            "/api/coding/proj_missing/codebook",
            json={"content": "x"},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404

    async def test_empty_content_returns_422(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c", content="old")
        resp = client.put(
            "/api/coding/proj_c/codebook",
            json={"content": ""},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 422

    async def test_overwrites_codebook_snapshot(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c", content="old")

        resp = client.put(
            "/api/coding/proj_c/codebook",
            json={"content": "new codebook text"},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 200

        follow_up = client.get(
            "/api/coding/proj_c", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert follow_up.json()["codebook_text"] == "new codebook text"


class TestSaveCodingRows:
    def test_requires_auth(self, client) -> None:
        resp = client.put("/api/coding/proj_a/rows", json={"rows": [{"item_id": "t3_1", "entries": []}]})
        assert resp.status_code == 401

    async def test_no_owned_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.put(
            "/api/coding/proj_missing/rows",
            json={"rows": [{"item_id": "t3_1", "entries": []}]},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404

    async def test_empty_rows_list_returns_422(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")
        resp = client.put(
            "/api/coding/proj_c/rows",
            json={"rows": []},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 422

    async def test_replaces_coding_for_submitted_rows(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        coding_file = await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s1")
        await _add_coding_entry(route_backed_by_sqlite_jobs, coding_file.id, post_id="s1", code="OLD")

        resp = client.put(
            "/api/coding/proj_c/rows",
            json={
                "rows": [
                    {
                        "item_id": "t3_s1",
                        "entries": [{"code": "NEW", "quote": "e", "start_offset": 0, "end_offset": 1}],
                    }
                ]
            },
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 200

        rows_resp = client.get(
            "/api/coding/proj_c/rows", headers=_auth_headers(make_token, sub=str(user.id))
        )
        codes = rows_resp.json()["rows"][0]["codes"]
        assert codes == [{"code": "NEW", "quote": "e", "start_offset": 0, "end_offset": 1, "notes": None}]

    async def test_empty_entries_list_clears_a_rows_codes(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        coding_file = await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s1")
        await _add_coding_entry(route_backed_by_sqlite_jobs, coding_file.id, post_id="s1", code="A")

        resp = client.put(
            "/api/coding/proj_c/rows",
            json={"rows": [{"item_id": "t3_s1", "entries": []}]},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 200

        rows_resp = client.get(
            "/api/coding/proj_c/rows", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert rows_resp.json()["rows"][0]["codes"] == []


class TestUpdateCodingMetadata:
    def test_requires_auth(self, client) -> None:
        resp = client.patch("/api/coding/proj_a", json={"display_name": "n"})
        assert resp.status_code == 401

    async def test_no_owned_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.patch(
            "/api/coding/proj_missing",
            json={"display_name": "n"},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404

    async def test_renames_file(self, client, route_backed_by_sqlite_jobs, make_token) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        await _make_file(route_backed_by_sqlite_jobs, user.id, schemaname="proj_c")

        resp = client.patch(
            "/api/coding/proj_c",
            json={"display_name": "renamed"},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 200
        assert resp.json()["file"]["filename"] == "renamed"


class TestDuplicateCoding:
    def test_requires_auth(self, client) -> None:
        resp = client.post("/api/coding/proj_a/duplicate", json={"display_name": "n"})
        assert resp.status_code == 401

    async def test_no_owned_source_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/coding/proj_missing/duplicate",
            json={"display_name": "n"},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404

    async def test_forks_codebook_rows_entries_and_lineage(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        from sqlalchemy import select

        from backend.app.database import FileDependency
        from backend.app.storage_models import CodingEntry, Submission

        user = await _make_user(route_backed_by_sqlite_jobs)
        codebook_file = await _make_file(route_backed_by_sqlite_jobs, user.id, file_type="codebook")
        source_file = await _make_file(
            route_backed_by_sqlite_jobs, user.id, schemaname="proj_src", content="original codebook"
        )
        await _link_dependency(
            route_backed_by_sqlite_jobs, child_file_id=source_file.id, parent_file_id=codebook_file.id
        )
        await _add_submission(route_backed_by_sqlite_jobs, source_file.id, sub_id="s1")
        await _add_coding_entry(route_backed_by_sqlite_jobs, source_file.id, post_id="s1", code="A")

        resp = client.post(
            "/api/coding/proj_src/duplicate",
            json={"display_name": "dup"},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 200
        new_file_id = int(resp.json()["file"]["id"])

        async with route_backed_by_sqlite_jobs() as session:
            deps = (
                await session.execute(select(FileDependency).where(FileDependency.child_file_id == new_file_id))
            ).scalars().all()
            assert {d.parent_file_id for d in deps} == {codebook_file.id, source_file.id}

            copied_subs = (
                await session.execute(select(Submission).where(Submission.file_id == new_file_id))
            ).scalars().all()
            assert [s.id for s in copied_subs] == ["s1"]

            copied_entries = (
                await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file_id))
            ).scalars().all()
            assert [(e.post_id, e.code) for e in copied_entries] == [("s1", "A")]


class TestRecodeItemsKickoff:
    def test_requires_auth(self, client) -> None:
        resp = client.post("/api/coding/proj_a/recode", json={"api_key": "k", "item_ids": ["t3_1"]})
        assert resp.status_code == 401

    async def test_missing_item_ids_returns_422(self, client, auth_cookies) -> None:
        resp = client.post("/api/coding/proj_a/recode", json={"api_key": "k"}, cookies=auth_cookies)
        assert resp.status_code == 422

    async def test_no_owned_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/coding/proj_missing/recode",
            json={"api_key": "k", "item_ids": ["t3_1"]},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404

    async def test_valid_kickoff_returns_202_with_job_id(
        self, client, route_backed_by_sqlite_jobs, make_token, monkeypatch
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        coding_file = await _make_file(
            route_backed_by_sqlite_jobs, user.id, schemaname="proj_c", content="CODEBOOK: code A"
        )
        await _add_submission(route_backed_by_sqlite_jobs, coding_file.id, sub_id="s1")
        classify_mock = AsyncMock(return_value=("POST_ID: t3_s1\nCODE: A\nEVIDENCE: \"x\"", "sys", "usr"))
        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", classify_mock)

        resp = client.post(
            "/api/coding/proj_c/recode",
            json={"api_key": "k", "item_ids": ["t3_s1"]},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], int)


class TestGetCodingComparison:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/coding-comparison")
        assert resp.status_code == 401

    async def test_no_matching_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.get(
            "/api/coding-comparison", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 404

    async def test_matches_by_schema_and_reads_content(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        await _make_file(
            route_backed_by_sqlite_jobs,
            user.id,
            file_type="coding_comparison",
            schemaname="cmp_a",
            content="comparison markdown",
        )

        resp = client.get(
            "/api/coding-comparison?coding_id=cmp_a", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 200
        assert resp.json()["coding_comparison"] == "comparison markdown"

    async def test_cannot_read_another_users_comparison(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        owner = await _make_user(route_backed_by_sqlite_jobs, "owner@x.com")
        other = await _make_user(route_backed_by_sqlite_jobs, "other@x.com")
        file_rec = await _make_file(
            route_backed_by_sqlite_jobs, owner.id, file_type="coding_comparison", content="secret"
        )

        resp = client.get(
            f"/api/coding-comparison?coding_id={file_rec.schemaname}",
            headers=_auth_headers(make_token, sub=str(other.id)),
        )
        assert resp.status_code == 404


class TestApplyCodebookValidation:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/apply-codebook/",
            data={"api_key": "k", "database": "proj_a", "codebook": "1", "report_name": "r"},
        )
        assert resp.status_code == 401

    def test_missing_required_fields_returns_422(self, client, auth_cookies) -> None:
        resp = client.post("/api/apply-codebook/", data={}, cookies=auth_cookies)
        assert resp.status_code == 422

    def test_invalid_codebook_ref_returns_422(self, client, auth_cookies) -> None:
        resp = client.post(
            "/api/apply-codebook/",
            data={
                "api_key": "k",
                "database": "proj_a",
                "codebook": "not-numeric-or-proj",
                "report_name": "r",
            },
            cookies=auth_cookies,
        )
        assert resp.status_code == 422

    async def test_unowned_database_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/apply-codebook/",
            data={
                "api_key": "k",
                "database": "proj_missing",
                "codebook": "1",
                "report_name": "r",
            },
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404

    async def test_codebook_not_found_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        source_file = await _make_file(route_backed_by_sqlite_jobs, user.id, file_type="raw_data")
        resp = client.post(
            "/api/apply-codebook/",
            data={
                "api_key": "k",
                "database": source_file.schemaname,
                "codebook": "proj_missing",
                "report_name": "r",
            },
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404


class TestApplyCodebookKickoff:
    async def test_valid_kickoff_returns_202_with_job_id(
        self, client, route_backed_by_sqlite_jobs, make_token, monkeypatch
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        source_file = await _make_file(route_backed_by_sqlite_jobs, user.id, file_type="raw_data")
        codebook_file = await _make_file(
            route_backed_by_sqlite_jobs, user.id, file_type="codebook", content="CODEBOOK: code A"
        )
        classify_mock = AsyncMock(return_value=("POST_ID: p1\nCODE: A\nEVIDENCE: \"x\"", "sys", "usr"))
        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", classify_mock)

        resp = client.post(
            "/api/apply-codebook/",
            data={
                "api_key": "k",
                "database": source_file.schemaname,
                "codebook": str(codebook_file.id),
                "report_name": "r",
            },
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], int)


class TestCompareCodingsGuard:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/compare-codings/",
            data={"coding_a": "proj_a", "coding_b": "proj_b", "api_key": "k", "name": "n"},
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "form",
        [
            {"coding_a": "not_proj", "coding_b": "proj_b", "api_key": "k", "name": "n"},
            {"coding_a": "proj_a", "coding_b": "not_proj", "api_key": "k", "name": "n"},
        ],
    )
    def test_non_proj_schema_returns_400(self, client, auth_cookies, form) -> None:
        resp = client.post("/api/compare-codings/", data=form, cookies=auth_cookies)
        assert resp.status_code == 400

    async def test_unowned_schema_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/compare-codings/",
            data={
                "coding_a": "proj_missing_a",
                "coding_b": "proj_missing_b",
                "api_key": "k",
                "name": "n",
            },
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 404

    async def test_valid_kickoff_returns_202_with_job_id(
        self, client, route_backed_by_sqlite_jobs, make_token, monkeypatch
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        file_a = await _make_file(route_backed_by_sqlite_jobs, user.id, content="coding a text")
        file_b = await _make_file(route_backed_by_sqlite_jobs, user.id, content="coding b text")
        llm_mock = AsyncMock(return_value="mocked comparison result")
        # compare_codings' job handler imports get_client via a LOCAL
        # import inside the handler body, so it must be patched at its
        # source module, not on coding_service.
        monkeypatch.setattr("backend.scripts.codebook_generator.get_client", llm_mock)

        resp = client.post(
            "/api/compare-codings/",
            data={
                "coding_a": file_a.schemaname,
                "coding_b": file_b.schemaname,
                "api_key": "k",
                "name": "n",
            },
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], int)


class TestSummarizeCodingGuard:
    """``summarize-coding`` kicks off a background job -- the
    schema-prefix/api_key guard clauses still reject synchronously with
    the same 400s as before (``coding_service.start_summarize_coding_job``
    raises before touching the DB or spawning a job), but a valid request
    returns ``202 {"job_id", "status": "pending"}`` instead of a blocking
    ``200 {"summary": ...}``. Content-not-found is no longer a synchronous
    400 either, since reading the coding artifact's content now happens
    inside the job handler, not the kickoff request -- see
    ``tests/backend/services/test_coding_service.py`` for that path.
    """

    def test_requires_auth_returns_401(self, client) -> None:
        resp = client.post(
            "/api/summarize-coding/", data={"coding": "proj_a", "api_key": "k", "name": "n"}
        )
        assert resp.status_code == 401

    def test_non_proj_schema_returns_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/summarize-coding/",
            data={"coding": "not_proj", "api_key": "k", "name": "n"},
            headers=_auth_headers(make_token),
        )
        assert resp.status_code == 400
        assert "proj_" in resp.json()["error"]

    # Note: an empty-string `api_key` can't reach the route's own guard
    # clause to exercise it at this layer -- FastAPI's `Form(...)` already
    # 422s an empty/absent value before the handler runs. The `api_key`
    # guard clause itself (for callers that reach it directly, e.g. a
    # future non-Form caller) is covered at the service layer in
    # tests/backend/services/test_coding_service.py::TestStartSummarizeCodingJobValidation.

    async def test_valid_kickoff_returns_202_with_job_id(
        self, client, make_token, route_backed_by_sqlite_jobs, monkeypatch
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        source_file = await _make_file(route_backed_by_sqlite_jobs, user.id, content="coded rows")
        summarize_mock = AsyncMock(return_value="mocked summary")
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.summarize_coding", summarize_mock
        )
        resp = client.post(
            "/api/summarize-coding/",
            data={"coding": source_file.schemaname, "api_key": "k", "name": "n"},
            headers=_auth_headers(make_token, sub=str(user.id)),
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], int)
