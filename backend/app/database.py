import os
from pathlib import Path

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
from sqlalchemy.sql import func
from dotenv import load_dotenv

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

# Create SQLAlchemy engine and session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """Yield a SQLAlchemy session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Association table for many-to-many between projects and files
project_files_table = Table(
    "project_files",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("file_id", Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
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

    user = relationship("User", back_populates="files")
    projects = relationship("Project", secondary=project_files_table, back_populates="files")
    tables = relationship("FileTable", back_populates="file", cascade="all, delete-orphan")


class FileTable(Base):
    __tablename__ = "file_tables"

    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    tablename = Column(String, primary_key=True)
    row_count = Column(Integer, default=0)

    file = relationship("File", back_populates="tables")


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    promptname = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    type = Column(String)

    user = relationship("User", back_populates="prompts")


try:
    Base.metadata.create_all(bind=engine)
except Exception as _err:
    print("Warning: could not create DB tables:", _err)
 