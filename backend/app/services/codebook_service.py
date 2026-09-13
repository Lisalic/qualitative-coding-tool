"""Service layer for codebook artifacts -- backs
backend/app/api/codebook_routes.py.

Reads/writes a codebook's content as structured ``codebook_codes`` rows
via ``services/version_service.py`` rather than a markdown blob -- see
that module and ``core/codebook_render.py`` for the row<->markdown
boundary. Adds the auth/ownership scoping ``get_codebook`` never had, and
supersedes the Stage-0 guard-clause patch on ``list_codebooks`` with a
real service-layer implementation.

Codebook generation has one entry point, the codebook editor: an AI
preview (``start_codebook_preview_job`` / ``_run_codebook_preview_job``,
job_type ``"codebook_preview"``) that proposes codes without creating
anything, and a synchronous manual submit (``create_manual_codebook``)
that materializes the researcher's accepted draft. Both share
``_assemble_source_records`` for sampling; only the preview job calls the
LLM. ``compare_codebooks`` is a separate, still one-shot, background job
(same job-queue pattern Stage 4/6 established for
``summarize-coding``/``filter-data``): a synchronous ``start_*_job`` that
validates and enqueues, and an ``@register_handler``-registered handler
that does the actual LLM-call/persistence work off the request path.

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
what the pre-existing regression test's workaround comment documents. That
issue disappears structurally here: this module calls
``codebook_generator_module.get_client`` through the one
already-module-level-imported reference, the same way
``_run_codebook_preview_job`` below calls
``codebook_generator_module.generate_codebook_map_reduce`` -- there is no
second, locally-scoped binding of the same name to shadow. (``MODEL_3``
itself no longer exists: ``model`` is a required field on every request
that reaches an LLM, so there is nothing left to fall back to.)
"""

from __future__ import annotations

import secrets
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.codebook_render import (
    parse_json_to_codes,
    parse_json_to_merge_proposals,
    parse_markdown_to_codes,
)
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
from backend.app.services import assist_service, version_service
from backend.app.services.version_service import EdgeSpec
from backend.app.versioning_models import (
    ASSIST_STAGE_CODEBOOK,
    ASSIST_STAGE_INTEGRATE,
    ORIGIN_EDITED,
    ORIGIN_FORKED,
    ORIGIN_GENERATED,
    ORIGIN_IMPORTED,
    RELATION_COMPARED,
    RELATION_DERIVED_FROM,
    RELATION_MERGED_FROM,
    ROLE_MERGE_INPUT,
    ROLE_SIDE_A,
    ROLE_SIDE_B,
    ROLE_SOURCE_DATA,
    ArtifactVersion,
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
    assist_runs: list[dict] | None = None,
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

    ``assist_runs`` (see ``schemas.AssistRunIn``) is the Refine-mode
    counterpart to ``create_manual_codebook``'s: Refine is an equally
    AI-assisted path as New. There is no ``database`` field on this
    save to say what the preview sampled from, so the expected source is
    resolved from this codebook's own ``source_data`` edge instead of
    being trusted from the request.
    """
    schema = (schema_name or "").strip()
    file_rec = await file_repo.get_owned_file(session, schema, user_id)

    rows = _resolve_code_rows(codes)
    version = await version_service.commit_codebook_version(
        session,
        file_id=file_rec.id,
        author_user_id=user_id,
        origin=ORIGIN_EDITED,
        codes=rows,
    )

    if display_name:
        file_rec.filename = display_name

    if assist_runs:
        edges = await version_repo.list_parent_edges_for_files(session, [file_rec.id])
        source_edge = next((e for e in edges if e.role == ROLE_SOURCE_DATA), None)
        await assist_service.record_assist_runs(
            session,
            user_id=user_id,
            file_id=file_rec.id,
            version_id=version.id,
            stage=ASSIST_STAGE_CODEBOOK,
            source_file_id=source_edge.parent_file_id if source_edge else None,
            runs=assist_runs,
        )

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



async def _assemble_source_records(
    session: AsyncSession,
    source_file_id: int,
    sample_percentage: float,
    content_scope: str,
) -> str:
    """Sample a data file's submissions/comments and flatten them into the
    one-record-per-item text the codebook prompts consume, joined with
    ``context_window.ITEM_SEPARATOR``.

    Shared by the one-shot generate job and the editor's propose-codes
    preview job, so both look at the source data in exactly the same way
    -- the codebook counterpart of ``data_service._sample_source_rows``.
    Raises ``ValidationAppError`` when the sample comes back empty, since
    neither caller can do anything useful with no data.
    """
    include_posts = content_scope in ("both", "posts")
    include_comments = content_scope in ("both", "comments")

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
    return assembled


async def _materialize_codebook(
    session: AsyncSession,
    *,
    user_id: int,
    parents: Sequence[EdgeSpec],
    name: str,
    description: str | None,
    project_id: int | None,
    code_rows: list[dict],
    message: str | None = None,
) -> tuple[File, ArtifactVersion]:
    """Create a new ``codebook`` File from ``code_rows`` and commit it as
    that file's v1, linked back to whatever it was built from via
    ``parents``. Returns the version alongside the file so a caller
    (``create_manual_codebook``, ``create_integrated_codebook``) can
    record assist-provenance against it.

    The codebook editors' only way to create a new codebook -- both the
    by-hand editor (one ``derived_from``/``source_data`` parent) and the
    integrate editor (N ``merged_from``/``merge_input`` parents, one per
    source codebook) go through this same function, since the actual work
    here (mint the ``proj_`` schema, create the File, commit v1, link the
    project) doesn't depend on how many parents there are or what
    relation they carry -- that's caller knowledge, expressed entirely
    through ``parents``. Always ``origin=ORIGIN_EDITED`` with no LLM
    provenance, since the researcher's accepted draft is what gets
    committed regardless of whether an AI preview helped write it.

    Does not commit -- the caller owns the transaction boundary.
    """
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

    version = await version_service.commit_codebook_version(
        session,
        file_id=file_rec.id,
        author_user_id=user_id,
        origin=ORIGIN_EDITED,
        codes=code_rows,
        message=message,
        parents=parents,
    )

    if project_id is not None:
        project = await project_repo.get_owned_project(session, project_id, user_id)
        await async_link_file_to_project(session, file_rec.id, project.id)

    return file_rec, version



# ---------------------------------------------------------------------------
# codebook_preview: background job kickoff + handler (the /codebook-editor
# "propose more codes" assistant). Creates nothing -- see the handler.
# ---------------------------------------------------------------------------


def _code_dedupe_key(family_name: str | None, name: str | None) -> str:
    """Normalized ``(family, name)`` identity used to tell a proposed code
    apart from one the researcher already has. Mirrors
    ``lib/codebookEditorState.js::codeKey`` exactly -- the two must agree
    or the server and the client would disagree about what counts as a
    duplicate.
    """
    return f"{(family_name or '').strip().lower()}\x00{(name or '').strip().lower()}"


def _render_existing_codes(existing_codes: list[dict]) -> str:
    """Render the researcher's current draft as the compact ``family ::
    name -- definition`` list the prompt shows under EXISTING CODES.
    """
    lines: list[str] = []
    for code in existing_codes:
        family = str(code.get("family_name") or "").strip()
        name = str(code.get("name") or "").strip()
        if not name:
            continue
        definition = str(code.get("definition") or "").strip()
        line = f"- {family} :: {name}" if family else f"- {name}"
        if definition:
            line += f" -- {definition}"
        lines.append(line)
    return "\n".join(lines)


async def start_codebook_preview_job(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    api_key: str,
    model: str | None,
    prompt: str,
    sample_percentage: float,
    content_scope: str = "both",
    existing_codes: list[dict] | None = None,
) -> Job:
    """Validate and enqueue a ``codebook_preview`` background job.

    Same guards as ``start_compare_codebooks_job`` (valid schema, api_key
    present, source owned by ``user_id``), and the same ``runtime_extra``
    handling so the key is never written to the ``jobs`` table. Takes no
    ``name``/``project_id`` because this job creates no artifact.
    """
    schema = require_valid_schema(database, field_name="database")
    if not api_key:
        raise ValidationAppError("api_key is required")

    source_file_id = await file_repo.resolve_file_id(session, schema, user_id)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="codebook_preview",
        payload={
            "source_file_id": source_file_id,
            "user_id": user_id,
            "model": model,
            "prompt": (prompt or "").strip(),
            "sample_percentage": sample_percentage,
            "content_scope": content_scope,
            "existing_codes": existing_codes or [],
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("codebook_preview")
async def _run_codebook_preview_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="codebook_preview"``.

    Samples the source data and asks the model for codes that are NOT
    already in ``existing_codes`` (the researcher's live draft), then
    returns them as plain proposal dicts for the editor's review tray.

    Deliberately creates no ``File``, no ``ArtifactVersion``, no
    ``codebook_codes`` row and no ``artifact_edges`` row -- a proposal is
    not an artifact, and nothing becomes one until the researcher accepts
    it and submits. Nothing here is written to the database at all, which
    is also why it needs no ``session.commit()``. Same contract as
    ``data_service._run_filter_preview_job``.

    Proposals already covered by ``existing_codes`` are dropped here as
    well as client-side: the prompt asks the model not to restate an
    existing code, but a prompt is not a guarantee, and a run started
    before the researcher added a code should not be able to re-propose
    it on return.
    """
    source_file_id = payload["source_file_id"]
    model = payload["model"]
    prompt = payload.get("prompt", "")
    api_key = payload["api_key"]
    sample_percentage = payload["sample_percentage"]
    content_scope = payload.get("content_scope") or "both"
    existing_codes: list[dict] = payload.get("existing_codes") or []

    async with AsyncSessionLocal() as session:
        assembled = await _assemble_source_records(
            session, source_file_id, sample_percentage, content_scope
        )

    codebook_text, system_prompt, rendered_prompt, coverage = await codebook_generator_module.generate_codebook_map_reduce(
        assembled,
        api_key,
        prompt,
        MODEL=model,
        progress=ProgressTracker(job_id),
        existing_codes=_render_existing_codes(existing_codes),
    )

    seen = {_code_dedupe_key(c.get("family_name"), c.get("name")) for c in existing_codes}
    proposals: list[dict] = []
    for row in parse_json_to_codes(str(codebook_text or "")):
        key = _code_dedupe_key(row.get("family_name"), row.get("name"))
        if not row.get("name") or key in seen:
            continue
        seen.add(key)
        proposals.append(
            {
                "family_name": row.get("family_name") or "",
                "name": row.get("name") or "",
                "definition": row.get("definition"),
                "inclusion": row.get("inclusion"),
                "exclusion": row.get("exclusion"),
                "keywords": row.get("keywords"),
                "example": row.get("example"),
            }
        )

    return {
        "proposals": proposals,
        # Surfaced so `assist_service.record_assist_runs` can source a
        # codebook editor's assist-provenance record from THIS job --
        # never trusted from the client. See GAP-4/C2.
        "system_prompt": system_prompt,
        "user_instructions": prompt,
        "prompt_meta": version_service.prompt_meta(rendered_prompt, batches=coverage.get("batches_total")),
        **context_window.coverage_result_fields(coverage),
    }


async def create_manual_codebook(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    name: str,
    description: str | None,
    project_id: int | None,
    codes: list[dict],
    assist_runs: list[dict] | None = None,
) -> File:
    """Create a codebook the researcher composed by hand in the codebook
    editor (with or without help from the preview assistant).

    ``origin=edited`` with null ``model``/``system_prompt``/``prompt_meta``
    is deliberate and matches ``data_service.create_manual_filtered_data``:
    an assist during editing is not the same claim as "a model produced
    this", and the version spine's provenance fields mean the stronger
    claim. ``assist_runs`` (see ``schemas.AssistRunIn``) is the separate
    C2 channel that DOES record which ``codebook_preview`` job(s)
    contributed and how many proposals were accepted/dismissed -- see
    ``services/assist_service.py``.
    """
    schema = require_valid_schema(database, field_name="database")
    source_file_id = await file_repo.resolve_file_id(session, schema, user_id)

    code_rows = _resolve_code_rows(codes)
    file_rec, version = await _materialize_codebook(
        session,
        user_id=user_id,
        parents=[EdgeSpec(parent_file_id=source_file_id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA)],
        name=name,
        description=description,
        project_id=project_id,
        code_rows=code_rows,
        message=f"Composed by hand from {len(code_rows)} codes",
    )
    if assist_runs:
        await assist_service.record_assist_runs(
            session,
            user_id=user_id,
            file_id=file_rec.id,
            version_id=version.id,
            stage=ASSIST_STAGE_CODEBOOK,
            source_file_id=source_file_id,
            runs=assist_runs,
        )

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


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

    ``name`` is required (matching ``create_project``'s
    blank-name-check convention): the job
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
    the same way ``_materialize_codebook`` persists a codebook -- no more
    separate ``/api/save-comparison/`` step required.
    ``artifact_edges`` rows link the new file to BOTH source codebooks,
    ordered ``side_a``/``side_b`` -- that ordering is load-bearing, since
    the comparison prose refers to the codebooks by name in that order.
    """
    user_id = payload["user_id"]
    file_id_a = payload["file_id_a"]
    file_id_b = payload["file_id_b"]
    api_key = payload["api_key"]
    model = payload["model"]
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


# ---------------------------------------------------------------------------
# integrate_codebooks: an AI-assist preview (creates nothing) + a synchronous
# manual submit that materializes the researcher's reviewed merge draft --
# the same two-halves shape as codebook_preview/create_manual_codebook, one
# level up: instead of proposing codes from raw data, this proposes codes
# merged from two or more existing codebooks.
# ---------------------------------------------------------------------------


async def _resolve_source_codebooks(session: AsyncSession, user_id: int, codebooks: list[str]) -> list[int]:
    """Resolve each ref in ``codebooks`` to a ``File.id`` owned by
    ``user_id`` and typed ``codebook`` (a ``codebook_comparison`` or any
    other artifact type is rejected, not silently accepted -- this is the
    same guard ``codebook editor``'s Refine-mode picker applies
    client-side, enforced here too since the client can't be trusted).
    Deduplicates while preserving selection order, then requires at least
    two distinct codebooks remain -- integrating one codebook with itself
    is not a merge.
    """
    seen: set[int] = set()
    ids: list[int] = []
    for ref in codebooks:
        schema = require_valid_schema(ref, field_name="codebooks")
        file_id = await file_repo.resolve_file_id(session, schema, user_id, file_types=("codebook",))
        if file_id in seen:
            continue
        seen.add(file_id)
        ids.append(file_id)
    if len(ids) < 2:
        raise ValidationAppError("Select at least two distinct codebooks to integrate")
    return ids


def _render_source_codebooks(entries: list[tuple[str, str]]) -> str:
    """Render each source codebook's markdown into one
    ``--- CODEBOOK {i+1}: {filename} ---`` block, mirroring
    ``codebook_generator._build_consolidation_user_prompt``'s
    ``--- DRAFT CODEBOOK {i+1} ---`` idiom. The 1-based numbering here is
    exactly what the model is asked to echo back in a proposal's
    ``sources[].codebook``, and what ``_verify_proposal_sources`` below
    expects to see.
    """
    blocks = [f"--- CODEBOOK {i + 1}: {name} ---\n{markdown}" for i, (name, markdown) in enumerate(entries)]
    return "\n\n".join(blocks)


def _verify_proposal_sources(raw_sources: list[dict], index: dict[tuple[int, str], str]) -> list[dict]:
    """Keep only the ``sources`` entries that resolve against ``index``
    (built from the codebooks this job actually read -- see
    ``_run_integrate_codebook_job``), dropping the rest.

    ``sources`` is model output, not a database read: the model can (and
    occasionally will) invent a plausible-looking source, so this is
    evidence, not assumption. A proposal whose sources all fail to
    resolve still comes back from the job with ``sources: []`` rather
    than being dropped entirely -- an unverifiable merge is still worth
    the researcher's review, just without a provenance claim attached.
    """
    verified: list[dict] = []
    for entry in raw_sources:
        key = (entry.get("codebook"), _code_dedupe_key(entry.get("family_name"), entry.get("name")))
        schema_name = index.get(key)
        if schema_name is None:
            continue
        verified.append(
            {
                "codebook": schema_name,
                "family_name": entry.get("family_name") or "",
                "name": entry.get("name") or "",
            }
        )
    return verified


async def start_integrate_codebook_job(
    session: AsyncSession,
    user_id: int,
    *,
    codebooks: list[str],
    api_key: str,
    model: str | None,
    prompt: str,
    existing_codes: list[dict] | None = None,
) -> Job:
    """Validate and enqueue an ``integrate_codebook_preview`` background
    job. Same guards as ``start_codebook_preview_job`` (api_key present,
    every ref owned by ``user_id``), plus ``_resolve_source_codebooks``'s
    "at least two distinct codebooks" and "must actually be codebooks"
    checks. Takes no ``name``/``project_id`` because, like
    ``codebook_preview``, this job creates no artifact -- only
    ``create_integrated_codebook`` does that.
    """
    if not api_key:
        raise ValidationAppError("api_key is required")

    source_file_ids = await _resolve_source_codebooks(session, user_id, codebooks)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="integrate_codebook_preview",
        payload={
            "user_id": user_id,
            "source_file_ids": source_file_ids,
            "model": model,
            "prompt": (prompt or "").strip(),
            "existing_codes": existing_codes or [],
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("integrate_codebook_preview")
async def _run_integrate_codebook_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="integrate_codebook_preview"``.

    Reads every source codebook's content (after sealing each one's head
    via ``version_service.pin_parent``, the same read-as-parent discipline
    ``_run_compare_codebooks_job`` applies) and asks the model to merge
    them into one set of proposed codes, each claiming which source
    code(s) it came from.

    No batching -- a merge is inherently over ALL sources at once (see
    ``codebook_generator.integrate_codebooks``'s docstring), so an
    over-budget prompt fails loudly via ``ContextBudgetError`` rather than
    being silently split.

    Deliberately creates no ``File``, no ``ArtifactVersion``, no
    ``codebook_codes`` row and no ``artifact_edges`` row -- same contract
    as ``_run_codebook_preview_job``: a proposal is not an artifact, and
    nothing becomes one until the researcher accepts and submits.
    """
    source_file_ids: list[int] = payload["source_file_ids"]
    model = payload["model"]
    prompt = payload.get("prompt", "")
    api_key = payload["api_key"]
    existing_codes: list[dict] = payload.get("existing_codes") or []

    async with AsyncSessionLocal() as session:
        # Read-as-parent: seal each source codebook's head before reading
        # its content, so the merge can (eventually, via artifact_edges)
        # pin exactly which revision of each source it was built from.
        entries: list[tuple[str, str]] = []
        # (codebook_1based, dedupe_key) -> that source codebook's schemaname,
        # built from the codes this job actually read -- the ground truth
        # _verify_proposal_sources checks a claimed source against.
        source_index: dict[tuple[int, str], str] = {}
        for i, file_id in enumerate(source_file_ids):
            await version_service.pin_parent(session, file_id)
            markdown = await version_service.read_codebook_markdown(session, file_id)
            codes = await version_service.read_codes(session, file_id)
            file_rec = await session.get(File, file_id)
            display_name = (file_rec.filename if file_rec else None) or f"Codebook {i + 1}"
            entries.append((display_name, markdown))
            for code in codes:
                key = (i + 1, _code_dedupe_key(code.family_name, code.name))
                source_index[key] = file_rec.schemaname if file_rec else ""
        await session.commit()

    if not any(markdown.strip() for _, markdown in entries):
        raise ValidationAppError("No content found in any of the selected codebooks")

    codebook_blocks = _render_source_codebooks(entries)
    existing_codes_rendered = _render_existing_codes(existing_codes)

    system_prompt = codebook_generator_module.build_integrate_system_prompt(existing_codes_rendered)
    user_prompt = codebook_generator_module.build_integrate_user_prompt(codebook_blocks, prompt)

    # A merge is inherently over every source codebook at once (see
    # codebook_generator.integrate_codebooks's docstring) -- no batching,
    # so an over-budget prompt fails loudly rather than being silently
    # split into a merge-of-merges that would also destroy per-code
    # sources provenance.
    if not context_window.prompt_fits(
        model,
        prompt_chars=len(system_prompt) + len(user_prompt),
        output_reserve_tokens=context_window.BOUNDED_OUTPUT_TOKENS,
    ):
        raise ContextBudgetError(
            f"These {len(source_file_ids)} codebooks are too large to integrate with {model}. "
            "Choose a larger-context model or integrate fewer at a time."
        )

    result, system_prompt, rendered_prompt = await codebook_generator_module.integrate_codebooks(
        codebook_blocks,
        api_key,
        prompt,
        MODEL=model,
        existing_codes=existing_codes_rendered,
    )

    seen = {_code_dedupe_key(c.get("family_name"), c.get("name")) for c in existing_codes}
    proposals: list[dict] = []
    for raw_proposal in parse_json_to_merge_proposals(str(result or "")):
        key = _code_dedupe_key(raw_proposal.get("family_name"), raw_proposal.get("name"))
        if key in seen:
            continue
        seen.add(key)
        raw_proposal["sources"] = _verify_proposal_sources(raw_proposal.get("sources") or [], source_index)
        proposals.append(raw_proposal)

    return {
        "proposals": proposals,
        # Surfaced so `assist_service.record_assist_runs` can source an
        # integrate editor's assist-provenance record from THIS job --
        # never trusted from the client. See GAP-4/C2.
        "system_prompt": system_prompt,
        "user_instructions": prompt,
        "prompt_meta": version_service.prompt_meta(rendered_prompt),
        **context_window.coverage_result_fields({"batches_processed": 1, "batches_total": 1, "error": None}),
    }


async def create_integrated_codebook(
    session: AsyncSession,
    user_id: int,
    *,
    codebooks: list[str],
    name: str,
    description: str | None,
    project_id: int | None,
    codes: list[dict],
    assist_runs: list[dict] | None = None,
) -> File:
    """Create a codebook the researcher assembled by reviewing a merge of
    two or more existing codebooks (with or without help from the
    integrate preview assistant).

    Every accepted/copied code in ``codes`` mints a FRESH ``code_uid``/
    ``family_uid`` on the client (see ``lib/codebookEditorState.js``'s
    ``acceptProposal``/``copySourceCode``) -- never a source codebook's
    own uid. This is enforced upstream, not re-checked here, but is worth
    restating: ``_resolve_code_rows`` *accepts* a bare carried-over
    ``code_uid`` (it satisfies the uid-or-is_new rule), so nothing would
    fail if a caller got this wrong -- it would just make
    ``codebook_codes`` rows for a brand-new File collide in identity with
    rows on one of its parents, and the lineage/diff views would then
    misread a 3-way merge as "the same code as" one arbitrarily-
    privileged source. Per-code provenance stays recoverable without any
    new storage: an accepted code's ``code_uid`` lands in this run's
    ``artifact_assists.accepted_refs``, whose ``job_id`` points back at
    the ``integrate_codebook_preview`` job whose ``result.proposals[].sources``
    names the real source codes.

    ``origin=edited`` with null ``model``/``system_prompt``/``prompt_meta``,
    same reasoning as ``create_manual_codebook``: an assist during editing
    is not the claim "a model produced this artifact". Lineage instead
    goes through N ``artifact_edges`` rows (``relation=merged_from``,
    ``role=merge_input``, ``position`` = selection order) -- one per
    source codebook, via ``_materialize_codebook``'s ``parents``.
    """
    source_file_ids = await _resolve_source_codebooks(session, user_id, codebooks)

    code_rows = _resolve_code_rows(codes)
    file_rec, version = await _materialize_codebook(
        session,
        user_id=user_id,
        parents=[
            EdgeSpec(parent_file_id=fid, relation=RELATION_MERGED_FROM, role=ROLE_MERGE_INPUT, position=i)
            for i, fid in enumerate(source_file_ids)
        ],
        name=name,
        description=description,
        project_id=project_id,
        code_rows=code_rows,
        message=f"Integrated from {len(source_file_ids)} codebooks",
    )
    if assist_runs:
        await assist_service.record_assist_runs(
            session,
            user_id=user_id,
            file_id=file_rec.id,
            version_id=version.id,
            stage=ASSIST_STAGE_INTEGRATE,
            source_file_ids=source_file_ids,
            runs=assist_runs,
        )

    await session.commit()
    await session.refresh(file_rec)
    return file_rec
