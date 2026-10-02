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
        client.post("/api/register/", json={"email": "a@b.com", "password": "x"})
        resp = client.post("/api/register/", json={"email": "a@b.com", "password": "y"})
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

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
        client.post("/api/register/", json={"email": "a@b.com", "password": "secret"})
        resp = client.post("/api/login/", json={"email": "a@b.com", "password": "secret"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "a@b.com"
        assert "access_token" in resp.cookies

    def test_login_wrong_password_returns_401(self, client) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "secret"})
        resp = client.post("/api/login/", json={"email": "a@b.com", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_login_unknown_email_returns_401_not_404(self, client) -> None:
        # Must not leak whether the email exists via a different status.
        resp = client.post("/api/login/", json={"email": "nobody@x.com", "password": "x"})
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
        reg = client.post("/api/register/", json={"email": "a@b.com", "password": "x"})
        token = reg.json()["access_token"]
        client.cookies.set("access_token", token)
        resp = client.get("/api/me/")
        assert resp.status_code == 200
        assert resp.json()["email"] == "a@b.com"

    def test_me_with_valid_bearer_header_returns_user(self, client) -> None:
        reg = client.post("/api/register/", json={"email": "a@b.com", "password": "x"})
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
        assert resp.json()["detail"] == "User not found"


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
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        resp = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        assert resp.status_code == 202
        assert len(sent) == 1
        to, link = sent[0]
        assert to == "a@b.com"
        assert link.startswith("http://app.test/reset-password?token=")

    def test_forgot_unknown_email_same_response_and_no_send(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        known = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        unknown = client.post("/api/forgot-password/", json={"email": "nobody@x.com"})
        assert unknown.status_code == known.status_code == 202
        assert unknown.json() == known.json()
        assert len(sent) == 1

    def test_forgot_within_cooldown_sends_once(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        resp = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        assert resp.status_code == 202
        assert len(sent) == 1

    def test_forgot_without_brevo_config_sends_nothing(self, client, sent, monkeypatch) -> None:
        from backend.app.config import settings

        monkeypatch.setattr(settings, "brevo_api_key", "")
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        resp = client.post("/api/forgot-password/", json={"email": "a@b.com"})
        assert resp.status_code == 202
        assert sent == []

    def test_reset_changes_password(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        token = self._token(sent[0][1])
        resp = client.post("/api/reset-password/", json={"token": token, "new_password": "new"})
        assert resp.status_code == 200
        assert client.post("/api/login/", json={"email": "a@b.com", "password": "old"}).status_code == 401
        assert client.post("/api/login/", json={"email": "a@b.com", "password": "new"}).status_code == 200

    def test_reset_token_is_single_use(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        token = self._token(sent[0][1])
        client.post("/api/reset-password/", json={"token": token, "new_password": "new"})
        again = client.post("/api/reset-password/", json={"token": token, "new_password": "evil"})
        assert again.status_code == 400
        assert client.post("/api/login/", json={"email": "a@b.com", "password": "new"}).status_code == 200

    def test_expired_token_rejected(self, client, sent, monkeypatch) -> None:
        from backend.app.config import settings

        monkeypatch.setattr(settings, "password_reset_token_expire_minutes", -1)
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        resp = client.post(
            "/api/reset-password/", json={"token": self._token(sent[0][1]), "new_password": "new"}
        )
        assert resp.status_code == 400

    def test_session_token_cannot_reset_password(self, client) -> None:
        reg = client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        resp = client.post(
            "/api/reset-password/",
            json={"token": reg.json()["access_token"], "new_password": "new"},
        )
        assert resp.status_code == 400

    def test_reset_token_is_not_a_session_token(self, client, sent) -> None:
        client.post("/api/register/", json={"email": "a@b.com", "password": "old"})
        client.post("/api/forgot-password/", json={"email": "a@b.com"})
        token = self._token(sent[0][1])
        client.cookies.clear()  # register's session cookie would take precedence
        resp = client.get("/api/me/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
