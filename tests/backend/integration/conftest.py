"""Fixtures for the opt-in integration suite.

Everything here is marked `integration` (see `pytest.ini`'s default
`addopts = -m "not integration"`) and is skipped by a plain `pytest` run.
Opt in explicitly with:

    .venv/bin/python -m pytest -m integration tests/backend/integration/

This is the only place in the test suite that touches a REAL Postgres
server. It creates a dedicated, disposable `qualitative_coding_tool_test`
database (derived from the same host/port/user as the app's normal
`DATABASE_URL`, never the configured database name itself), runs the ORM
schema against it, and drops it again at the end of the session. Your
actual dev database is never opened by anything in this file.
"""

import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def pytest_collection_modifyitems(items):
    """Auto-mark every test under this directory as `integration`.

    A bare module-level `pytestmark` here would only apply within THIS
    conftest.py -- it does not propagate to sibling test files, so each
    test module would need to repeat `pytestmark = pytest.mark.integration`
    itself. This hook applies the marker directory-wide instead, which is
    what actually makes `pytest.ini`'s default `-m "not integration"`
    exclude these tests, and what makes `-m integration` select them.
    """
    for item in items:
        if "tests/backend/integration/" in str(item.fspath).replace(os.sep, "/"):
            item.add_marker(pytest.mark.integration)


def _admin_url_and_target_db() -> tuple[str, str]:
    """Derive an admin connection URL (targeting the default `postgres`
    maintenance DB) and a fresh, disposable target database name, from
    whatever real Postgres connection info is configured for the app --
    explicitly NOT from the sentinel `DATABASE_URL` set in
    tests/conftest.py, which is a fake host/user that must never resolve.
    """
    base = (
        os.environ.get("INTEGRATION_DATABASE_URL")
        or os.environ.get("REAL_DATABASE_URL")
    )
    if not base:
        pg_user = os.environ.get("PGUSER", "postgres")
        pg_pass = os.environ.get("PGPASSWORD", "")
        pg_host = os.environ.get("PGHOST", "localhost")
        pg_port = os.environ.get("PGPORT", "5432")
        auth = f"{pg_user}:{pg_pass}@" if pg_pass else f"{pg_user}@"
        base = f"postgresql://{auth}{pg_host}:{pg_port}/postgres"

    parts = urlsplit(base)
    admin_url = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    target_db = f"qualitative_coding_tool_test_{uuid.uuid4().hex[:8]}"
    return admin_url, target_db


@pytest.fixture(scope="session")
def integration_db_url():
    """Create a fresh throwaway Postgres database for this test session
    and drop it afterward, regardless of test outcome.
    """
    admin_url, target_db = _admin_url_and_target_db()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Could not create throwaway integration database: {exc}")
    finally:
        admin_engine.dispose()

    parts = urlsplit(admin_url)
    db_url = urlunsplit((parts.scheme, parts.netloc, f"/{target_db}", "", ""))

    yield db_url

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": target_db},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{target_db}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def integration_sync_engine(integration_db_url):
    from backend.app.database import Base

    engine = create_engine(integration_db_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest_asyncio.fixture()
async def integration_async_engine(integration_db_url, integration_sync_engine):
    # Function-scoped, not session-scoped: asyncpg connections are bound
    # to the event loop they were created on, and pytest-asyncio gives
    # each test function its own loop by default. A session-scoped async
    # engine would have its pool created on the first test's loop and
    # then fail with "another operation is in progress" / "Event loop is
    # closed" on every subsequent test. The throwaway database itself
    # (created once per session) is cheap to reconnect to per test.
    #
    # Depends on `integration_sync_engine` purely for its side effect
    # (`Base.metadata.create_all`) -- tests that only ever request this
    # async fixture still need the schema to exist.
    parts = urlsplit(integration_db_url)
    async_url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, "", ""))
    engine = create_async_engine(async_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def integration_async_session(integration_async_engine):
    SessionLocal = async_sessionmaker(integration_async_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
