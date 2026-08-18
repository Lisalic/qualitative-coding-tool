"""Shared pytest fixtures for the backend test suite.

Import-order safety
--------------------
This file sets ``DATABASE_URL`` to a sentinel value *before* any
``backend.*`` module is imported, so the real dev database can never be
touched by the default test run.

Why this is safe: ``backend/app/database.py`` calls
``load_dotenv(backend/.env)`` (default ``override=False``) and only then
reads ``os.environ.get("DATABASE_URL")``. A value already present in the
environment therefore always wins over ``backend/.env`` -- verified
empirically before writing this fixture (see plan notes). The sentinel
name embeds ``_test`` so a real connection attempt is easy to spot in
logs, and none of the default (non-``integration``-marked) tests connect
to Postgres at all: ORM-backed routes are exercised against an in-memory
SQLite database, and raw-SQL/network code paths are exercised only up to
their validation/auth/guard boundary with the engine patched to a sentinel
that fails loudly if actually used.
"""

import os

os.environ["DATABASE_URL"] = (
    "postgresql://sentinel:sentinel@localhost:5432/"
    "qualitative_coding_tool_test__DO_NOT_USE"
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key-unused")

from typing import Any, AsyncIterator, Iterator  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app.auth import create_access_token  # noqa: E402
from backend.app.database import Base, get_async_db, get_db  # noqa: E402
from backend.app.main import app as fastapi_app  # noqa: E402


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """A ``TestClient`` built *without* the ``with`` block.

    Starlette's ``TestClient`` only runs the ASGI ``lifespan`` (which, for
    this app, opens a real Postgres connection via ``async_engine.begin()``)
    on ``__enter__``/``__exit__``. A bare ``TestClient(app).get(...)`` never
    triggers it -- verified empirically with a lifespan that raises.
    """
    yield TestClient(fastapi_app)


@pytest.fixture()
def sqlite_engine():
    """Fresh in-memory SQLite database per test, standing in for the
    relational metadata tables (``users``, ``projects``, ``files``, ...).
    ``StaticPool`` keeps one connection alive across ``Session()`` calls
    within a single test so ``:memory:`` data isn't lost between queries.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine) -> Iterator[Session]:
    SessionLocal = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def override_db(db_session: Session) -> Iterator[Session]:
    """Install a ``get_db`` override that always yields ``db_session``."""

    def _get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _get_db
    try:
        yield db_session
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def async_sqlite_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture()
async def override_async_db(async_sqlite_engine) -> AsyncIterator[None]:
    """Install a ``get_async_db`` override backed by in-memory SQLite."""
    SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)

    async def _get_async_db():
        async with SessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_async_db] = _get_async_db
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.pop(get_async_db, None)


@pytest.fixture()
def patch_async_database_manager(monkeypatch, async_sqlite_engine):
    """Some routes (e.g. ``list_projects``, ``save_comparison``) construct
    ``AsyncDatabaseManager()`` directly instead of going through
    ``Depends(get_async_db)``, so ``app.dependency_overrides`` can't reach
    them. ``AsyncDatabaseManager.__aenter__`` calls the module-level
    ``AsyncSessionLocal`` imported into ``backend.app.databasemanager`` --
    patch that name to a sessionmaker bound to the in-memory SQLite engine.
    """
    SessionLocal = async_sessionmaker(async_sqlite_engine, expire_on_commit=False)
    monkeypatch.setattr("backend.app.databasemanager.AsyncSessionLocal", SessionLocal)
    return SessionLocal


@pytest.fixture()
def frozen_time(monkeypatch) -> float:
    """Freeze ``time.time()`` as seen by ``backend.app.auth`` so JWT
    ``iat``/``exp`` boundaries are deterministic. Returns the frozen epoch.
    """
    fixed = 1_700_000_000.0
    monkeypatch.setattr("backend.app.auth.time.time", lambda: fixed)
    return fixed


@pytest.fixture()
def make_token():
    """Factory: ``make_token(sub="1", **extra_claims) -> str`` signed JWT."""

    def _make(sub: Any = "1", **extra: Any) -> str:
        payload = {"sub": sub, **extra}
        return create_access_token(payload)

    return _make


@pytest.fixture()
def auth_cookies(make_token) -> dict[str, str]:
    return {"access_token": make_token()}


class FakeRequest:
    """Minimal stand-in for ``fastapi.Request``, exposing only what
    ``get_user_id_from_request`` reads: ``.cookies`` and ``.headers``.
    """

    def __init__(
        self, cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None
    ) -> None:
        self.cookies = cookies or {}
        self.headers = headers or {}


@pytest.fixture()
def fake_request():
    return FakeRequest


@pytest.fixture()
def unused_engine() -> MagicMock:
    """A sentinel ``engine``-shaped mock that raises if actually used.

    For negative-path route tests (auth/validation/schema-guard failures
    that must short-circuit *before* touching the database), patch a route
    module's imported ``engine``/``async_engine`` name to this and assert
    the guard fires first -- i.e. that the mock's ``.connect()``/``.begin()``
    is never called.
    """
    mock = MagicMock(name="unused_engine")
    mock.connect.side_effect = AssertionError(
        "engine.connect() was called but this test expected the request "
        "to be rejected before touching the database"
    )
    mock.begin.side_effect = AssertionError(
        "engine.begin() was called but this test expected the request "
        "to be rejected before touching the database"
    )
    return mock
