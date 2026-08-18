"""Fixed, indexed storage tables, keyed by ``file_id``.

Replaces the old model of creating a brand-new Postgres schema per
artifact (``proj_*``/``cmp_*``/``sum_*``) with a handful of normal
tables. ``files.schemaname`` stays as the opaque identifier the frontend
already passes around; these tables are looked up by ``file_id``
(resolved from ``schemaname`` via ``repositories/file_repo.py``), not by
a dynamic schema name spliced into SQL.

``word_count`` on ``Submission``/``Comment`` is declared here as a plain
``Integer`` for ORM/test purposes (SQLite has no equivalent of Postgres
generated columns); the real ``GENERATED ALWAYS AS (...) STORED`` DDL is
added by the Alembic migration that creates these tables against
Postgres, matching the expression the old per-artifact-schema DDL used.

Landed in Stage 0, unused by any route until each domain's stage wires
its repository in.
"""

from sqlalchemy import Column, ForeignKey, Integer, BigInteger, String, Text, DateTime, Index
from sqlalchemy.sql import func

from backend.app.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    id = Column(String, primary_key=True)
    subreddit = Column(String)
    title = Column(String)
    selftext = Column(String)
    author = Column(String)
    created_utc = Column(BigInteger)
    score = Column(Integer)
    num_comments = Column(Integer)
    word_count = Column(Integer)

    __table_args__ = (
        Index("idx_submissions_file_id_word_count", "file_id", "word_count"),
    )


class Comment(Base):
    __tablename__ = "comments"

    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    id = Column(String, primary_key=True)
    subreddit = Column(String)
    body = Column(String)
    author = Column(String)
    created_utc = Column(BigInteger)
    score = Column(Integer)
    link_id = Column(String)
    parent_id = Column(String)
    word_count = Column(Integer)

    __table_args__ = (
        Index("idx_comments_file_id_word_count", "file_id", "word_count"),
    )


class ArtifactContent(Base):
    """One TEXT blob per artifact -- codebook / codebook_comparison /
    coding_comparison / summary / (for `coding`) the classification output.
    Replaces the ~10 duplicated ``CREATE SCHEMA`` + ``content_store``
    blocks that existed for these file types.
    """

    __tablename__ = "artifact_content"

    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CodingEntry(Base):
    """Structured coding output: one row per (post, code) pair.

    Populated from the same POST_ID/CODE/EVIDENCE parse
    ``backend/scripts/codebook_apply.py`` already does -- this persists
    the structure that used to be parsed out and then discarded when the
    classification text was flattened back into one blob. Enables
    ``SELECT code, COUNT(*) ... GROUP BY code`` directly in SQL.
    """

    __tablename__ = "coding_entries"

    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    post_id = Column(String, primary_key=True)
    code = Column(String, primary_key=True)
    evidence = Column(Text)

    __table_args__ = (
        Index("idx_coding_entries_file_id_code", "file_id", "code"),
    )
