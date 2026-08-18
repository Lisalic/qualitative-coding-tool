"""Guard-level tests for the raw-SQL and OpenRouter-backed routes across
codebook_routes.py, coding_routes.py, data_routes.py, content_routes.py,
and file_routes.py.

These routes' *full* happy path needs real Postgres semantics (CREATE
SCHEMA, information_schema introspection, generated columns, RANDOM()
sampling) that SQLite can't faithfully stand in for -- that's covered by
the opt-in integration suite (tests/backend/integration/). Here we test
what's reachable without Postgres: request validation (422), auth
gating, schema-name guards, and -- for the AI routes -- that the network
call is mocked out via each script's `get_client`/classify_posts seam
rather than making a real OpenRouter request.

Also documents (without "fixing", per the plan) a real architectural
finding: several routes check authentication *after* already doing the
expensive raw-SQL sampling and/or LLM call, so an unauthenticated caller
can trigger both before being told no.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.usefixtures("override_db")


def _mock_sync_engine(*, tables=(), rows_by_table=None):
    """A module-`engine`-shaped mock: `to_regclass` reports `tables` as
    existing, and each table's SELECT returns `rows_by_table[table]`.
    """
    rows_by_table = rows_by_table or {}
    conn = MagicMock()

    def _execute(clause, params=None):
        sql = str(clause)
        result = MagicMock()
        if "to_regclass" in sql:
            tbl = (params or {}).get("tbl", "")
            table_name = tbl.split(".")[-1]
            result.scalar.return_value = table_name in tables
        elif "COUNT(*)" in sql:
            for t in rows_by_table:
                if f'"{t}"' in sql or f".{t}" in sql:
                    result.scalar.return_value = len(rows_by_table[t])
                    break
            else:
                result.scalar.return_value = 0
        else:
            for t, rows in rows_by_table.items():
                if f'"{t}"' in sql:
                    result.fetchall.return_value = rows
                    result.fetchone.return_value = rows[0] if rows else None
                    result.__iter__ = lambda self, rows=rows: iter(rows)
                    break
            else:
                # No configured table matched this SELECT: represent
                # "found nothing" for both the fetchall()-style callers
                # (data_routes) and the fetchone()-style callers
                # (codebook_routes' single-row content_store reads).
                result.fetchall.return_value = []
                result.fetchone.return_value = None
        return result

    conn.execute.side_effect = _execute

    @contextmanager
    def _connect():
        yield conn

    engine = MagicMock()
    engine.connect.side_effect = _connect
    engine.begin.side_effect = _connect
    return engine


# ---------------------------------------------------------------------------
# data_routes.py -- schema-name guards (400 before touching the engine)
# ---------------------------------------------------------------------------


class TestWordCountRangesGuard:
    @pytest.mark.parametrize("schema", ["", "1abc", "proj a", "proj-a", "proj_a; DROP TABLE x"])
    def test_invalid_schema_returns_400_before_engine(self, client, unused_engine, monkeypatch, schema):
        monkeypatch.setattr("backend.app.api.data_routes.engine", unused_engine)
        resp = client.get(f"/api/word-count-ranges/?schema={schema}")
        assert resp.status_code == 400

    def test_db_suffix_stripped_before_validation(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.api.data_routes.engine", _mock_sync_engine(tables=())
        )
        resp = client.get("/api/word-count-ranges/?schema=proj_a.db")
        assert resp.status_code == 200


class TestFileEntriesGuard:
    def test_invalid_schema_returns_400_before_engine(self, client, unused_engine, monkeypatch) -> None:
        monkeypatch.setattr("backend.app.api.data_routes.engine", unused_engine)
        resp = client.get("/api/file-entries/?schema=1invalid")
        assert resp.status_code == 400

    def test_missing_schema_returns_422(self, client) -> None:
        # `schema` has no default -> FastAPI 422s before the handler body runs.
        resp = client.get("/api/file-entries/")
        assert resp.status_code == 422


class TestCommentsForSubmissionGuard:
    @pytest.mark.parametrize("database", ["", "not_proj_prefixed", "proj"])
    async def test_non_proj_schema_returns_400(self, client, database) -> None:
        resp = client.get(f"/api/comments/sub1?database={database}")
        assert resp.status_code == 400


class TestPostContentsGuard:
    def test_missing_schema_returns_400(self, client) -> None:
        resp = client.post("/api/post-contents/", json={"post_ids": ["1"]})
        assert resp.status_code == 400

    def test_missing_post_ids_returns_400(self, client) -> None:
        resp = client.post("/api/post-contents/", json={"schema": "proj_a"})
        assert resp.status_code == 400

    def test_empty_post_ids_list_returns_400(self, client) -> None:
        # `not post_ids` is True for an empty list too.
        resp = client.post("/api/post-contents/", json={"schema": "proj_a", "post_ids": []})
        assert resp.status_code == 400

    @pytest.mark.parametrize(
        "schema", ["1abc", "proj a", "proj-a", 'proj_a"; DROP TABLE x; --', "not_proj_prefixed"]
    )
    def test_invalid_schema_returns_400_before_engine(
        self, client, unused_engine, monkeypatch, schema
    ) -> None:
        # Regression test: this endpoint used to splice `schema` straight
        # into a SELECT with zero validation.
        monkeypatch.setattr("backend.app.api.data_routes.async_engine", unused_engine)
        resp = client.post(
            "/api/post-contents/", json={"schema": schema, "post_ids": ["1"]}
        )
        assert resp.status_code == 400

    def test_malformed_json_body_returns_500(self, client) -> None:
        # The whole handler body is wrapped in one broad except -> 500,
        # not 400, for a body that fails `await request.json()`.
        resp = client.post(
            "/api/post-contents/",
            headers={"Content-Type": "application/json"},
            content=b"{not valid json",
        )
        assert resp.status_code == 500


class TestFilterDataValidation:
    def test_missing_required_fields_returns_422(self, client) -> None:
        resp = client.post("/api/filter-data/", data={})
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

    def test_tag_expansion_error_short_circuits_before_engine(
        self, client, unused_engine, monkeypatch
    ) -> None:
        """When filter_tags are supplied, tag expansion runs first -- a
        TagExpansionError here must return its mapped status code without
        ever reaching the raw-SQL sampling step.
        """
        from backend.scripts.tag_expansion import TagExpansionError

        monkeypatch.setattr("backend.app.api.data_routes.engine", unused_engine)
        monkeypatch.setattr(
            "backend.app.api.data_routes.tag_expansion_module.expand_tags_via_openrouter",
            MagicMock(side_effect=TagExpansionError("bad key", code=401)),
        )
        resp = client.post(
            "/api/filter-data/",
            data={
                "api_key": "bad-key",
                "database": "proj_a",
                "name": "n",
                "model": "m",
                "filter_tags": "anxiety,stress",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# codebook_routes.py -- generate-codebook / compare-codebooks
# ---------------------------------------------------------------------------


class TestGenerateCodebookValidation:
    def test_missing_required_fields_returns_422(self, client) -> None:
        resp = client.post("/api/generate-codebook/", data={})
        assert resp.status_code == 422

    def test_no_records_sampled_returns_400(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.api.codebook_routes.engine", _mock_sync_engine(tables=())
        )
        resp = client.post(
            "/api/generate-codebook/",
            data={"api_key": "k", "database": "proj_a", "name": "n"},
        )
        assert resp.status_code == 400
        assert "No records were sampled" in resp.json()["error"]

    def test_auth_is_checked_after_the_llm_call_not_before(self, client, monkeypatch) -> None:
        """Documents a real ordering issue (not fixed, per plan): with no
        Authorization at all, the raw-SQL sample AND the mocked LLM call
        both still execute before the 401 is raised. An unauthenticated
        caller can trigger the network call.
        """
        monkeypatch.setattr(
            "backend.app.api.codebook_routes.engine",
            _mock_sync_engine(
                tables=("submissions",),
                rows_by_table={"submissions": [MagicMock(_mapping={"title": "t", "selftext": "s"})]},
            ),
        )
        generate_mock = MagicMock(return_value=("generated codebook text", "sys", "usr"))
        monkeypatch.setattr(
            "backend.app.api.codebook_routes.codebook_generator_module.generate_codebook",
            generate_mock,
        )
        resp = client.post(
            "/api/generate-codebook/",
            data={"api_key": "k", "database": "proj_a", "name": "n"},
            # deliberately no Authorization header
        )
        assert generate_mock.called, "the LLM call ran before the auth check"
        assert resp.status_code == 401


class TestCompareCodebooksGuard:
    @pytest.mark.parametrize(
        "form",
        [
            {"codebook_a": "not_proj", "codebook_b": "proj_b", "api_key": "k"},
            {"codebook_a": "proj_a", "codebook_b": "not_proj", "api_key": "k"},
        ],
    )
    def test_non_proj_schema_returns_400_before_engine(
        self, client, unused_engine, monkeypatch, form
    ) -> None:
        monkeypatch.setattr("backend.app.api.codebook_routes.engine", unused_engine)
        resp = client.post("/api/compare-codebooks/", data=form)
        assert resp.status_code == 400

    # NOTE: `if not api_key:` can only be reached with a truly empty
    # string, but httpx's TestClient silently drops empty-string form
    # fields when encoding `data=`, so FastAPI's own `Form(...)`
    # required-field check (422) fires first and that branch is not
    # reachable through this client -- same limitation documented on
    # ProjectRoutes' blank-name test.

    def test_no_auth_required_at_all(self, client, monkeypatch) -> None:
        # Confirmed by reading the route: compare-codebooks never calls
        # get_user_id_from_request -- it's reachable by anyone with the
        # schema names, no login needed.
        #
        # NOTE: `compare_codebooks` does `from backend.app.database import
        # engine` as a LOCAL import inside the function body, shadowing
        # the module-level `engine` already imported at the top of
        # codebook_routes.py. That means patching
        # `codebook_routes.engine` (as used elsewhere in this file) has
        # no effect here -- the real fix point is `database.engine`
        # itself, which is safe to patch in this test because the route
        # takes no `db` dependency at all (nothing else in this test
        # relies on the real sync engine).
        monkeypatch.setattr("backend.app.database.engine", _mock_sync_engine(tables=()))
        resp = client.post(
            "/api/compare-codebooks/",
            data={"codebook_a": "proj_a", "codebook_b": "proj_b", "api_key": "k"},
        )
        assert resp.status_code == 400  # "No content found", not 401
        assert "No content found" in resp.json()["error"]


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
    def test_no_id_and_no_summaries_returns_404(self, client, override_async_db) -> None:
        resp = client.get("/api/summary/")
        assert resp.status_code == 404

    def test_unmatched_id_returns_404(self, client, override_async_db) -> None:
        resp = client.get("/api/summary/nonexistent")
        assert resp.status_code == 404
