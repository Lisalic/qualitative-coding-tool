"""Service layer for coding-artifact operations -- backs
backend/app/api/coding_routes.py.

A ``coding`` ``File`` is now a self-contained artifact made of three
parts, all keyed by its own ``file_id``:

1. its own codebook snapshot (``artifact_content`` -- repurposed: it used
   to hold the flattened classification blob, now it holds the codebook
   markdown copied in at Apply Codebook time, via
   ``artifact_content_repo``);
2. its own copy of every sampled post/comment (``submissions``/
   ``comments``, copied in from the source data file via
   ``raw_data_repo.copy_rows_by_id``, read back via
   ``coding_repo.list_rows_with_codes``/``count_rows``); and
3. its coding (``coding_entries``, via ``coding_repo``) -- the *sole*
   source of truth for the classification, including rows the AI left
   uncoded (which now simply have zero ``coding_entries`` rows, rather
   than being omitted from a blob entirely).

This replaces the earlier design where a coding artifact only ever held
the classification blob and borrowed its row text and codebook back from
its parents via ``file_dependencies`` on every read (the old
``get_coded_data``/``_resolve_parent_codebook_text``/
``save_project_coded_data(_duplicate)``, all removed here) -- per
CLAUDE.md's early-prototyping rule, there is no compatibility shim for
coding artifacts created before this change; re-running Apply Codebook
produces a self-contained one.

Apply Codebook (``start_apply_codebook_job``) still samples and codes;
this also adds ``start_recode_items_job``, which re-runs the AI over a
caller-chosen subset of a coding artifact's *own* rows with a
caller-chosen model, replacing only that subset's coding
(``coding_repo.replace_entries_for_items``).
"""

from __future__ import annotations

import json
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.evidence_match import find_quote
from backend.app.core.exceptions import ContextBudgetError, NotFoundError, ValidationAppError
from backend.app.core.item_types import COMMENT, SUBMISSION, qualify_item_id, split_item_id
from backend.app.database import (
    AsyncSessionLocal,
    File,
    FileDependency,
    async_link_file_to_project,
)
from backend.app.external import context_window
from backend.app.jobs.models import Job
from backend.app.jobs.progress import ProgressTracker
from backend.app.jobs.registry import register_handler
from backend.app.jobs.service import enqueue_job
from backend.app.repositories import artifact_content_repo, coding_repo, file_repo, project_repo, raw_data_repo
from backend.app.storage_models import Comment, Submission
from backend.scripts.codebook_apply import classify_posts
from backend.scripts.display_codebook import parse_codebook_to_json

_PARENT_TEXT_TRUNCATE_CHARS = 280

_CODING_FILE_TYPES = ("coding", "coding_comparison")
_CODEBOOK_FILE_TYPES = ("codebook", "codebook_comparison")


async def _read_coding_content(session: AsyncSession, file_id: int) -> str:
    """Text for a ``coding``/``coding_comparison`` file, appropriate to
    its type: a ``coding_comparison``'s ``artifact_content`` markdown is
    unchanged by the coding-artifact overhaul, while a ``coding`` file's
    classification text no longer exists as a stored blob -- it's
    generated on demand from ``coding_entries``, the sole source of truth
    for its coding.
    """
    file_rec = await session.get(File, file_id)
    if file_rec is not None and file_rec.file_type == "coding":
        return await coding_repo.render_coding_text(session, file_id)
    return await artifact_content_repo.read_content(session, file_id) or ""


async def get_coding_comparison(session: AsyncSession, user_id: int, ref: str | None) -> File:
    """Resolve a ``coding_comparison`` file owned by ``user_id`` -- by
    ``ref`` (schemaname, filename, id) if given, otherwise the most
    recently created one. Mirrors ``codebook_service.get_codebook``'s
    lookup shape; a coding_comparison's content is still one
    ``artifact_content`` markdown blob, unchanged by the coding-artifact
    overhaul (which only restructures the plain ``coding`` artifact
    type).
    """
    base = select(File).where(File.file_type == "coding_comparison", File.user_id == user_id)
    file_rec: File | None = None
    if ref:
        result = await session.execute(base.where(File.schemaname == ref))
        file_rec = result.scalar_one_or_none()
        if file_rec is None:
            result = await session.execute(base.where(File.filename == ref))
            file_rec = result.scalar_one_or_none()
        if file_rec is None:
            try:
                fid = int(ref)
            except ValueError:
                fid = None
            if fid is not None:
                result = await session.execute(base.where(File.id == fid))
                file_rec = result.scalar_one_or_none()
    else:
        result = await session.execute(base.order_by(File.created_at.desc(), File.id.desc()).limit(1))
        file_rec = result.scalars().first()

    if file_rec is None:
        raise NotFoundError("No coding comparison file found")
    return file_rec


# ---------------------------------------------------------------------------
# Reading a coding artifact: metadata, paged rows, read-only rendered text
# ---------------------------------------------------------------------------


async def get_coding_artifact(session: AsyncSession, user_id: int, ref: str) -> dict:
    """Metadata for a coding file owned by ``user_id``: the file record,
    its own codebook snapshot text, row/coded counts, and code frequency
    -- everything ``GET /api/coding/{ref}`` needs besides the row page
    itself (``list_coding_rows``, fetched separately so the frontend can
    page/filter/search independently of the artifact header).
    """
    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))
    codebook_text = await artifact_content_repo.read_content(session, file_rec.id) or ""
    total_rows = await coding_repo.count_rows(session, file_rec.id)
    total_coded = await coding_repo.count_rows(session, file_rec.id, only="coded")
    frequency = await coding_repo.code_frequency(session, file_rec.id)
    return {
        "file": file_rec,
        "codebook_text": codebook_text,
        "total_rows": total_rows,
        "total_coded": total_coded,
        "code_frequency": [{"code": code, "count": count} for code, count in frequency],
    }


async def list_coding_rows(
    session: AsyncSession,
    user_id: int,
    ref: str,
    *,
    limit: int = 50,
    offset: int = 0,
    only: str = "all",
    code: str | None = None,
    q: str | None = None,
) -> dict:
    """One page of a coding file's own rows (coded or not), each with its
    codes -- backs ``GET /api/coding/{ref}/rows``.
    """
    file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))
    rows = await coding_repo.list_rows_with_codes(
        session, file_id, limit=limit, offset=offset, only=only, code=code, q=q
    )
    total = await coding_repo.count_rows(session, file_id, only=only, code=code, q=q)
    return {"rows": rows, "total": total}


async def get_coding_text(session: AsyncSession, user_id: int, ref: str) -> str:
    """Read-only canonical POST_ID/CODE/EVIDENCE text for a coding file,
    generated fresh from ``coding_entries`` -- backs the Text View tab
    and ``GET /api/coding/{ref}/text``.
    """
    file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))
    return await coding_repo.render_coding_text(session, file_id)


# ---------------------------------------------------------------------------
# Editing a coding artifact: codebook, rows, metadata
# ---------------------------------------------------------------------------


async def save_coding_codebook(session: AsyncSession, user_id: int, ref: str, content: str) -> File:
    """Overwrite a coding file's own codebook snapshot."""
    if not content or not content.strip():
        raise ValidationAppError("content is required")

    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))
    await artifact_content_repo.write_content(session, file_rec.id, content)
    await session.commit()
    await session.refresh(file_rec)
    return file_rec


async def save_coding_rows(session: AsyncSession, user_id: int, ref: str, rows: list[dict]) -> File:
    """Replace the coding for exactly the rows given -- a manual table
    edit's save, parallel to an AI recode
    (``start_recode_items_job``/``_run_recode_items_job``) using the same
    ``coding_repo.replace_entries_for_items`` primitive.

    ``rows`` is ``[{"item_id": <qualified id>, "entries": [{"code",
    "quote", "start_offset", "end_offset", "notes"}]}]`` -- one entry per
    quote, already shaped and validated by ``CodingEntryIn``
    (min-length/offset-ordering) at the route boundary. An entry with a
    blank ``code`` is dropped (a user clearing a code field), and a row
    with no surviving entries ends up with zero codes rather than being
    left as-is. Unlike an AI coding, a manual entry's ``quote``/offsets
    come straight from the real DOM selection range the frontend computed
    them from (see ``HighlightedContent.jsx``), so there is no separate
    existence check here -- it is trusted the same way a hand-typed value
    always has been in this editor.
    """
    if not rows:
        raise ValidationAppError("rows is required")

    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))

    items = []
    for row in rows:
        row_type, post_id = split_item_id(row["item_id"])
        entries = []
        for entry in row.get("entries") or []:
            code = (entry.get("code") or "").strip()
            if not code:
                continue
            entries.append(
                {
                    "code": code,
                    "quote": entry.get("quote"),
                    "start_offset": entry.get("start_offset"),
                    "end_offset": entry.get("end_offset"),
                    "notes": entry.get("notes"),
                }
            )
        items.append({"row_type": row_type, "post_id": post_id, "entries": entries})

    await coding_repo.replace_entries_for_items(session, file_rec.id, items)
    await session.commit()
    return file_rec


async def update_coding_metadata(
    session: AsyncSession, user_id: int, ref: str, *, display_name: str | None, description: str | None
) -> File:
    """Rename/re-describe a coding file. Both fields optional; a blank
    ``description`` clears it.
    """
    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))
    if display_name:
        file_rec.filename = display_name.strip()
    if description is not None:
        file_rec.description = description.strip() or None
    await session.commit()
    await session.refresh(file_rec)
    return file_rec


# ---------------------------------------------------------------------------
# duplicate_coding
# ---------------------------------------------------------------------------


async def _clone_file_dependencies(
    session: AsyncSession, *, source_file_id: int, target_file_id: int, user_id: int
) -> None:
    """Copy every ``FileDependency`` parent link from ``source_file_id``
    onto ``target_file_id`` (skipping parents not owned by ``user_id``),
    then link ``target_file_id`` to ``source_file_id`` itself as a parent
    too, unless that link was already copied above.
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


async def duplicate_coding(session: AsyncSession, user_id: int, ref: str, *, display_name: str) -> File:
    """Fork a whole coding artifact into a brand-new file: its codebook
    snapshot, its own submissions/comments rows
    (``raw_data_repo.copy_all_rows``), its ``coding_entries``
    (``coding_repo.copy_entries``), its project links, and its
    dependency lineage.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValidationAppError("display_name is required")

    source_file = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))
    codebook_text = await artifact_content_repo.read_content(session, source_file.id) or ""

    new_schema = f"proj_{secrets.token_hex(6)}"
    file_rec = File(
        user_id=user_id,
        filename=display_name,
        schemaname=new_schema,
        file_type="coding",
        systemprompt=source_file.systemprompt,
        userprompt=source_file.userprompt,
        description=source_file.description,
    )
    session.add(file_rec)
    await session.flush()

    await artifact_content_repo.write_content(session, file_rec.id, codebook_text)
    await raw_data_repo.copy_all_rows(session, source_file_id=source_file.id, target_file_id=file_rec.id)
    await coding_repo.copy_entries(session, source_file_id=source_file.id, target_file_id=file_rec.id)

    source_with_projects = await session.execute(
        select(File).where(File.id == source_file.id, File.user_id == user_id).options(selectinload(File.projects))
    )
    source_file_loaded = source_with_projects.scalar_one_or_none()
    for project in (source_file_loaded.projects if source_file_loaded else []):
        await async_link_file_to_project(session, file_rec.id, project.id)

    await _clone_file_dependencies(session, source_file_id=source_file.id, target_file_id=file_rec.id, user_id=user_id)

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


# ---------------------------------------------------------------------------
# start_apply_codebook_job: kickoff + handler
# ---------------------------------------------------------------------------


_EMPTY_VALIDATION_COUNTS = {
    "accepted": 0,
    "rejected_unknown_item": 0,
    "rejected_unknown_code": 0,
    "rejected_quote_not_found": 0,
}


def _codebook_code_names(codebook_text: str) -> dict[str, str]:
    """Map of normalized (casefolded, stripped) code name -> its canonical
    spelling exactly as it appears in ``codebook_text``, parsed with the
    same ``display_codebook.parse_codebook_to_json`` the codebook editor
    already uses. Lets an AI-produced code name through when it matches
    case/whitespace-insensitively, while what gets stored is always the
    codebook's own spelling -- never the model's possibly differently-cased
    echo of it.
    """
    try:
        structure = json.loads(parse_codebook_to_json(codebook_text))
    except Exception:  # noqa: BLE001 - a malformed codebook snapshot just yields no valid codes
        return {}

    names: dict[str, str] = {}
    for family in structure or []:
        for code in family.get("codes") or []:
            name = str(code.get("code_name") or "").strip()
            if name:
                names[name.casefold()] = name
    return names


def _validate_and_resolve_coding_entries(
    raw_entries: list[dict],
    *,
    valid_keys: set[tuple[str, str]],
    codebook_text: str,
    content_by_key: dict[tuple[str, str], str],
) -> tuple[list[dict], dict[str, int]]:
    """The anti-hallucination gate every AI coding passes through before
    it's ever written to ``coding_entries`` -- turns ``classify_posts``'s
    raw ``{item_id, code, quotes}`` entries into rows ready for
    ``coding_repo.bulk_insert_coding_entries``/``replace_entries_for_items``,
    dropping anything that doesn't check out against real data:

    - **item exists**: ``item_id`` (split into ``row_type``/``post_id``)
      must be in ``valid_keys``, the set of items actually sent to the
      model this run -- catches a garbled/invented id.
    - **code exists**: ``code`` must match a code name from the artifact's
      own codebook snapshot (via :func:`_codebook_code_names`, case/
      whitespace-insensitive) -- catches an invented or mis-copied code
      name; the canonical spelling is what gets stored.
    - **quote exists**: each quote must resolve, via
      ``core.evidence_match.find_quote``, against that item's own content
      -- catches invented or misattributed evidence. The *resolved*
      offsets are stored, not a naive ``len(quote)`` from the model's
      copy, so a normalized-match still ends up with exact original
      offsets (see that module's docstring).

    Checks run per-quote, not per-entry: one bad quote in a ``quotes``
    list doesn't reject its siblings, and an unknown item/code rejects
    every quote in that entry (there's nothing left to check them
    against). Returns ``(rows, counts)`` where ``counts`` is
    ``{accepted, rejected_unknown_item, rejected_unknown_code,
    rejected_quote_not_found}`` -- surfaced in the job result so silently
    -dropped work is visible rather than invisible.
    """
    code_names = _codebook_code_names(codebook_text)
    counts = dict(_EMPTY_VALIDATION_COUNTS)
    rows: list[dict] = []

    for entry in raw_entries:
        quotes = entry.get("quotes") or []
        if not quotes:
            continue

        row_type, post_id = split_item_id(entry.get("item_id") or "")
        key = (row_type, post_id)
        if key not in valid_keys:
            counts["rejected_unknown_item"] += len(quotes)
            continue

        canonical_code = code_names.get(str(entry.get("code") or "").strip().casefold())
        if not canonical_code:
            counts["rejected_unknown_code"] += len(quotes)
            continue

        content = content_by_key.get(key) or ""
        for quote in quotes:
            match = find_quote(content, quote)
            if match is None:
                counts["rejected_quote_not_found"] += 1
                continue
            start, end = match
            rows.append(
                {
                    "row_type": row_type,
                    "post_id": post_id,
                    "code": canonical_code,
                    "quote": content[start:end],
                    "start_offset": start,
                    "end_offset": end,
                }
            )
            counts["accepted"] += 1

    return rows, counts


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
    content_scope: str = "both",
) -> Job:
    """Validate and enqueue an ``apply_codebook`` background job.

    Resolves both ``database`` (the raw/filtered data source) and
    ``codebook`` (accepts a ``proj_<hex>`` schema name or a numeric File
    id -- ``ApplyCodebookRequest`` already structurally validates which
    shape it is) to ownership-checked ``file_id``s via
    ``repositories/file_repo.py`` *before* enqueuing.

    ``sample_percentage`` chooses *which* rows the new coding artifact
    contains -- the artifact then copies exactly those rows in and codes
    all of them (no further sampling happens inside the classifier).
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
            "content_scope": content_scope,
        },
        runtime_extra={"api_key": api_key},
    )


def _format_in_reply_to(parent: dict[str, str]) -> str:
    title = (parent.get("title") or "").strip()
    body = (parent.get("selftext") or "").strip()
    if len(body) > _PARENT_TEXT_TRUNCATE_CHARS:
        body = body[:_PARENT_TEXT_TRUNCATE_CHARS].rstrip() + "..."
    if title and body:
        return f"{title} — {body}"
    return title or body


def _assemble_posts_content(
    submissions: list, comments: list, *, parent_context: dict[str, dict[str, str]] | None = None
) -> str:
    """Assemble every sampled submission/comment into one ``POST_ID:``/
    ``TYPE:``/``CONTENT:`` record per item, joined with
    ``context_window.ITEM_SEPARATOR`` (not ``"\\n\\n"`` -- see that
    constant's docstring for why a plain blank-line join tears a
    multi-paragraph item across a batch boundary).

    Each id is qualified with its Reddit-fullname-style type prefix
    (``core/item_types.py::qualify_item_id``) so ``codebook_apply``'s
    classifier -- and, downstream, ``coding_entries.row_type`` -- can tell
    a coded comment apart from a coded post; a comment's record also
    carries an ``IN_REPLY_TO:`` line (its parent post's title/text, from
    ``parent_context``, when that parent is in this file) as context the
    model must never quote as evidence.
    """
    parent_context = parent_context or {}
    records: list[str] = []
    for submission in submissions:
        qualified_id = qualify_item_id(SUBMISSION, submission.id)
        records.append(
            f"POST_ID: {qualified_id}\n"
            "TYPE: post\n"
            f"TITLE: {submission.title or ''}\n"
            f"CONTENT: {submission.selftext or ''}"
        )
    for comment in comments:
        qualified_id = qualify_item_id(COMMENT, comment.id)
        lines = [f"POST_ID: {qualified_id}", "TYPE: comment"]
        parent = parent_context.get(comment.link_id) if comment.link_id else None
        if parent:
            in_reply_to = _format_in_reply_to(parent)
            if in_reply_to:
                lines.append(f"IN_REPLY_TO: {in_reply_to}")
        lines.append(f"CONTENT: {comment.body or ''}")
        records.append("\n".join(lines))
    return context_window.ITEM_SEPARATOR.join(records).strip()


@register_handler("apply_codebook")
async def _run_apply_codebook_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="apply_codebook"``.

    Runs in the background job runner's context (no request-scoped
    session), so it opens its own sessions via the module-level
    ``AsyncSessionLocal`` -- same pattern as
    ``_run_summarize_coding_job``/``data_service._run_filter_data_job``.

    Builds a self-contained coding artifact: the sampled submissions and
    comments are copied into the new file's own ``submissions``/
    ``comments`` rows (``raw_data_repo.copy_rows_by_id``), the codebook
    text is copied into its own ``artifact_content`` as a snapshot, and
    the parsed classification goes into ``coding_entries`` -- no row or
    codebook text is ever borrowed back from a parent file at read time.
    ``FileDependency`` rows still record lineage back to the source data
    file and the codebook file, for traceability, not for content lookup.
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
    content_scope = payload.get("content_scope") or "both"
    include_posts = content_scope in ("both", "posts")
    include_comments = content_scope in ("both", "comments")

    async with AsyncSessionLocal() as session:
        codebook_text = await artifact_content_repo.read_content(session, codebook_file_id)
        if not codebook_text:
            raise ValidationAppError("Cannot apply codebook: codebook not found or empty")

        submissions = (
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
        assembled = _assemble_posts_content(submissions, comments, parent_context=parent_context)
        submission_ids = [s.id for s in submissions]
        comment_ids = [c.id for c in comments]
        content_by_key = {(SUBMISSION, s.id): (s.selftext or "") for s in submissions}
        content_by_key.update({(COMMENT, c.id): (c.body or "") for c in comments})

    valid_keys = set(content_by_key.keys())

    raw_entries, system_prompt, user_prompt, coverage = await classify_posts(
        codebook_text, assembled, methodology, api_key, model, progress=ProgressTracker(job_id)
    )
    coding_entries, validation_counts = _validate_and_resolve_coding_entries(
        raw_entries, valid_keys=valid_keys, codebook_text=codebook_text, content_by_key=content_by_key
    )

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

        await raw_data_repo.copy_rows_by_id(
            session,
            source_file_id=source_file_id,
            target_file_id=file_rec.id,
            submission_ids=submission_ids,
            comment_ids=comment_ids,
        )
        await artifact_content_repo.write_content(session, file_rec.id, codebook_text)
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
        "file": {"id": str(file_id), "schema_name": schema_name, "filename": filename},
        **validation_counts,
        **context_window.coverage_result_fields(coverage),
    }


# ---------------------------------------------------------------------------
# start_recode_items_job: kickoff + handler
# ---------------------------------------------------------------------------


async def start_recode_items_job(
    session: AsyncSession,
    user_id: int,
    *,
    ref: str,
    item_ids: list[str],
    api_key: str,
    model: str | None,
    methodology: str | None,
) -> Job:
    """Validate and enqueue a ``recode_items`` background job: re-run the
    AI classifier over a caller-chosen subset of a coding artifact's own
    rows, with a caller-chosen model, replacing only that subset's
    coding.
    """
    if not api_key:
        raise ValidationAppError("api_key is required")
    if not item_ids:
        raise ValidationAppError("item_ids is required")

    coding_file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="recode_items",
        payload={
            "coding_file_id": coding_file_id,
            "item_ids": item_ids,
            "methodology": methodology or "",
            "model": model,
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("recode_items")
async def _run_recode_items_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="recode_items"``.

    Reads the codebook snapshot and the requested rows from the coding
    artifact's *own* tables (not the original source data file -- a
    coding artifact is self-contained), classifies just those rows with
    the caller's chosen model, and replaces exactly their coding via
    ``coding_repo.replace_entries_for_items`` -- including clearing codes
    from a requested row the model no longer applies any code to.
    """
    coding_file_id = payload["coding_file_id"]
    item_ids: list[str] = payload["item_ids"]
    methodology = payload.get("methodology") or ""
    model = payload.get("model") or ""
    api_key = payload["api_key"]

    requested_keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    submission_ids: set[str] = set()
    comment_ids: set[str] = set()
    for qualified_id in item_ids:
        row_type, post_id = split_item_id(qualified_id)
        key = (row_type, post_id)
        if key in seen:
            continue
        seen.add(key)
        requested_keys.append(key)
        if row_type == SUBMISSION:
            submission_ids.add(post_id)
        else:
            comment_ids.add(post_id)

    async with AsyncSessionLocal() as session:
        codebook_text = await artifact_content_repo.read_content(session, coding_file_id)
        if not codebook_text:
            raise ValidationAppError("Cannot recode: this coding artifact has no codebook snapshot")

        submissions = []
        if submission_ids:
            result = await session.execute(
                select(Submission).where(Submission.file_id == coding_file_id, Submission.id.in_(submission_ids))
            )
            submissions = list(result.scalars().all())

        comments = []
        if comment_ids:
            result = await session.execute(
                select(Comment).where(Comment.file_id == coding_file_id, Comment.id.in_(comment_ids))
            )
            comments = list(result.scalars().all())

        parent_context = await raw_data_repo.parent_post_context_for_comments(session, coding_file_id, comments)
        assembled = _assemble_posts_content(submissions, comments, parent_context=parent_context)
        content_by_key = {(SUBMISSION, s.id): (s.selftext or "") for s in submissions}
        content_by_key.update({(COMMENT, c.id): (c.body or "") for c in comments})

    if not assembled:
        raise ValidationAppError("None of the selected rows were found in this coding artifact")

    raw_entries, _system_prompt, _user_prompt, coverage = await classify_posts(
        codebook_text, assembled, methodology, api_key, model, progress=ProgressTracker(job_id)
    )
    # Restricted to exactly the rows sent this run (not every row the
    # whole coding artifact owns) -- same anti-hallucination gate Apply
    # Codebook uses, see _validate_and_resolve_coding_entries.
    valid_keys = set(content_by_key.keys())
    coding_entries, validation_counts = _validate_and_resolve_coding_entries(
        raw_entries, valid_keys=valid_keys, codebook_text=codebook_text, content_by_key=content_by_key
    )

    entries_by_item: dict[tuple[str, str], list[dict]] = {}
    for entry in coding_entries:
        entries_by_item.setdefault((entry["row_type"], entry["post_id"]), []).append(
            {
                "code": entry["code"],
                "quote": entry["quote"],
                "start_offset": entry["start_offset"],
                "end_offset": entry["end_offset"],
            }
        )

    items_payload = [
        {"row_type": row_type, "post_id": post_id, "entries": entries_by_item.get((row_type, post_id), [])}
        for row_type, post_id in requested_keys
    ]

    async with AsyncSessionLocal() as session:
        await coding_repo.replace_entries_for_items(session, coding_file_id, items_payload)
        await session.commit()

    return {
        "recoded_item_count": len(items_payload),
        **validation_counts,
        **context_window.coverage_result_fields(coverage),
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
    name: str,
    description: str | None = None,
    project_id: int | None = None,
) -> Job:
    """Validate and enqueue a ``compare_codings`` background job.

    Both schemas must resolve, via ``repositories/file_repo.py``, to a
    coding file owned by ``user_id``.
    """
    schema_a = (coding_a or "").strip()
    schema_b = (coding_b or "").strip()
    if not schema_a.startswith("proj_") or not schema_b.startswith("proj_"):
        raise ValidationAppError("schema names must be proj_<id>")
    if not api_key:
        raise ValidationAppError("api_key is required")
    if not name or not name.strip():
        raise ValidationAppError("name is required")

    file_id_a = await file_repo.resolve_file_id(session, schema_a, user_id, file_types=_CODING_FILE_TYPES)
    file_id_b = await file_repo.resolve_file_id(session, schema_b, user_id, file_types=_CODING_FILE_TYPES)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="compare_codings",
        payload={
            "user_id": user_id,
            "file_id_a": file_id_a,
            "file_id_b": file_id_b,
            "model": model,
            "prompt": prompt or "",
            "name": name,
            "description": description,
            "project_id": project_id,
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("compare_codings")
async def _run_compare_codings_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="compare_codings"``.

    Persists the comparison as a ``File`` (``file_type="coding_comparison"``).
    ``FileDependency`` rows link the new file to BOTH source codings.
    """
    from backend.scripts import summarize_coding as summarize_coding_module
    from backend.scripts.codebook_generator import MODEL_3
    from backend.scripts.codebook_generator import get_client as codebook_get_client

    user_id = payload["user_id"]
    file_id_a = payload["file_id_a"]
    file_id_b = payload["file_id_b"]
    model = payload.get("model")
    prompt = payload.get("prompt", "")
    api_key = payload["api_key"]
    name = payload.get("name")
    description = payload.get("description")
    project_id = payload.get("project_id")

    async with AsyncSessionLocal() as session:
        file_a = await session.get(File, file_id_a)
        file_b = await session.get(File, file_id_b)
        text_a = await _read_coding_content(session, file_id_a)
        text_b = await _read_coding_content(session, file_id_b)

    if not text_a and not text_b:
        raise ValidationAppError("No content found in either coding")

    name_a = (file_a.filename if file_a else None) or "Coding A"
    name_b = (file_b.filename if file_b else None) or "Coding B"

    system_prompt = (
        "You are an expert qualitative researcher. Compare the two provided coded datasets.\n"
        "Provide a clear, structured comparison including:\n"
        "- Major overlaps and divergences in coding decisions\n"
        "- Instances where codes appear inconsistent or misapplied\n"
        "- Suggestions for reconciliation or re-labeling\n"
        "- An overall recommendation and confidence level.\n"
        f"Refer to the coded datasets by their names, \"{name_a}\" and \"{name_b}\", "
        "not as \"Coding A\"/\"Coding B\".\n"
        "Return the full comparison in a markdown format."
    )
    chosen_model = model or MODEL_3

    def _compare_user_prompt(body_a: str, body_b: str, *, aggregated: bool) -> str:
        note = (
            " Each coding is shown as per-code counts with sampled evidence, not the full coded text."
            if aggregated
            else ""
        )
        return (
            f'Coding "{name_a}": {body_a} Coding "{name_b}": {body_b} '
            f"Please compare them in detail.{note} Additional instructions: {prompt}"
        )

    def _fits(candidate: str) -> bool:
        return context_window.prompt_fits(
            chosen_model,
            prompt_chars=len(system_prompt) + len(candidate),
            output_reserve_tokens=context_window.BOUNDED_OUTPUT_TOKENS,
        )

    user_prompt = _compare_user_prompt(text_a, text_b, aggregated=False)
    if not _fits(user_prompt):
        # The raw codings overflow the window (no batching -- a comparison
        # is inherently over the whole corpus). Compact each side to
        # per-code counts + sampled evidence, the same SQL aggregation
        # summarize uses: far smaller, and a GROUP BY COUNT(*) beats an LLM
        # eyeballing frequency from two walls of text. A side with no
        # structured coding_entries rows (a coding_comparison, which has
        # none) falls back to its raw text.
        async with AsyncSessionLocal() as session:
            summaries_a = await coding_repo.code_summary_with_samples(session, file_id_a)
            summaries_b = await coding_repo.code_summary_with_samples(session, file_id_b)

        agg_a = summarize_coding_module.build_aggregated_coding_data(summaries_a) if summaries_a else text_a
        agg_b = summarize_coding_module.build_aggregated_coding_data(summaries_b) if summaries_b else text_b
        user_prompt = _compare_user_prompt(agg_a, agg_b, aggregated=True)

        if not _fits(user_prompt):
            raise ContextBudgetError(
                f"These two codings are too large to compare with {chosen_model}, even after "
                "summarizing each to per-code counts. Choose a larger-context model."
            )

    comparison = await codebook_get_client(system_prompt, user_prompt, api_key, chosen_model)

    final_description = (description or "").strip() if description is not None else None
    if final_description == "":
        final_description = None

    async with AsyncSessionLocal() as session:
        new_schema = f"cmp_{secrets.token_hex(6)}"
        file_rec = File(
            user_id=user_id,
            filename=name,
            schemaname=new_schema,
            file_type="coding_comparison",
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


# ---------------------------------------------------------------------------
# summarize_coding: kickoff + handler
# ---------------------------------------------------------------------------


async def start_summarize_coding_job(
    session: AsyncSession,
    user_id: int,
    *,
    coding: str,
    api_key: str,
    model: str | None,
    prompt: str,
    name: str,
    description: str | None = None,
    project_id: int | None = None,
) -> Job:
    """Validate and enqueue a ``summarize_coding`` background job."""
    schema = (coding or "").strip()
    if not schema.startswith("proj_"):
        raise ValidationAppError("schema name must be proj_<id>")

    if not api_key:
        raise ValidationAppError("api_key is required")

    if not name or not name.strip():
        raise ValidationAppError("name is required")

    source_file_id = await file_repo.resolve_file_id(session, schema, user_id, file_types=_CODING_FILE_TYPES)

    return await enqueue_job(
        session,
        user_id=user_id,
        job_type="summarize_coding",
        payload={
            "user_id": user_id,
            "schema": schema,
            "prompt": prompt,
            "model": model,
            "source_file_id": source_file_id,
            "name": name,
            "description": description,
            "project_id": project_id,
        },
        runtime_extra={"api_key": api_key},
    )


@register_handler("summarize_coding")
async def _run_summarize_coding_job(job_id: int, payload: dict) -> dict:
    """Handler for ``job_type="summarize_coding"``.

    Builds the LLM's input from ``coding_repo.code_summary_with_samples``
    (exact per-code counts plus a capped evidence sample) -- orders of
    magnitude smaller than the raw text for a large dataset, and more
    accurate (`GROUP BY COUNT(*)` vs. an LLM eyeballing frequency from a
    wall of text). ``coding_entries`` is the sole source of truth for a
    coding artifact's classification, so there is no separate blob to
    fall back to; a coding artifact with literally zero coded rows fails
    with a clear error instead.
    """
    from backend.scripts.summarize_coding import summarize_coding as summarize_coding_function
    from backend.scripts import summarize_coding as summarize_coding_module

    user_id = payload["user_id"]
    prompt = payload.get("prompt", "")
    model = payload.get("model")
    api_key = payload["api_key"]
    source_file_id = payload["source_file_id"]
    name = payload.get("name")
    description = payload.get("description")
    project_id = payload.get("project_id")

    async with AsyncSessionLocal() as session:
        code_summaries = await coding_repo.code_summary_with_samples(session, source_file_id)

    if not code_summaries:
        raise ValidationAppError("No coded content found in this coding artifact")

    coding_data = summarize_coding_module.build_aggregated_coding_data(code_summaries)

    summary, coverage = await summarize_coding_function(coding_data, prompt, api_key, model, progress=ProgressTracker(job_id))

    final_description = (description or "").strip() if description is not None else None
    if final_description == "":
        final_description = None

    async with AsyncSessionLocal() as session:
        new_schema = f"sum_{secrets.token_hex(6)}"
        file_rec = File(
            user_id=user_id,
            filename=name,
            schemaname=new_schema,
            file_type="summary",
            description=final_description,
        )
        session.add(file_rec)
        await session.flush()

        session.add(FileDependency(child_file_id=file_rec.id, parent_file_id=source_file_id))
        await artifact_content_repo.write_content(session, file_rec.id, summary)

        if project_id is not None:
            project = await project_repo.get_owned_project(session, project_id, user_id)
            await async_link_file_to_project(session, file_rec.id, project.id)

        await session.commit()
        file_id, schema_name, filename = file_rec.id, file_rec.schemaname, file_rec.filename

    return {
        "summary": summary,
        "file": {"id": str(file_id), "schema_name": schema_name, "filename": filename},
        **context_window.coverage_result_fields(coverage),
    }
