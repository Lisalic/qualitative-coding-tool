"""Guard-level tests for backend/app/api/file_routes.py.

Same rationale as the other route test modules: SQLite (via
`override_db`) covers the ORM lookups; `engine` is patched (or replaced
with `unused_engine` to prove a guard fires first) for the raw-SQL
DROP/DELETE/INSERT paths, which need real Postgres semantics for a full
happy-path test -- covered by the opt-in integration suite.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.usefixtures("override_db")


def _auth_headers(make_token):
    return {"Authorization": f"Bearer {make_token()}"}


def _own_file(db_session, user_id, schemaname, filename="f"):
    from backend.app.database import File

    f = File(user_id=user_id, filename=filename, schemaname=schemaname, file_type="raw_data")
    db_session.add(f)
    db_session.commit()
    return f


def _make_user(db_session, email="a@b.com"):
    from backend.app.database import User

    user = User(email=email, password="hash")
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# upload-zst
# ---------------------------------------------------------------------------


class TestUploadZst:
    def test_non_zst_filename_returns_400_before_reading_file(self, client) -> None:
        resp = client.post(
            "/api/upload-zst/",
            files={"file": ("data.txt", b"content", "text/plain")},
            data={"data_type": "posts"},
        )
        assert resp.status_code == 400
        assert ".zst" in resp.json()["detail"]

    def test_invalid_subreddits_json_returns_400(self, client) -> None:
        resp = client.post(
            "/api/upload-zst/",
            files={"file": ("data.zst", b"x", "application/octet-stream")},
            data={"data_type": "posts", "subreddits": "{not json"},
        )
        assert resp.status_code == 400

    def test_invalid_data_type_returns_400(self, client) -> None:
        resp = client.post(
            "/api/upload-zst/",
            files={"file": ("data.zst", b"x", "application/octet-stream")},
            data={"data_type": "invalid"},
        )
        assert resp.status_code == 400
        assert "data_type" in resp.json()["detail"]

    def test_no_auth_returns_401(self, client) -> None:
        # Reaches the auth check after saving the temp file (no
        # DB/engine work happens before it), so no patching needed.
        resp = client.post(
            "/api/upload-zst/",
            files={"file": ("data.zst", b"x", "application/octet-stream")},
            data={"data_type": "posts"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthenticated"


# ---------------------------------------------------------------------------
# delete-database
# ---------------------------------------------------------------------------


class TestDeleteDatabase:
    def test_invalid_prefix_returns_400_even_without_auth(self, client) -> None:
        """Confirmed finding: the schema-prefix guard runs BEFORE the
        auth check, so an unauthenticated caller gets 400 (not 401) for
        a bad schema name -- documented, not changed, per the plan.
        """
        resp = client.delete("/api/delete-database/not_a_valid_prefix")
        assert resp.status_code == 400

    @pytest.mark.parametrize("prefix", ["proj_", "cmp_", "sum_"])
    def test_valid_prefix_without_auth_returns_401(self, client, prefix) -> None:
        resp = client.delete(f"/api/delete-database/{prefix}abc")
        assert resp.status_code == 401

    def test_missing_file_returns_404(self, client, make_token) -> None:
        resp = client.delete(
            "/api/delete-database/proj_missing", headers=_auth_headers(make_token)
        )
        assert resp.status_code == 404

    def test_deletes_owned_file_and_drops_schema(
        self, client, make_token, db_session, monkeypatch
    ) -> None:
        user = _make_user(db_session)
        _own_file(db_session, user.id, "proj_a")

        eng = MagicMock()

        @contextmanager
        def _begin():
            yield MagicMock()

        eng.begin.side_effect = _begin
        monkeypatch.setattr("backend.app.api.file_routes.engine", eng)

        resp = client.delete(
            "/api/delete-database/proj_a",
            headers={"Authorization": f"Bearer {make_token(sub=str(user.id))}"},
        )
        assert resp.status_code == 200
        assert eng.begin.called

    def test_someone_elses_file_returns_404(self, client, make_token, db_session) -> None:
        owner = _make_user(db_session, "owner@x.com")
        _own_file(db_session, owner.id, "proj_a")

        resp = client.delete(
            "/api/delete-database/proj_a",
            headers={"Authorization": f"Bearer {make_token(sub='999999')}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# delete-row
# ---------------------------------------------------------------------------


class TestDeleteRow:
    def test_invalid_schema_returns_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/delete-row/",
            headers=_auth_headers(make_token),
            data={"schemaname": "not_proj", "table": "submissions", "row_id": "1"},
        )
        assert resp.status_code == 400

    def test_invalid_table_returns_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/delete-row/",
            headers=_auth_headers(make_token),
            data={"schemaname": "proj_a", "table": "users", "row_id": "1"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "Invalid table"

    def test_no_auth_returns_401(self, client) -> None:
        resp = client.post(
            "/api/delete-row/",
            data={"schemaname": "proj_a", "table": "submissions", "row_id": "1"},
        )
        assert resp.status_code == 401

    def test_not_owned_returns_403(self, client, make_token) -> None:
        resp = client.post(
            "/api/delete-row/",
            headers=_auth_headers(make_token),
            data={"schemaname": "proj_missing", "table": "submissions", "row_id": "1"},
        )
        assert resp.status_code == 403

    def test_deletes_row_for_owned_file(self, client, make_token, db_session, monkeypatch) -> None:
        user = _make_user(db_session)
        _own_file(db_session, user.id, "proj_a")

        conn = MagicMock()
        delete_result = MagicMock()
        delete_result.rowcount = 1
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        conn.execute.side_effect = [delete_result, count_result]

        eng = MagicMock()

        @contextmanager
        def _ctx():
            yield conn

        eng.begin.side_effect = _ctx
        eng.connect.side_effect = _ctx
        monkeypatch.setattr("backend.app.api.file_routes.engine", eng)

        resp = client.post(
            "/api/delete-row/",
            headers={"Authorization": f"Bearer {make_token(sub=str(user.id))}"},
            data={"schemaname": "proj_a", "table": "submissions", "row_id": "abc123"},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1


# ---------------------------------------------------------------------------
# move-rows
# ---------------------------------------------------------------------------


class TestMoveRows:
    def test_malformed_json_returns_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/move-rows/",
            headers={**_auth_headers(make_token), "Content-Type": "application/json"},
            content=b"{not valid json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "Invalid JSON body"

    def test_non_proj_schemas_return_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/move-rows/",
            headers=_auth_headers(make_token),
            json={
                "source_schema": "not_proj",
                "target_schema": "proj_b",
                "table": "submissions",
                "row_ids": ["1"],
            },
        )
        assert resp.status_code == 400

    def test_invalid_table_returns_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/move-rows/",
            headers=_auth_headers(make_token),
            json={
                "source_schema": "proj_a",
                "target_schema": "proj_b",
                "table": "users",
                "row_ids": ["1"],
            },
        )
        assert resp.status_code == 400

    def test_empty_row_ids_returns_400(self, client, make_token) -> None:
        resp = client.post(
            "/api/move-rows/",
            headers=_auth_headers(make_token),
            json={
                "source_schema": "proj_a",
                "target_schema": "proj_b",
                "table": "submissions",
                "row_ids": [],
            },
        )
        assert resp.status_code == 400

    def test_no_auth_returns_401(self, client) -> None:
        resp = client.post(
            "/api/move-rows/",
            json={
                "source_schema": "proj_a",
                "target_schema": "proj_b",
                "table": "submissions",
                "row_ids": ["1"],
            },
        )
        assert resp.status_code == 401

    def test_not_owned_returns_403(self, client, make_token) -> None:
        resp = client.post(
            "/api/move-rows/",
            headers=_auth_headers(make_token),
            json={
                "source_schema": "proj_missing_a",
                "target_schema": "proj_missing_b",
                "table": "submissions",
                "row_ids": ["1"],
            },
        )
        assert resp.status_code == 403
