"""Service layer for raw/filtered data access and the filter-data pipeline
-- backs backend/app/api/data_routes.py.

Retires the last raw-SQL-with-spliced-schema-name call sites in the app
(``get_post_contents`` was the confirmed SQL-injection-adjacent one; the
same pattern existed, just less dangerously, in ``word_count_ranges``/
``file_entries``/``get_comments_for_submission``). Every lookup here goes
through ``repositories/file_repo.py::resolve_file_id`` first, which is
scoped to ``File.user_id == user_id`` -- so a caller can only ever query
rows for a file they own, and there is no raw schema-name string left to
interpolate into SQL. ``core/schema_guard.py::require_valid_schema`` is
still applied first as a fast, cheap input check (reject malformed input
with a clear 400 before even hitting the DB) -- defense in depth, not the
only guard, now that ``file_repo`` does the real ownership-scoped
resolution.

``word_count_ranges``/``file_entries``/``get_comments_for_submission``
query the fixed ``submissions``/``comments`` tables (``storage_models.py``)
directly -- no more per-schema ``information_schema``/``to_regclass``
introspection, since the fixed tables (and their ``word_count`` column)
always exist for every file.

``filter_data`` becomes a background job (same job-queue pattern Stage 4
established for ``summarize-coding``): ``start_filter_data_job`` validates
and enqueues, ``_run_filter_data_job`` (registered for job_type
``"filter_data"``) does the actual sampling/AI-filtering/materialization
work, decomposed into ``_sample_source_rows`` / ``_apply_tag_or_ai_filter``
/ ``_materialize_filtered_schema``. The per-ID ``SELECT``+``INSERT``+
``begin_nested()`` Python loop the old synchronous route used is replaced
by one call to ``repositories/raw_data_repo.py::copy_rows_by_id`` -- a
set-based ``INSERT ... SELECT`` for each of submissions/comments.
"""

from __future__ import annotations

import json
import math
import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.core.item_types import COMMENT, SUBMISSION, split_item_id
from backend.app.core.schema_guard import require_valid_schema
from backend.app.database import (
    AsyncSessionLocal,
    File,
    FileTable,
    async_link_file_to_project,
)
from backend.app.jobs.models import Job
from backend.app.jobs.progress import ProgressTracker
from backend.app.jobs.registry import register_handler
from backend.app.jobs.service import enqueue_job
from backend.app.repositories import file_repo, memo_repo, project_repo, raw_data_repo, version_repo
from backend.app.services import version_service
from backend.app.services.version_service import EdgeSpec
from backend.app.storage_models import Comment, Submission
from backend.app.versioning_models import (
    ORIGIN_EDITED,
    ORIGIN_FORKED,
    ORIGIN_GENERATED,
    RELATION_DERIVED_FROM,
    ROLE_SOURCE_DATA,
)

# ---------------------------------------------------------------------------
# Read paths: word-count ranges / file entries / comments / post contents
# ---------------------------------------------------------------------------

_ROW_COLUMNS_TO_DROP = {"file_id", "pk", "valid_from", "valid_to"}


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Serialize a ``Submission``/``Comment`` ORM row to a plain dict,
    matching the old ``dict(r._mapping)`` shape -- minus ``file_id``
    (which didn't exist as a column in the old per-artifact schema, each
    file had its own schema so there was nothing to scope by) and the
    versioning-internal ``pk``/``valid_from``/``valid_to`` columns, which
    are plumbing, not artifact content.
    """
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
        if c.name not in _ROW_COLUMNS_TO_DROP
    }


async def _word_count_ranges_for(session: AsyncSession, model: type, file_id: int) -> list[dict[str, int]]:
    """Binned word-count histogram (0-1000 in steps of 10) for ``model``
    (``Submission`` or ``Comment``) rows belonging to ``file_id``.

    ``word_count`` is always a non-negative integer column on the fixed
    tables, so ``(word_count // 10) * 10`` is already the floor-to-nearest-10
    bin under integer (floor) division (both Postgres and SQLite truncate
    integer/integer division the same way for non-negative operands) --
    no ``floor()`` call needed. Note this must be SQLAlchemy's ``//``
    (``__floordiv__``), not ``/`` -- SQLAlchemy's ``/`` always compiles to
    *true* division (e.g. ``CAST(... AS NUMERIC)`` on Postgres, ``+ 0.0``
    on SQLite) for cross-dialect consistency, which would silently produce
    a float and round-trip back to the original, unbinned value. The
    ``WHERE ... BETWEEN 0 AND 1000`` predicate already bounds the bin to
    <=1000, so the old ``LEAST(..., 1000)`` clamp is redundant here too.
    Avoiding both keeps this expressible with plain SQLAlchemy Core
    arithmetic that behaves identically on Postgres (production) and
    SQLite (this service's unit tests), rather than Postgres-only
    ``floor()``/``least()`` functions.
    """
    bin_expr = (model.word_count // 10) * 10
    stmt = (
        select(bin_expr.label("min_words"), func.count().label("count"))
        .where(model.file_id == file_id, model.word_count.between(0, 1000), model.valid_to.is_(None))
        .group_by(bin_expr)
        .order_by(bin_expr)
    )
    result = await session.execute(stmt)
    return [{"min_words": int(row.min_words), "count": int(row.count)} for row in result]


async def get_word_count_ranges(session: AsyncSession, user_id: int, schema: str) -> dict[str, list[dict[str, int]]]:
    """Word-count histograms for both tables of the file identified by
    ``schema`` (schemaname/filename/id), owned by ``user_id``.
    """
    normalized = require_valid_schema(schema, field_name="schema")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)
    submissions_ranges = await _word_count_ranges_for(session, Submission, file_id)
    comments_ranges = await _word_count_ranges_for(session, Comment, file_id)
    return {"submissions": submissions_ranges, "comments": comments_ranges}


def _liveness_predicate(model, version_no: int | None):
    """Same as-of/live predicate ``raw_data_repo`` applies internally,
    duplicated here (rather than imported) because this is a plain
    SQLAlchemy expression fragment, not a query -- see
    ``raw_data_repo._as_of``/``_liveness_condition`` for the canonical
    version this mirrors.
    """
    from sqlalchemy import and_, or_

    if version_no is None:
        return model.valid_to.is_(None)
    return and_(model.valid_from <= version_no, or_(model.valid_to.is_(None), model.valid_to >= version_no))


async def get_file_entries(
    session: AsyncSession, user_id: int, schema: str, limit: int, offset: int, version_no: int | None = None
) -> dict[str, Any]:
    """Paginated submissions/comments rows (plus total counts) for the
    file identified by ``schema``, owned by ``user_id``. ``version_no``
    reads the file AS OF that version (time travel over the SCD-2
    ranges on ``submissions``/``comments`` -- see their docstrings in
    ``storage_models.py``); the default (``None``) reads the currently
    LIVE rows.
    """
    normalized = require_valid_schema(schema, field_name="schema")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)
    safe_offset = max(0, offset)

    sub_condition = _liveness_predicate(Submission, version_no)
    com_condition = _liveness_predicate(Comment, version_no)

    sub_count = (
        await session.execute(
            select(func.count()).select_from(Submission).where(Submission.file_id == file_id, sub_condition)
        )
    ).scalar() or 0
    com_count = (
        await session.execute(
            select(func.count()).select_from(Comment).where(Comment.file_id == file_id, com_condition)
        )
    ).scalar() or 0

    sub_rows = (
        await session.execute(
            select(Submission)
            .where(Submission.file_id == file_id, sub_condition)
            .order_by(Submission.id)
            .limit(limit)
            .offset(safe_offset)
        )
    ).scalars().all()
    com_rows = (
        await session.execute(
            select(Comment)
            .where(Comment.file_id == file_id, com_condition)
            .order_by(Comment.id)
            .limit(limit)
            .offset(safe_offset)
        )
    ).scalars().all()

    return {
        "submissions": [_row_to_dict(r) for r in sub_rows],
        "comments": [_row_to_dict(r) for r in com_rows],
        "total_submissions": sub_count,
        "total_comments": com_count,
        "database": normalized,
        "date_created": None,
        "version_no": version_no,
    }


async def get_comments_for_submission(
    session: AsyncSession, user_id: int, submission_id: str, database: str
) -> dict[str, Any]:
    """All comments whose ``link_id`` matches ``submission_id``, from the
    file identified by ``database`` (schemaname/filename/id), owned by
    ``user_id``.
    """
    normalized = require_valid_schema(database, field_name="database")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)
    rows = (
        await session.execute(
            select(Comment)
            .where(Comment.file_id == file_id, Comment.link_id == submission_id, Comment.valid_to.is_(None))
            .order_by(Comment.created_utc.asc())
        )
    ).scalars().all()
    return {"comments": [_row_to_dict(r) for r in rows]}


async def get_post_contents(
    session: AsyncSession, user_id: int, schema: str, post_ids: list[str]
) -> dict[str, Any]:
    """Title/content for a set of post and/or comment ids in the file
    identified by ``schema``, owned by ``user_id``.

    This is the retirement of the confirmed SQL-injection-adjacent gap:
    ``schema`` never touches a SQL string. ``require_valid_schema`` rejects
    malformed input outright (fast 400, no DB call); the ``id IN (...)``
    predicate is a normal SQLAlchemy Core query parameterized the usual
    way; and the actual scoping is ``file_repo.resolve_file_id``, which
    only ever resolves to a file owned by ``user_id`` in the first place.

    ``post_ids`` may mix qualified ids (``t3_<id>``/``t1_<id>``, see
    ``core/item_types.py``) with legacy unprefixed ids -- every coding
    artifact saved before item types existed only ever contains the
    latter, and an unprefixed id defaults to "submission". Any unprefixed
    id that doesn't resolve against ``submissions`` is retried against
    ``comments`` as a legacy-comment-id fallback, so an old artifact that
    happened to code a comment still resolves instead of silently
    returning nothing for it (which was the pre-existing bug this whole
    change fixes).

    Returned dict is keyed by the id exactly as the caller sent it, each
    value ``{type, title, content, parent_id, parent_title}`` -- ``title``
    is the post's own title for a submission, or ``None`` for a comment
    (``parent_title`` carries the comment's parent post's title instead,
    resolved via ``Comment.link_id``, when that parent is itself in this
    file).
    """
    if not schema or not post_ids:
        raise ValidationAppError("schema and post_ids are required")
    normalized = require_valid_schema(schema, field_name="schema")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)

    parsed = [(str(pid), *split_item_id(str(pid))) for pid in post_ids]
    submission_candidates = {raw_id for _, row_type, raw_id in parsed if row_type == SUBMISSION}
    comment_candidates = {raw_id for _, row_type, raw_id in parsed if row_type == COMMENT}

    sub_rows: dict[str, dict[str, Any]] = {}
    if submission_candidates:
        rows = await session.execute(
            select(Submission.id, Submission.title, Submission.selftext).where(
                Submission.file_id == file_id,
                Submission.id.in_(submission_candidates),
                Submission.valid_to.is_(None),
            )
        )
        sub_rows = {str(r.id): {"title": r.title or "", "content": r.selftext or ""} for r in rows}

    # Legacy fallback: an unprefixed id that isn't a submission might be an
    # old, unqualified comment id.
    unresolved_submission_ids = submission_candidates - sub_rows.keys()
    all_comment_candidates = comment_candidates | unresolved_submission_ids

    comment_rows: dict[str, dict[str, Any]] = {}
    if all_comment_candidates:
        rows = await session.execute(
            select(Comment.id, Comment.body, Comment.link_id).where(
                Comment.file_id == file_id,
                Comment.id.in_(all_comment_candidates),
                Comment.valid_to.is_(None),
            )
        )
        comment_rows = {str(r.id): {"content": r.body or "", "link_id": r.link_id} for r in rows}

    parent_ids = {v["link_id"] for v in comment_rows.values() if v.get("link_id")}
    parent_titles: dict[str, str] = {}
    if parent_ids:
        rows = await session.execute(
            select(Submission.id, Submission.title).where(
                Submission.file_id == file_id,
                Submission.id.in_(parent_ids),
                Submission.valid_to.is_(None),
            )
        )
        parent_titles = {str(r.id): (r.title or "") for r in rows}

    contents: dict[str, dict[str, Any]] = {}
    for qualified, _row_type, raw_id in parsed:
        if raw_id in sub_rows:
            data = sub_rows[raw_id]
            contents[qualified] = {
                "type": SUBMISSION,
                "title": data["title"],
                "content": data["content"],
                "parent_id": None,
                "parent_title": None,
            }
        elif raw_id in comment_rows:
            data = comment_rows[raw_id]
            contents[qualified] = {
                "type": COMMENT,
                "title": None,
                "content": data["content"],
                "parent_id": data["link_id"],
                "parent_title": parent_titles.get(data["link_id"]) if data["link_id"] else None,
            }
    return {"contents": contents}


# ---------------------------------------------------------------------------
# filter_data: background job kickoff + handler
# ---------------------------------------------------------------------------


def _word_count_expr_ai_ready(rows: list, content_type: str) -> str:
    """Compact string representation of sampled rows for AI filtering,
    identical formatting to the old inline helper in ``data_routes.py``.
    """
    parts = []
    for r in rows:
        mapping = r._mapping
        if content_type == "submission":
            rid = mapping.get("id", "")
            title = mapping.get("title", "") or ""
            selftext = mapping.get("selftext", "") or ""
            parts.append(f"[{rid}] {title}\n{selftext}")
        else:
            cid = mapping.get("id", "")
            body = mapping.get("body", "") or ""
            parts.append(f"[{cid}] {body}")
    return "\n---\n".join(parts)


async def start_filter_data_job(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    name: str,
    api_key: str,
    model: str | None,
    prompt: str | None,
    min_words: int,
    sample_percentage: float,
    filter_tags: str | None,
    description: str | None,
    project_id: int | None,
    content_scope: str = "both",
) -> Job:
    """Validate and enqueue a ``filter_data`` background job.

    Keeps the same guard-clause validation the old synchronous route did
    (schema must look like ``proj_<id>``, ``api_key`` required) plus the
    new ownership check (``database`` must resolve to a file owned by
    ``user_id``) -- all of which raise before anything is persisted or a
    background task is spawned. ``api_key`` goes into ``runtime_extra`` so
    it's never written to the ``jobs`` table.
    """
    schema = require_valid_schema(database, field_name="database")
    if not api_key:
        raise ValidationAppError("api_key is required")

    source_file_id = await file_repo.resolve_file_id(session, schema, user_id)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="filter_data",
        payload={
            "source_file_id": source_file_id,
            "user_id": user_id,
            "name": name,
            "model": model,
            "prompt": (prompt or "").strip(),
            "min_words": min_words,
            "sample_percentage": sample_percentage,
            "filter_tags": filter_tags,
            "description": description,
            "project_id": project_id,
            "content_scope": content_scope,
        },
        runtime_extra={"api_key": api_key},
    )


def _exclude_clause(ids: list[str] | None, param: str) -> tuple[str, dict[str, Any], list]:
    """SQL fragment + bind value + expanding-bindparam spec that removes
    already-decided rows from the candidate pool.

    Backs the filter editor's "the AI only proposes rows I haven't ruled
    on yet" rule (see ``start_filter_preview_job``). Returns three empty
    values when there is nothing to exclude, so the caller can splice the
    fragment in unconditionally.

    ``expanding=True`` is what makes ``IN``/``NOT IN`` safe with a
    variable-length list on a ``text()`` construct -- SQLAlchemy renders
    one bind parameter per element at execution time rather than us
    interpolating ids into SQL, which is the whole reason the sampling
    queries in this module are allowed to be raw ``text()`` at all.
    """
    if not ids:
        return "", {}, []
    return f" AND id NOT IN :{param}", {param: list(ids)}, [bindparam(param, expanding=True)]


def _text(sql: str, expanding: list):
    """``text(sql)`` with any expanding bindparams attached."""
    stmt = text(sql)
    return stmt.bindparams(*expanding) if expanding else stmt


async def _sample_source_rows(
    session: AsyncSession,
    *,
    source_file_id: int,
    min_words: int,
    sub_tag_sql: str,
    sub_tag_bind: dict[str, Any],
    com_tag_sql: str,
    com_tag_bind: dict[str, Any],
    pct: float,
    use_ai_posts: bool,
    use_ai_comments: bool,
    include_posts: bool = True,
    include_comments: bool = True,
    exclude_submission_ids: list[str] | None = None,
    exclude_comment_ids: list[str] | None = None,
) -> tuple[list, list, str, str]:
    """Count eligible rows (``word_count >= min_words`` and, if tags were
    supplied, a keyword match), random-sample ``ceil(eligible * pct / 100)``
    of them, and build the AI-ready text blob for whichever of
    submissions/comments actually needs an AI call.

    ``include_posts``/``include_comments`` implement ``content_scope``
    ("both"/"posts"/"comments"): when a type is excluded, its table isn't
    even queried, so it can never be sampled or filtered into the output
    -- distinct from ``use_ai_posts``/``use_ai_comments``, which is about
    whether a type needs an *AI* pass (a tags-only filter still samples
    and copies rows without ever building AI-ready text for them).

    ``exclude_submission_ids``/``exclude_comment_ids`` narrow the
    candidate pool before counting *and* before sampling, so an excluded
    row can neither consume a sample slot nor be proposed. Only the
    filter editor's preview job passes them (the rows the user already
    included or excluded by hand); the one-shot ``filter_data`` job
    leaves them empty and behaves exactly as before.

    Uses ``text()`` against the fixed ``submissions``/``comments`` tables
    scoped by ``file_id`` -- safe (no identifier interpolation; ``file_id``
    is a bound int, table names are fixed literals, and the exclusion
    lists go through expanding bindparams -- see ``_exclude_clause``) and
    reuses the tag-predicate SQL fragments from ``tag_expansion.py``
    unchanged.
    """
    sub_rows: list = []
    comm_rows: list = []
    submissions_text = ""
    comments_text = ""

    if include_posts:
        sub_ex_sql, sub_ex_bind, sub_ex_params = _exclude_clause(exclude_submission_ids, "ex_subs")
        subs_params = {"fid": source_file_id, "mw": min_words, **sub_tag_bind, **sub_ex_bind}
        subs_where = (
            f"WHERE file_id = :fid AND valid_to IS NULL AND word_count >= :mw{sub_tag_sql}{sub_ex_sql}"
        )
        subs_eligible = (
            await session.execute(
                _text(f"SELECT COUNT(*) FROM submissions {subs_where}", sub_ex_params),
                subs_params,
            )
        ).scalar() or 0
        subs_limit = math.ceil((subs_eligible * pct) / 100.0)
        if subs_limit > 0:
            cols = "id, title, selftext" if use_ai_posts else "id"
            sub_rows = (
                await session.execute(
                    _text(
                        f"SELECT {cols} FROM submissions {subs_where} ORDER BY RANDOM() LIMIT :lim",
                        sub_ex_params,
                    ),
                    {**subs_params, "lim": subs_limit},
                )
            ).fetchall()
        submissions_text = _word_count_expr_ai_ready(sub_rows, "submission") if use_ai_posts else ""

    if include_comments:
        com_ex_sql, com_ex_bind, com_ex_params = _exclude_clause(exclude_comment_ids, "ex_comms")
        comm_params = {"fid": source_file_id, "mw": min_words, **com_tag_bind, **com_ex_bind}
        comm_where = (
            f"WHERE file_id = :fid AND valid_to IS NULL AND word_count >= :mw{com_tag_sql}{com_ex_sql}"
        )
        comm_eligible = (
            await session.execute(
                _text(f"SELECT COUNT(*) FROM comments {comm_where}", com_ex_params),
                comm_params,
            )
        ).scalar() or 0
        comm_limit = math.ceil((comm_eligible * pct) / 100.0)
        if comm_limit > 0:
            cols = "id, body" if use_ai_comments else "id"
            comm_rows = (
                await session.execute(
                    _text(
                        f"SELECT {cols} FROM comments {comm_where} ORDER BY RANDOM() LIMIT :lim",
                        com_ex_params,
                    ),
                    {**comm_params, "lim": comm_limit},
                )
            ).fetchall()
        comments_text = _word_count_expr_ai_ready(comm_rows, "comment") if use_ai_comments else ""

    return sub_rows, comm_rows, submissions_text, comments_text


async def _apply_tag_or_ai_filter(
    *,
    sub_rows: list,
    comm_rows: list,
    use_ai_posts: bool,
    use_ai_comments: bool,
    submissions_text: str,
    comments_text: str,
    filter_prompt: str,
    api_key: str,
    model: str | None,
    has_tags: bool,
    original_tags_meta: list[str],
    expanded_terms_sql: list[str],
    progress: ProgressTracker | None = None,
) -> tuple[list[str], list[str], str, str, dict]:
    """Resolve the final set of submission/comment ids to copy: either the
    tag-matched sample ids directly (tags-only, no AI step) or the AI's
    filtered id list (``filter_db_module.filter_posts_with_ai``/
    ``filter_comments_with_ai``, both native ``async def`` as of Stage 9
    and awaited directly -- no more ``asyncio.to_thread`` wrapper around a
    sync OpenRouter SDK call).

    The 6th return value, ``coverage``, is ``{}`` when no AI filtering ran
    (tags-only), otherwise has a ``"posts"``/``"comments"`` key (whichever
    AI path(s) ran) each mapping to that call's
    ``{"batches_processed", "batches_total"}`` -- lets the caller detect and
    surface a free-model batch cap or mid-run batch failure instead of
    silently returning an incomplete id list.
    """
    from backend.scripts import filter_db as filter_db_module
    from backend.scripts.filter_db import AIFilterError

    post_ids: list[str] = []
    comment_ids: list[str] = []
    system_prompt = ""
    user_instructions = ""
    rendered_prompt = ""
    coverage: dict[str, dict[str, int]] = {}

    if not use_ai_posts and sub_rows:
        post_ids = [str(r._mapping["id"]) for r in sub_rows if r._mapping.get("id")]
    if not use_ai_comments and comm_rows:
        comment_ids = [str(r._mapping["id"]) for r in comm_rows if r._mapping.get("id")]

    if use_ai_posts and submissions_text:
        try:
            post_ids, system_prompt, rendered_prompt, posts_coverage = await filter_db_module.filter_posts_with_ai(
                filter_prompt, submissions_text, api_key, model, progress=progress
            )
            user_instructions = filter_prompt
            coverage["posts"] = posts_coverage
        except AIFilterError:
            raise
        except Exception as exc:
            raise AIFilterError(f"AI filtering failed for posts: {exc}") from exc

    if use_ai_comments and comments_text:
        try:
            comment_ids, _, _, comments_coverage = await filter_db_module.filter_comments_with_ai(
                filter_prompt, comments_text, api_key, model, progress=progress
            )
            coverage["comments"] = comments_coverage
        except AIFilterError:
            raise
        except Exception as exc:
            raise AIFilterError(f"AI filtering failed for comments: {exc}") from exc

    if has_tags and not filter_prompt:
        tag_ctx = json.dumps(
            {"original_tags": original_tags_meta, "expanded_terms": expanded_terms_sql},
            ensure_ascii=False,
        )
        system_prompt = "Tag-based pre-filter only (no AI content criteria)."
        # Small and already capped -- this IS the instruction, there is no
        # separate rendered prompt for a tags-only filter.
        user_instructions = tag_ctx[:8000]

    if not isinstance(post_ids, list):
        post_ids = []
    if not isinstance(comment_ids, list):
        comment_ids = []

    batches = sum(c["batches_total"] for c in coverage.values()) or None
    return (
        post_ids,
        comment_ids,
        system_prompt,
        user_instructions,
        version_service.prompt_meta(rendered_prompt, batches=batches),
        coverage,
    )


async def _materialize_filtered_schema(
    session: AsyncSession,
    *,
    user_id: int,
    source_file_id: int,
    name: str | None,
    description: str | None,
    project_id: int | None,
    post_ids: list[str],
    comment_ids: list[str],
    system_prompt: str | None,
    user_instructions: str | None,
    prompt_meta: dict | None,
    origin: str = ORIGIN_GENERATED,
    message: str | None = None,
) -> tuple[File, dict[str, int]]:
    """Create the new ``filtered_data`` ``File`` row, its dependency on the
    source file, and copy the matched rows into the fixed
    ``submissions``/``comments`` tables via
    ``raw_data_repo.copy_rows_by_id`` -- the set-based replacement for the
    old per-ID ``SELECT``+``INSERT``+``begin_nested()`` loop.

    Filter Data filters posts and comments independently (two separate
    AI calls / tag predicates), so the result can legitimately contain a
    comment whose parent post didn't survive filtering. Rather than
    silently producing that incoherent-looking dataset, ``counts`` gains
    an ``"orphaned_comments"`` entry: comments copied into the new file
    whose ``link_id`` doesn't match any submission id also copied in
    (comparing against ``post_ids`` directly -- both are bare Reddit ids
    with the ``t3_`` prefix already stripped at import, so no
    id-qualification is needed here).

    Shared by both ways a ``filtered_data`` artifact can come into
    existence -- the one-shot AI job (``_run_filter_data_job``,
    ``origin=ORIGIN_GENERATED``) and the filter editor's hand-composed
    submit (``create_manual_filtered_data``, ``origin=ORIGIN_EDITED``).
    Only the provenance recorded on v1 differs; the artifact's structure,
    lineage pin, row copy and counts are identical, so a manually
    composed filtered database is a first-class artifact rather than a
    second kind of thing.
    """
    # The source file was read before the (minutes-long) LLM call and
    # its matched rows are copied in below -- if it was deleted in that
    # window the copy silently produces zero rows, leaving a
    # finished-looking filtered_data artifact with nothing in it. Fail
    # the job instead. See `file_repo.require_existing_file_ids`.
    await file_repo.require_existing_file_ids(session, {source_file_id})

    new_schema = f"proj_{secrets.token_hex(6)}"
    file_rec = File(
        user_id=user_id,
        filename=name or new_schema,
        schemaname=new_schema,
        file_type="filtered_data",
        description=description or None,
    )
    session.add(file_rec)
    await session.flush()

    # filtered_data's v1 carries the filter prompts/provenance and gives
    # the source_data edge a parent_version_id to pin; its actual
    # content is the submissions/comments rows copied below, which is
    # why this is commit_data_version (a range table), not
    # commit_blob_version.
    await version_service.commit_data_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin=origin, message=message,
        system_prompt=system_prompt, user_instructions=user_instructions or None, prompt_meta=prompt_meta,
        parents=[EdgeSpec(parent_file_id=source_file_id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA)],
    )

    counts = await raw_data_repo.copy_rows_by_id(
        session,
        source_file_id=source_file_id,
        target_file_id=file_rec.id,
        submission_ids=post_ids or None,
        comment_ids=comment_ids or None,
    )

    # A memo follows its row: whatever the researcher wrote about a post
    # while reading the source database is still there when they open
    # that post inside the filtered one. See `repositories/memo_repo.py`.
    counts["memos"] = await memo_repo.copy_memos_by_id(
        session,
        source_file_id=source_file_id,
        target_file_id=file_rec.id,
        submission_ids=post_ids or None,
        comment_ids=comment_ids or None,
    )

    orphaned_comments = 0
    if counts["comments"] and comment_ids:
        kept_post_ids = set(post_ids or [])
        link_id_rows = await session.execute(
            select(Comment.link_id).where(
                Comment.file_id == file_rec.id,
                Comment.id.in_(comment_ids),
            )
        )
        orphaned_comments = sum(
            1 for (link_id,) in link_id_rows if not link_id or link_id not in kept_post_ids
        )
    counts["orphaned_comments"] = orphaned_comments

    session.add(FileTable(file_id=file_rec.id, tablename="submissions", row_count=counts["submissions"]))
    session.add(FileTable(file_id=file_rec.id, tablename="comments", row_count=counts["comments"]))

    if project_id is not None:
        project = await project_repo.get_owned_project(session, project_id, user_id)
        await async_link_file_to_project(session, file_rec.id, project.id)

    await session.flush()
    return file_rec, counts


# ---------------------------------------------------------------------------
# duplicate_data: restore -- fork a raw_data/filtered_data file from a
# chosen point in its history, non-destructively.
# ---------------------------------------------------------------------------


async def duplicate_data(
    session: AsyncSession, user_id: int, ref: str, *, display_name: str, from_version_no: int | None = None
) -> File:
    """Fork a whole ``raw_data``/``filtered_data`` artifact into a
    brand-new file: its own submissions/comments rows AS OF
    ``from_version_no`` (``raw_data_repo.copy_all_rows``, default: head)
    and its lineage (``version_service.fork_lineage``) -- the data-file
    counterpart of ``coding_service.duplicate_coding`` /
    ``codebook_service.duplicate_codebook``. There is deliberately no
    revert route (see ``version_routes.py``'s module docstring): this is
    how a user "undoes" a delete/move without destroying the original
    artifact's history -- the source is untouched, a new file starts
    from the old state.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValidationAppError("display_name is required")

    source_file = await file_repo.get_owned_file(session, ref, user_id, file_types=("raw_data", "filtered_data"))
    if from_version_no is not None:
        target = await version_repo.get_version_by_no(session, source_file.id, from_version_no)
        if target is None:
            raise NotFoundError(f"No version {from_version_no} for '{ref}'")

    new_schema = f"proj_{secrets.token_hex(6)}"
    file_rec = File(
        user_id=user_id,
        filename=display_name,
        schemaname=new_schema,
        file_type=source_file.file_type,
        description=source_file.description,
    )
    session.add(file_rec)
    await session.flush()

    await version_service.commit_data_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin=ORIGIN_FORKED,
        message=f"Duplicated from v{from_version_no}" if from_version_no is not None else "Duplicated",
    )
    counts = await raw_data_repo.copy_all_rows(
        session, source_file_id=source_file.id, target_file_id=file_rec.id,
        target_version_no=1, source_version_no=from_version_no,
    )
    # Memos are not range-versioned (see `storage_models.py::RowMemo`), so
    # a fork FROM an older version still carries today's memos -- the fork
    # restores the artifact's *content* as of that version, not the
    # researcher's notes as of that day.
    await memo_repo.copy_all_memos(
        session, source_file_id=source_file.id, target_file_id=file_rec.id
    )

    source_with_projects = await session.execute(
        select(File).where(File.id == source_file.id, File.user_id == user_id).options(selectinload(File.projects))
    )
    source_file_loaded = source_with_projects.scalar_one_or_none()
    for project in (source_file_loaded.projects if source_file_loaded else []):
        await async_link_file_to_project(session, file_rec.id, project.id)

    session.add(FileTable(file_id=file_rec.id, tablename="submissions", row_count=counts["submissions"]))
    session.add(FileTable(file_id=file_rec.id, tablename="comments", row_count=counts["comments"]))

    await version_service.fork_lineage(session, source_file_id=source_file.id, target_file_id=file_rec.id, user_id=user_id)

    await session.commit()
    await session.refresh(file_rec)
    return file_rec

# ---------------------------------------------------------------------------
# The two filter jobs.
#
# `_run_ai_filter` is the whole AI pass -- tag expansion, sampling,
# LLM call, coverage bookkeeping -- shared verbatim by both. What the
# two handlers do with the ids it returns is the only difference:
# `filter_data` materializes a `filtered_data` artifact immediately,
# while `filter_preview` hands the ids back to the filter editor as
# *suggestions* for a human to accept, reject, or extend before anything
# is created (`create_manual_filtered_data` is the submit half).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FilterOutcome:
    """What one AI filter pass decided, independent of what is done with it."""

    post_ids: list[str]
    comment_ids: list[str]
    system_prompt: str
    user_instructions: str
    prompt_meta: dict | None
    coverage: dict
    has_tags: bool
    original_tags_meta: list[str]
    expanded_terms_sql: list[str]
    submissions_text: str
    comments_text: str


def _coverage_result_fields(coverage: dict) -> dict[str, Any]:
    """Flatten per-content-type coverage into the job-result fields the
    frontend reads.

    ``coverage`` is keyed ``"posts"``/``"comments"`` because posts and
    comments are filtered by two independent AI calls, so this is a
    per-type version of what
    ``external/context_window.coverage_result_fields`` does for the
    single-stream services. Crucially it forwards ``error``: a mid-run
    batch failure used to be dropped here, leaving ``FilterDataPanel``
    to blame every partial run on a free model's batch cap even when the
    real cause was an API error.
    """
    if not coverage:
        return {}
    errors = [c.get("error") for c in coverage.values() if c.get("error")]
    return {
        "batches_processed": {k: v["batches_processed"] for k, v in coverage.items()},
        "batches_total": {k: v["batches_total"] for k, v in coverage.items()},
        "partial": any(v["batches_processed"] < v["batches_total"] for v in coverage.values()),
        "partial_error": "; ".join(errors) or None,
    }


async def _run_ai_filter(
    session: AsyncSession,
    job_id: int,
    payload: dict,
    *,
    exclude_submission_ids: list[str] | None = None,
    exclude_comment_ids: list[str] | None = None,
) -> _FilterOutcome:
    """Expand tags, sample the source, and run the AI filter.

    The complete AI half of filtering, extracted so the one-shot job and
    the editor's preview job share one implementation rather than two
    that drift. ``exclude_*_ids`` is the editor's contribution: rows the
    user has already ruled on are removed from the candidate pool before
    sampling, so a repeated preview run keeps proposing *new* rows
    instead of the same ones.
    """
    from backend.scripts.tag_expansion import (
        comment_body_tag_predicate_sql,
        parse_filter_tags_input,
        submission_text_tag_predicate_sql,
    )
    from backend.scripts import tag_expansion as tag_expansion_module

    api_key = payload["api_key"]
    model = payload.get("model")
    filter_prompt = (payload.get("prompt") or "").strip()
    content_scope = payload.get("content_scope") or "both"

    user_tags_list = parse_filter_tags_input(payload.get("filter_tags"))
    expanded_terms_sql: list[str] = []
    original_tags_meta: list[str] = []
    if user_tags_list:
        original_tags_meta, expanded_terms_sql = await tag_expansion_module.expand_tags_via_openrouter(
            user_tags_list, api_key, model
        )

    has_tags = bool(user_tags_list)
    use_ai_posts = (not has_tags) or bool(filter_prompt)
    use_ai_comments = (not has_tags) or bool(filter_prompt)
    sub_tag_sql, sub_tag_bind = submission_text_tag_predicate_sql(expanded_terms_sql)
    com_tag_sql, com_tag_bind = comment_body_tag_predicate_sql(expanded_terms_sql)

    sub_rows, comm_rows, submissions_text, comments_text = await _sample_source_rows(
        session,
        source_file_id=payload["source_file_id"],
        min_words=payload["min_words"],
        sub_tag_sql=sub_tag_sql,
        sub_tag_bind=sub_tag_bind,
        com_tag_sql=com_tag_sql,
        com_tag_bind=com_tag_bind,
        pct=payload["sample_percentage"],
        use_ai_posts=use_ai_posts,
        use_ai_comments=use_ai_comments,
        include_posts=content_scope in ("both", "posts"),
        include_comments=content_scope in ("both", "comments"),
        exclude_submission_ids=exclude_submission_ids,
        exclude_comment_ids=exclude_comment_ids,
    )

    post_ids, comment_ids, system_prompt, user_instructions, filter_prompt_meta, coverage = await _apply_tag_or_ai_filter(
        sub_rows=sub_rows,
        comm_rows=comm_rows,
        use_ai_posts=use_ai_posts,
        use_ai_comments=use_ai_comments,
        submissions_text=submissions_text,
        comments_text=comments_text,
        filter_prompt=filter_prompt,
        api_key=api_key,
        model=model,
        has_tags=has_tags,
        original_tags_meta=original_tags_meta,
        expanded_terms_sql=expanded_terms_sql,
        progress=ProgressTracker(job_id),
    )

    return _FilterOutcome(
        post_ids=post_ids,
        comment_ids=comment_ids,
        system_prompt=system_prompt,
        user_instructions=user_instructions,
        prompt_meta=filter_prompt_meta,
        coverage=coverage,
        has_tags=has_tags,
        original_tags_meta=original_tags_meta,
        expanded_terms_sql=expanded_terms_sql,
        submissions_text=submissions_text,
        comments_text=comments_text,
    )


@register_handler("filter_data")
async def _run_filter_data_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="filter_data"`` -- the one-shot AI filter
    behind ``/filter``, which produces a ``filtered_data`` artifact
    directly with no human review step.

    Runs in the background job runner's context (no request-scoped
    session), so it opens its own session via the module-level
    ``AsyncSessionLocal`` -- same pattern as ``jobs/service.py::_execute_job``
    and Stage 4's ``coding_service._run_summarize_coding_job``.
    """
    async with AsyncSessionLocal() as session:
        outcome = await _run_ai_filter(session, job_id, payload)

        file_rec, counts = await _materialize_filtered_schema(
            session,
            user_id=payload["user_id"],
            source_file_id=payload["source_file_id"],
            name=payload.get("name"),
            description=payload.get("description"),
            project_id=payload.get("project_id"),
            post_ids=outcome.post_ids,
            comment_ids=outcome.comment_ids,
            system_prompt=outcome.system_prompt,
            user_instructions=outcome.user_instructions,
            prompt_meta=outcome.prompt_meta,
        )
        await session.commit()
        file_id, schema_name, filename = file_rec.id, file_rec.schemaname, file_rec.filename

    result: dict[str, Any] = {
        "message": "Database filtered and saved",
        "submissions_length": len(outcome.submissions_text),
        "comments_length": len(outcome.comments_text),
        "posts_filtered_count": counts["submissions"],
        "comments_filtered_count": counts["comments"],
        "orphaned_comments": counts.get("orphaned_comments", 0),
        "file": {"id": str(file_id), "schema_name": schema_name, "filename": filename},
    }
    if outcome.has_tags:
        result["tag_filter"] = {
            "original_tags": outcome.original_tags_meta,
            "expanded_terms": outcome.expanded_terms_sql,
        }
    result.update(_coverage_result_fields(outcome.coverage))
    return result


# ---------------------------------------------------------------------------
# Filter editor: AI preview (suggests ids) + manual submit (creates the file)
# ---------------------------------------------------------------------------


async def start_filter_preview_job(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    api_key: str,
    model: str | None,
    prompt: str | None,
    min_words: int,
    sample_percentage: float,
    filter_tags: str | None,
    content_scope: str = "both",
    decided_post_ids: list[str] | None = None,
    decided_comment_ids: list[str] | None = None,
) -> Job:
    """Validate and enqueue a ``filter_preview`` background job.

    Same validation and same ``runtime_extra`` API-key handling as
    ``start_filter_data_job``, but the job it enqueues creates nothing --
    it answers "of the rows I haven't decided on, which would you keep?"
    and returns ids. That is what lets the filter editor run the AI tool
    repeatedly and treat each run as a suggestion rather than a
    commitment.
    """
    schema = require_valid_schema(database, field_name="database")
    if not api_key:
        raise ValidationAppError("api_key is required")

    source_file_id = await file_repo.resolve_file_id(session, schema, user_id)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="filter_preview",
        payload={
            "source_file_id": source_file_id,
            "user_id": user_id,
            "model": model,
            "prompt": (prompt or "").strip(),
            "min_words": min_words,
            "sample_percentage": sample_percentage,
            "filter_tags": filter_tags,
            "content_scope": content_scope,
            "decided_post_ids": list(decided_post_ids or []),
            "decided_comment_ids": list(decided_comment_ids or []),
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("filter_preview")
async def _run_filter_preview_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="filter_preview"``.

    Deliberately creates no ``File``, no ``ArtifactVersion`` and no
    ``artifact_edges`` row: a preview is a suggestion, and an artifact
    should exist only once a human has submitted one. Nothing here is
    written to the database at all, which is also why it needs no
    ``session.commit()``.
    """
    async with AsyncSessionLocal() as session:
        outcome = await _run_ai_filter(
            session,
            job_id,
            payload,
            exclude_submission_ids=payload.get("decided_post_ids") or None,
            exclude_comment_ids=payload.get("decided_comment_ids") or None,
        )

    result: dict[str, Any] = {
        "post_ids": outcome.post_ids,
        "comment_ids": outcome.comment_ids,
    }
    if outcome.has_tags:
        result["tag_filter"] = {
            "original_tags": outcome.original_tags_meta,
            "expanded_terms": outcome.expanded_terms_sql,
        }
    result.update(_coverage_result_fields(outcome.coverage))
    return result


async def create_manual_filtered_data(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    name: str,
    description: str | None,
    project_id: int | None,
    post_ids: list[str],
    comment_ids: list[str],
) -> tuple[File, dict[str, int]]:
    """Create a ``filtered_data`` artifact from a hand-picked set of rows.

    The submit half of the filter editor, and the manual counterpart of
    ``_run_filter_data_job``. Synchronous rather than a background job:
    there is no LLM call here, only the same set-based ``INSERT ...
    SELECT`` per table that the AI path ends with.

    Recorded as ``origin=ORIGIN_EDITED`` with no ``system_prompt`` or
    ``prompt_meta`` even when the AI preview tool helped assemble the
    selection. An assist during editing is not the same claim as "a
    model produced this", and the version spine's provenance fields mean
    the stronger claim -- overstating it would make ``model``/
    ``system_prompt`` useless for auditing which artifacts an LLM
    actually generated.
    """
    schema = require_valid_schema(database, field_name="database")
    source_file_id = await file_repo.resolve_file_id(session, schema, user_id)

    file_rec, counts = await _materialize_filtered_schema(
        session,
        user_id=user_id,
        source_file_id=source_file_id,
        name=name,
        description=description,
        project_id=project_id,
        post_ids=post_ids,
        comment_ids=comment_ids,
        system_prompt=None,
        user_instructions=None,
        prompt_meta=None,
        origin=ORIGIN_EDITED,
        message=f"Composed by hand from {len(post_ids)} posts and {len(comment_ids)} comments",
    )
    await session.commit()
    await session.refresh(file_rec)
    return file_rec, counts
