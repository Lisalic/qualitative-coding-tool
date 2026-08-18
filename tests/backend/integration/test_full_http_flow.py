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
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.database import get_async_db, get_db
from backend.app.main import app as fastapi_app


def test_register_login_create_project_flow(integration_sync_engine, integration_db_url):
    parts = urlsplit(integration_db_url)
    async_url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, "", ""))
    async_engine = create_async_engine(async_url, poolclass=NullPool)

    SyncSession = sessionmaker(bind=integration_sync_engine, expire_on_commit=False)
    AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)

    def _get_db():
        db = SyncSession()
        try:
            yield db
        finally:
            db.close()

    async def _get_async_db():
        async with AsyncSession() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _get_db
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
        fastapi_app.dependency_overrides.pop(get_db, None)
        fastapi_app.dependency_overrides.pop(get_async_db, None)
