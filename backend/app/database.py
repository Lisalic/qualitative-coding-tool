import os
import re
from pathlib import Path
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    DateTime,
    Table,
    create_engine,
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from dotenv import load_dotenv
import uuid

# Load .env from backend/ if present so running scripts picks up DATABASE_URL
env_path = Path(__file__).resolve().parents[1] / ".env"
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

# Create SQLAlchemy engine and session factory (sync — scripts and incremental migration)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

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


def get_db():
    """Yield a SQLAlchemy session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async session for FastAPI; callers commit/rollback explicitly (matches get_db)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Association table for many-to-many between projects and files
project_files_table = Table(
    "project_files",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("file_id", Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True),
)


async def async_link_file_to_project(session: AsyncSession, file_id: int, project_id: int) -> None:
    """Associate a file with a project via ``project_files`` (avoids ORM collection lazy IO in async)."""
    stmt = (
        pg_insert(project_files_table)
        .values(project_id=project_id, file_id=file_id)
        .on_conflict_do_nothing(
            index_elements=[
                project_files_table.c.project_id,
                project_files_table.c.file_id,
            ],
        )
    )
    await session.execute(stmt)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column("hashed_password", String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
    prompts = relationship("Prompt", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    projectname = Column(String, nullable=False)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="projects")
    files = relationship("File", secondary=project_files_table, back_populates="projects")



class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    schemaname = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    file_type = Column(String)
    description = Column(String)
    systemprompt = Column(String)
    userprompt = Column(String)

    user = relationship("User", back_populates="files")
    projects = relationship("Project", secondary=project_files_table, back_populates="files")
    tables = relationship("FileTable", back_populates="file", cascade="all, delete-orphan")


class FileTable(Base):
    __tablename__ = "file_tables"

    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    tablename = Column(String, primary_key=True)
    row_count = Column(Integer, default=0)

    file = relationship("File", back_populates="tables")


class FileDependency(Base):
    __tablename__ = "file_dependencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    child_file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    parent_file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    child_file = relationship("File", foreign_keys=[child_file_id], backref="child_dependencies")
    parent_file = relationship("File", foreign_keys=[parent_file_id], backref="parent_dependencies")


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    promptname = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    type = Column(String)

    user = relationship("User", back_populates="prompts")
