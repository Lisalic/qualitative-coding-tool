"""Relational metadata: users, projects, files and the saved prompt library.

A ``files`` row is an artifact's identity only; its content lives in the
fixed tables of ``storage.py`` and ``versioning.py``.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.app.core.database import Base


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
    password = Column("hashed_password", String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Last time a reset email was sent -- a per-account cooldown that holds
    # across every backend instance (see services/auth_service.py).
    password_reset_requested_at = Column(DateTime(timezone=True), nullable=True)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
    prompts = relationship("Prompt", back_populates="user", cascade="all, delete-orphan")

    # Emails are case-insensitive: Foo@x.com and foo@x.com are one account.
    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)


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
