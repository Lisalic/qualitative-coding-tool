"""Guard-level (and, where SQLite can carry it, happy-path) tests for
backend/app/api/coding_routes.py.

Stage 8 converts every endpoint here except `summarize-coding` (Stage 4,
`TestSummarizeCodingGuard` -- left untouched) to the same pattern: async,
`Depends(require_user_id)` + `Depends(get_async_db)`, thin delegation to
`backend/app/services/coding_service.py`. `apply-codebook` and
`compare-codings` become `202 {job_id, status}` kickoff endpoints, exactly
like `summarize-coding` already was. Since every endpoint is now
ORM-backed (no more raw-SQL-against-a-mocked-`engine` guard tests), these
run against the in-memory async SQLite fixtures rather than mocking
`engine`/`async_engine` -- see
`tests/backend/services/test_coding_service.py` for deeper coverage of
the service functions themselves (including the job handlers'
`coding_entries` population).
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
    """Insert a ``File`` (optionally with an ``artifact_content`` row)
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


class TestGetCodedData:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/coded-data")
        assert resp.status_code == 401

    async def test_no_matching_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        await _make_user(route_backed_by_sqlite_jobs)
        resp = client.get("/api/coded-data", headers=_auth_headers(make_token))
        assert resp.status_code == 404

    async def test_matches_by_schema_and_reads_content(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        await _make_file(
            route_backed_by_sqlite_jobs,
            user.id,
            schemaname="proj_a",
            content="coded content",
        )

        resp = client.get(
            "/api/coded-data?coded_id=proj_a", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["coded_data"] == "coded content"
        assert body["codebook_text"] == ""
        assert body["codebook_tree"] == []

    async def test_includes_parent_codebook_text_and_tree(
        self, client, route_backed_by_sqlite_jobs, make_token, monkeypatch
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        codebook_file = await _make_file(
            route_backed_by_sqlite_jobs,
            user.id,
            file_type="codebook",
            content="# Codebook\n- code A",
        )
        coding_file = await _make_file(
            route_backed_by_sqlite_jobs,
            user.id,
            schemaname="proj_c",
            content="POST_ID: p1",
        )
        await _link_dependency(
            route_backed_by_sqlite_jobs, child_file_id=coding_file.id, parent_file_id=codebook_file.id
        )
        monkeypatch.setattr(
            "backend.app.api.coding_routes.parse_codebook_to_json",
            MagicMock(return_value="[]"),
        )

        resp = client.get(
            "/api/coded-data?coded_id=proj_c", headers=_auth_headers(make_token, sub=str(user.id))
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["codebook_text"] == "# Codebook\n- code A"
        assert body["codebook_tree"] == []

    async def test_cannot_read_another_users_file(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        owner = await _make_user(route_backed_by_sqlite_jobs, "owner@x.com")
        other = await _make_user(route_backed_by_sqlite_jobs, "other@x.com")
        file_rec = await _make_file(route_backed_by_sqlite_jobs, owner.id, content="secret")

        resp = client.get(
            f"/api/coded-data?coded_id={file_rec.schemaname}",
            headers=_auth_headers(make_token, sub=str(other.id)),
        )
        assert resp.status_code == 404


class TestSaveFileCodedData:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/save-file-coded-data/", data={"schema_name": "proj_a", "content": "x"}
        )
        assert resp.status_code == 401

    async def test_missing_fields_returns_400(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/save-file-coded-data/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={},
        )
        assert resp.status_code == 400

    async def test_no_owned_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/save-file-coded-data/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={"schema_name": "proj_missing", "content": "x"},
        )
        assert resp.status_code == 404

    async def test_saves_content_and_renames(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        file_rec = await _make_file(
            route_backed_by_sqlite_jobs, user.id, schemaname="proj_a", content="old content"
        )

        resp = client.post(
            "/api/save-file-coded-data/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={"schema_name": "proj_a", "content": "new content", "display_name": "renamed"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(file_rec.id)
        assert body["filename"] == "renamed"

        # A caller-supplied `codebook_text` field is tolerated (parsed,
        # ignored) rather than rejected -- backward compatibility for a
        # not-yet-updated client.
        resp2 = client.post(
            "/api/save-file-coded-data/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={"schema_name": "proj_a", "content": "v3", "codebook_text": "ignored"},
        )
        assert resp2.status_code == 200


class TestSaveFileCodedDataDuplicate:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/save-file-coded-data-duplicate/",
            data={"source_schema_name": "proj_a", "content": "x", "display_name": "y"},
        )
        assert resp.status_code == 401

    async def test_missing_fields_returns_400(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/save-file-coded-data-duplicate/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={},
        )
        assert resp.status_code == 400

    async def test_no_owned_source_file_returns_404(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        user = await _make_user(route_backed_by_sqlite_jobs)
        resp = client.post(
            "/api/save-file-coded-data-duplicate/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={"source_schema_name": "proj_missing", "content": "x", "display_name": "y"},
        )
        assert resp.status_code == 404

    async def test_duplicates_content_and_dependencies(
        self, client, route_backed_by_sqlite_jobs, make_token
    ) -> None:
        from sqlalchemy import select

        from backend.app.database import FileDependency

        user = await _make_user(route_backed_by_sqlite_jobs)
        codebook_file = await _make_file(route_backed_by_sqlite_jobs, user.id, file_type="codebook")
        source_file = await _make_file(
            route_backed_by_sqlite_jobs, user.id, schemaname="proj_src", content="original"
        )
        await _link_dependency(
            route_backed_by_sqlite_jobs, child_file_id=source_file.id, parent_file_id=codebook_file.id
        )

        resp = client.post(
            "/api/save-file-coded-data-duplicate/",
            headers=_auth_headers(make_token, sub=str(user.id)),
            data={
                "source_schema_name": "proj_src",
                "content": "duplicated content",
                "display_name": "dup",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "dup"
        new_file_id = int(body["id"])

        async with route_backed_by_sqlite_jobs() as session:
            deps = (
                await session.execute(select(FileDependency).where(FileDependency.child_file_id == new_file_id))
            ).scalars().all()
            parent_ids = {d.parent_file_id for d in deps}
            # Lineage preserved via copied FileDependency rows -- both the
            # source's own parent (the codebook) and the source file
            # itself -- no redundant codebook-text copy involved.
            assert parent_ids == {codebook_file.id, source_file.id}


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
    """``summarize-coding`` now kicks off a background job (Stage 4) instead
    of running the LLM call inline -- the schema-prefix/api_key guard
    clauses still reject synchronously with the same 400s as before
    (``coding_service.start_summarize_coding_job`` raises before touching
    the DB or spawning a job), but a valid request now returns
    ``202 {"job_id", "status": "pending"}`` instead of a blocking
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
