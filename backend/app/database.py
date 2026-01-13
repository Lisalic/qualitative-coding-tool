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


def get_db():
    """Yield a SQLAlchemy session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


class AuthUser(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column("password_hash", String, nullable=False)
    date_created = Column("created_at", DateTime(timezone=True), server_default=func.now())
    # Do not define `projects` relationship here to avoid mapper/back_populates conflicts


class ProjectTable(Base):
    __tablename__ = "project_tables"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    table_name = Column(String, nullable=False) # Table name inside the schema
    row_count = Column(Integer, default=0)

    project = relationship("Project", back_populates="tables")


class Prompt(Base):
    __tablename__ = "prompts"

    # Integer primary key (rowid) as requested
    rowid = Column(Integer, primary_key=True, autoincrement=True)
    # Link to users table
    uuid = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    display_name = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    type = Column(String, nullable=False)

    # Relationship to User for convenience
    user = relationship("User", backref="prompts")


# Ensure tables exist in the target database. Wrap in try/except so
# failures (e.g., DB not available during local dev) don't crash imports.
try: 
    Base.metadata.create_all(bind=engine)
except Exception as _err:
    # Defer detailed error handling to startup logs; printing helps
    # debugging when running scripts interactively.
    print("Warning: could not create DB tables:", _err)
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


def get_db():
    """Yield a SQLAlchemy session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


# Compatibility ORM used by existing routes expecting `AuthUser` with
# attributes `hashed_password` and `date_created`. This maps to the same
# underlying `users` table but exposes the legacy attribute names.
class AuthUser(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    # Map attribute `hashed_password` to the actual column `password_hash`
    hashed_password = Column("password_hash", String, nullable=False)
    # Map attribute `date_created` to the actual column `created_at`
    date_created = Column("created_at", DateTime(timezone=True), server_default=func.now())

    # Optional relationship (not required by routes but harmless)
    # No relationship here to avoid mapper/back_populates conflicts


class ProjectTable(Base):
    __tablename__ = "project_tables"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    table_name = Column(String, nullable=False) # Table name inside the schema
    row_count = Column(Integer, default=0)

    project = relationship("Project", back_populates="tables")