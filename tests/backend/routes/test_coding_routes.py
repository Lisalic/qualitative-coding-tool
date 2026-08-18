"""Guard-level tests for backend/app/api/coding_routes.py.

Same rationale as test_ai_and_raw_sql_routes.py: full artifact-creation
flows need real Postgres and are covered by the opt-in integration
suite. Here: ORM-only paths run against SQLite; raw-SQL/network paths
are tested up to their validation/auth/guard boundary with `engine`/
`async_engine` patched to mocks or sentinels.
"""

from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.usefixtures("override_db")


def _mock_sync_engine_no_tables():
    conn = MagicMock()
    result = MagicMock()
    result.scalar.return_value = False  # every to_regclass() lookup -> "doesn't exist"
    result.fetchone.return_value = None
    conn.execute.return_value = result

    @contextmanager
    def _connect():
        yield conn

    engine = MagicMock()
    engine.connect.side_effect = _connect
    return engine


def _mock_async_engine_no_row():
    conn = AsyncMock()
    result = MagicMock()
    result.fetchone.return_value = None
    conn.execute.return_value = result

    @asynccontextmanager
    async def _connect():
        yield conn

    engine = MagicMock()
    engine.connect.side_effect = _connect
    return engine


def _mock_async_engine_with_content(text_value: str):
    conn = AsyncMock()
    result = MagicMock()
    result.fetchone.return_value = (text_value,)
    conn.execute.return_value = result

    @asynccontextmanager
    async def _connect():
        yield conn

    engine = MagicMock()
    engine.connect.side_effect = _connect
    return engine


def _auth_headers(make_token):
    return {"Authorization": f"Bearer {make_token()}"}


class TestGetCodedData:
    def test_no_matching_file_returns_404(self, client) -> None:
        resp = client.get("/api/coded-data")
        assert resp.status_code == 404

    def test_matches_by_schema_and_reads_content(self, client, db_session, monkeypatch) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        db_session.add(
            File(user_id=user.id, filename="c", schemaname="proj_a", file_type="coding")
        )
        db_session.commit()

        conn = MagicMock()

        def _execute(clause, params=None):
            # `str(clause)` is the literal SQL text with `:tbl` as a bind
            # placeholder -- both to_regclass() calls compile to the same
            # string, so which table they're checking is only visible in
            # `params["tbl"]`, not in the compiled SQL.
            sql = str(clause)
            result = MagicMock()
            if "to_regclass" in sql:
                tbl = (params or {}).get("tbl", "")
                result.scalar.return_value = not tbl.endswith(".codebook")
            elif "content_store" in sql:
                result.fetchone.return_value = ("coded content",)
            else:
                result.fetchone.return_value = None
                result.scalar.return_value = None
            return result

        conn.execute.side_effect = _execute

        @contextmanager
        def _connect():
            yield conn

        engine = MagicMock()
        engine.connect.side_effect = _connect
        monkeypatch.setattr("backend.app.api.coding_routes.engine", engine)

        resp = client.get("/api/coded-data?coded_id=proj_a")
        assert resp.status_code == 200
        assert resp.json()["coded_data"] == "coded content"
        assert resp.json()["codebook_tree"] == []


class TestSaveFileCodedData:
    def test_requires_auth(self, client) -> None:
        resp = client.post(
            "/api/save-file-coded-data/", data={"schema_name": "proj_a", "content": "x"}
        )
        assert resp.status_code == 401

    def test_missing_fields_returns_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/save-file-coded-data/",
            headers=_auth_headers(make_token),
            data={},
        )
        assert resp.status_code == 400

    def test_no_owned_file_returns_404_before_engine(
        self, client, make_token, unused_engine, monkeypatch
    ) -> None:
        # No File row exists for this user+schema -> 404 before the
        # async_engine schema-write is ever attempted.
        monkeypatch.setattr("backend.app.api.coding_routes.async_engine", unused_engine)
        resp = client.post(
            "/api/save-file-coded-data/",
            headers=_auth_headers(make_token),
            data={"schema_name": "proj_missing", "content": "x"},
        )
        assert resp.status_code == 404


class TestApplyCodebookValidation:
    def test_missing_required_fields_returns_422(self, client) -> None:
        resp = client.post("/api/apply-codebook/", data={})
        assert resp.status_code == 422

    def test_invalid_codebook_ref_returns_422(self, client) -> None:
        resp = client.post(
            "/api/apply-codebook/",
            data={
                "api_key": "k",
                "database": "proj_a",
                "codebook": "not-numeric-or-proj",
                "report_name": "r",
            },
        )
        assert resp.status_code == 422

    def test_codebook_not_found_returns_404(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.api.coding_routes.engine", _mock_sync_engine_no_tables()
        )
        resp = client.post(
            "/api/apply-codebook/",
            data={
                "api_key": "k",
                "database": "proj_a",
                "codebook": "proj_missing",
                "report_name": "r",
            },
        )
        assert resp.status_code == 404

    def test_auth_is_checked_after_the_llm_call_not_before(self, client, monkeypatch) -> None:
        """Same finding as generate-codebook: `apply_codebook` samples the
        schema, resolves+loads the codebook, and runs classification
        BEFORE checking `get_user_id_from_request`. Documented, not
        fixed, per the plan.
        """
        conn = MagicMock()

        def _execute(clause, params=None):
            sql = str(clause)
            result = MagicMock()
            if "to_regclass" in sql:
                # `_assemble_posts_content` checks submissions/comments
                # (must be absent, so sampling contributes nothing); then
                # `_load_content_store_text` checks the codebook schema's
                # content_store (must be present, with real content).
                tbl = (params or {}).get("tbl", "")
                result.scalar.return_value = tbl.endswith(".content_store")
            elif "content_store" in sql:
                result.fetchone.return_value = ("existing codebook text",)
            else:
                result.fetchone.return_value = None
                result.scalar.return_value = 0
                result.fetchall.return_value = []
            return result

        conn.execute.side_effect = _execute

        @contextmanager
        def _connect():
            yield conn

        engine = MagicMock()
        engine.connect.side_effect = _connect
        monkeypatch.setattr("backend.app.api.coding_routes.engine", engine)

        classify_mock = MagicMock(return_value=("classification output", "sys", "usr"))
        monkeypatch.setattr("backend.app.api.coding_routes.classify_posts", classify_mock)

        resp = client.post(
            "/api/apply-codebook/",
            data={
                "api_key": "k",
                "database": "proj_a",
                "codebook": "proj_a",
                "report_name": "r",
            },
            # deliberately no Authorization header
        )
        assert classify_mock.called, "classification ran before the auth check"
        # No auth -> file_rec_info stays None, but the response is still
        # 200 with the classification output -- `apply_codebook` never
        # actually 401s an unauthenticated caller, it just skips saving.
        assert resp.status_code == 200
        assert resp.json()["file"] is None


class TestCompareCodingsGuard:
    @pytest.mark.parametrize(
        "form",
        [
            {"coding_a": "not_proj", "coding_b": "proj_b", "api_key": "k"},
            {"coding_a": "proj_a", "coding_b": "not_proj", "api_key": "k"},
        ],
    )
    def test_non_proj_schema_returns_400_before_engine(
        self, client, unused_engine, monkeypatch, form
    ) -> None:
        monkeypatch.setattr("backend.app.api.coding_routes.async_engine", unused_engine)
        resp = client.post("/api/compare-codings/", data=form)
        assert resp.status_code == 400

    def test_no_content_returns_400(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.api.coding_routes.async_engine", _mock_async_engine_no_row()
        )
        resp = client.post(
            "/api/compare-codings/",
            data={"coding_a": "proj_a", "coding_b": "proj_b", "api_key": "k"},
        )
        assert resp.status_code == 400
        assert "No content found" in resp.json()["error"]

    def test_calls_mocked_llm_client_not_real_network(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.api.coding_routes.async_engine",
            _mock_async_engine_with_content("some coding content"),
        )
        llm_mock = MagicMock(return_value="mocked comparison result")
        # compare_codings imports get_client via a LOCAL import inside the
        # function body (`from backend.scripts.codebook_generator import
        # get_client as codebook_get_client`), so it must be patched at
        # its source module, not on coding_routes.
        monkeypatch.setattr("backend.scripts.codebook_generator.get_client", llm_mock)
        resp = client.post(
            "/api/compare-codings/",
            data={"coding_a": "proj_a", "coding_b": "proj_b", "api_key": "k"},
        )
        assert resp.status_code == 200
        assert resp.json()["comparison"] == "mocked comparison result"
        assert llm_mock.called


class TestSummarizeCodingGuard:
    def test_non_proj_schema_returns_400(self, client, unused_engine, monkeypatch) -> None:
        monkeypatch.setattr("backend.app.api.coding_routes.async_engine", unused_engine)
        resp = client.post(
            "/api/summarize-coding/", data={"coding": "not_proj", "api_key": "k"}
        )
        assert resp.status_code == 400

    def test_no_content_returns_400(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.api.coding_routes.async_engine", _mock_async_engine_no_row()
        )
        resp = client.post(
            "/api/summarize-coding/", data={"coding": "proj_a", "api_key": "k"}
        )
        assert resp.status_code == 400
        assert "No content found" in resp.json()["error"]

    def test_calls_mocked_summarizer_not_real_network(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.api.coding_routes.async_engine",
            _mock_async_engine_with_content("coded rows"),
        )
        summarize_mock = MagicMock(return_value="mocked summary")
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.summarize_coding", summarize_mock
        )
        resp = client.post(
            "/api/summarize-coding/", data={"coding": "proj_a", "api_key": "k"}
        )
        assert resp.status_code == 200
        assert resp.json()["summary"] == "mocked summary"
        assert summarize_mock.called
