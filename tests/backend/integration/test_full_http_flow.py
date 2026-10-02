"""One full HTTP-level round trip through the real FastAPI app, wired to
the real throwaway Postgres database rather than the SQLite fixtures
used everywhere else -- this is the end-to-end proof that the
`TestClient` + dependency-override wiring used throughout
tests/backend/routes/ generalizes to a real database, not just SQLite's
more forgiving semantics.

Deliberately a SYNCHRONOUS test (`def`, not `async def`): Starlette's
`TestClient` drives the ASGI app through anyio, and -- confirmed while
writing this test -- it does not keep one event loop alive across the
whole client lifetime; each `client.get/post(...)` call can run on a
fresh loop. A normal pooled `AsyncEngine` hands the SECOND request a
connection object that's still bound to the FIRST request's loop,
failing with "attached to a different loop" / "cannot perform operation:
another operation is in progress". `NullPool` sidesteps this by opening
(and closing) a brand-new physical connection for every checkout, so no
connection is ever reused across requests/loops.
"""

from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.database import get_async_db
from backend.app.main import app as fastapi_app


def test_register_login_create_project_flow(integration_sync_engine, integration_db_url):
    parts = urlsplit(integration_db_url)
    async_url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, "", ""))
    async_engine = create_async_engine(async_url, poolclass=NullPool)

    AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _get_async_db():
        async with AsyncSession() as session:
            yield session

    fastapi_app.dependency_overrides[get_async_db] = _get_async_db
    try:
        from fastapi.testclient import TestClient

        client = TestClient(fastapi_app)

        register_resp = client.post(
            "/api/register/", json={"email": "integration@x.com", "password": "secret123"}
        )
        assert register_resp.status_code == 200
        token = register_resp.json()["access_token"]

        me_resp = client.get("/api/me/", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "integration@x.com"

        login_resp = client.post(
            "/api/login/", json={"email": "integration@x.com", "password": "secret123"}
        )
        assert login_resp.status_code == 200

        create_resp = client.post(
            "/api/create-project/",
            headers={"Authorization": f"Bearer {token}"},
            data={"name": "Integration Project"},
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["project"]["projectname"] == "Integration Project"
    finally:
        fastapi_app.dependency_overrides.pop(get_async_db, None)


def test_password_reset_revocation_flow(integration_sync_engine, integration_db_url, monkeypatch):
    """End-to-end integration test on real Postgres proving that resetting a password
    immediately revokes existing session credentials across all authenticated routes.
    """
    from urllib.parse import parse_qs, urlparse
    from backend.app.config import settings
    from backend.app.services import auth_service

    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "brevo_sender_email", "noreply@example.com")
    monkeypatch.setattr(settings, "frontend_url", "http://app.test")

    outbox: list[tuple[str, str]] = []

    async def _record(to: str, link: str) -> None:
        outbox.append((to, link))

    monkeypatch.setattr(auth_service, "send_reset_email", _record)

    parts = urlsplit(integration_db_url)
    async_url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, "", ""))
    async_engine = create_async_engine(async_url, poolclass=NullPool)
    AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _get_async_db():
        async with AsyncSession() as session:
            yield session

    fastapi_app.dependency_overrides[get_async_db] = _get_async_db
    try:
        from fastapi.testclient import TestClient

        client = TestClient(fastapi_app)

        # 1. Register user
        register_resp = client.post(
            "/api/register/", json={"email": "reset_integration@x.com", "password": "password123"}
        )
        assert register_resp.status_code == 200
        pre_reset_token = register_resp.json()["access_token"]
        pre_headers = {"Authorization": f"Bearer {pre_reset_token}"}

        # 2. Authenticated endpoints work before reset
        me_before = client.get("/api/me/", headers=pre_headers)
        assert me_before.status_code == 200
        assert me_before.json()["email"] == "reset_integration@x.com"

        create_before = client.post(
            "/api/create-project/",
            headers=pre_headers,
            data={"name": "Project Before Reset"},
        )
        assert create_before.status_code == 200

        # 3. Request reset and perform password change
        forgot_resp = client.post("/api/forgot-password/", json={"email": "reset_integration@x.com"})
        assert forgot_resp.status_code == 202
        assert len(outbox) == 1
        reset_link = outbox[0][1]
        reset_token = parse_qs(urlparse(reset_link).query)["token"][0]

        reset_resp = client.post(
            "/api/reset-password/",
            json={"token": reset_token, "new_password": "newpassword123"},
        )
        assert reset_resp.status_code == 200

        # 4. Old pre-reset token must immediately be rejected on /me/ and protected endpoints
        me_after = client.get("/api/me/", headers=pre_headers)
        assert me_after.status_code == 401

        create_after = client.post(
            "/api/create-project/",
            headers=pre_headers,
            data={"name": "Should Fail"},
        )
        assert create_after.status_code == 401

        # 5. Login with new credentials returns a fresh, valid token
        login_resp = client.post(
            "/api/login/",
            json={"email": "reset_integration@x.com", "password": "newpassword123"},
        )
        assert login_resp.status_code == 200
        post_reset_token = login_resp.json()["access_token"]
        post_headers = {"Authorization": f"Bearer {post_reset_token}"}

        me_new = client.get("/api/me/", headers=post_headers)
        assert me_new.status_code == 200

        create_new = client.post(
            "/api/create-project/",
            headers=post_headers,
            data={"name": "Project After Reset"},
        )
        assert create_new.status_code == 200
        assert create_new.json()["project"]["projectname"] == "Project After Reset"
    finally:
        fastapi_app.dependency_overrides.pop(get_async_db, None)
