"""Tests for backend/app/api/prompt_routes.py: /api/prompts/ CRUD.

ORM-only, no raw SQL -- runs against in-memory SQLite via `override_db`.

`create_prompt` looks the authenticated user up in the DB
(`db.query(User).filter(User.id == user_id_from_request).first()`) when
`user_id` isn't supplied in the body, so a signed token alone isn't
enough for that endpoint -- a real `User` row must exist. The other
three endpoints (list/update/delete) trust the token's `sub` without
checking the user exists, so they're exercised with plain tokens.
"""

import pytest

from backend.app.database import User

pytestmark = pytest.mark.usefixtures("override_db")


@pytest.fixture()
def make_user(db_session):
    """Create a real `User` row and return its id as a string."""

    def _make(email: str = "u@x.com") -> str:
        user = User(email=email, password="hash")
        db_session.add(user)
        db_session.commit()
        return str(user.id)

    return _make


def _auth_headers(make_token, sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


def _create_prompt(client, make_token, sub: str, **fields):
    data = {"promptname": "orig", "prompt": "orig text", "type": "filter"}
    data.update(fields)
    resp = client.post("/api/prompts/", headers=_auth_headers(make_token, sub), data=data)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class TestListPrompts:
    def test_requires_auth(self, client) -> None:
        assert client.get("/api/prompts/").status_code == 401

    def test_empty_list_for_new_user(self, client, make_token, make_user) -> None:
        uid = make_user()
        resp = client.get("/api/prompts/", headers=_auth_headers(make_token, uid))
        assert resp.status_code == 200
        assert resp.json() == {"prompts": []}

    def test_lists_only_own_prompts(self, client, make_token, make_user) -> None:
        uid1 = make_user("u1@x.com")
        uid2 = make_user("u2@x.com")
        _create_prompt(client, make_token, uid1, promptname="p1")
        _create_prompt(client, make_token, uid2, promptname="p2")

        resp = client.get("/api/prompts/", headers=_auth_headers(make_token, uid1))
        names = [p["promptname"] for p in resp.json()["prompts"]]
        assert names == ["p1"]

    def test_filters_by_prompt_type(self, client, make_token, make_user) -> None:
        uid = make_user()
        _create_prompt(client, make_token, uid, promptname="a", type="filter")
        _create_prompt(client, make_token, uid, promptname="b", type="generate")

        resp = client.get("/api/prompts/?prompt_type=generate", headers=_auth_headers(make_token, uid))
        names = [p["promptname"] for p in resp.json()["prompts"]]
        assert names == ["b"]


class TestCreatePrompt:
    def test_create_via_form_data(self, client, make_token, make_user) -> None:
        uid = make_user()
        resp = client.post(
            "/api/prompts/",
            headers=_auth_headers(make_token, uid),
            data={"promptname": "p1", "prompt": "text", "type": "filter"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["promptname"] == "p1"
        assert body["type"] == "filter"

    def test_create_via_json_body(self, client, make_token, make_user) -> None:
        uid = make_user()
        resp = client.post(
            "/api/prompts/",
            headers=_auth_headers(make_token, uid),
            json={"promptname": "p1", "prompt": "text", "type": "filter"},
        )
        assert resp.status_code == 200
        assert resp.json()["promptname"] == "p1"

    @pytest.mark.parametrize("missing", ["promptname", "prompt", "type"])
    def test_missing_required_field_returns_400(self, client, make_token, make_user, missing) -> None:
        uid = make_user()
        data = {"promptname": "p1", "prompt": "text", "type": "filter"}
        del data[missing]
        resp = client.post("/api/prompts/", headers=_auth_headers(make_token, uid), data=data)
        assert resp.status_code == 400

    def test_no_auth_returns_401(self, client) -> None:
        resp = client.post(
            "/api/prompts/", data={"promptname": "p1", "prompt": "text", "type": "filter"}
        )
        assert resp.status_code == 401

    def test_valid_token_but_user_row_missing_returns_401(self, client, make_token) -> None:
        # A well-signed token for a user id that was never created.
        resp = client.post(
            "/api/prompts/",
            headers=_auth_headers(make_token, "999999"),
            data={"promptname": "p1", "prompt": "text", "type": "filter"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "User not found"

    def test_malformed_json_body_returns_400(self, client, make_token, make_user) -> None:
        uid = make_user()
        resp = client.post(
            "/api/prompts/",
            headers={**_auth_headers(make_token, uid), "Content-Type": "application/json"},
            content=b"{not valid json",
        )
        assert resp.status_code == 400
        assert "Invalid request payload" in resp.json()["detail"]


class TestUpdatePrompt:
    def test_update_own_prompt(self, client, make_token, make_user) -> None:
        uid = make_user()
        pid = _create_prompt(client, make_token, uid)
        resp = client.post(
            f"/api/prompts/{pid}/update",
            headers=_auth_headers(make_token, uid),
            data={"promptname": "renamed"},
        )
        assert resp.status_code == 200
        assert resp.json()["promptname"] == "renamed"
        assert resp.json()["prompt"] == "orig text"  # untouched field preserved

    def test_update_someone_elses_prompt_returns_403(self, client, make_token, make_user) -> None:
        uid1 = make_user("u1@x.com")
        uid2 = make_user("u2@x.com")
        pid = _create_prompt(client, make_token, uid1)
        resp = client.post(
            f"/api/prompts/{pid}/update",
            headers=_auth_headers(make_token, uid2),
            data={"promptname": "hijacked"},
        )
        assert resp.status_code == 403

    def test_update_missing_prompt_returns_404(self, client, make_token, make_user) -> None:
        uid = make_user()
        resp = client.post(
            "/api/prompts/999999/update",
            headers=_auth_headers(make_token, uid),
            data={"promptname": "x"},
        )
        assert resp.status_code == 404

    def test_update_requires_auth(self, client) -> None:
        resp = client.post("/api/prompts/1/update", data={"promptname": "x"})
        assert resp.status_code == 401

    def test_malformed_body_returns_400_not_silent_noop(self, client, make_token, make_user) -> None:
        """`update_prompt`'s malformed-body handling matches
        `create_prompt`'s: a 400, not a silent no-op 200.
        """
        uid = make_user()
        pid = _create_prompt(client, make_token, uid)
        resp = client.post(
            f"/api/prompts/{pid}/update",
            headers={**_auth_headers(make_token, uid), "Content-Type": "application/json"},
            content=b"{not valid json",
        )
        assert resp.status_code == 400


class TestDeletePrompt:
    def test_delete_own_prompt(self, client, make_token, make_user) -> None:
        uid = make_user()
        pid = _create_prompt(client, make_token, uid)
        resp = client.delete(f"/api/prompts/{pid}", headers=_auth_headers(make_token, uid))
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True, "id": pid}

        listing = client.get("/api/prompts/", headers=_auth_headers(make_token, uid))
        assert listing.json()["prompts"] == []

    def test_delete_someone_elses_prompt_returns_403(self, client, make_token, make_user) -> None:
        uid1 = make_user("u1@x.com")
        uid2 = make_user("u2@x.com")
        pid = _create_prompt(client, make_token, uid1)
        resp = client.delete(f"/api/prompts/{pid}", headers=_auth_headers(make_token, uid2))
        assert resp.status_code == 403

    def test_delete_missing_prompt_returns_404(self, client, make_token, make_user) -> None:
        uid = make_user()
        resp = client.delete("/api/prompts/999999", headers=_auth_headers(make_token, uid))
        assert resp.status_code == 404

    def test_delete_requires_auth(self, client) -> None:
        assert client.delete("/api/prompts/1").status_code == 401
