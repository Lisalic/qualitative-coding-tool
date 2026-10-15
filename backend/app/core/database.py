"""Async engine, session factory and the declarative ``Base`` every ORM
model in ``backend/app/models/`` registers on."""

import os
import re
from pathlib import Path
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from dotenv import load_dotenv

# Load .env from backend/ if present so running scripts picks up DATABASE_URL
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Build database URL from env
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("AUTH_DATABASE_URL")
if not DATABASE_URL:
    pg_user = os.environ.get("PGUSER") or os.environ.get("DB_USER") or "postgres"
    pg_pass = os.environ.get("PGPASSWORD") or os.environ.get("DB_PASSWORD") or ""
    pg_host = os.environ.get("PGHOST") or "localhost"
    pg_port = os.environ.get("PGPORT") or "5432"
    pg_db = os.environ.get("PGDATABASE") or os.environ.get("DB_NAME") or "qualitative_coding_tool"
    if pg_pass:
        DATABASE_URL = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    else:
        DATABASE_URL = f"postgresql://{pg_user}@{pg_host}:{pg_port}/{pg_db}"


def _sync_url_to_asyncpg(sync_url: str) -> tuple[str, dict[str, Any]]:
    """Build a SQLAlchemy asyncpg URL from any sync Postgres URL.

    asyncpg does not understand libpq ``sslmode=`` query parameters. If present,
    they are stripped and mapped to connect_args['ssl'] when possible.
    """
    u = sync_url.strip()
    u = re.sub(r"^postgresql\+[^:/]+://", "postgresql://", u, count=1)
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]
    if not u.startswith("postgresql://"):
        u = "postgresql://" + u.split("://", 1)[-1]

    connect_args: dict[str, Any] = {}
    ssl_match = re.search(r"[?&]sslmode=([^&]*)", u, re.I)
    if ssl_match:
        mode = (ssl_match.group(1) or "").lower()
        if mode in ("require", "verify-ca", "verify-full", "prefer", "allow"):
            connect_args["ssl"] = True
        elif mode == "disable":
            connect_args["ssl"] = False
        u = re.sub(r"[?&]sslmode=[^&]*", "", u)
        u = re.sub(r"\?&", "?", u).rstrip("?&")

    async_url = "postgresql+asyncpg://" + u[len("postgresql://") :]
    return async_url, connect_args


ASYNC_DATABASE_URL, _async_connect_args = _sync_url_to_asyncpg(DATABASE_URL)

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_async_connect_args,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base(cls=AsyncAttrs)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async session for FastAPI; callers commit/rollback explicitly.

    Catches ``BaseException``, not just ``Exception``: a cancelled request
    (client disconnect) raises ``asyncio.CancelledError``/``GeneratorExit``
    at this generator's ``yield``, and both inherit from ``BaseException``,
    not ``Exception`` -- an ``except Exception`` here would silently skip
    the explicit rollback for exactly the disconnect case that leaves a
    transaction open longest.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
