"""Service layer for codebook artifacts -- backs
backend/app/api/codebook_routes.py.

Reads/writes a codebook's content as structured ``codebook_codes`` rows
via ``services/version_service.py`` rather than a markdown blob -- see
that module and ``core/codebook_render.py`` for the row<->markdown
boundary. Adds the auth/ownership scoping ``get_codebook`` never had, and
supersedes the Stage-0 guard-clause patch on ``list_codebooks`` with a
real service-layer implementation.

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
``codebook_generator_module.generate_codebook_map_reduce`` -- there is no
second, locally-scoped binding of the same name to shadow.
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.codebook_render import parse_json_to_codes, parse_markdown_to_codes
from backend.app.core.exceptions import ContextBudgetError, NotFoundError, ValidationAppError
from backend.app.core.schema_guard import require_valid_schema
from backend.app.database import (
    AsyncSessionLocal,
    File,
    async_link_file_to_project,
)
from backend.app.external import context_window
from backend.app.jobs.models import Job
from backend.app.jobs.progress import ProgressTracker
from backend.app.jobs.registry import register_handler
from backend.app.jobs.service import enqueue_job
from backend.app.repositories import file_repo, project_repo, raw_data_repo, version_repo
from backend.app.services import version_service
from backend.app.services.version_service import EdgeSpec
from backend.app.versioning_models import (
    ORIGIN_EDITED,
    ORIGIN_FORKED,
    ORIGIN_GENERATED,
    ORIGIN_IMPORTED,
    RELATION_COMPARED,
    RELATION_DERIVED_FROM,
    ROLE_SIDE_A,
    ROLE_SIDE_B,
    ROLE_SOURCE_DATA,
)
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
        # Lowest-id match, not scalar_one_or_none: `filename` is a
        # non-unique display name, and requiring uniqueness turned a
        # name collision into an unhandled 500 -- see
        # `repositories/file_repo.py::_lookup_file` for the full
        # reasoning this mirrors.
        for condition in (File.schemaname == codebook_id, File.filename == codebook_id):
            result = await session.execute(base.where(condition).order_by(File.id).limit(1))
            file_rec = result.scalars().first()
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
    ``version_service.read_codes``/``read_blob``, matching
    ``content_routes.py::get_summary_file``'s split between "resolve the
    file" (service) and "read its content" (route + ``version_service``).
    """
    file_rec = await _lookup_codebook_file(session, user_id, codebook_id, file_types=_CODEBOOK_LIST_TYPES)
    if file_rec is None:
        raise NotFoundError("No codebook file found")
    return file_rec


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


def _resolve_code_rows(codes: list[dict]) -> list[dict]:
    """Turn client-supplied code dicts into rows ready for
    ``version_service.commit_codebook_version``. Every code must carry
    either a ``code_uid`` (an existing code being kept/edited/moved) or
    an explicit ``is_new: true`` (a code the editor just created) --
    there is no third option. This is the enforcement point for "fail
    loudly, never silently mint": a client that forgot to carry a
    ``code_uid`` forward (e.g. a stale draft) is rejected here rather
    than having its codes silently re-identified as new, which would
    show up as a wall of spurious deletions+additions in the version
    history diff.
    """
    rows: list[dict] = []
    for position, code in enumerate(codes):
        code_uid = code.get("code_uid")
        is_new = bool(code.get("is_new"))
        if not code_uid and not is_new:
            raise ValidationAppError(
                f"Code {code.get('name')!r} has neither a code_uid nor is_new=true -- "
                "refusing to silently mint a new identity for it."
            )
        family_uid = code.get("family_uid")
        family_is_new = bool(code.get("family_is_new"))
        if not family_uid and not family_is_new:
            raise ValidationAppError(
                f"Code {code.get('name')!r}'s family has neither a family_uid nor "
                "family_is_new=true -- refusing to silently mint a new identity for it."
            )
        rows.append(
            {
                "code_uid": code_uid or uuid.uuid4().hex,
                "family_uid": family_uid or uuid.uuid4().hex,
                "family_name": str(code.get("family_name") or "").strip(),
                "name": str(code.get("name") or "").strip(),
                "body": code.get("body") or "",
                "definition": code.get("definition"),
                "inclusion": code.get("inclusion"),
                "exclusion": code.get("exclusion"),
                "keywords": code.get("keywords"),
                "example": code.get("example"),
                "position": position,
            }
        )
    return rows


async def save_project_codebook(
    session: AsyncSession,
    user_id: int,
    *,
    schema_name: str,
    codes: list[dict],
    display_name: str | None = None,
) -> File:
    """Save a file's codebook content as structured code rows (owned by
    ``user_id``), and its display name if one is given. Raises
    ``NotFoundError`` (404) if ``schema_name`` doesn't resolve to a file
    owned by ``user_id``, or ``ValidationAppError`` if any code is
    missing an identity (see ``_resolve_code_rows``).

    Opens (or extends) a human-edit draft version via
    ``version_service.commit_codebook_version`` rather than overwriting
    in place -- this is what makes every save a recoverable point in
    history instead of a destructive blob overwrite.
    """
    schema = (schema_name or "").strip()
    file_rec = await file_repo.get_owned_file(session, schema, user_id)

    rows = _resolve_code_rows(codes)
    await version_service.commit_codebook_version(
        session,
        file_id=file_rec.id,
        author_user_id=user_id,
        origin=ORIGIN_EDITED,
        codes=rows,
    )

    if display_name:
        file_rec.filename = display_name

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


async def import_codebook_markdown(
    session: AsyncSession, user_id: int, ref: str, *, markdown: str
) -> File:
    """Parse pasted/uploaded codebook markdown into structured rows and
    commit them as a new version -- the recovery path for a codebook
    stored as prose (an external document, or a snapshot from before
    this artifact carried structured rows at all). Uses
    ``codebook_render.parse_markdown_to_codes`` with the file's current
    codes as ``existing``, so re-importing a lightly-edited export of the
    same codebook reuses identity by ``(family_name, name)`` match
    instead of minting a fresh uid for every code.
    """
    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("codebook", "coding"))
    existing = await version_service.read_codes(session, file_rec.id)
    existing_rows = [
        {
            "code_uid": c.code_uid, "family_uid": c.family_uid, "family_name": c.family_name,
            "name": c.name, "body": c.body, "definition": c.definition, "inclusion": c.inclusion,
            "exclusion": c.exclusion, "keywords": c.keywords, "example": c.example, "position": c.position,
        }
        for c in existing
    ]
    rows = parse_markdown_to_codes(markdown, existing=existing_rows)

    await version_service.commit_codebook_version(
        session,
        file_id=file_rec.id,
        author_user_id=user_id,
        origin=ORIGIN_IMPORTED,
        codes=[dict(r) for r in rows],
    )
    await session.commit()
    await session.refresh(file_rec)
    return file_rec


async def duplicate_codebook(
    session: AsyncSession, user_id: int, ref: str, *, display_name: str, from_version_no: int | None = None
) -> File:
    """Fork a whole codebook into a brand-new file: its codes (copied
    with ``code_uid``/``family_uid`` preserved, starting the fork's own
    history at v1 -- see ``version_service.fork_lineage``'s docstring for
    why) and its project links.

    ``from_version_no=None`` (the default) forks from the current head.
    Passing a version number instead forks from that point in the
    codebook's history -- the non-destructive replacement for the old
    forward-commit ``revert``: the original codebook's history is left
    untouched, and a new codebook starts from the old state. Mirrors
    ``coding_service.duplicate_coding``.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValidationAppError("display_name is required")

    source_file = await file_repo.get_owned_file(session, ref, user_id, file_types=("codebook",))
    if from_version_no is not None:
        target = await version_repo.get_version_by_no(session, source_file.id, from_version_no)
        if target is None:
            raise NotFoundError(f"No version {from_version_no} for '{ref}'")
    source_codes = await version_service.read_codes(session, source_file.id, version_no=from_version_no)

    new_schema = f"proj_{secrets.token_hex(6)}"
    file_rec = File(
        user_id=user_id,
        filename=display_name,
        schemaname=new_schema,
        file_type="codebook",
        description=source_file.description,
    )
    session.add(file_rec)
    await session.flush()

    code_rows = [
        {
            "code_uid": c.code_uid, "family_uid": c.family_uid, "family_name": c.family_name,
            "name": c.name, "body": c.body, "definition": c.definition, "inclusion": c.inclusion,
            "exclusion": c.exclusion, "keywords": c.keywords, "example": c.example, "position": c.position,
        }
        for c in source_codes
    ]
    source_version = (
        await version_repo.get_version_by_no(session, source_file.id, from_version_no)
        if from_version_no is not None
        else await version_repo.head_version(session, source_file.id)
    )
    await version_service.commit_codebook_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin=ORIGIN_FORKED, codes=code_rows,
        system_prompt=source_version.system_prompt if source_version else None,
        user_instructions=source_version.user_instructions if source_version else None,
        prompt_meta=source_version.prompt_meta if source_version else None,
    )

    source_with_projects = await session.execute(
        select(File).where(File.id == source_file.id, File.user_id == user_id).options(selectinload(File.projects))
    )
    source_file_loaded = source_with_projects.scalar_one_or_none()
    for project in (source_file_loaded.projects if source_file_loaded else []):
        await async_link_file_to_project(session, file_rec.id, project.id)

    await version_service.fork_lineage(session, source_file_id=source_file.id, target_file_id=file_rec.id, user_id=user_id)

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
    content_scope: str = "both",
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
            "content_scope": content_scope,
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
    content_scope = payload.get("content_scope") or "both"
    include_posts = content_scope in ("both", "posts")
    include_comments = content_scope in ("both", "comments")

    async with AsyncSessionLocal() as session:
        subs = (
            await raw_data_repo.sample_submissions(session, source_file_id, sample_percentage)
            if include_posts
            else []
        )
        comments = (
            await raw_data_repo.sample_comments(session, source_file_id, sample_percentage)
            if include_comments
            else []
        )
        parent_context = await raw_data_repo.parent_post_context_for_comments(session, source_file_id, comments)

        records: list[str] = []
        for sub in subs:
            records.append(f"[POST] Title: {sub.title or ''}\n{sub.selftext or ''}")
        for comment in comments:
            parent = parent_context.get(comment.link_id) if comment.link_id else None
            parent_title = (parent or {}).get("title") or ""
            prefix = f'[COMMENT] (replying to "{parent_title}") ' if parent_title else "[COMMENT] "
            records.append(f"{prefix}{comment.body or ''}")
        assembled = context_window.ITEM_SEPARATOR.join(records)

        if not assembled.strip():
            raise ValidationAppError(
                "No records were sampled from the selected database. Increase sample size above 0%."
            )

        codebook_text, system_prompt, rendered_prompt, coverage = await codebook_generator_module.generate_codebook_map_reduce(
            assembled, api_key, prompt, MODEL=model, progress=ProgressTracker(job_id)
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
        )
        session.add(file_rec)
        await session.flush()

        code_rows = parse_json_to_codes(codebook_text)
        await version_service.commit_codebook_version(
            session,
            file_id=file_rec.id,
            author_user_id=user_id,
            origin=ORIGIN_GENERATED,
            codes=[dict(r) for r in code_rows],
            job_id=job_id,
            model=model,
            system_prompt=system_prompt,
            user_instructions=prompt or None,
            prompt_meta=version_service.prompt_meta(rendered_prompt, batches=coverage["batches_total"]),
            parents=[EdgeSpec(parent_file_id=source_file_id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA)],
        )

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
        **context_window.coverage_result_fields(coverage),
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

    Reads both codebooks' content via ``version_service.read_codebook_markdown``
    after sealing each one's head via ``version_service.pin_parent`` (the
    read-as-parent seal trigger), then ``await``s
    ``codebook_generator.get_client`` directly.

    Persists the comparison as a ``File`` (``file_type="codebook_comparison"``)
    the same way ``_run_generate_codebook_job`` persists a generated
    codebook -- no more separate ``/api/save-comparison/`` step required.
    ``artifact_edges`` rows link the new file to BOTH source codebooks,
    ordered ``side_a``/``side_b`` -- that ordering is load-bearing, since
    the comparison prose refers to the codebooks by name in that order.
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
        # Read-as-parent: seal each codebook's head before reading its
        # content, so the comparison can pin exactly which revision of
        # each side it was built from.
        version_a = await version_service.pin_parent(session, file_id_a)
        version_b = await version_service.pin_parent(session, file_id_b)
        text_a = await version_service.read_codebook_markdown(session, file_id_a)
        text_b = await version_service.read_codebook_markdown(session, file_id_b)
        file_a = await session.get(File, file_id_a)
        file_b = await session.get(File, file_id_b)
        await session.commit()

    if not text_a and not text_b:
        raise ValidationAppError("No content found in either codebook")

    name_a = (file_a.filename if file_a else None) or "Codebook A"
    name_b = (file_b.filename if file_b else None) or "Codebook B"

    system_prompt = (
        "You are an expert qualitative researcher. Compare the two provided codebooks.\n"
        "Provide a clear, structured comparison including:\n"
        "- Major similarities and differences\n"
        "- Conflicting or duplicate codes\n"
        "- Suggestions for merging or refining codes\n"
        "- An overall recommendation and confidence level.\n"
        f"Refer to the codebooks by their names, \"{name_a}\" and \"{name_b}\", "
        "not as \"Codebook A\"/\"Codebook B\".\n"
        "Return the full comparison as text (no extra JSON or metadata)."
    )
    user_prompt = (
        f'Codebook "{name_a}": {text_a} Codebook "{name_b}": {text_b} '
        f"Please compare them in detail. Additional instructions: {prompt}"
    )

    # Codebooks are compact taxonomies -- nothing to aggregate the way a
    # coding comparison compacts its per-code rows -- so a comparison that
    # overflows the window can only fail loudly (no batching: a comparison
    # is inherently over both whole codebooks).
    if not context_window.prompt_fits(
        model,
        prompt_chars=len(system_prompt) + len(user_prompt),
        output_reserve_tokens=context_window.BOUNDED_OUTPUT_TOKENS,
    ):
        raise ContextBudgetError(
            f"These two codebooks are too large to compare with {model}. "
            "Choose a larger-context model."
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

        await version_service.commit_blob_version(
            session,
            file_id=file_rec.id,
            author_user_id=user_id,
            origin=ORIGIN_GENERATED,
            content=comparison,
            job_id=job_id,
            model=model,
            parents=[
                EdgeSpec(parent_file_id=file_id_a, relation=RELATION_COMPARED, role=ROLE_SIDE_A, position=0),
                EdgeSpec(parent_file_id=file_id_b, relation=RELATION_COMPARED, role=ROLE_SIDE_B, position=1),
            ],
        )

        if project_id is not None:
            project = await project_repo.get_owned_project(session, project_id, user_id)
            await async_link_file_to_project(session, file_rec.id, project.id)

        await session.commit()
        file_id, schema_name, filename = file_rec.id, file_rec.schemaname, file_rec.filename

    return {
        "comparison": comparison,
        "file": {"id": str(file_id), "schema_name": schema_name, "filename": filename},
    }
