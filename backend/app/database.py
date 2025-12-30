import os
import uuid
from pathlib import Path

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load .env from backend/ if present so running scripts picks up DATABASE_URL
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Build database URL from env
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("AUTH_DATABASE_URL")
if not DATABASE_URL:
    # Fallback to individual PG vars if provided
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

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to Projects
    projects = relationship("Project", back_populates="user")
class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    display_name = Column(String, nullable=False)  # Editable frontend name
    schema_name = Column(String, unique=True, nullable=False) # Fixed backend schema name
    project_type = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="projects")
    tables = relationship("ProjectTable", back_populates="project", cascade="all, delete-orphan")

class ProjectTable(Base):
    __tablename__ = "project_tables"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    table_name = Column(String, nullable=False) # Table name inside the schema
    row_count = Column(Integer, default=0)

    project = relationship("Project", back_populates="tables")