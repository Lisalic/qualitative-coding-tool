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
added by ``backend/alembic/versions/a1e6f2c9b3d7_baseline_untracked_schema.py``,
matching the expression the old per-artifact-schema DDL used.

Artifact *content* no longer lives here: the old one-blob-per-file
``ArtifactContent`` table is gone (see
``backend/app/versioning_models.py`` -- content now lives on
``ArtifactVersion.content`` for blob artifacts, or on ``CodebookCode``
rows for codebooks and a coding artifact's own codebook snapshot).
"""

from sqlalchemy import Column, ForeignKey, Integer, BigInteger, String, Text, Index

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


class CodingEntry(Base):
    """Structured coding output: one row per (item, code, quote) --
    i.e. one row per *quote*, not per code, since a single code can be
    supported by several distinct quotes in the same item.

    Populated from the AI's JSON output (``backend/scripts/codebook_apply.py::
    classify_posts``) after it passes every anti-hallucination check in
    ``backend/app/services/coding_service.py`` (item exists, code exists in
    the codebook, quote exists verbatim-or-normalized in the item's own
    text -- see ``backend/app/core/evidence_match.py``), or from a manual
    edit whose ``quote``/offsets are computed directly from the real DOM
    selection range (``HighlightedContent.jsx``). Either way, ``quote`` is
    always the exact substring ``content[start_offset:end_offset]`` of the
    item's own body text -- there is no unverified free-text evidence
    column any more, and nothing here is a raw, unparsed AI response.

    ``row_type`` (``"submission"`` or ``"comment"``, see
    ``backend/app/core/item_types.py``) distinguishes a coded post from a
    coded comment -- ``post_id`` alone is not enough, since submission and
    comment ids share one bare-string namespace (both strip their Reddit
    fullname prefix at import) and a genuine collision between the two
    tables would otherwise silently merge into one row.

    ``code_uid`` identifies the code by its stable id in the coding
    artifact's own ``codebook_codes`` (see ``versioning_models.py``)
    rather than by name, so a code rename never orphans the entries that
    use it -- ``code`` (the display name) is kept alongside purely as a
    denormalized label for reads that don't want to join.

    ``valid_from``/``valid_to`` are SCD-2 revision range columns keyed on
    the owning coding file's ``artifact_versions.version_no`` (not on
    ``ArtifactVersion.id`` -- a plain indexed integer range keeps the
    liveness predicate a cheap ``valid_to IS NULL`` / range comparison
    rather than a join). A row is live at version ``v`` iff
    ``valid_from <= v <= coalesce(valid_to, infinity)``; ``valid_to IS
    NULL`` means "still live". Real multi-version coding history is live:
    ``coding_service.save_coding_revision`` and an accepted AI recode
    proposal both mint a new version and stamp their writes with it, so
    a row's ``valid_from``/``valid_to`` genuinely bracket the versions it
    was live for -- see ``coding_repo.py::replace_entries_for_items``
    for the three-step SCD-2 write.
    """

    __tablename__ = "coding_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    row_type = Column(String, nullable=False, server_default="submission", default="submission")
    post_id = Column(String, nullable=False)
    code = Column(String, nullable=False)
    code_uid = Column(String, nullable=False)
    quote = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    notes = Column(Text)
    valid_from = Column(Integer, nullable=False, server_default="1", default=1)
    valid_to = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_coding_entries_file_id_code", "file_id", "code"),
        Index("idx_coding_entries_file_id_row", "file_id", "row_type", "post_id"),
        Index("idx_coding_entries_file_id_code_uid", "file_id", "code_uid"),
        Index("idx_coding_entries_live", "file_id", "valid_to"),
    )
