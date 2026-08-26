"""Guard-level tests for the raw-SQL and OpenRouter-backed routes across
codebook_routes.py, coding_routes.py, data_routes.py, content_routes.py,
and file_routes.py.

These routes' *full* happy path needs real Postgres semantics (CREATE
SCHEMA, information_schema introspection, generated columns, RANDOM()
sampling) that SQLite can't faithfully stand in for -- that's covered by
the opt-in integration suite (tests/backend/integration/). Here we test
what's reachable without Postgres: request validation (422), auth
gating, schema-name guards, and -- for the AI routes -- that requests are
accepted/rejected correctly at the kickoff boundary. codebook_routes.py's
AI endpoints (generate-codebook, compare-codebooks) are now background-job
kickoffs (Stage 7): this file covers their 422/401/404/202 guard behavior,
while the job handlers themselves (LLM-call mocking, persistence) are
covered in tests/backend/services/test_codebook_service.py.

Also documents (without "fixing", per the plan) a real architectural
finding: some routes still check authentication *after* already doing
expensive raw-SQL/ORM work for endpoints not yet converted to this
module's job-kickoff pattern.
"""

import pytest

pytestmark = pytest.mark.usefixtures("override_db")


# ---------------------------------------------------------------------------
# data_routes.py -- now fully async, ORM-backed via the fixed storage
# tables (Stage 6). Every endpoint requires auth (added to the 3 that were
# missing it -- word_count_ranges/file_entries/get_comments_for_submission
# -- plus get_post_contents, whose service-layer resolution now depends on
# an owning user_id too) and resolves its schema/database identifier to an
# ownership-scoped file_id via repositories/file_repo.py before any query
# runs, rather than validating a raw schema-name string and then splicing
# it into SQL.
# ---------------------------------------------------------------------------


@pytest.fixture()
def route_backed_by_sqlite_jobs(async_sqlite_engine, monkeypatch):
    """Point the route's ``get_async_db`` dependency, and the background
    job runner's session factory, at the same in-memory SQLite engine --
    so both plain CRUD-style route tests (word-count-ranges, file-entries,
    comments, post-contents) and a filter-data job kicked off through the
    ``TestClient`` see the same data. Same pattern as
    ``tests/backend/routes/test_coding_routes.py::route_backed_by_sqlite_jobs``.
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
    monkeypatch.setattr("backend.app.services.data_service.AsyncSessionLocal", SessionLocal)
    try:
        yield SessionLocal
    finally:
        fastapi_app.dependency_overrides.pop(get_async_db, None)


async def _make_file(SessionLocal, user_id: int, *, file_type: str = "raw_data", submissions=None, comments=None):
    """Insert a ``File`` (plus optional ``Submission``/``Comment`` rows)
    directly via the ORM, owned by ``user_id`` -- no real upload pipeline
    needed since these tests only exercise the read/query side.
    """
    import secrets

    from backend.app.database import File
    from backend.app.storage_models import Comment, Submission

    async with SessionLocal() as session:
        file_rec = File(
            user_id=user_id,
            filename="f",
            schemaname=f"proj_{secrets.token_hex(4)}",
            file_type=file_type,
        )
        session.add(file_rec)
        await session.flush()
        for row in submissions or []:
            session.add(Submission(file_id=file_rec.id, **row))
        for row in comments or []:
            session.add(Comment(file_id=file_rec.id, **row))
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


class TestWordCountRangesGuard:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/word-count-ranges/?schema=proj_a")
        assert resp.status_code == 401

    @pytest.mark.parametrize("schema", ["", "1abc", "proj a", "proj-a", "proj_a; DROP TABLE x"])
    def test_invalid_schema_returns_400(self, client, override_async_db, auth_cookies, schema) -> None:
        resp = client.get(f"/api/word-count-ranges/?schema={schema}", cookies=auth_cookies)
        assert resp.status_code == 400

    def test_unknown_schema_returns_404(self, client, override_async_db, auth_cookies) -> None:
        # Structural fix in action: a well-formed but nonexistent/unowned
        # schema resolves to nothing via file_repo, not a bare empty result.
        resp = client.get("/api/word-count-ranges/?schema=proj_missing", cookies=auth_cookies)
        assert resp.status_code == 404

    async def test_db_suffix_stripped_and_bins_word_counts(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_rec = await _make_file(
            route_backed_by_sqlite_jobs,
            user_id=1,
            submissions=[
                {"id": "s1", "title": "hello", "selftext": "world", "word_count": 12},
                {"id": "s2", "title": "a b c d e f g h i j k l", "selftext": "", "word_count": 47},
            ],
        )
        resp = client.get(
            f"/api/word-count-ranges/?schema={file_rec.schemaname}.db",
            cookies={"access_token": make_token(sub="1")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert {"min_words": 10, "count": 1} in body["submissions"]
        assert {"min_words": 40, "count": 1} in body["submissions"]
        assert body["comments"] == []

    async def test_cannot_read_another_users_file(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_rec = await _make_file(route_backed_by_sqlite_jobs, user_id=1)
        resp = client.get(
            f"/api/word-count-ranges/?schema={file_rec.schemaname}",
            cookies={"access_token": make_token(sub="2")},
        )
        assert resp.status_code == 404


class TestFileEntriesGuard:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/file-entries/?schema=proj_a")
        assert resp.status_code == 401

    def test_invalid_schema_returns_400(self, client, override_async_db, auth_cookies) -> None:
        resp = client.get("/api/file-entries/?schema=1invalid", cookies=auth_cookies)
        assert resp.status_code == 400

    def test_missing_schema_returns_422(self, client, auth_cookies) -> None:
        # `schema` has no default -> FastAPI 422s before the handler body runs.
        resp = client.get("/api/file-entries/", cookies=auth_cookies)
        assert resp.status_code == 422

    async def test_returns_paginated_rows_and_counts(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_rec = await _make_file(
            route_backed_by_sqlite_jobs,
            user_id=1,
            submissions=[{"id": "s1", "title": "t", "selftext": "x", "word_count": 1}],
            comments=[{"id": "c1", "body": "hi", "link_id": "s1", "word_count": 1}],
        )
        resp = client.get(
            f"/api/file-entries/?schema={file_rec.schemaname}&limit=10&offset=0",
            cookies={"access_token": make_token(sub="1")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_submissions"] == 1
        assert body["total_comments"] == 1
        assert body["submissions"][0]["id"] == "s1"
        assert body["comments"][0]["id"] == "c1"
        # No `file_id` leaking into the serialized row -- matches the old
        # per-schema shape, where there was no such column at all.
        assert "file_id" not in body["submissions"][0]


class TestCommentsForSubmissionGuard:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/comments/sub1?database=proj_a")
        assert resp.status_code == 401

    @pytest.mark.parametrize("database", ["", "not_proj_prefixed", "proj"])
    def test_non_proj_schema_returns_400(self, client, override_async_db, auth_cookies, database) -> None:
        resp = client.get(f"/api/comments/sub1?database={database}", cookies=auth_cookies)
        assert resp.status_code == 400

    async def test_returns_comments_for_submission(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_rec = await _make_file(
            route_backed_by_sqlite_jobs,
            user_id=1,
            comments=[
                {"id": "c1", "body": "hi", "link_id": "sub1", "created_utc": 1, "word_count": 1},
                {"id": "c2", "body": "unrelated", "link_id": "other", "created_utc": 1, "word_count": 1},
            ],
        )
        resp = client.get(
            f"/api/comments/sub1?database={file_rec.schemaname}",
            cookies={"access_token": make_token(sub="1")},
        )
        assert resp.status_code == 200
        comments = resp.json()["comments"]
        assert [c["id"] for c in comments] == ["c1"]


class TestPostContentsGuard:
    def test_requires_auth(self, client) -> None:
        resp = client.post("/api/post-contents/", json={"schema": "proj_a", "post_ids": ["1"]})
        assert resp.status_code == 401

    def test_missing_schema_returns_422(self, client, override_async_db, auth_cookies) -> None:
        # PostContentsRequest is a real Pydantic model now (was a bare
        # `dict` body) -- a missing required field is FastAPI's own
        # request-validation 422, matching every other schema-backed route.
        resp = client.post("/api/post-contents/", json={"post_ids": ["1"]}, cookies=auth_cookies)
        assert resp.status_code == 422

    def test_missing_post_ids_returns_422(self, client, override_async_db, auth_cookies) -> None:
        resp = client.post("/api/post-contents/", json={"schema": "proj_a"}, cookies=auth_cookies)
        assert resp.status_code == 422

    def test_empty_post_ids_list_returns_422(self, client, override_async_db, auth_cookies) -> None:
        # `post_ids` has `min_length=1` on PostContentsRequest.
        resp = client.post(
            "/api/post-contents/", json={"schema": "proj_a", "post_ids": []}, cookies=auth_cookies
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "schema", ["1abc", "proj a", "proj-a", 'proj_a"; DROP TABLE x; --', "not_proj_prefixed"]
    )
    def test_invalid_schema_returns_400(
        self, client, override_async_db, auth_cookies, schema
    ) -> None:
        # Regression test: this endpoint used to splice `schema` straight
        # into a SELECT with zero validation. Now it never touches SQL at
        # all -- require_valid_schema rejects it before file_repo runs.
        resp = client.post(
            "/api/post-contents/", json={"schema": schema, "post_ids": ["1"]}, cookies=auth_cookies
        )
        assert resp.status_code == 400

    def test_unowned_schema_returns_404(self, client, override_async_db, auth_cookies) -> None:
        resp = client.post(
            "/api/post-contents/",
            json={"schema": "proj_missing", "post_ids": ["1"]},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404

    def test_malformed_json_body_returns_422(self, client, auth_cookies) -> None:
        # Body parsing is now FastAPI's own `Body(...)` -- a request that
        # fails JSON decoding is a validation error (422), not caught by a
        # broad handler `except Exception` -> 500 the way the old
        # hand-rolled `await request.json()` parsing was.
        resp = client.post(
            "/api/post-contents/",
            headers={"Content-Type": "application/json"},
            content=b"{not valid json",
            cookies=auth_cookies,
        )
        assert resp.status_code == 422

    async def test_returns_title_and_content_for_matching_ids(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_rec = await _make_file(
            route_backed_by_sqlite_jobs,
            user_id=1,
            submissions=[
                {"id": "s1", "title": "Title 1", "selftext": "Body 1", "word_count": 2},
                {"id": "s2", "title": "Title 2", "selftext": "Body 2", "word_count": 2},
            ],
        )
        resp = client.post(
            "/api/post-contents/",
            json={"schema": file_rec.schemaname, "post_ids": ["s1"]},
            cookies={"access_token": make_token(sub="1")},
        )
        assert resp.status_code == 200
        contents = resp.json()["contents"]
        assert contents == {
            "s1": {
                "type": "submission",
                "title": "Title 1",
                "content": "Body 1",
                "parent_id": None,
                "parent_title": None,
            }
        }


class TestFilterDataValidation:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/filter-data/",
            data={"api_key": "k", "database": "proj_a", "name": "n", "model": "m"},
        )
        assert resp.status_code == 401

    def test_missing_required_fields_returns_422(self, client, auth_cookies) -> None:
        # With every Form(...) field absent, FastAPI's own missing-field
        # checks are collected passively (not raised immediately) while
        # `require_user_id` raises eagerly -- so this needs valid auth to
        # actually exercise the missing-fields guard rather than 401 first.
        resp = client.post("/api/filter-data/", data={}, cookies=auth_cookies)
        assert resp.status_code == 422

    def test_non_proj_database_returns_422(self, client) -> None:
        resp = client.post(
            "/api/filter-data/",
            data={"api_key": "k", "database": "not_proj", "name": "n", "model": "m"},
        )
        assert resp.status_code == 422

    def test_sample_percentage_out_of_range_returns_422(self, client) -> None:
        resp = client.post(
            "/api/filter-data/",
            data={
                "api_key": "k",
                "database": "proj_a",
                "name": "n",
                "model": "m",
                "sample_percentage": "0",
            },
        )
        assert resp.status_code == 422

    def test_unowned_database_returns_404(self, client, override_async_db, auth_cookies) -> None:
        resp = client.post(
            "/api/filter-data/",
            data={"api_key": "k", "database": "proj_missing", "name": "n", "model": "m"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404


class TestFilterDataKickoff:
    """``filter-data`` now kicks off a background job (Stage 6, same
    pattern as ``summarize-coding`` in Stage 4) instead of running the
    tag-expansion/AI-filtering/materialization pipeline inline -- the
    schema/api_key/ownership guard clauses still reject synchronously
    (``data_service.start_filter_data_job`` raises before touching the job
    table), but a valid request now returns
    ``202 {"job_id", "status": "pending"}`` instead of a blocking
    ``200`` with the filtered counts. See
    ``tests/backend/services/test_data_service.py`` for the job handler's
    own behavior (sampling, tag/AI filtering, materialization).
    """

    async def test_valid_kickoff_returns_202_with_job_id(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_rec = await _make_file(
            route_backed_by_sqlite_jobs,
            user_id=1,
            submissions=[{"id": "s1", "title": "t", "selftext": "x", "word_count": 1}],
        )
        resp = client.post(
            "/api/filter-data/",
            data={
                "api_key": "k",
                "database": file_rec.schemaname,
                "name": "n",
                "model": "m",
            },
            cookies={"access_token": make_token(sub="1")},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], int)


# ---------------------------------------------------------------------------
# codebook_routes.py -- generate-codebook / compare-codebooks
#
# Stage 7 converted both into background-job kickoff endpoints (same
# pattern as data_routes.py::filter_data in Stage 6) and added the
# `require_user_id` auth dependency both were missing (generate-codebook
# checked it late, inline; compare-codebooks never checked it at all -- see
# TestCompareCodebooksAuth below). Sampling/LLM-call/persistence now happen
# in the job handler, not synchronously in the route, so validation guard
# clauses that used to return a synchronous 400 (e.g. "no records sampled")
# now surface as a failed job instead -- covered in
# tests/backend/services/test_codebook_service.py, not here.
# ---------------------------------------------------------------------------


@pytest.fixture()
def codebook_route_backed_by_sqlite_jobs(async_sqlite_engine, monkeypatch):
    """Same shape as `route_backed_by_sqlite_jobs` above, but also points
    `codebook_service`'s module-level `AsyncSessionLocal` at the in-memory
    SQLite engine, since its job handlers open their own session the same
    way `data_service`'s do.
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
    monkeypatch.setattr("backend.app.services.codebook_service.AsyncSessionLocal", SessionLocal)
    try:
        yield SessionLocal
    finally:
        fastapi_app.dependency_overrides.pop(get_async_db, None)


async def _make_codebook_file(SessionLocal, user_id: int, *, file_type: str = "raw_data"):
    import secrets

    from backend.app.database import File

    async with SessionLocal() as session:
        file_rec = File(
            user_id=user_id,
            filename="f",
            schemaname=f"proj_{secrets.token_hex(4)}",
            file_type=file_type,
        )
        session.add(file_rec)
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


class TestGenerateCodebookValidation:
    def test_missing_required_fields_returns_422(self, client, auth_cookies) -> None:
        # With every Form(...) field absent, FastAPI's own missing-field
        # checks are collected passively (not raised immediately) while
        # `require_user_id` raises eagerly -- so this needs valid auth to
        # actually exercise the missing-fields guard rather than 401 first
        # (same ordering documented on TestFilterDataValidation above).
        resp = client.post("/api/generate-codebook/", data={}, cookies=auth_cookies)
        assert resp.status_code == 422

    def test_requires_auth(self, client) -> None:
        # Regression test: the old route checked auth only after already
        # doing the raw-SQL sample and the LLM call. `require_user_id` now
        # runs as a route dependency, before the job is even enqueued.
        resp = client.post(
            "/api/generate-codebook/",
            data={"api_key": "k", "database": "proj_a", "name": "n"},
        )
        assert resp.status_code == 401

    def test_non_proj_database_returns_422(self, client) -> None:
        resp = client.post(
            "/api/generate-codebook/",
            data={"api_key": "k", "database": "not_proj", "name": "n"},
        )
        assert resp.status_code == 422

    def test_unowned_database_returns_404(self, client, override_async_db, auth_cookies) -> None:
        resp = client.post(
            "/api/generate-codebook/",
            data={"api_key": "k", "database": "proj_missing", "name": "n"},
            cookies=auth_cookies,
        )
        assert resp.status_code == 404


class TestGenerateCodebookKickoff:
    async def test_valid_kickoff_returns_202_with_job_id(
        self, client, codebook_route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_rec = await _make_codebook_file(codebook_route_backed_by_sqlite_jobs, user_id=1)
        resp = client.post(
            "/api/generate-codebook/",
            data={"api_key": "k", "database": file_rec.schemaname, "name": "n"},
            cookies={"access_token": make_token(sub="1")},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], int)


class TestCompareCodebooksValidation:
    @pytest.mark.parametrize(
        "form",
        [
            {"codebook_a": "not_proj", "codebook_b": "proj_b", "api_key": "k", "name": "n"},
            {"codebook_a": "proj_a", "codebook_b": "not_proj", "api_key": "k", "name": "n"},
        ],
    )
    def test_non_proj_schema_returns_422(self, client, form) -> None:
        # Now a Pydantic field-pattern check (like generate-codebook's
        # `database` field), so it fails at request-parsing time -- 422,
        # not the old route's hand-rolled 400.
        resp = client.post("/api/compare-codebooks/", data=form)
        assert resp.status_code == 422

    def test_requires_auth(self, client) -> None:
        # Regression test: this endpoint used to never call
        # get_user_id_from_request at all -- reachable by anyone with the
        # schema names, no login needed. `require_user_id` closes that gap.
        resp = client.post(
            "/api/compare-codebooks/",
            data={"codebook_a": "proj_a", "codebook_b": "proj_b", "api_key": "k", "name": "n"},
        )
        assert resp.status_code == 401

    def test_unowned_codebook_returns_404(self, client, override_async_db, auth_cookies) -> None:
        resp = client.post(
            "/api/compare-codebooks/",
            data={
                "codebook_a": "proj_missing_a",
                "codebook_b": "proj_missing_b",
                "api_key": "k",
                "name": "n",
            },
            cookies=auth_cookies,
        )
        assert resp.status_code == 404


class TestCompareCodebooksKickoff:
    async def test_valid_kickoff_returns_202_with_job_id(
        self, client, codebook_route_backed_by_sqlite_jobs, make_token
    ) -> None:
        file_a = await _make_codebook_file(codebook_route_backed_by_sqlite_jobs, user_id=1, file_type="codebook")
        file_b = await _make_codebook_file(codebook_route_backed_by_sqlite_jobs, user_id=1, file_type="codebook")
        resp = client.post(
            "/api/compare-codebooks/",
            data={
                "codebook_a": file_a.schemaname,
                "codebook_b": file_b.schemaname,
                "api_key": "k",
                "name": "n",
            },
            cookies={"access_token": make_token(sub="1")},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert isinstance(body["job_id"], int)


# ---------------------------------------------------------------------------
# content_routes.py -- save-comparison / save-summary / summary/{id}
# ---------------------------------------------------------------------------


class TestSaveComparisonAndSummaryAuth:
    def test_save_comparison_requires_auth_before_any_db_work(self, client) -> None:
        # No AsyncDatabaseManager/engine patch needed: with a sentinel
        # Postgres DATABASE_URL, a call that reaches the DB would hang or
        # error loudly -- getting a clean 401 here proves auth is checked
        # first for this route (unlike generate-codebook above).
        resp = client.post("/api/save-comparison/", data={"content": "x", "title": "t"})
        assert resp.status_code == 401

    def test_save_summary_requires_auth_before_content_check(self, client) -> None:
        # Non-empty content: httpx's TestClient drops empty-string form
        # fields entirely when encoding `data=`, so an actually-empty
        # `content` can't be sent this way (see the `content: str =
        # Form(...)`-required 422 elsewhere in this file). This test only
        # needs to prove auth is checked before the DB/schema work runs.
        resp = client.post("/api/save-summary/", data={"content": "x", "name": "n"})
        assert resp.status_code == 401


class TestGetSummaryFile:
    def test_requires_auth(self, client, override_async_db) -> None:
        # Regression test: this endpoint used to return summary content
        # (or a 404) with no auth check at all -- any caller, authenticated
        # or not, could read any user's saved summaries.
        resp = client.get("/api/summary/nonexistent")
        assert resp.status_code == 401

    def test_no_id_and_no_summaries_returns_404(self, client, override_async_db) -> None:
        # `/summary/` (empty path segment) never matches
        # `/summary/{summary_id}` at all -- this is a framework-level 404,
        # reached without auth being checked, whether or not a caller is
        # authenticated.
        resp = client.get("/api/summary/")
        assert resp.status_code == 404

    def test_unmatched_id_returns_404(self, client, override_async_db, auth_cookies) -> None:
        resp = client.get("/api/summary/nonexistent", cookies=auth_cookies)
        assert resp.status_code == 404

    def test_cannot_read_another_users_summary(
        self, client, override_async_db, make_token
    ) -> None:
        # Save a summary as user 1, then confirm user 2 can't fetch it by
        # schemaname -- proves get_summary_file is ownership-scoped, not
        # just authenticated.
        save_resp = client.post(
            "/api/save-summary/",
            data={"content": "secret", "name": "owner-only"},
            cookies={"access_token": make_token(sub="1")},
        )
        assert save_resp.status_code == 200
        schema_name = save_resp.json()["file"]["schema_name"]

        resp = client.get(
            f"/api/summary/{schema_name}", cookies={"access_token": make_token(sub="2")}
        )
        assert resp.status_code == 404

    def test_owner_can_read_own_summary(self, client, override_async_db, make_token) -> None:
        save_resp = client.post(
            "/api/save-summary/",
            data={"content": "my content", "name": "mine"},
            cookies={"access_token": make_token(sub="1")},
        )
        assert save_resp.status_code == 200
        schema_name = save_resp.json()["file"]["schema_name"]

        resp = client.get(
            f"/api/summary/{schema_name}", cookies={"access_token": make_token(sub="1")}
        )
        assert resp.status_code == 200
        assert resp.json()["summary"]["content"] == "my content"
        assert resp.json()["summary"]["display_name"] == "mine"
