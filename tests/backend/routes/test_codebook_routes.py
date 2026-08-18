"""Tests for backend/app/api/codebook_routes.py -- the ORM-reachable
subset: GET /api/list-codebooks (pure ORM), GET /api/codebook and
GET /api/parse-codebook (ORM lookup + a raw-SQL `engine.connect()` read
against a per-artifact schema, which we mock rather than hit Postgres for).

The AI/schema-creation routes in this module (generate-codebook,
compare-codebooks) are covered separately in test_ai_routes.py at the
validation/auth-guard boundary; their full artifact-creation flow is
covered by the opt-in integration suite.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.usefixtures("override_db")


def _mock_engine_with_row(row):
    """A `codebook_routes.engine`-shaped mock whose `.connect()` yields a
    connection whose `.execute(...).fetchone()` returns `row` (or None).
    """
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = row

    @contextmanager
    def _connect():
        yield conn

    engine = MagicMock()
    engine.connect.side_effect = _connect
    return engine


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

    def test_lists_codebook_and_comparison_types_sorted_by_name(
        self, client, db_session, make_token
    ) -> None:
        from backend.app.database import File, User

        user = User(id=1, email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        db_session.add_all(
            [
                File(user_id=user.id, filename="Zeta", schemaname="proj_z", file_type="codebook"),
                File(
                    user_id=user.id,
                    filename="Alpha",
                    schemaname="cmp_a",
                    file_type="codebook_comparison",
                ),
                File(
                    user_id=user.id, filename="Other", schemaname="proj_o", file_type="raw_data"
                ),
            ]
        )
        db_session.commit()

        resp = client.get(
            "/api/list-codebooks", cookies={"access_token": make_token(sub=str(user.id))}
        )
        names = [c["name"] for c in resp.json()["codebooks"]]
        assert names == ["Alpha", "Zeta"]  # sorted, raw_data excluded

    def test_scoped_to_owner_not_all_users(self, client, db_session, make_token) -> None:
        from backend.app.database import File, User

        owner = User(id=1, email="owner@b.com", password="hash")
        other = User(id=2, email="other@b.com", password="hash")
        db_session.add_all([owner, other])
        db_session.commit()
        db_session.add_all(
            [
                File(
                    user_id=owner.id, filename="Mine", schemaname="proj_m", file_type="codebook"
                ),
                File(
                    user_id=other.id,
                    filename="NotMine",
                    schemaname="proj_n",
                    file_type="codebook",
                ),
            ]
        )
        db_session.commit()

        resp = client.get(
            "/api/list-codebooks", cookies={"access_token": make_token(sub=str(owner.id))}
        )
        names = [c["name"] for c in resp.json()["codebooks"]]
        assert names == ["Mine"]


class TestGetCodebook:
    def test_no_id_and_no_files_returns_404(self, client) -> None:
        resp = client.get("/api/codebook")
        assert resp.status_code == 404
        assert resp.json()["error"] == "No codebook file found"

    def test_unmatched_id_returns_404_before_touching_engine(
        self, client, unused_engine, monkeypatch
    ) -> None:
        monkeypatch.setattr("backend.app.api.codebook_routes.engine", unused_engine)
        resp = client.get("/api/codebook?codebook_id=nonexistent")
        assert resp.status_code == 404

    def test_matches_by_schemaname_and_reads_content(
        self, client, db_session, monkeypatch
    ) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        db_session.add(
            File(
                user_id=user.id,
                filename="cb",
                schemaname="proj_a",
                file_type="codebook",
                systemprompt="sys",
                userprompt="usr",
            )
        )
        db_session.commit()

        monkeypatch.setattr(
            "backend.app.api.codebook_routes.engine",
            _mock_engine_with_row(("codebook text content",)),
        )
        resp = client.get("/api/codebook?codebook_id=proj_a")
        assert resp.status_code == 200
        body = resp.json()
        assert body["codebook"] == "codebook text content"
        assert body["systemprompt"] == "sys"
        assert body["userprompt"] == "usr"

    def test_matches_by_integer_file_id(self, client, db_session, monkeypatch) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        f = File(user_id=user.id, filename="cb", schemaname="proj_a", file_type="codebook")
        db_session.add(f)
        db_session.commit()

        monkeypatch.setattr(
            "backend.app.api.codebook_routes.engine", _mock_engine_with_row(("content",))
        )
        resp = client.get(f"/api/codebook?codebook_id={f.id}")
        assert resp.status_code == 200

    def test_content_missing_in_schema_returns_404(self, client, db_session, monkeypatch) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        db_session.add(File(user_id=user.id, filename="cb", schemaname="proj_a", file_type="codebook"))
        db_session.commit()

        monkeypatch.setattr(
            "backend.app.api.codebook_routes.engine", _mock_engine_with_row(None)
        )
        resp = client.get("/api/codebook?codebook_id=proj_a")
        assert resp.status_code == 404
        assert resp.json()["error"] == "Codebook content not found in file"

    def test_engine_exception_returns_500(self, client, db_session, monkeypatch) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        db_session.add(File(user_id=user.id, filename="cb", schemaname="proj_a", file_type="codebook"))
        db_session.commit()

        broken_engine = MagicMock()
        broken_engine.connect.side_effect = RuntimeError("schema does not exist")
        monkeypatch.setattr("backend.app.api.codebook_routes.engine", broken_engine)

        resp = client.get("/api/codebook?codebook_id=proj_a")
        assert resp.status_code == 500


class TestParseCodebook:
    def test_no_matching_file_returns_404(self, client) -> None:
        resp = client.get("/api/parse-codebook?codebook_id=nonexistent")
        assert resp.status_code == 404

    def test_parses_raw_content_into_json_structure(
        self, client, db_session, monkeypatch
    ) -> None:
        from backend.app.database import File, User

        user = User(email="a@b.com", password="hash")
        db_session.add(user)
        db_session.commit()
        db_session.add(File(user_id=user.id, filename="cb", schemaname="proj_a", file_type="codebook"))
        db_session.commit()

        raw = "### Code Family: F\n#### Code Name: C\ncontent"
        monkeypatch.setattr(
            "backend.app.api.codebook_routes.engine", _mock_engine_with_row((raw,))
        )
        resp = client.get("/api/parse-codebook?codebook_id=proj_a")
        assert resp.status_code == 200
        parsed = resp.json()["parsed"]
        assert parsed[0]["family_name"] == "F"
        assert parsed[0]["codes"][0]["code_name"] == "C"
