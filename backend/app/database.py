from __future__ import annotations

from pathlib import Path
import os
import uuid

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    TIMESTAMP,
    ForeignKey,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Load .env from the backend folder (explicit path so imports work independent of CWD)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Read credentials (support both PG* standard vars and fallback names)
DB_HOST = os.getenv("PGHOST", os.getenv("DB_HOST", "localhost"))
DB_PORT = os.getenv("PGPORT", os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("PGUSER", os.getenv("DB_USER", "qc_user"))
DB_PASSWORD = os.getenv("PGPASSWORD", os.getenv("DB_PASSWORD", "password"))
DB_NAME = os.getenv("PGDATABASE", os.getenv("DB_NAME", os.getenv("DATABASE", "qualitative_coding_auth")))

# Allow a full DATABASE_URL in the env to override composed values
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

# Create SQLAlchemy engine and session factory
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    files = relationship("UserFile", back_populates="user")


# Authentication user table (UUID primary key). Maps to the created `user` table.
class AuthUser(Base):
    __tablename__ = "user"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    date_created = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class UserFile(Base):
    __tablename__ = "user_files"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    display_name = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    user = relationship("User", back_populates="files")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> None:
    """Attempt a simple connection and print status."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Connected to {DB_NAME} at {DB_HOST}:{DB_PORT} successfully.")
    except Exception as exc:
        print("Failed to connect to the database:", exc)
        raise

