"""Tests for backend/app/api/auth_routes.py: /api/login/, /api/register/,
/api/me/, /api/logout/.

All ORM-only (no raw SQL, no network), so they run against the
`override_async_db` in-memory SQLite fixture -- no Postgres needed.
"""

import pytest

pytestmark = pytest.mark.usefixtures("override_async_db")


class TestRegister:
    def test_register_creates_user_and_sets_cookie(self, client) -> None:
        resp = client.post("/api/register/", json={"email": "a@b.com", "password": "secret123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "a@b.com"
        assert "access_token" in body
        assert "access_token" in resp.cookies

    def test_register_duplicate_email_returns_400(self, client) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "password-x"})
        resp = client.post("/api/register/", json={"email": "a@b.com", "password": "password-y"})
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_register_duplicate_email_differing_only_in_case_returns_400(self, client) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "password-x"})
        resp = client.post("/api/register/", json={"email": " A@B.Com ", "password": "password-y"})
        assert resp.status_code == 400

    def test_register_losing_a_race_for_the_same_email_returns_400(self, client, monkeypatch) -> None:
        """Both requests pass the "already registered?" check before either
        commits; the loser hits the lower(email) unique index, which must
        read as a duplicate (400), not a 500 echoing the SQL.
        """
        from unittest.mock import AsyncMock

        from backend.app.services import auth_service

        assert client.post("/api/register/", json={"email": "race@b.com", "password": "password-x"}).status_code == 200
        monkeypatch.setattr(auth_service, "find_user_by_email", AsyncMock(return_value=None))

        resp = client.post("/api/register/", json={"email": "Race@b.com", "password": "password-x"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Email already registered"

    @pytest.mark.parametrize(
        "body",
        [{"email": "a@b.com", "password": "short"}, {"email": "not-an-email", "password": "long-enough"}],
        ids=["password under 8 characters", "malformed email"],
    )
    def test_register_rejects_weak_password_or_malformed_email(self, client, body) -> None:
        assert client.post("/api/register/", json=body).status_code == 422

    def test_register_stores_email_lowercased(self, client) -> None:
        resp = client.post("/api/register/", json={"email": " Mixed@Case.COM ", "password": "password-x"})
        assert resp.json()["email"] == "mixed@case.com"

    def test_register_missing_field_returns_422(self, client) -> None:
        resp = client.post("/api/register/", json={"email": "a@b.com"})
        assert resp.status_code == 422

    def test_register_password_is_hashed_not_stored_plaintext(self, client) -> None:
        resp = client.post("/api/register/", json={"email": "a@b.com", "password": "plaintext"})
        assert resp.status_code == 200
        login = client.post("/api/login/", json={"email": "a@b.com", "password": "plaintext"})
        assert login.status_code == 200


class TestLogin:
    def test_login_success(self, client) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "secret-password"})
        resp = client.post("/api/login/", json={"email": "a@b.com", "password": "secret-password"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "a@b.com"
        assert "access_token" in resp.cookies

    def test_login_wrong_password_returns_401(self, client) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "secret-password"})
        resp = client.post("/api/login/", json={"email": "a@b.com", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_email_is_case_insensitive(self, client) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "password-pw"})
        resp = client.post("/api/login/", json={"email": " A@B.COM ", "password": "password-pw"})
        assert resp.status_code == 200

    @pytest.fixture()
    async def mixed_case_user(self, async_sqlite_engine) -> None:
        """A row stored before emails were normalized on the way in."""
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from backend.app.api.utils import _hash_password
        from backend.app.database import User

        async with async_sessionmaker(async_sqlite_engine)() as db:
            db.add(User(email="Legacy@B.com", password=_hash_password("pw")))
            await db.commit()

    def test_login_matches_mixed_case_stored_email(self, client, mixed_case_user) -> None:
        resp = client.post("/api/login/", json={"email": "legacy@b.com", "password": "pw"})
        assert resp.status_code == 200

    def test_login_unknown_email_returns_401_not_404(self, client) -> None:
        # Must not leak whether the email exists via a different status.
        resp = client.post("/api/login/", json={"email": "nobody@x.com", "password": "password-x"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_missing_field_returns_422(self, client) -> None:
        resp = client.post("/api/login/", json={"email": "a@b.com"})
        assert resp.status_code == 422


class TestMe:
    def test_me_without_auth_returns_401(self, client) -> None:
        resp = client.get("/api/me/")
        assert resp.status_code == 401

    def test_me_with_valid_cookie_returns_user(self, client) -> None:
        reg = client.post("/api/register/", json={"email": "a@b.com", "password": "password-x"})
        token = reg.json()["access_token"]
        client.cookies.set("access_token", token)
        resp = client.get("/api/me/")
        assert resp.status_code == 200
        assert resp.json()["email"] == "a@b.com"

    def test_me_with_valid_bearer_header_returns_user(self, client) -> None:
        reg = client.post("/api/register/", json={"email": "a@b.com", "password": "password-x"})
        token = reg.json()["access_token"]
        resp = client.get("/api/me/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_me_with_malformed_bearer_header_returns_401_not_500(self, client) -> None:
        # Exercises the fixed get_user_id_from_request bug end-to-end.
        resp = client.get("/api/me/", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401

    def test_me_for_deleted_user_returns_401(self, client, make_token) -> None:
        # A well-signed token whose subject doesn't exist in the DB.
        token = make_token(sub="999999")
        client.cookies.set("access_token", token)
        resp = client.get("/api/me/")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Not authenticated"


class TestLogout:
    def test_logout_clears_cookie_no_auth_required(self, client) -> None:
        resp = client.post("/api/logout/")
        assert resp.status_code == 200
        assert resp.json() == {"message": "Logged out"}
        set_cookie = resp.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie


class TestPasswordReset:
    """Forgot/reset flow with the Brevo send replaced by a recorder."""

    @pytest.fixture()
    def sent(self, monkeypatch) -> list[tuple[str, str]]:
        from backend.app.config import settings
        from backend.app.services import auth_service

        monkeypatch.setattr(settings, "brevo_api_key", "test-key")
        monkeypatch.setattr(settings, "brevo_sender_email", "noreply@example.com")
        monkeypatch.setattr(settings, "frontend_url", "http://app.test")
        outbox: list[tuple[str, str]] = []

        async def _record(to: str, link: str) -> None:
            outbox.append((to, link))

        monkeypatch.setattr(auth_service, "send_reset_email", _record)
        return outbox

    @staticmethod
    def _token(link: str) -> str:
        from urllib.parse import parse_qs, urlparse

        return parse_qs(urlparse(link).query)["token"][0]

    def test_forgot_known_email_sends_link(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        resp = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        assert resp.status_code == 202
        assert len(sent) == 1
        to, link = sent[0]
        assert to == "a@b.com"
        assert link.startswith("http://app.test/reset-password?token=")

    def test_forgot_email_is_case_insensitive(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        resp = client.post("/api/forgot-password/", json={"email": " A@B.COM "})
        assert resp.status_code == 202
        assert [to for to, _ in sent] == ["a@b.com"]

    def test_forgot_unknown_email_same_response_and_no_send(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        known = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        unknown = client.post("/api/forgot-password/", json={"email": "nobody@x.com"})
        assert unknown.status_code == known.status_code == 202
        assert unknown.json() == known.json()
        assert len(sent) == 1

    def test_forgot_within_cooldown_sends_once(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        resp = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        assert resp.status_code == 202
        assert len(sent) == 1

    def test_forgot_without_brevo_config_sends_nothing(self, client, sent, monkeypatch) -> None:
        from backend.app.config import settings

        monkeypatch.setattr(settings, "brevo_api_key", "")
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        resp = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        assert resp.status_code == 202
        assert sent == []

    def test_reset_changes_password(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        token = self._token(sent[0][1])
        resp = client.post("/api/reset-password/", json={"token": token, "new_password": "new-password"})
        assert resp.status_code == 200
        assert client.post("/api/login/", json={"email": "a@b.com", "password": "old-password"}).status_code == 401
        assert client.post("/api/login/", json={"email": "a@b.com", "password": "new-password"}).status_code == 200

    def test_reset_token_is_single_use(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        token = self._token(sent[0][1])
        client.post("/api/reset-password/", json={"token": token, "new_password": "new-password"})
        again = client.post("/api/reset-password/", json={"token": token, "new_password": "evil-password"})
        assert again.status_code == 400
        assert client.post("/api/login/", json={"email": "a@b.com", "password": "new-password"}).status_code == 200

    def test_expired_token_rejected(self, client, sent, monkeypatch) -> None:
        from backend.app.config import settings

        monkeypatch.setattr(settings, "password_reset_token_expire_minutes", -1)
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        resp = client.post(
            "/api/reset-password/", json={"token": self._token(sent[0][1]), "new_password": "new-password"}
        )
        assert resp.status_code == 400

    def test_session_token_cannot_reset_password(self, client) -> None:
        reg = client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        resp = client.post(
            "/api/reset-password/",
            json={"token": reg.json()["access_token"], "new_password": "new-password"},
        )
        assert resp.status_code == 400

    def test_reset_token_is_not_a_session_token(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old-password"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        token = self._token(sent[0][1])
        client.cookies.clear()  # register's session cookie would take precedence
        resp = client.get("/api/me/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_reset_password_immediately_invalidates_pre_reset_session_cookie(self, client, sent) -> None:
        reg = client.post("/api/register/", json={"email": "cookie_user@b.com", "password": "old-password"})
        assert reg.status_code == 200
        me_before = client.get("/api/me/")
        assert me_before.status_code == 200
        assert me_before.json()["email"] == "cookie_user@b.com"

        client.post("/api/forgot-password/", json={"email": "cookie_user@b.com"})
        token = self._token(sent[0][1])
        reset_resp = client.post(
            "/api/reset-password/", json={"token": token, "new_password": "new-password"}
        )
        assert reset_resp.status_code == 200

        me_after = client.get("/api/me/")
        assert me_after.status_code == 401
        assert me_after.json()["detail"] == "Not authenticated"

    def test_reset_password_immediately_invalidates_pre_reset_bearer_token(self, client, sent) -> None:
        reg = client.post("/api/register/", json={"email": "bearer_user@b.com", "password": "old-password"})
        assert reg.status_code == 200
        old_token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {old_token}"}
        client.cookies.clear()

        me_before = client.get("/api/me/", headers=headers)
        assert me_before.status_code == 200

        client.post("/api/forgot-password/", json={"email": "bearer_user@b.com"})
        reset_token = self._token(sent[0][1])
        client.post("/api/reset-password/", json={"token": reset_token, "new_password": "new-password"})

        me_after = client.get("/api/me/", headers=headers)
        assert me_after.status_code == 401
        assert me_after.json()["detail"] == "Not authenticated"

        login = client.post("/api/login/", json={"email": "bearer_user@b.com", "password": "new-password"})
        assert login.status_code == 200
        new_token = login.json()["access_token"]
        me_new = client.get("/api/me/", headers={"Authorization": f"Bearer {new_token}"})
        assert me_new.status_code == 200

    def test_reset_password_invalidates_access_to_protected_endpoints(self, client, sent) -> None:
        reg = client.post("/api/register/", json={"email": "endpoint_user@b.com", "password": "old-password"})
        old_token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {old_token}"}
        client.cookies.clear()

        proj_before = client.get("/api/projects/", headers=headers)
        assert proj_before.status_code == 200

        client.post("/api/forgot-password/", json={"email": "endpoint_user@b.com"})
        reset_token = self._token(sent[0][1])
        client.post("/api/reset-password/", json={"token": reset_token, "new_password": "new-password"})

        proj_after = client.get("/api/projects/", headers=headers)
        assert proj_after.status_code == 401
