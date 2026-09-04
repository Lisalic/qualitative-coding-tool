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

``RowMemo`` is the one table here that is *not* artifact content and
*not* revision-ranged -- see its docstring.
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from backend.app.database import Base


class Submission(Base):
    """A row is a git-style *ref*'s owned copy of one Reddit submission.

    ``pk`` is a surrogate primary key -- ``(file_id, id)`` is no longer
    unique on its own, since ``valid_from``/``valid_to`` (SCD-2 revision
    ranges keyed on the owning file's ``artifact_versions.version_no``,
    identical semantics to ``CodingEntry`` -- see that model's docstring)
    let the same ``id`` reappear more than once for the same ``file_id``:
    a row moved out (closed) and later moved back in would otherwise
    collide under a composite ``(file_id, id)`` PK. A row is live iff
    ``valid_to IS NULL``; live *as of* version ``v`` iff ``valid_from <=
    v AND (valid_to IS NULL OR valid_to >= v)``. Every read in this
    codebase must apply one of those two predicates -- see
    ``repositories/raw_data_repo.py``.
    """

    __tablename__ = "submissions"

    pk = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    id = Column(String, nullable=False)
    subreddit = Column(String)
    title = Column(String)
    selftext = Column(String)
    author = Column(String)
    created_utc = Column(BigInteger)
    score = Column(Integer)
    num_comments = Column(Integer)
    word_count = Column(Integer)
    valid_from = Column(Integer, nullable=False, server_default="1", default=1)
    valid_to = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_submissions_file_id_word_count", "file_id", "word_count"),
        Index("idx_submissions_live", "file_id", "valid_to"),
        Index(
            "uq_submissions_file_id_id_live",
            "file_id", "id",
            unique=True,
            postgresql_where=(valid_to.is_(None)),
            sqlite_where=(valid_to.is_(None)),
        ),
    )


class Comment(Base):
    """Same shape and SCD-2 semantics as ``Submission`` -- see its
    docstring.
    """

    __tablename__ = "comments"

    pk = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    id = Column(String, nullable=False)
    subreddit = Column(String)
    body = Column(String)
    author = Column(String)
    created_utc = Column(BigInteger)
    score = Column(Integer)
    link_id = Column(String)
    parent_id = Column(String)
    word_count = Column(Integer)
    valid_from = Column(Integer, nullable=False, server_default="1", default=1)
    valid_to = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_comments_file_id_word_count", "file_id", "word_count"),
        Index("idx_comments_live", "file_id", "valid_to"),
        Index(
            "uq_comments_file_id_id_live",
            "file_id", "id",
            unique=True,
            postgresql_where=(valid_to.is_(None)),
            sqlite_where=(valid_to.is_(None)),
        ),
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


class RowMemo(Base):
    """One user-authored analytic memo about one row of one artifact.

    Distinct from ``CodingEntry.notes``, which annotates a single coded
    *quote* inside a coded item. A memo annotates the row itself, exists
    for ``raw_data``/``filtered_data``/``coding`` artifacts alike, and
    needs no codebook or coding to exist first -- it is the "write down
    what you noticed while reading" surface that the pipeline previously
    had nowhere to put (GAP-4 in
    ``documentation/research/qualitative-coding-landscape-and-expansion.md``).

    Scoped by ``file_id`` like every other table in this module, so a
    memo belongs to *one artifact's copy* of a row rather than to a
    global row identity. That matches the self-contained-artifact model
    already used by ``coding`` (see ``services/coding_service.py``): a
    memo written on a raw-data row is copied forward into a derived
    artifact when that row is (``repositories/memo_repo.py``'s
    ``copy_memos_by_id``/``copy_all_memos``, called from every
    ``raw_data_repo.copy_rows_by_id``/``copy_all_rows`` call site), and
    editing it afterwards in the child never reaches back into the
    parent.

    ``row_type`` (``"submission"``/``"comment"``, see
    ``core/item_types.py``) is part of the identity for the same reason
    it is on ``CodingEntry``: submission and comment ids share one bare
    string namespace once their Reddit fullname prefixes are stripped at
    import, so ``row_id`` alone would silently merge a post's memo with
    a same-id comment's.

    Deliberately **not** SCD-2 range-versioned like ``Submission``/
    ``Comment``/``CodingEntry``, and deliberately one row per
    ``(file_id, row_type, row_id)`` rather than an append-only thread. A
    memo is commentary *about* an artifact, not part of the artifact's
    content, so it is not what a version diff is meant to describe;
    range-versioning it would push a ``version_no`` argument through
    every write path (and mint a version per keystroke-save) for no
    analytic gain. ``updated_at`` carries the "when did I last think
    about this" signal that actually matters here.
    """

    __tablename__ = "row_memos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    row_type = Column(String, nullable=False)
    row_id = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    author_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("file_id", "row_type", "row_id", name="uq_row_memos_file_row"),
        Index("idx_row_memos_file_row", "file_id", "row_type", "row_id"),
    )
