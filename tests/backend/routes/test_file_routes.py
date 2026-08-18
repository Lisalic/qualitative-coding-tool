"""Tests for backend/app/api/file_routes.py.

The router is fully async (`Depends(get_async_db)`), so every test here
runs against `override_async_db` (in-memory SQLite via
`async_sqlite_engine`), matching the pattern used in
`test_project_routes.py`/`test_prompt_routes.py`. Raw-dynamic-schema
paths (`upload_zst`'s `.zst` streaming, `merge_databases`' reads from old
`proj_*` schemas) need real Postgres semantics not reachable from SQLite
-- those are covered by `tests/backend/services/test_file_service.py`
(mocked at the streaming/raw-SQL-read boundary) and the opt-in
integration suite, not here. This module covers request validation,
auth/ownership guards, and the fixed-table happy paths for
delete-database/delete-row/move-rows.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import File, User
from backend.app.storage_models import Submission

pytestmark = pytest.mark.usefixtures("override_async_db")


def _auth_headers(make_token, sub="1"):
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session_factory, email="a@b.com") -> int:
    async with session_factory() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        return user.id


async def _make_file(session_factory, user_id, schemaname, filename="f", file_type="raw_data") -> int:
    async with session_factory() as session:
        f = File(user_id=user_id, filename=filename, schemaname=schemaname, file_type=file_type)
        session.add(f)
        await session.commit()
        return f.id


async def _add_submission(session_factory, file_id, row_id, **overrides):
    async with session_factory() as session:
        defaults = dict(
            file_id=file_id,
            id=row_id,
            subreddit="s",
            title="t",
            selftext="body text",
            author="a",
            created_utc=1,
            score=1,
            num_comments=0,
            word_count=2,
        )
        defaults.update(overrides)
        session.add(Submission(**defaults))
        await session.commit()


# ---------------------------------------------------------------------------
# upload-zst -- pure request validation, no DB touched before the checks
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
        # Reaches the auth check after reading the upload's bytes (no
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

    async def test_deletes_owned_file_and_its_fixed_table_rows(
        self, client, make_token, session_factory
    ) -> None:
        uid = await _make_user(session_factory)
        fid = await _make_file(session_factory, uid, "proj_a")
        await _add_submission(session_factory, fid, "s1")

        resp = client.delete(
            "/api/delete-database/proj_a",
            headers=_auth_headers(make_token, sub=str(uid)),
        )
        assert resp.status_code == 200
        assert "proj_a" in resp.json()["message"] or "f" in resp.json()["message"]

        async with session_factory() as session:
            assert (await session.execute(select(File).where(File.id == fid))).scalar_one_or_none() is None
            remaining = (
                await session.execute(select(Submission).where(Submission.file_id == fid))
            ).scalars().all()
            assert remaining == []

    async def test_someone_elses_file_returns_404(self, client, make_token, session_factory) -> None:
        owner_id = await _make_user(session_factory, "owner@x.com")
        await _make_file(session_factory, owner_id, "proj_a")

        resp = client.delete(
            "/api/delete-database/proj_a",
            headers=_auth_headers(make_token, sub="999999"),
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

    async def test_deletes_row_for_owned_file(self, client, make_token, session_factory) -> None:
        uid = await _make_user(session_factory)
        fid = await _make_file(session_factory, uid, "proj_a")
        await _add_submission(session_factory, fid, "abc123")

        resp = client.post(
            "/api/delete-row/",
            headers=_auth_headers(make_token, sub=str(uid)),
            data={"schemaname": "proj_a", "table": "submissions", "row_id": "abc123"},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1

        async with session_factory() as session:
            remaining = (
                await session.execute(select(Submission).where(Submission.file_id == fid))
            ).scalars().all()
            assert remaining == []

    async def test_deletes_zero_for_missing_row(self, client, make_token, session_factory) -> None:
        uid = await _make_user(session_factory)
        await _make_file(session_factory, uid, "proj_a")

        resp = client.post(
            "/api/delete-row/",
            headers=_auth_headers(make_token, sub=str(uid)),
            data={"schemaname": "proj_a", "table": "submissions", "row_id": "nonexistent"},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0


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

    async def test_moves_matching_rows_between_owned_files(
        self, client, make_token, session_factory
    ) -> None:
        """Row/content-parity proof for the new set-based
        `raw_data_repo.copy_rows_by_id` path (replacing the old per-id
        SELECT+INSERT Python loop): the moved row lands in the target
        with its content intact and is gone from the source.
        """
        uid = await _make_user(session_factory)
        src_id = await _make_file(session_factory, uid, "proj_src")
        tgt_id = await _make_file(session_factory, uid, "proj_tgt")
        await _add_submission(session_factory, src_id, "keep", selftext="stay")
        await _add_submission(session_factory, src_id, "move", selftext="move me")

        resp = client.post(
            "/api/move-rows/",
            headers=_auth_headers(make_token, sub=str(uid)),
            json={
                "source_schema": "proj_src",
                "target_schema": "proj_tgt",
                "table": "submissions",
                "row_ids": ["move"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["moved"] == 1

        async with session_factory() as session:
            src_rows = (
                await session.execute(select(Submission).where(Submission.file_id == src_id))
            ).scalars().all()
            assert [r.id for r in src_rows] == ["keep"]

            tgt_rows = (
                await session.execute(select(Submission).where(Submission.file_id == tgt_id))
            ).scalars().all()
            assert len(tgt_rows) == 1
            assert tgt_rows[0].id == "move"
            assert tgt_rows[0].selftext == "move me"

    async def test_no_matching_rows_returns_zero_with_message(
        self, client, make_token, session_factory
    ) -> None:
        uid = await _make_user(session_factory)
        await _make_file(session_factory, uid, "proj_src")
        await _make_file(session_factory, uid, "proj_tgt")

        resp = client.post(
            "/api/move-rows/",
            headers=_auth_headers(make_token, sub=str(uid)),
            json={
                "source_schema": "proj_src",
                "target_schema": "proj_tgt",
                "table": "submissions",
                "row_ids": ["nonexistent"],
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"moved": 0, "message": "No matching rows found"}
