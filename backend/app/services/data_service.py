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

import asyncio
import json
import math
import secrets
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationAppError
from backend.app.core.schema_guard import require_valid_schema
from backend.app.database import (
    AsyncSessionLocal,
    File,
    FileDependency,
    FileTable,
    async_link_file_to_project,
)
from backend.app.jobs.models import Job
from backend.app.jobs.registry import register_handler
from backend.app.jobs.service import enqueue_job
from backend.app.repositories import file_repo, project_repo, raw_data_repo
from backend.app.storage_models import Comment, Submission

# ---------------------------------------------------------------------------
# Read paths: word-count ranges / file entries / comments / post contents
# ---------------------------------------------------------------------------

_ROW_COLUMNS_TO_DROP = {"file_id"}


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Serialize a ``Submission``/``Comment`` ORM row to a plain dict,
    matching the old ``dict(r._mapping)`` shape -- minus ``file_id``,
    which didn't exist as a column in the old per-artifact schema (each
    file had its own schema, so there was nothing to scope by).
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
        .where(model.file_id == file_id, model.word_count.between(0, 1000))
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


async def get_file_entries(
    session: AsyncSession, user_id: int, schema: str, limit: int, offset: int
) -> dict[str, Any]:
    """Paginated submissions/comments rows (plus total counts) for the file
    identified by ``schema``, owned by ``user_id``.
    """
    normalized = require_valid_schema(schema, field_name="schema")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)
    safe_offset = max(0, offset)

    sub_count = (
        await session.execute(select(func.count()).select_from(Submission).where(Submission.file_id == file_id))
    ).scalar() or 0
    com_count = (
        await session.execute(select(func.count()).select_from(Comment).where(Comment.file_id == file_id))
    ).scalar() or 0

    sub_rows = (
        await session.execute(
            select(Submission)
            .where(Submission.file_id == file_id)
            .order_by(Submission.id)
            .limit(limit)
            .offset(safe_offset)
        )
    ).scalars().all()
    com_rows = (
        await session.execute(
            select(Comment)
            .where(Comment.file_id == file_id)
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
            .where(Comment.file_id == file_id, Comment.link_id == submission_id)
            .order_by(Comment.created_utc.asc())
        )
    ).scalars().all()
    return {"comments": [_row_to_dict(r) for r in rows]}


async def get_post_contents(
    session: AsyncSession, user_id: int, schema: str, post_ids: list[str]
) -> dict[str, Any]:
    """Title/selftext for a set of submission ids in the file identified by
    ``schema``, owned by ``user_id``.

    This is the retirement of the confirmed SQL-injection-adjacent gap:
    ``schema`` never touches a SQL string. ``require_valid_schema`` rejects
    malformed input outright (fast 400, no DB call); the ``id IN (...)``
    predicate is a normal SQLAlchemy Core query parameterized the usual
    way; and the actual scoping is ``file_repo.resolve_file_id``, which
    only ever resolves to a file owned by ``user_id`` in the first place.
    """
    if not schema or not post_ids:
        raise ValidationAppError("schema and post_ids are required")
    normalized = require_valid_schema(schema, field_name="schema")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)

    rows = await session.execute(
        select(Submission.id, Submission.title, Submission.selftext).where(
            Submission.file_id == file_id,
            Submission.id.in_([str(pid) for pid in post_ids]),
        )
    )
    posts = {
        str(row.id): {"title": row.title or "", "content": row.selftext or ""} for row in rows
    }
    return {"contents": posts}


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
        },
        runtime_extra={"api_key": api_key},
    )


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
) -> tuple[list, list, str, str]:
    """Count eligible rows (``word_count >= min_words`` and, if tags were
    supplied, a keyword match), random-sample ``ceil(eligible * pct / 100)``
    of them, and build the AI-ready text blob for whichever of
    submissions/comments actually needs an AI call.

    Uses ``text()`` against the fixed ``submissions``/``comments`` tables
    scoped by ``file_id`` -- safe (no identifier interpolation; ``file_id``
    is a bound int, table names are fixed literals) and reuses the
    tag-predicate SQL fragments from ``tag_expansion.py`` unchanged.
    """
    sub_rows: list = []
    comm_rows: list = []

    subs_params = {"fid": source_file_id, "mw": min_words, **sub_tag_bind}
    subs_eligible = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM submissions "
                f"WHERE file_id = :fid AND word_count >= :mw{sub_tag_sql}"
            ),
            subs_params,
        )
    ).scalar() or 0
    subs_limit = math.ceil((subs_eligible * pct) / 100.0)
    if subs_limit > 0:
        cols = "id, title, selftext" if use_ai_posts else "id"
        sub_rows = (
            await session.execute(
                text(
                    f"SELECT {cols} FROM submissions "
                    f"WHERE file_id = :fid AND word_count >= :mw{sub_tag_sql} "
                    "ORDER BY RANDOM() LIMIT :lim"
                ),
                {**subs_params, "lim": subs_limit},
            )
        ).fetchall()
    submissions_text = _word_count_expr_ai_ready(sub_rows, "submission") if use_ai_posts else ""

    comm_params = {"fid": source_file_id, "mw": min_words, **com_tag_bind}
    comm_eligible = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM comments "
                f"WHERE file_id = :fid AND word_count >= :mw{com_tag_sql}"
            ),
            comm_params,
        )
    ).scalar() or 0
    comm_limit = math.ceil((comm_eligible * pct) / 100.0)
    if comm_limit > 0:
        cols = "id, body" if use_ai_comments else "id"
        comm_rows = (
            await session.execute(
                text(
                    f"SELECT {cols} FROM comments "
                    f"WHERE file_id = :fid AND word_count >= :mw{com_tag_sql} "
                    "ORDER BY RANDOM() LIMIT :lim"
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
) -> tuple[list[str], list[str], str, str]:
    """Resolve the final set of submission/comment ids to copy: either the
    tag-matched sample ids directly (tags-only, no AI step) or the AI's
    filtered id list (``filter_db_module.filter_posts_with_ai``/
    ``filter_comments_with_ai``, run off the event loop via
    ``asyncio.to_thread`` since the OpenRouter SDK call is sync).
    """
    from backend.scripts import filter_db as filter_db_module
    from backend.scripts.filter_db import AIFilterError

    post_ids: list[str] = []
    comment_ids: list[str] = []
    system_prompt = ""
    user_prompt = ""

    if not use_ai_posts and sub_rows:
        post_ids = [str(r._mapping["id"]) for r in sub_rows if r._mapping.get("id")]
    if not use_ai_comments and comm_rows:
        comment_ids = [str(r._mapping["id"]) for r in comm_rows if r._mapping.get("id")]

    if use_ai_posts and submissions_text:
        try:
            post_ids, system_prompt, user_prompt = await asyncio.to_thread(
                filter_db_module.filter_posts_with_ai, filter_prompt, submissions_text, api_key, model
            )
        except AIFilterError:
            raise
        except Exception as exc:
            raise AIFilterError(f"AI filtering failed for posts: {exc}") from exc

    if use_ai_comments and comments_text:
        try:
            comment_ids, _, _ = await asyncio.to_thread(
                filter_db_module.filter_comments_with_ai, filter_prompt, comments_text, api_key, model
            )
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
        user_prompt = tag_ctx[:8000]

    if not isinstance(post_ids, list):
        post_ids = []
    if not isinstance(comment_ids, list):
        comment_ids = []

    return post_ids, comment_ids, system_prompt, user_prompt


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
    system_prompt: str,
    user_prompt: str,
) -> tuple[File, dict[str, int]]:
    """Create the new ``filtered_data`` ``File`` row, its dependency on the
    source file, and copy the matched rows into the fixed
    ``submissions``/``comments`` tables via
    ``raw_data_repo.copy_rows_by_id`` -- the set-based replacement for the
    old per-ID ``SELECT``+``INSERT``+``begin_nested()`` loop.
    """
    new_schema = f"proj_{secrets.token_hex(6)}"
    file_rec = File(
        user_id=user_id,
        filename=name or new_schema,
        schemaname=new_schema,
        file_type="filtered_data",
        systemprompt=system_prompt,
        userprompt=user_prompt,
        description=description or None,
    )
    session.add(file_rec)
    await session.flush()

    session.add(FileDependency(child_file_id=file_rec.id, parent_file_id=source_file_id))

    counts = await raw_data_repo.copy_rows_by_id(
        session,
        source_file_id=source_file_id,
        target_file_id=file_rec.id,
        submission_ids=post_ids or None,
        comment_ids=comment_ids or None,
    )

    session.add(FileTable(file_id=file_rec.id, tablename="submissions", row_count=counts["submissions"]))
    session.add(FileTable(file_id=file_rec.id, tablename="comments", row_count=counts["comments"]))

    if project_id is not None:
        project = await project_repo.get_owned_project(session, project_id, user_id)
        await async_link_file_to_project(session, file_rec.id, project.id)

    await session.flush()
    return file_rec, counts


@register_handler("filter_data")
async def _run_filter_data_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="filter_data"``.

    Runs in the background job runner's context (no request-scoped
    session), so it opens its own session via the module-level
    ``AsyncSessionLocal`` -- same pattern as ``jobs/service.py::_execute_job``
    and Stage 4's ``coding_service._run_summarize_coding_job``.
    """
    from backend.scripts.tag_expansion import (
        comment_body_tag_predicate_sql,
        parse_filter_tags_input,
        submission_text_tag_predicate_sql,
    )
    from backend.scripts import tag_expansion as tag_expansion_module

    source_file_id = payload["source_file_id"]
    user_id = payload["user_id"]
    api_key = payload["api_key"]
    model = payload.get("model")
    name = payload.get("name")
    filter_prompt = (payload.get("prompt") or "").strip()
    pct = payload["sample_percentage"]
    min_words = payload["min_words"]
    description = payload.get("description")
    project_id = payload.get("project_id")

    user_tags_list = parse_filter_tags_input(payload.get("filter_tags"))
    expanded_terms_sql: list[str] = []
    original_tags_meta: list[str] = []
    if user_tags_list:
        original_tags_meta, expanded_terms_sql = await asyncio.to_thread(
            tag_expansion_module.expand_tags_via_openrouter, user_tags_list, api_key, model
        )

    has_tags = bool(user_tags_list)
    use_ai_posts = (not has_tags) or bool(filter_prompt)
    use_ai_comments = (not has_tags) or bool(filter_prompt)
    sub_tag_sql, sub_tag_bind = submission_text_tag_predicate_sql(expanded_terms_sql)
    com_tag_sql, com_tag_bind = comment_body_tag_predicate_sql(expanded_terms_sql)

    async with AsyncSessionLocal() as session:
        sub_rows, comm_rows, submissions_text, comments_text = await _sample_source_rows(
            session,
            source_file_id=source_file_id,
            min_words=min_words,
            sub_tag_sql=sub_tag_sql,
            sub_tag_bind=sub_tag_bind,
            com_tag_sql=com_tag_sql,
            com_tag_bind=com_tag_bind,
            pct=pct,
            use_ai_posts=use_ai_posts,
            use_ai_comments=use_ai_comments,
        )

        post_ids, comment_ids, system_prompt, user_prompt = await _apply_tag_or_ai_filter(
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
        )

        file_rec, counts = await _materialize_filtered_schema(
            session,
            user_id=user_id,
            source_file_id=source_file_id,
            name=name,
            description=description,
            project_id=project_id,
            post_ids=post_ids,
            comment_ids=comment_ids,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        await session.commit()
        file_id, schema_name, filename = file_rec.id, file_rec.schemaname, file_rec.filename

    result: dict[str, Any] = {
        "message": "Database filtered and saved",
        "submissions_length": len(submissions_text),
        "comments_length": len(comments_text),
        "posts_filtered_count": counts["submissions"],
        "comments_filtered_count": counts["comments"],
        "file": {"id": str(file_id), "schema_name": schema_name, "filename": filename},
    }
    if has_tags:
        result["tag_filter"] = {"original_tags": original_tags_meta, "expanded_terms": expanded_terms_sql}
    return result
