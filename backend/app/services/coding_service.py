"""Service layer for coding-artifact AI operations -- backs
backend/app/api/coding_routes.py.

Started in Stage 4 (the job-queue pilot) with just the
``summarize-coding`` kickoff + job handler; Stage 8 fills in the rest
(``get_coded_data``, ``save_project_coded_data(_duplicate)``,
``start_apply_codebook_job``, ``start_compare_codings_job``) now that the
storage migration for ``coding`` artifacts has landed
(``backend/scripts/migrate_to_fixed_tables.py --file-type coding``).

Stage 8 also retires the last per-artifact-schema write paths in this
domain: every coding artifact used to get its own dynamic Postgres schema
with TWO tables -- ``content_store`` (the classification output, now
``artifact_content``, see ``repositories/artifact_content_repo.py``) and a
REDUNDANT copy of the parent codebook's text (``codebook`` table). That
copy is dropped everywhere in this file: it was always reachable via
``file_dependencies`` -> parent codebook file -> its own
``artifact_content`` row, so nothing about lineage/traceability is lost by
no longer duplicating the text. ``apply_codebook`` additionally now
persists the *structured* parse of the classification output into
``coding_entries`` (``repositories/coding_repo.py``) -- data that used to
be parsed out of the AI response and then discarded when it was flattened
back into one opaque blob.
"""

from __future__ import annotations

import asyncio
import secrets

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import (
    AsyncSessionLocal,
    File,
    FileDependency,
    async_engine,
    async_link_file_to_project,
)
from backend.app.jobs.models import Job
from backend.app.jobs.registry import register_handler
from backend.app.jobs.service import enqueue_job
from backend.app.repositories import artifact_content_repo, coding_repo, file_repo, project_repo, raw_data_repo
from backend.scripts.codebook_apply import _extract_structured_records, _format_evidence_segments, classify_posts

_CODING_FILE_TYPES = ("coding", "coding_comparison")
_CODEBOOK_FILE_TYPES = ("codebook", "codebook_comparison")


# ---------------------------------------------------------------------------
# get_coded_data
# ---------------------------------------------------------------------------


async def _resolve_parent_codebook_text(session: AsyncSession, coding_file_id: int) -> str:
    """The classification's parent codebook's stored text, found by
    walking ``file_dependencies`` from ``coding_file_id`` to its (most
    recently linked) ``codebook``/``codebook_comparison`` parent and
    reading that file's ``artifact_content`` row.

    Replaces the old ``_load_codebook_snapshot``, which read a redundant
    copy of this same text that used to be duplicated into every coding
    artifact's own schema at write time.
    """
    result = await session.execute(
        select(File)
        .join(FileDependency, FileDependency.parent_file_id == File.id)
        .where(
            FileDependency.child_file_id == coding_file_id,
            File.file_type.in_(_CODEBOOK_FILE_TYPES),
        )
        .order_by(FileDependency.id.desc())
        .limit(1)
    )
    parent = result.scalars().first()
    if parent is None:
        return ""
    content = await artifact_content_repo.read_content(session, parent.id)
    return content or ""


async def get_coded_data(session: AsyncSession, user_id: int, coded_id: str | None) -> tuple[File, str, str]:
    """Resolve a ``coding``/``coding_comparison`` file owned by
    ``user_id`` -- by ``coded_id`` (schemaname, then filename, then id) if
    given, otherwise the most recently created one -- and return
    ``(file, classification_content, parent_codebook_text)``.

    Adds the auth/ownership scoping the old route-level lookup
    (``_resolve_coding_file_record``) never had: that helper queried
    across *every* user's coding files, both for a specific ``coded_id``
    and for the "no id given -> most recent" fallback. Raises
    ``NotFoundError`` if nothing matches, or if the matched file has no
    ``artifact_content`` row.
    """
    base = select(File).where(File.file_type.in_(_CODING_FILE_TYPES), File.user_id == user_id)

    file_rec: File | None = None
    if coded_id:
        result = await session.execute(base.where(File.schemaname == coded_id))
        file_rec = result.scalar_one_or_none()
        if file_rec is None:
            result = await session.execute(base.where(File.filename == coded_id))
            file_rec = result.scalar_one_or_none()
        if file_rec is None:
            try:
                fid = int(coded_id)
            except ValueError:
                fid = None
            if fid is not None:
                result = await session.execute(base.where(File.id == fid))
                file_rec = result.scalar_one_or_none()
    else:
        result = await session.execute(base.order_by(File.created_at.desc(), File.id.desc()).limit(1))
        file_rec = result.scalars().first()

    if file_rec is None:
        raise NotFoundError("No coded data file found")

    content = await artifact_content_repo.read_content(session, file_rec.id)
    if content is None:
        raise NotFoundError("Coded data content not found in file")

    codebook_text = await _resolve_parent_codebook_text(session, file_rec.id)
    return file_rec, content, codebook_text


# ---------------------------------------------------------------------------
# save_project_coded_data
# ---------------------------------------------------------------------------


async def save_project_coded_data(
    session: AsyncSession,
    user_id: int,
    *,
    schema_name: str,
    content: str,
    display_name: str | None,
) -> File:
    """Overwrite the stored classification text for an owned coding file.

    Note: the old route also accepted an optional ``codebook_text`` field
    and, when present, upserted it into that file's redundant ``codebook``
    table copy. That write path is retired entirely here -- the parent
    codebook's real text is already reachable via ``file_dependencies``
    (see ``_resolve_parent_codebook_text``), so a caller-supplied
    ``codebook_text`` value has nothing left to do and is intentionally
    not part of this function's signature. The route still tolerates
    (and ignores) a ``codebook_text`` field on the request body for
    backward compatibility with any not-yet-updated caller.
    """
    if not schema_name or not content:
        raise ValidationAppError("schema_name and content are required")

    file_rec = await file_repo.get_owned_file(session, schema_name, user_id, file_types=_CODING_FILE_TYPES)

    await artifact_content_repo.write_content(session, file_rec.id, content)

    if display_name:
        file_rec.filename = display_name

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


# ---------------------------------------------------------------------------
# save_project_coded_data_duplicate
# ---------------------------------------------------------------------------


async def _clone_file_dependencies(
    session: AsyncSession, *, source_file_id: int, target_file_id: int, user_id: int
) -> None:
    """Copy every ``FileDependency`` parent link from ``source_file_id``
    onto ``target_file_id`` (skipping parents not owned by ``user_id``),
    then link ``target_file_id`` to ``source_file_id`` itself as a parent
    too (matching the old handler's own behavior) unless that link was
    already copied above.

    This -- not a redundant codebook-text copy -- is what preserves the
    duplicate's lineage back to the same parent codebook (and raw/filtered
    data) the source pointed at.
    """
    result = await session.execute(select(FileDependency).where(FileDependency.child_file_id == source_file_id))
    source_dependencies = result.scalars().all()

    copied_parent_ids: set[int] = set()
    for dependency in source_dependencies:
        parent_result = await session.execute(
            select(File).where(File.id == dependency.parent_file_id, File.user_id == user_id)
        )
        parent_file = parent_result.scalar_one_or_none()
        if parent_file is None or parent_file.id in copied_parent_ids:
            continue
        session.add(FileDependency(child_file_id=target_file_id, parent_file_id=parent_file.id))
        copied_parent_ids.add(parent_file.id)

    if source_file_id not in copied_parent_ids:
        session.add(FileDependency(child_file_id=target_file_id, parent_file_id=source_file_id))


async def _clone_content(session: AsyncSession, target_file_id: int, content: str) -> None:
    await artifact_content_repo.write_content(session, target_file_id, content)


async def save_project_coded_data_duplicate(
    session: AsyncSession,
    user_id: int,
    *,
    source_schema_name: str,
    content: str,
    display_name: str,
) -> File:
    """Duplicate an owned coding file into a brand-new file, copying its
    classification content, project links, and dependency lineage.
    """
    source_schema_name = (source_schema_name or "").strip()
    display_name = (display_name or "").strip()
    if not source_schema_name or not content or not display_name:
        raise ValidationAppError("source_schema_name, content, and display_name are required")

    source_file = await file_repo.get_owned_file(
        session, source_schema_name, user_id, file_types=_CODING_FILE_TYPES
    )

    new_schema = f"proj_{secrets.token_hex(6)}"
    file_rec = File(
        user_id=user_id,
        filename=display_name,
        schemaname=new_schema,
        file_type=source_file.file_type or "coding",
        systemprompt=source_file.systemprompt,
        userprompt=source_file.userprompt,
    )
    session.add(file_rec)
    await session.flush()

    await _clone_content(session, file_rec.id, content)

    source_with_projects = await session.execute(
        select(File).where(File.id == source_file.id, File.user_id == user_id).options(selectinload(File.projects))
    )
    source_file_loaded = source_with_projects.scalar_one_or_none()
    for project in (source_file_loaded.projects if source_file_loaded else []):
        await async_link_file_to_project(session, file_rec.id, project.id)

    await _clone_file_dependencies(
        session, source_file_id=source_file.id, target_file_id=file_rec.id, user_id=user_id
    )

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


# ---------------------------------------------------------------------------
# start_apply_codebook_job: kickoff + handler
# ---------------------------------------------------------------------------


def _build_coding_entries_from_output(raw_text: str) -> list[dict[str, str]]:
    """Parse ``raw_text`` (the ``POST_ID:/CODE:/EVIDENCE:`` classification
    output ``classify_posts`` already produces) into ``coding_entries``
    rows, merging evidence when the same ``(post_id, code)`` pair appears
    twice.

    Identical logic to ``backend/scripts/migrate_to_fixed_tables.py``'s
    ``_parse_coding_entries`` (kept as a service-local copy rather than an
    import -- that script is a one-off CLI backfill tool, not a shared
    library import site -- but reusing the exact same underlying parser,
    ``codebook_apply.py::_extract_structured_records``).
    """
    records = _extract_structured_records(raw_text)
    merged: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for post_id, entries in records:
        for code_name, evidence_segments in entries:
            key = (post_id, code_name)
            if key not in merged:
                merged[key] = []
                order.append(key)
            merged[key].extend(evidence_segments)
    return [
        {
            "post_id": post_id,
            "code": code_name,
            "evidence": _format_evidence_segments(merged[(post_id, code_name)]),
        }
        for post_id, code_name in order
    ]


async def start_apply_codebook_job(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    codebook: str,
    methodology: str | None,
    api_key: str,
    model: str | None,
    sample_percentage: float,
    report_name: str,
    project_id: int | None,
) -> Job:
    """Validate and enqueue an ``apply_codebook`` background job.

    Resolves both ``database`` (the raw/filtered data source) and
    ``codebook`` (accepts a ``proj_<hex>`` schema name or a numeric File
    id -- ``ApplyCodebookRequest`` already structurally validates which
    shape it is) to ownership-checked ``file_id``s via
    ``repositories/file_repo.py`` *before* enqueuing -- this is also a
    fix, not just a refactor: the old ``_resolve_codebook_schema`` trusted
    a ``proj_``-prefixed ``codebook`` value as-is with no ownership check
    at all when it looked like a schema name (only the numeric-id form was
    ever verified against the ``files`` table). Both forms now go through
    the same ownership-scoped lookup.

    Whether the resolved codebook file actually has non-empty content is
    checked inside the job handler, not here -- matching
    ``start_summarize_coding_job``'s precedent (Stage 4): "does this
    resolve to an owned file" is a fast synchronous guard clause, "is its
    content non-empty" is a data check deferred to the background job.
    """
    if not api_key:
        raise ValidationAppError("api_key is required")

    source_file_id = await file_repo.resolve_file_id(session, database, user_id)
    codebook_file_id = await file_repo.resolve_file_id(
        session, codebook, user_id, file_types=_CODEBOOK_FILE_TYPES
    )

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="apply_codebook",
        payload={
            "user_id": user_id,
            "source_file_id": source_file_id,
            "codebook_file_id": codebook_file_id,
            "methodology": methodology or "",
            "model": model,
            "sample_percentage": sample_percentage,
            "report_name": report_name,
            "project_id": project_id,
        },
        runtime_extra={"api_key": api_key},
    )


def _assemble_posts_content(submissions: list, comments: list) -> str:
    """Same text shape the old raw-SQL ``_assemble_posts_content`` built,
    now from already-sampled ``Submission``/``Comment`` ORM rows.
    """
    assembled_rows: list[str] = []
    for submission in submissions:
        assembled_rows.append(
            f"POST_ID: {submission.id}  Title: {submission.title or ''}  {submission.selftext or ''}"
        )
    for comment in comments:
        assembled_rows.append(f"POST_ID: {comment.id}  {comment.body or ''}")
    return "\n\n".join(assembled_rows).strip()


@register_handler("apply_codebook")
async def _run_apply_codebook_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="apply_codebook"``.

    Runs in the background job runner's context (no request-scoped
    session), so it opens its own sessions via the module-level
    ``AsyncSessionLocal`` -- same pattern as
    ``_run_summarize_coding_job``/``data_service._run_filter_data_job``.

    Persists the classification output to *both* ``artifact_content``
    (the full blob, for display) and ``coding_entries`` (structured, one
    row per post/code pair, parsed from that same output) -- no redundant
    copy of the codebook text; the new file's lineage back to both the
    source data file and the codebook file is recorded via
    ``FileDependency`` instead.
    """
    user_id = payload["user_id"]
    source_file_id = payload["source_file_id"]
    codebook_file_id = payload["codebook_file_id"]
    methodology = payload.get("methodology") or ""
    model = payload.get("model") or ""
    sample_percentage = payload.get("sample_percentage", 100.0)
    report_name = payload.get("report_name") or ""
    project_id = payload.get("project_id")
    api_key = payload["api_key"]

    async with AsyncSessionLocal() as session:
        codebook_text = await artifact_content_repo.read_content(session, codebook_file_id)
        if not codebook_text:
            raise ValidationAppError("Cannot apply codebook: codebook not found or empty")

        submissions = await raw_data_repo.sample_submissions(session, source_file_id, sample_percentage)
        comments = await raw_data_repo.sample_comments(session, source_file_id, sample_percentage)
        assembled = _assemble_posts_content(submissions, comments)

    classification_output, system_prompt, user_prompt = await asyncio.to_thread(
        classify_posts, codebook_text, assembled, methodology, api_key, model
    )
    coding_entries = _build_coding_entries_from_output(classification_output)

    async with AsyncSessionLocal() as session:
        display_name = (report_name or "").strip() or "coding"
        new_schema = f"proj_{secrets.token_hex(6)}"
        file_rec = File(
            user_id=user_id,
            filename=display_name,
            schemaname=new_schema,
            file_type="coding",
            systemprompt=system_prompt,
            userprompt=user_prompt,
        )
        session.add(file_rec)
        await session.flush()

        await artifact_content_repo.write_content(session, file_rec.id, classification_output)
        await coding_repo.bulk_insert_coding_entries(session, file_rec.id, coding_entries)

        session.add(FileDependency(child_file_id=file_rec.id, parent_file_id=source_file_id))
        session.add(FileDependency(child_file_id=file_rec.id, parent_file_id=codebook_file_id))

        # Matches the old handler's own behavior exactly: link the new
        # coding file to the *source* file's projects, but only when the
        # source is itself a raw_data file (not filtered_data) -- a
        # pre-existing narrowing this stage doesn't change.
        source_result = await session.execute(
            select(File).where(File.id == source_file_id).options(selectinload(File.projects))
        )
        source_file = source_result.scalar_one_or_none()
        if source_file is not None and source_file.file_type == "raw_data":
            for project in source_file.projects:
                await async_link_file_to_project(session, file_rec.id, project.id)

        if project_id is not None:
            project = await project_repo.get_owned_project(session, project_id, user_id)
            await async_link_file_to_project(session, file_rec.id, project.id)

        await session.commit()
        file_id, schema_name, filename = file_rec.id, file_rec.schemaname, file_rec.filename

    return {
        "classification_output": classification_output,
        "file": {"id": str(file_id), "schema_name": schema_name, "filename": filename},
    }


# ---------------------------------------------------------------------------
# start_compare_codings_job: kickoff + handler
# ---------------------------------------------------------------------------


async def start_compare_codings_job(
    session: AsyncSession,
    user_id: int,
    *,
    coding_a: str,
    coding_b: str,
    api_key: str,
    model: str | None,
    prompt: str,
) -> Job:
    """Validate and enqueue a ``compare_codings`` background job.

    Adds the auth/ownership check the old synchronous route never had at
    all (no ``get_user_id_from_request`` call anywhere in
    ``compare_codings``): both schemas must resolve, via
    ``repositories/file_repo.py``, to a coding file owned by ``user_id``.
    Keeps the same ``proj_<id>``/``api_key`` guard-clause shape the old
    route used, so a malformed request still fails fast with a 400 before
    anything is persisted or a background task is spawned.
    """
    schema_a = (coding_a or "").strip()
    schema_b = (coding_b or "").strip()
    if not schema_a.startswith("proj_") or not schema_b.startswith("proj_"):
        raise ValidationAppError("schema names must be proj_<id>")
    if not api_key:
        raise ValidationAppError("api_key is required")

    file_id_a = await file_repo.resolve_file_id(session, schema_a, user_id, file_types=_CODING_FILE_TYPES)
    file_id_b = await file_repo.resolve_file_id(session, schema_b, user_id, file_types=_CODING_FILE_TYPES)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="compare_codings",
        payload={"file_id_a": file_id_a, "file_id_b": file_id_b, "model": model, "prompt": prompt or ""},
        runtime_extra={"api_key": api_key},
    )


@register_handler("compare_codings")
async def _run_compare_codings_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="compare_codings"``.

    The LLM call now runs via ``asyncio.to_thread`` -- the old route
    called ``codebook_get_client`` (a sync OpenAI SDK call) directly
    inline, one of the confirmed request-blocking-event-loop sites this
    whole refactor started from.
    """
    from backend.scripts.codebook_generator import MODEL_3
    from backend.scripts.codebook_generator import get_client as codebook_get_client

    file_id_a = payload["file_id_a"]
    file_id_b = payload["file_id_b"]
    model = payload.get("model")
    prompt = payload.get("prompt", "")
    api_key = payload["api_key"]

    async with AsyncSessionLocal() as session:
        text_a = await artifact_content_repo.read_content(session, file_id_a) or ""
        text_b = await artifact_content_repo.read_content(session, file_id_b) or ""

    if not text_a and not text_b:
        raise ValidationAppError("No content found in either coding")

    system_prompt = (
        "You are an expert qualitative researcher. Compare the two provided coded datasets.\n"
        "Provide a clear, structured comparison including:\n"
        "- Major overlaps and divergences in coding decisions\n"
        "- Instances where codes appear inconsistent or misapplied\n"
        "- Suggestions for reconciliation or re-labeling\n"
        "- An overall recommendation and confidence level.\n"
        "Return the full comparison in a markdown format."
    )
    user_prompt = (
        f"Coding A: {text_a} Coding B: {text_b} Please compare them in detail. "
        f"Additional instructions: {prompt}"
    )
    chosen_model = model or MODEL_3

    comparison = await asyncio.to_thread(codebook_get_client, system_prompt, user_prompt, api_key, chosen_model)
    return {"comparison": comparison}


# ---------------------------------------------------------------------------
# summarize_coding: kickoff + handler (Stage 4 -- unchanged by Stage 8)
# ---------------------------------------------------------------------------


async def start_summarize_coding_job(
    session: AsyncSession,
    user_id: int,
    *,
    coding: str,
    api_key: str,
    model: str | None,
    prompt: str,
) -> Job:
    """Validate and enqueue a ``summarize_coding`` background job.

    Keeps the same guard-clause validation the old synchronous route did
    (schema must look like ``proj_<id>``, ``api_key`` must be present) --
    both raise ``ValidationAppError`` (400) so a bad request still fails
    fast, before anything is persisted or a background task is spawned.

    ``model``/``prompt``/the resolved schema name go into the persisted
    ``payload``; ``api_key`` is passed as ``runtime_extra`` so it is never
    written to the ``jobs`` table (see ``jobs/service.py::enqueue_job``).
    """
    schema = (coding or "").strip()
    if not schema.startswith("proj_"):
        raise ValidationAppError("schema name must be proj_<id>")

    if not api_key:
        raise ValidationAppError("api_key is required")

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="summarize_coding",
        payload={"schema": schema, "prompt": prompt, "model": model},
        runtime_extra={"api_key": api_key},
    )


@register_handler("summarize_coding")
async def _run_summarize_coding_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="summarize_coding"``.

    Runs in the background job runner's context (no request-scoped
    session/connection), so it opens its own connection directly via the
    module-level ``async_engine`` -- same as the route did inline before
    this stage.
    """
    from backend.scripts.summarize_coding import summarize_coding as summarize_coding_function

    schema = payload["schema"]
    prompt = payload.get("prompt", "")
    model = payload.get("model")
    api_key = payload["api_key"]

    async with async_engine.connect() as conn:
        rr = await conn.execute(text(f'SELECT file_text FROM "{schema}".content_store LIMIT 1'))
        row = rr.fetchone()

    coding_data = (row[0] if row else "") or ""
    if not coding_data:
        raise ValidationAppError("No content found in coding")

    summary = await asyncio.to_thread(
        summarize_coding_function, coding_data, prompt, api_key, model
    )
    return {"summary": summary}
