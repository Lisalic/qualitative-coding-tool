"""Tests for backend/app/api/memo_routes.py.

Covers the route boundary only -- the storage decisions (blank body
deletes, one memo per row, memos copy forward with their rows) are
pinned in ``tests/backend/repositories/test_memo_repo.py``.

The ownership check is worth its own cases here rather than being taken
on trust from ``file_repo``: memos are free-text a researcher wrote, so
a leak across users would be a leak of their analysis, not just of row
ids someone could already see.
"""

import pytest

pytestmark = pytest.mark.usefixtures("override_async_db")


@pytest.fixture()
def session_factory(async_sqlite_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _make_user(session_factory, email: str = "a@b.com"):
    from backend.app.database import User

    async with session_factory() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_file(session_factory, user_id: int, schemaname: str = "proj_a"):
    from backend.app.database import File

    async with session_factory() as session:
        file_rec = File(
            user_id=user_id, filename=f"{schemaname}.zst", schemaname=schemaname, file_type="raw_data"
        )
        session.add(file_rec)
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


def _put(client, token, **body):
    return client.put("/api/memos/", json=body, cookies={"access_token": token})


class TestListMemos:
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/memos/?schema=proj_a").status_code == 401

    async def test_returns_empty_for_a_file_with_no_memos(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id)
        token = make_token(sub=str(user.id))

        resp = client.get("/api/memos/?schema=proj_a", cookies={"access_token": token})
        assert resp.status_code == 200
        assert resp.json() == {"memos": []}

    async def test_rejects_a_malformed_schema(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        token = make_token(sub=str(user.id))
        resp = client.get("/api/memos/?schema=not-a-schema", cookies={"access_token": token})
        assert resp.status_code == 400

    async def test_another_users_file_is_not_found(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner@b.com")
        await _make_file(session_factory, owner.id)
        intruder = await _make_user(session_factory, "intruder@b.com")

        resp = client.get(
            "/api/memos/?schema=proj_a", cookies={"access_token": make_token(sub=str(intruder.id))}
        )
        assert resp.status_code == 404


class TestUpsertMemo:
    def test_requires_auth(self, client) -> None:
        resp = client.put(
            "/api/memos/", json={"schema": "proj_a", "row_type": "submission", "row_id": "s1", "body": "x"}
        )
        assert resp.status_code == 401

    async def test_saves_then_reads_back(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id)
        token = make_token(sub=str(user.id))

        resp = _put(client, token, schema="proj_a", row_type="submission", row_id="s1", body="a thought")
        assert resp.status_code == 200
        assert resp.json()["memo"]["body"] == "a thought"

        listed = client.get("/api/memos/?schema=proj_a", cookies={"access_token": token}).json()
        assert listed["memos"] == [
            {
                "row_type": "submission",
                "row_id": "s1",
                "body": "a thought",
                "updated_at": listed["memos"][0]["updated_at"],
            }
        ]

    async def test_second_save_replaces_rather_than_appends(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id)
        token = make_token(sub=str(user.id))

        _put(client, token, schema="proj_a", row_type="submission", row_id="s1", body="first")
        _put(client, token, schema="proj_a", row_type="submission", row_id="s1", body="second")

        memos = client.get("/api/memos/?schema=proj_a", cookies={"access_token": token}).json()["memos"]
        assert [m["body"] for m in memos] == ["second"]

    async def test_blank_body_clears_the_memo(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id)
        token = make_token(sub=str(user.id))

        _put(client, token, schema="proj_a", row_type="submission", row_id="s1", body="a thought")
        resp = _put(client, token, schema="proj_a", row_type="submission", row_id="s1", body="")

        assert resp.status_code == 200
        assert resp.json() == {"memo": None}
        assert client.get("/api/memos/?schema=proj_a", cookies={"access_token": token}).json() == {"memos": []}

    async def test_rejects_an_unknown_row_type(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id)
        token = make_token(sub=str(user.id))

        resp = _put(client, token, schema="proj_a", row_type="post", row_id="s1", body="x")
        assert resp.status_code == 422

    async def test_cannot_write_to_another_users_file(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner@b.com")
        await _make_file(session_factory, owner.id)
        intruder = await _make_user(session_factory, "intruder@b.com")

        resp = _put(
            client,
            make_token(sub=str(intruder.id)),
            schema="proj_a",
            row_type="submission",
            row_id="s1",
            body="not mine",
        )
        assert resp.status_code == 404
