"""Artifact version spine: git-like commits, typed derivation edges, and
structured codebook code rows.

Replaces two things at once: the single untyped ``file_dependencies``
table (which conflated "artifact B was derived from artifact A" with
"artifact A's content changed", and could not say which parent played
which role, in what order, or from which revision -- see
``coding_service.py::_clone_file_dependencies``'s grandparent-copying
hack for what that produced in practice), and the one-row-per-file
``artifact_content`` blob (which made every save a destructive overwrite
with no history).

``files`` becomes a git-style *ref*: identity, name, type, project links
only. ``ArtifactVersion`` is the *commit*. ``ArtifactEdge`` is a typed,
ordered, version-pinned derivation edge. ``CodebookCode`` is one row per
code, fully materialized per codebook version (cheap at ~30-80 codes per
version -- this is what makes a structural diff a plain full outer join
on ``code_uid`` rather than a heuristic name-similarity match).

Content storage is deliberately per-type, not one polymorphic blob:
summary/comparison artifacts put their markdown on
``ArtifactVersion.content``; codebooks (and a coding artifact's own
codebook snapshot) store their codes as ``CodebookCode`` rows instead;
coding classification lives in ``coding_entries`` SCD-2 ranges (see
``storage_models.py::CodingEntry``), never on a version row at all.
Nothing in the schema enforces which storage a given ``file_type`` uses
(no CHECK constraint -- see CLAUDE.md's YAGNI guidance); it is enforced
in ``backend/app/services/version_service.py``'s three ``commit_*``
functions instead.
"""

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text, DateTime, Index, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.database import Base

# ArtifactVersion.origin values.
ORIGIN_GENERATED = "generated"   # produced by an LLM job, born sealed
ORIGIN_EDITED = "edited"         # a human save (opens/extends a draft)
ORIGIN_IMPORTED = "imported"     # pasted/uploaded markdown parsed into rows
ORIGIN_FORKED = "forked"         # v1 of a brand-new file created by duplicate_coding/duplicate_codebook

# ArtifactEdge.relation values.
RELATION_DERIVED_FROM = "derived_from"   # single- or multi-parent, same role each
RELATION_COMPARED = "compared"           # two-sided (or client-supplied N-sided), ordered
RELATION_MERGED_FROM = "merged_from"     # variadic, arity = number of merge inputs
RELATION_FORKED_FROM = "forked_from"     # duplicate_coding's one true fork edge

# ArtifactEdge.role values.
ROLE_SOURCE_DATA = "source_data"
ROLE_CODEBOOK = "codebook"
ROLE_SIDE_A = "side_a"
ROLE_SIDE_B = "side_b"
ROLE_MERGE_INPUT = "merge_input"
ROLE_FORK_ORIGIN = "fork_origin"


class ArtifactVersion(Base):
    """One commit in a file's history. ``version_no`` is 1-based and
    monotonic per ``file_id`` (``UniqueConstraint(file_id, version_no)``
    is the concurrency guarantee -- see ``version_service.py``'s
    ``_lock_file``/``_next_version``). ``parent_version_id`` is normally
    the previous version of the *same* file, but for a fork's v1 it
    deliberately points at a DIFFERENT file's version -- the source
    artifact's head at fork time (see ``version_service.fork_lineage``
    and ``duplicate_coding``). That cross-file pointer is intentional
    (git's "a branch points at a commit, it doesn't copy it" model, not
    a bug) and has one real consequence: deleting the source file must
    null out any fork's ``parent_version_id`` that points into it before
    the source's own versions can be deleted (see
    ``file_service.py::delete_database``).

    ``sealed_at`` is set in the same insert that creates the version --
    every commit is sealed immediately and there is no open-draft state.
    See ``version_service.py``'s "Sealing" section.

    ``content`` is used only by blob-storage artifact types (summary,
    the comparison types); codebook versions leave it NULL and store
    their codes as ``CodebookCode`` rows instead, and coding versions
    leave it NULL and carry no per-version payload at all (the
    classification lives in ``coding_entries`` SCD-2 ranges).
    ``content_hash`` is the canonical-serialization hash used for no-op
    save suppression -- see ``version_service.py``'s ``_blob_hash``/
    ``_codes_hash``.

    **Prompt provenance is deliberately NOT the rendered prompt.**
    ``system_prompt`` is the template (small, and genuinely reusable
    context). ``user_instructions`` is only the human-authored fragment
    -- the generate prompt, the apply methodology, the filter criteria.
    The *rendered* user prompt is not stored at all, because it embeds
    the entire batch of sampled submission/comment text, which the same
    artifact already owns in ``submissions``/``comments``: storing it
    made this table 119 MB across 61 rows (99.94% of it duplication) and
    put a multi-megabyte string in the JSON body of every ViewCoding and
    ViewCodebook page load. ``prompt_meta`` keeps the claim falsifiable
    without the payload::

        {"rendered_chars": int, "rendered_sha256": str, "batches": int}

    Caveat worth knowing: for the filter and apply pipelines the scripts
    return only the LAST batch's prompt, so ``rendered_chars`` and
    ``rendered_sha256`` describe that batch, not the whole input --
    ``batches`` says how many there were. The full generation parameters
    (source file, sample percentage, content scope, model, the user's
    prompt) live in ``jobs.payload``, reachable via ``job_id``.

    ``codes_materialized`` (default ``True``) is ``False`` for a version
    that doesn't own a full ``CodebookCode`` row set of its own -- either
    because it never needed one (a row-only coding edit -- see
    ``commit_coding_version``) or because it USED to have one and was
    later compacted out once it aged past the retained window (see
    ``version_service._demote_if_eligible``). ``codes_delta`` (JSON,
    ``core/codebook_delta.py``'s ``encode_delta`` output) carries what a
    compacted version actually changed relative to its anchor; it is
    ``NULL`` for a materialized version and also ``NULL`` for a
    never-materialized row-only edit, which has nothing to encode in the
    first place (its codes are identical to its predecessor's by
    definition -- see below).

    **What stays materialized, and why each rule exists:**

    - v1 -- always. The base case; there is no ancestor to inherit from.
    - Every real codebook write (``commit_codebook_version`` -- a
      ``codebook`` file's own save, or a ``coding`` file's codebook-
      editing path) -- always, at commit time. Its content is already
      fully known; there's no reason to defer materializing it.
    - The 3 most recent versions of any file (``LATEST_MATERIALIZED_WINDOW``
      in ``version_service.py``) -- so a diff or a fork against anything
      recent needs zero delta application.
    - Every ``version_no`` that's a multiple of ``KEYFRAME_INTERVAL``
      (10) -- a permanent anchor placed on a fixed schedule, so
      reconstructing ANY version, however old, never needs to walk back
      further than ``KEYFRAME_INTERVAL`` versions to find one.
    - A row-only coding edit (``save_coding_rows``, an AI recode) whose
      ``version_no`` happens to land on a keyframe boundary -- forced
      materialized (its current, already-resolved codes are copied in)
      purely to keep the keyframe schedule unconditional; skipping it
      would leave a gap an unlucky reconstruction could walk into.

    Everything else that ages out of the latest-3 window gets compacted
    (``_demote_if_eligible``, checked once per commit -- O(1), not a
    sweep): the version's own current rows are diffed against its
    nearest still-materialized ancestor with ``encode_delta``, that
    result is stored as ``codes_delta``, and the row set is deleted. This
    is computed once, at compaction time, directly against the anchor --
    not as a chain of consecutive per-version deltas -- so
    reconstruction is always exactly one lookup plus at most one delta
    application, never a multi-step replay, and churn (a code added then
    removed between two keyframes) nets out to nothing in the delta
    rather than costing two stored entries. A pure row-only edit is never
    compacted because it's never materialized to begin with -- its
    "delta" from its predecessor is empty by construction, so there is
    nothing to store; ``read_codes`` just borrows the ancestor's rows
    wholesale, unconditionally cheaper than computing and applying an
    empty delta.

    Every version that existed before this scheme was added defaults to
    materialized (``server_default=true``) -- no backfill needed, since a
    fully materialized version is trivially a valid anchor.
    """

    __tablename__ = "artifact_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    version_no = Column(Integer, nullable=False)
    parent_version_id = Column(Integer, ForeignKey("artifact_versions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    author_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    origin = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    sealed_at = Column(DateTime(timezone=True), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    model = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=True)
    user_instructions = Column(Text, nullable=True)
    # sa.JSON, not JSONB: the default test suite runs on SQLite (same
    # reasoning as backend/app/jobs/models.py). Never queried into.
    prompt_meta = Column(JSON, nullable=True)
    content = Column(Text, nullable=True)
    content_hash = Column(String, nullable=True)
    codes_materialized = Column(Boolean, nullable=False, server_default="true", default=True)
    # sa.JSON, not JSONB: same SQLite-test-suite reasoning as prompt_meta.
    # NULL for a materialized version and for a never-materialized
    # row-only edit (nothing to encode); a real encode_delta() dict only
    # for a compacted version -- see the docstring above.
    codes_delta = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("file_id", "version_no", name="uq_artifact_versions_file_id_version_no"),
        Index("idx_artifact_versions_file_id_version_no", "file_id", "version_no"),
    )


class ArtifactEdge(Base):
    """A typed, ordered, version-pinned derivation edge -- replaces
    ``file_dependencies``. ``child_file_id``/``parent_file_id`` name the
    two artifacts; ``parent_version_id`` pins exactly which revision of
    the parent was used (nullable only because a parent created before
    this system existed, or one whose head was never sealed at edge
    creation time, may not have a resolvable version yet). ``relation``
    and ``role`` say what kind of derivation this is and which slot this
    parent fills (see the ``RELATION_*``/``ROLE_*`` constants above);
    ``position`` orders siblings sharing a ``(child_file_id, relation)``
    (comparison sides, merge inputs).
    """

    __tablename__ = "artifact_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    child_file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    parent_file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    parent_version_id = Column(Integer, ForeignKey("artifact_versions.id", ondelete="SET NULL"), nullable=True)
    relation = Column(String, nullable=False)
    role = Column(String, nullable=False)
    position = Column(Integer, nullable=False, server_default="0", default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_artifact_edges_child", "child_file_id"),
        Index("idx_artifact_edges_parent", "parent_file_id"),
    )


class CodebookCode(Base):
    """One code, fully materialized for one codebook version.
    ``code_uid`` is the stable identity that survives a rename -- it is
    what makes ``codebook_diff.py`` a plain full outer join instead of a
    name-similarity heuristic, and what lets ``coding_entries.code_uid``
    reference a code without breaking when it's renamed.

    ``family_uid`` is likewise stable and independent of
    ``family_name`` -- ``tests/backend/test_display_codebook.py`` pins
    that duplicate family names are NOT merged when parsing model
    output, so two families both named e.g. "Anxiety" must keep distinct
    identities; ``codebook_render.py`` groups by ``family_uid``, never by
    name, when rendering rows back to markdown.

    ``definition``/``inclusion``/``exclusion``/``keywords``/``example``
    are the structured fields the generator JSON fills (and the markdown
    importer splits out of labeled body lines). ``body`` is the labeled
    reconstruction of those fields (or leftover unlabeled prose on
    older rows) so apply/compare still receive markdown.
    ``position`` is the code's order within the whole codebook (not just
    within its family) so the renderer can reproduce the original
    ordering, including which family a code was adjacent to.
    """

    __tablename__ = "codebook_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey("artifact_versions.id", ondelete="CASCADE"), nullable=False)
    code_uid = Column(String, nullable=False)
    family_uid = Column(String, nullable=False)
    family_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    body = Column(Text, nullable=False, server_default="")
    definition = Column(Text, nullable=True)
    inclusion = Column(Text, nullable=True)
    exclusion = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, server_default="0", default=0)

    __table_args__ = (
        UniqueConstraint("version_id", "code_uid", name="uq_codebook_codes_version_id_code_uid"),
        Index("idx_codebook_codes_version_position", "version_id", "position"),
    )
