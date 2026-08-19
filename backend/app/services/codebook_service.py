"""Service layer for codebook artifacts -- backs
backend/app/api/codebook_routes.py.

Retires the last two per-artifact ``content_store`` raw-SQL read paths in
this module (``get_codebook``/``parse_codebook``) onto
``repositories/artifact_content_repo.py`` (Stage 3's fixed
``artifact_content`` table), adds the auth/ownership scoping ``get_codebook``
and ``parse_codebook`` never had, and supersedes the Stage-0 guard-clause
patch on ``list_codebooks`` with a real service-layer implementation.

``generate_codebook`` and ``compare_codebooks`` become background jobs (same
job-queue pattern Stage 4/6 established for ``summarize-coding``/
``filter-data``): each gets a synchronous ``start_*_job`` that validates and
enqueues, and an ``@register_handler``-registered handler that does the
actual sampling/LLM-call/persistence work off the request path.

On the "local-import-shadowing" question the plan flagged for the old
``compare_codebooks`` route (``from backend.app.database import engine`` and
``from backend.scripts.codebook_generator import MODEL_3, get_client as
codebook_get_client`` as local imports inside the function body): reading
the old route, only ``engine`` was genuinely duplicated at module level --
``MODEL_3``/``get_client`` were never imported at module level at all, only
the ``codebook_generator`` module itself was (as
``codebook_generator_module``, still used below). The ``engine`` case is a
real but narrow bug: because the local import re-executes
``from backend.app.database import engine`` on every call, it always
re-reads whatever ``backend.app.database.engine`` currently is, never
whatever ``codebook_routes.engine`` (the name every other test in that file
patches) currently is -- so it isn't a production correctness bug (both
names denote the same object under normal operation), but it silently
defeats the module's usual test-mockability convention, which is exactly
what the pre-existing regression test's workaround comment documents. Both
issues disappear structurally here: this module calls
``codebook_generator_module.MODEL_3``/``codebook_generator_module.get_client``
through the one already-module-level-imported reference, the same way
``generate_codebook``'s handler below calls
``codebook_generator_module.generate_codebook`` -- there is no second,
locally-scoped binding of the same name to shadow.
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.core.schema_guard import require_valid_schema
from backend.app.database import (
    AsyncSessionLocal,
    File,
    FileDependency,
    async_link_file_to_project,
)
from backend.app.jobs.models import Job
from backend.app.jobs.registry import register_handler
from backend.app.jobs.service import enqueue_job
from backend.app.repositories import artifact_content_repo, file_repo, project_repo, raw_data_repo
from backend.scripts import codebook_generator as codebook_generator_module

_CODEBOOK_LIST_TYPES = ("codebook", "codebook_comparison")


# ---------------------------------------------------------------------------
# Read paths: get_codebook / parse_codebook / list_codebooks
# ---------------------------------------------------------------------------


async def _lookup_codebook_file(
    session: AsyncSession, user_id: int, codebook_id: str | None, *, file_types: tuple[str, ...]
) -> File | None:
    """3-way schemaname/filename/id lookup scoped to ``user_id``, falling
    back to the most recently created matching file when ``codebook_id`` is
    falsy.

    Doesn't reuse ``repositories/file_repo.py``'s 3-way lookup helpers:
    those don't have a "most recent if no ref given" fallback, which this
    endpoint's existing behavior depends on -- the same reasoning
    ``content_service.get_summary`` documents for its own equivalent lookup.
    """
    base = select(File).where(File.user_id == user_id, File.file_type.in_(file_types))

    if codebook_id:
        result = await session.execute(base.where(File.schemaname == codebook_id))
        file_rec = result.scalar_one_or_none()
        if file_rec is not None:
            return file_rec

        result = await session.execute(base.where(File.filename == codebook_id))
        file_rec = result.scalar_one_or_none()
        if file_rec is not None:
            return file_rec

        try:
            fid = int(codebook_id)
        except ValueError:
            return None
        result = await session.execute(base.where(File.id == fid))
        return result.scalar_one_or_none()

    # Tie-break on id (not just created_at): SQLite's `created_at`
    # resolution can tie two rows inserted in the same test/request, and
    # even on Postgres two rows created in the same statement batch could
    # share a timestamp -- id.desc() keeps "most recent" well-defined
    # either way (same reasoning as content_service.get_summary's
    # equivalent fallback).
    result = await session.execute(base.order_by(File.created_at.desc(), File.id.desc()).limit(1))
    return result.scalars().first()


async def get_codebook(session: AsyncSession, user_id: int, codebook_id: str | None) -> File:
    """Resolve a ``codebook``/``codebook_comparison`` ``File`` owned by
    ``user_id`` -- by schemaname, filename, id, or (if ``codebook_id`` is
    falsy) the most recently created one. Raises ``NotFoundError`` (404) if
    nothing matches. The route reads the actual content separately via
    ``artifact_content_repo.read_content``, matching
    ``content_routes.py::get_summary_file``'s split between "resolve the
    file" (service) and "read its blob" (route + repo).
    """
    file_rec = await _lookup_codebook_file(session, user_id, codebook_id, file_types=_CODEBOOK_LIST_TYPES)
    if file_rec is None:
        raise NotFoundError("No codebook file found")
    return file_rec


async def parse_codebook(session: AsyncSession, user_id: int, codebook_id: str | None) -> tuple[File, str]:
    """Same lookup as ``get_codebook`` but scoped to ``file_type='codebook'``
    only (matching the old route's narrower filter -- comparisons were
    never parseable), returning both the ``File`` and its raw content since
    the route needs the raw text to call ``parse_codebook_to_json``.
    """
    file_rec = await _lookup_codebook_file(session, user_id, codebook_id, file_types=("codebook",))
    if file_rec is None:
        raise NotFoundError("No codebook file found")
    content = await artifact_content_repo.read_content(session, file_rec.id)
    if content is None:
        raise NotFoundError("Codebook content not found in file")
    return file_rec, content


async def list_codebooks(session: AsyncSession, user_id: int) -> list[File]:
    """Every ``codebook`` file owned by ``user_id`` -- comparisons are
    excluded so the generic codebook picker (View Codebook, Apply Codebook)
    never offers a comparison as if it were a real codebook; they're only
    reachable through their own dedicated comparison viewer.

    Supersedes the Stage-0 guard-clause patch (which lived directly in the
    route) with a real service-layer implementation -- same query, same
    ownership scoping, just moved to where the rest of this refactor's
    read paths live. The route still builds the response dict / sorts by
    name, matching the pre-existing wire shape exactly.
    """
    result = await session.execute(
        select(File).where(File.user_id == user_id, File.file_type == "codebook")
    )
    return list(result.scalars().all())


async def save_project_codebook(
    session: AsyncSession,
    user_id: int,
    *,
    schema_name: str,
    content: str,
    display_name: str | None = None,
) -> File:
    """Overwrite a file's codebook content (owned by ``user_id``), and its
    display name if one is given. Raises ``NotFoundError`` (404) if
    ``schema_name`` doesn't resolve to a file owned by ``user_id`` --
    previously an ``HTTPException(404, "File/project not found or you do
    not have permission")`` raised inline in the route; the message text
    changes (now ``file_repo``'s standard "File not found: ..."), the
    404-on-not-owned behavior does not.
    """
    schema = (schema_name or "").strip()
    file_rec = await file_repo.get_owned_file(session, schema, user_id)

    await artifact_content_repo.write_content(session, file_rec.id, content)

    if display_name:
        file_rec.filename = display_name

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


# ---------------------------------------------------------------------------
# generate_codebook: background job kickoff + handler
# ---------------------------------------------------------------------------


async def start_generate_codebook_job(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    api_key: str,
    prompt: str,
    name: str,
    description: str | None,
    project_id: int | None,
    model: str | None,
    sample_percentage: float,
) -> Job:
    """Validate and enqueue a ``generate_codebook`` background job.

    Keeps the same guard-clause validation the old synchronous route did
    (schema must look like ``proj_<id>``, ``api_key`` required) plus the new
    ownership check (``database`` must resolve to a file owned by
    ``user_id``) -- both raise before anything is persisted or a background
    task is spawned. ``api_key`` goes into ``runtime_extra`` so it's never
    written to the ``jobs`` table.

    Deliberate behavior change from the old synchronous route: "no records
    were sampled from the selected database" used to be a synchronous 400
    from this call. Since sampling now happens inside the job handler (it
    needs a DB session, and the whole point of this stage is to get that
    off the request path), that check now surfaces as a failed job instead
    -- same as the equivalent ``filter_data`` conversion in Stage 6.
    """
    schema = require_valid_schema(database, field_name="database")
    if not api_key:
        raise ValidationAppError("api_key is required")

    source_file_id = await file_repo.resolve_file_id(session, schema, user_id)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="generate_codebook",
        payload={
            "source_file_id": source_file_id,
            "user_id": user_id,
            "name": name,
            "model": model,
            "prompt": (prompt or "").strip(),
            "description": description,
            "project_id": project_id,
            "sample_percentage": sample_percentage,
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("generate_codebook")
async def _run_generate_codebook_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="generate_codebook"``.

    Runs in the background job runner's context (no request-scoped
    session), so it opens its own session via the module-level
    ``AsyncSessionLocal`` -- same pattern as
    ``data_service._run_filter_data_job``. Sampling goes through
    ``repositories/raw_data_repo.py::sample_submissions``/``sample_comments``
    against the fixed ``submissions``/``comments`` tables (replacing the old
    raw-SQL ``ORDER BY RANDOM() LIMIT`` reads against a per-artifact
    schema); ``codebook_generator.generate_codebook`` is a native
    ``async def`` (Stage 9, backed by
    ``external/openrouter_client.py::chat_completion``), so it's ``await``ed
    directly -- no more ``asyncio.to_thread`` wrapper around a sync
    OpenAI SDK call.
    """
    source_file_id = payload["source_file_id"]
    user_id = payload["user_id"]
    api_key = payload["api_key"]
    model = payload.get("model") or codebook_generator_module.MODEL_1
    prompt = payload.get("prompt", "")
    name = payload.get("name")
    description = payload.get("description")
    project_id = payload.get("project_id")
    sample_percentage = payload["sample_percentage"]

    async with AsyncSessionLocal() as session:
        subs = await raw_data_repo.sample_submissions(session, source_file_id, sample_percentage)
        comments = await raw_data_repo.sample_comments(session, source_file_id, sample_percentage)

        assembled = ""
        for sub in subs:
            assembled += f"Title: {sub.title or ''}\n{sub.selftext or ''}\n\n"
        for comment in comments:
            assembled += f"{comment.body or ''}\n\n"

        if not assembled.strip():
            raise ValidationAppError(
                "No records were sampled from the selected database. Increase sample size above 0%."
            )

        codebook_text, system_prompt, user_prompt = await codebook_generator_module.generate_codebook(
            assembled, api_key, prompt, MODEL=model
        )
        codebook_text = str(codebook_text or "")

        final_description = (description or "").strip() if description is not None else None
        if final_description == "":
            final_description = None

        new_schema = f"proj_{secrets.token_hex(6)}"
        file_rec = File(
            user_id=user_id,
            filename=name,
            schemaname=new_schema,
            file_type="codebook",
            description=final_description,
            systemprompt=system_prompt,
            userprompt=user_prompt,
        )
        session.add(file_rec)
        await session.flush()

        session.add(FileDependency(child_file_id=file_rec.id, parent_file_id=source_file_id))
        await artifact_content_repo.write_content(session, file_rec.id, codebook_text)

        if project_id is not None:
            project = await project_repo.get_owned_project(session, project_id, user_id)
            await async_link_file_to_project(session, file_rec.id, project.id)

        await session.commit()
        file_id, schema_name, filename, saved_description = (
            file_rec.id,
            file_rec.schemaname,
            file_rec.filename,
            file_rec.description,
        )

    return {
        "codebook": codebook_text,
        "file": {
            "id": str(file_id),
            "schema_name": schema_name,
            "filename": filename,
            "description": saved_description,
        },
    }


# ---------------------------------------------------------------------------
# compare_codebooks: background job kickoff + handler
# ---------------------------------------------------------------------------


async def start_compare_codebooks_job(
    session: AsyncSession,
    user_id: int,
    *,
    codebook_a: str,
    codebook_b: str,
    api_key: str,
    model: str | None,
    prompt: str,
    name: str,
    description: str | None = None,
    project_id: int | None = None,
) -> Job:
    """Validate and enqueue a ``compare_codebooks`` background job.

    Adds the auth/ownership check the old route never had at all (it took
    no ``user_id``/``Request`` dependency whatsoever): both schema names
    must resolve to a file owned by ``user_id`` via
    ``repositories/file_repo.py`` before anything is enqueued. Keeps the
    old ``proj_<id>``-shape guard and ``api_key`` requirement.

    ``name`` is required (matching ``start_generate_codebook_job``'s
    ``name``/``create_project``'s blank-name-check convention): the job
    handler now persists the comparison as a ``File`` artifact directly,
    so it needs a display name up front rather than via a later separate
    save step.
    """
    schema_a = require_valid_schema(codebook_a, field_name="codebook_a")
    schema_b = require_valid_schema(codebook_b, field_name="codebook_b")
    if not api_key:
        raise ValidationAppError("api_key is required")
    if not name or not name.strip():
        raise ValidationAppError("name is required")

    file_id_a = await file_repo.resolve_file_id(session, schema_a, user_id)
    file_id_b = await file_repo.resolve_file_id(session, schema_b, user_id)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="compare_codebooks",
        payload={
            "user_id": user_id,
            "file_id_a": file_id_a,
            "file_id_b": file_id_b,
            "model": model,
            "prompt": (prompt or "").strip(),
            "name": name,
            "description": description,
            "project_id": project_id,
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("compare_codebooks")
async def _run_compare_codebooks_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="compare_codebooks"``.

    Reads both codebooks' content via ``artifact_content_repo.read_content``
    (replacing the old inline ``with engine.connect(): ...`` synchronous
    blocking read), then ``await``s ``codebook_generator.get_client``
    directly -- it's a native ``async def`` as of Stage 9, so no more
    ``asyncio.to_thread`` wrapper is needed.

    Persists the comparison as a ``File`` (``file_type="codebook_comparison"``)
    the same way ``_run_generate_codebook_job`` persists a generated
    codebook -- no more separate ``/api/save-comparison/`` step required.
    ``FileDependency`` rows link the new file to BOTH source codebooks.
    """
    user_id = payload["user_id"]
    file_id_a = payload["file_id_a"]
    file_id_b = payload["file_id_b"]
    api_key = payload["api_key"]
    model = payload.get("model") or codebook_generator_module.MODEL_3
    prompt = payload.get("prompt", "")
    name = payload.get("name")
    description = payload.get("description")
    project_id = payload.get("project_id")

    async with AsyncSessionLocal() as session:
        text_a = await artifact_content_repo.read_content(session, file_id_a) or ""
        text_b = await artifact_content_repo.read_content(session, file_id_b) or ""

    if not text_a and not text_b:
        raise ValidationAppError("No content found in either codebook")

    system_prompt = (
        "You are an expert qualitative researcher. Compare the two provided codebooks.\n"
        "Provide a clear, structured comparison including:\n"
        "- Major similarities and differences\n"
        "- Conflicting or duplicate codes\n"
        "- Suggestions for merging or refining codes\n"
        "- An overall recommendation and confidence level.\n"
        "Return the full comparison as text (no extra JSON or metadata)."
    )
    user_prompt = (
        f"Codebook A: {text_a} Codebook B: {text_b} "
        f"Please compare them in detail. Additional instructions: {prompt}"
    )

    comparison = await codebook_generator_module.get_client(system_prompt, user_prompt, api_key, model)

    final_description = (description or "").strip() if description is not None else None
    if final_description == "":
        final_description = None

    async with AsyncSessionLocal() as session:
        new_schema = f"cmp_{secrets.token_hex(6)}"
        file_rec = File(
            user_id=user_id,
            filename=name,
            schemaname=new_schema,
            file_type="codebook_comparison",
            description=final_description,
        )
        session.add(file_rec)
        await session.flush()

        session.add(FileDependency(child_file_id=file_rec.id, parent_file_id=file_id_a))
        session.add(FileDependency(child_file_id=file_rec.id, parent_file_id=file_id_b))
        await artifact_content_repo.write_content(session, file_rec.id, comparison)

        if project_id is not None:
            project = await project_repo.get_owned_project(session, project_id, user_id)
            await async_link_file_to_project(session, file_rec.id, project.id)

        await session.commit()
        file_id, schema_name, filename = file_rec.id, file_rec.schemaname, file_rec.filename

    return {
        "comparison": comparison,
        "file": {"id": str(file_id), "schema_name": schema_name, "filename": filename},
    }
