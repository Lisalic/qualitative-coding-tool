"""Service layer for coding-artifact operations -- backs
backend/app/api/coding_routes.py.

A ``coding`` ``File`` is now a self-contained artifact made of three
parts, all keyed by its own ``file_id``:

1. its own codebook snapshot (structured ``codebook_codes`` rows on its
   own ``artifact_versions`` v1, copied in at Apply Codebook time via
   ``version_service.commit_codebook_version``);
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

Coding has one entry point, the coding editor: ``create_manual_coding``
starts a coding artifact with every row uncoded, via
``_materialize_coding_artifact`` -- the coding counterpart of
``data_service._materialize_filtered_schema``. ``start_recode_items_job``
re-runs the AI over a caller-chosen subset of a coding artifact's *own*
rows with a caller-chosen model and returns the classification as
reviewable proposals -- it does not itself write to ``coding_entries``.
``save_coding_revision`` is the single write path for a coding artifact's
whole editing session (codebook edits, manual row tags, and/or accepted
recode proposals), committing at most one new ``artifact_versions`` row
per save via ``coding_repo.replace_entries_for_items``.
"""

from __future__ import annotations

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
    async_link_file_to_project,
)
from backend.app.external import context_window
from backend.app.jobs.models import Job
from backend.app.jobs.progress import ProgressTracker
from backend.app.jobs.registry import register_handler
from backend.app.jobs.service import enqueue_job
from backend.app.repositories import coding_repo, file_repo, memo_repo, project_repo, raw_data_repo, version_repo
from backend.app.services import assist_service, codebook_service, version_service
from backend.app.services.version_service import EdgeSpec
from backend.app.storage_models import CODER_AI, CODER_HUMAN, Comment, Submission
from backend.app.versioning_models import (
    ASSIST_STAGE_CODING,
    ORIGIN_EDITED,
    ORIGIN_FORKED,
    ORIGIN_GENERATED,
    ORIGIN_IMPORTED,
    RELATION_COMPARED,
    RELATION_DERIVED_FROM,
    ROLE_CODEBOOK,
    ROLE_SIDE_A,
    ROLE_SIDE_B,
    ROLE_SOURCE_DATA,
)
from backend.scripts.codebook_apply import classify_posts

_PARENT_TEXT_TRUNCATE_CHARS = 280

_CODING_FILE_TYPES = ("coding", "coding_comparison")
_CODEBOOK_FILE_TYPES = ("codebook", "codebook_comparison")


async def _read_coding_content(session: AsyncSession, file_id: int) -> str:
    """Text for a ``coding``/``coding_comparison`` file, appropriate to
    its type: a ``coding_comparison``'s content is a blob version
    (``version_service.read_blob``), while a ``coding`` file's
    classification text no longer exists as a stored blob -- it's
    generated on demand from ``coding_entries``, the sole source of truth
    for its coding.
    """
    file_rec = await session.get(File, file_id)
    if file_rec is not None and file_rec.file_type == "coding":
        return await coding_repo.render_coding_text(session, file_id)
    return await version_service.read_blob(session, file_id) or ""


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
        # Lowest-id match, not scalar_one_or_none -- see
        # `repositories/file_repo.py::_lookup_file` for why a
        # non-unique `filename` must not raise here.
        for condition in (File.schemaname == ref, File.filename == ref):
            result = await session.execute(base.where(condition).order_by(File.id).limit(1))
            file_rec = result.scalars().first()
            if file_rec is not None:
                break
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


async def get_coding_artifact(
    session: AsyncSession, user_id: int, ref: str, *, version_no: int | None = None
) -> dict:
    """Metadata for a coding file owned by ``user_id``: the file record,
    its own codebook snapshot as structured code rows, row/coded counts,
    and code frequency -- everything ``GET /api/coding/{ref}`` needs
    besides the row page itself (``list_coding_rows``, fetched separately
    so the frontend can page/filter/search independently of the artifact
    header).

    ``version_no``, when given, reads the codebook snapshot and coding
    counts/frequency AS OF that version instead of live -- backs "view a
    previous version" in the version-history UI. ``total_rows`` is left
    unconditional even then: it counts the coding artifact's own copied
    submissions/comments, which (unlike ``coding_entries``) never change
    after Apply Codebook -- there is no delete/move UI for a coding
    file's rows -- so there is nothing for a version to be "as of" there.
    ``total_coded``/``code_frequency`` are derived from
    ``coding_repo.entries_as_of`` (the same as-of primitive
    ``version_service.diff_coding`` uses) rather than from the live-only
    ``count_rows``/``code_frequency``, so every field in the response is
    consistently as-of the same version.
    """
    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))
    codes = await version_service.read_codes(session, file_rec.id, version_no=version_no)
    total_rows = await coding_repo.count_rows(session, file_rec.id)
    if version_no is None:
        total_coded = await coding_repo.count_rows(session, file_rec.id, only="coded")
        frequency = await coding_repo.code_frequency(session, file_rec.id)
    else:
        entries = await coding_repo.entries_as_of(session, file_rec.id, version_no)
        total_coded = len({(e.row_type, e.post_id) for e in entries})
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry.code] = counts.get(entry.code, 0) + 1
        frequency = sorted(counts.items(), key=lambda kv: -kv[1])
    return {
        "file": file_rec,
        "codes": codes,
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
    version_no: int | None = None,
) -> dict:
    """One page of a coding file's own rows (coded or not), each with its
    codes -- backs ``GET /api/coding/{ref}/rows``. ``version_no`` reads
    the coding entries as they existed at that historical version.
    """
    file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))
    rows = await coding_repo.list_rows_with_codes(
        session, file_id, limit=limit, offset=offset, only=only, code=code, q=q,
        version_no=version_no,
    )
    total = await coding_repo.count_rows(
        session, file_id, only=only, code=code, q=q, version_no=version_no
    )
    return {"rows": rows, "total": total}


async def get_coding_text(
    session: AsyncSession, user_id: int, ref: str, *, version_no: int | None = None
) -> str:
    """Read-only canonical POST_ID/CODE/EVIDENCE text for a coding file,
    generated fresh from ``coding_entries`` -- backs the Text View tab
    and ``GET /api/coding/{ref}/text``. ``version_no``, when given,
    renders a pinned text export instead of the live version -- see
    ``coding_repo.render_coding_text``.
    """
    file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))
    return await coding_repo.render_coding_text(session, file_id, version_no=version_no)


async def list_quote_bank(
    session: AsyncSession,
    user_id: int,
    ref: str,
    *,
    code: str | None = None,
    coder: str | None = None,
    q: str | None = None,
    starred_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    version_no: int | None = None,
) -> dict:
    """Paginated quote bank for a coding file owned by user_id."""
    file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))
    quotes, total = await coding_repo.list_quote_bank(
        session,
        file_id,
        user_id,
        code=code,
        coder=coder,
        q=q,
        starred_only=starred_only,
        limit=limit,
        offset=offset,
        version_no=version_no,
    )
    return {"quotes": quotes, "total": total}


async def set_quote_star(
    session: AsyncSession,
    user_id: int,
    ref: str,
    entry_id: int,
    starred: bool,
) -> bool:
    """Star or unstar a quote entry for the calling user."""
    file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))
    result = await coding_repo.set_quote_star(
        session,
        user_id=user_id,
        file_id=file_id,
        entry_id=entry_id,
        starred=starred,
    )
    await session.commit()
    return result


async def update_quote_note(
    session: AsyncSession,
    user_id: int,
    ref: str,
    entry_id: int,
    notes: str | None,
) -> tuple[int, str | None]:
    """Set the note on one live quote as a new coding version.

    A note is part of the coding's content, so it is written through the
    same SCD-2 path as any row edit (``replace_entries_for_items`` over
    the quote's item) rather than updated in place -- a read AS OF an
    earlier version keeps showing the note that version had. Returns the
    re-inserted entry's new id alongside the cleaned note.
    """
    file_id = await file_repo.resolve_file_id(session, ref, user_id, file_types=("coding",))
    entry = await coding_repo.get_entry_for_file(session, file_id, entry_id)
    if entry.valid_to is not None:
        raise ValidationAppError("Only a live quote can be annotated")

    cleaned = notes.strip() if notes and notes.strip() else None
    if cleaned == entry.notes:
        return entry.id, cleaned

    target = (entry.code_uid, entry.start_offset, entry.end_offset)
    siblings = await coding_repo.live_entries_for_item(session, file_id, entry.row_type, entry.post_id)
    entries = [
        {
            "code": e.code,
            "code_uid": e.code_uid,
            "quote": e.quote,
            "start_offset": e.start_offset,
            "end_offset": e.end_offset,
            "notes": cleaned if e.id == entry.id else e.notes,
            "coder": e.coder,
            "coder_model": e.coder_model,
        }
        for e in siblings
    ]
    row_type, post_id = entry.row_type, entry.post_id

    version = await version_service.commit_coding_version(
        session, file_id=file_id, author_user_id=user_id, origin=ORIGIN_EDITED,
    )
    await coding_repo.replace_entries_for_items(
        session,
        file_id,
        [{"row_type": row_type, "post_id": post_id, "entries": entries}],
        version_no=version.version_no,
    )
    await session.flush()

    new_id = next(
        e.id
        for e in await coding_repo.live_entries_for_item(session, file_id, row_type, post_id)
        if (e.code_uid, e.start_offset, e.end_offset) == target
    )
    await session.commit()
    return new_id, cleaned


# ---------------------------------------------------------------------------
# Editing a coding artifact: codebook, rows, metadata
# ---------------------------------------------------------------------------


async def save_coding_revision(
    session: AsyncSession,
    user_id: int,
    ref: str,
    *,
    codes: list[dict] | None,
    rows: list[dict] | None,
    assist_runs: list[dict] | None = None,
) -> File:
    """Save a coding artifact's whole editing session -- an updated
    codebook snapshot, updated row coding (manual tags and/or reviewed AI
    recode proposals -- see ``_run_recode_items_job``, which no longer
    commits on its own), or both -- as **at most one** new
    ``artifact_versions`` row. Replaces the old separate
    ``save_coding_codebook``/``save_coding_rows``, which each minted
    their own version even when a researcher changed both in one sitting.

    No ``model``/``job_id`` params any more -- that used to be the one
    place an AI assist leaked onto this ``origin=ORIGIN_EDITED`` version's
    ``model`` field (see ``versioning_models.ArtifactAssist`` for why that
    is exactly what the C2 design forbids). ``assist_runs`` is the
    replacement channel (recorded once the version is settled, below);
    each row entry's own ``coder``/``assist_job_id`` (validated via
    ``assist_service.resolve_ai_coder_model``) is the B1 per-quote
    counterpart.

    Ordering matters and is the correctness crux here:

    1. If ``codes`` is given, commit the codebook version FIRST (see
       ``codebook_service._resolve_code_rows`` for the identity
       enforcement this shares with a plain codebook save).
       ``commit_codebook_version`` no-op-suppresses when the codes are
       byte-identical to head, returning the existing head instead of a
       new version -- detected by comparing ids against the pre-save
       head, so a rows-only change still gets its own version next.
    2. If no new version was minted yet and ``rows`` is given, commit a
       coding version via ``commit_coding_version``.
    3. If neither step produced a new version, there is nothing to save.
    4. Only once a version number is settled do we resolve each row
       entry's ``code_uid`` against the (possibly just-updated) codebook
       snapshot -- so a code created in this very save resolves, and a
       code removed in this very save is rejected on any row still
       trying to use it.
    5. ``coding_repo.replace_entries_for_items`` is stamped with that
       version's number -- never a number that wasn't just minted, since
       its first step deletes rows born at that exact ``version_no``
       (see its docstring); reusing a no-op-suppressed head would delete
       the *previous* sealed version's entries.
    6. Any ``code_uid`` removed from the codebook in this save that
       ``rows`` didn't itself touch is closed the same way a
       codebook-only save does, so "every live entry's code_uid resolves
       to a code in the current snapshot" stays true either way.
    """
    if not codes and not rows:
        raise ValidationAppError("codes or rows is required")

    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))

    head_before = await version_repo.head_version(session, file_rec.id)
    before_uids = {c.code_uid for c in await version_service.read_codes(session, file_rec.id)}

    version = None
    after_uids = before_uids
    if codes:
        resolved_codes = codebook_service._resolve_code_rows(codes)
        codebook_version = await version_service.commit_codebook_version(
            session,
            file_id=file_rec.id,
            author_user_id=user_id,
            origin=ORIGIN_EDITED,
            codes=resolved_codes,
        )
        after_uids = {r["code_uid"] for r in resolved_codes}
        if head_before is None or codebook_version.id != head_before.id:
            version = codebook_version

    if version is None and rows:
        version = await version_service.commit_coding_version(
            session, file_id=file_rec.id, author_user_id=user_id, origin=ORIGIN_EDITED,
        )

    if version is None:
        # Codebook was submitted but hashed identical to head, and there
        # were no rows to save either -- nothing changed.
        return file_rec

    if rows:
        current_codes = await version_service.read_codes(session, file_rec.id)
        name_by_uid = {c.code_uid: c.name for c in current_codes}
        # Cache: several entries in the same save routinely share one
        # recode job_id, and each lookup validates the job (a DB read) --
        # see assist_service.resolve_ai_coder_model.
        model_by_assist_job_id: dict[int, str | None] = {}

        items = []
        for row in rows:
            row_type, post_id = split_item_id(row["item_id"])
            entries = []
            for entry in row.get("entries") or []:
                code_uid = (entry.get("code_uid") or "").strip()
                if not code_uid:
                    continue
                code_name = name_by_uid.get(code_uid)
                if code_name is None:
                    raise ValidationAppError(
                        f"code_uid {code_uid!r} is not in this artifact's current codebook snapshot"
                    )
                coder = entry.get("coder") or CODER_HUMAN
                coder_model = None
                if coder == CODER_AI:
                    assist_job_id = entry.get("assist_job_id")
                    if assist_job_id not in model_by_assist_job_id:
                        model_by_assist_job_id[assist_job_id] = await assist_service.resolve_ai_coder_model(
                            session, user_id=user_id, file_id=file_rec.id, job_id=assist_job_id
                        )
                    coder_model = model_by_assist_job_id[assist_job_id]
                entries.append(
                    {
                        "code": code_name,
                        "code_uid": code_uid,
                        "quote": entry.get("quote"),
                        "start_offset": entry.get("start_offset"),
                        "end_offset": entry.get("end_offset"),
                        "notes": entry.get("notes"),
                        "coder": coder,
                        "coder_model": coder_model,
                    }
                )
            items.append({"row_type": row_type, "post_id": post_id, "entries": entries})

        await coding_repo.replace_entries_for_items(session, file_rec.id, items, version_no=version.version_no)

    if codes:
        for removed_uid in before_uids - after_uids:
            await coding_repo.close_entries_for_code_uid(
                session, file_rec.id, removed_uid, version_no=version.version_no
            )

    if assist_runs:
        await assist_service.record_assist_runs(
            session,
            user_id=user_id,
            file_id=file_rec.id,
            version_id=version.id,
            stage=ASSIST_STAGE_CODING,
            runs=assist_runs,
        )

    await session.commit()
    await session.refresh(file_rec)
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


async def duplicate_coding(
    session: AsyncSession, user_id: int, ref: str, *, display_name: str, from_version_no: int | None = None
) -> File:
    """Fork a whole coding artifact into a brand-new file: its codebook
    snapshot (codes copied with ``code_uid``/``family_uid`` preserved,
    starting the fork's own history at v1 -- see
    ``version_service.fork_lineage``'s docstring for why), its own
    submissions/comments rows (``raw_data_repo.copy_all_rows``), its
    ``coding_entries`` (``coding_repo.copy_entries``), its project links,
    and its lineage (``version_service.fork_lineage``).

    ``from_version_no=None`` (the default) forks from the current head.
    Passing a version number instead forks from that point in history --
    the codebook snapshot AND the coding_entries live set are both read
    as of that version, not head -- which is how you "undo" a later edit
    without destroying it: the original artifact's history is untouched,
    a new one starts from the old state. This replaces the old
    forward-commit ``revert``, which used to rewrite the SAME artifact's
    history in place.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValidationAppError("display_name is required")

    source_file = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))
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
        file_type="coding",
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
    await raw_data_repo.copy_all_rows(session, source_file_id=source_file.id, target_file_id=file_rec.id)
    await memo_repo.copy_all_memos(session, source_file_id=source_file.id, target_file_id=file_rec.id)
    await coding_repo.copy_entries(
        session, source_file_id=source_file.id, target_file_id=file_rec.id, as_of_version_no=from_version_no
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
# create_manual_coding and the shared helpers/materializer it uses
# ---------------------------------------------------------------------------


_EMPTY_VALIDATION_COUNTS = {
    "accepted": 0,
    "rejected_unknown_item": 0,
    "rejected_unknown_code": 0,
    "rejected_quote_not_found": 0,
}


def _codebook_code_lookup(codes) -> dict[str, tuple[str, str]]:
    """Map of normalized (casefolded, stripped) code name -> ``(canonical
    spelling, code_uid)``, built from a codebook's actual
    ``CodebookCode`` rows rather than re-parsing markdown. Lets an
    AI-produced code name through when it matches case/whitespace-
    insensitively, while what gets stored is always the codebook's own
    spelling and its stable ``code_uid`` -- never the model's possibly
    differently-cased echo of the name, and never a name-only reference
    that a later rename would orphan.
    """
    lookup: dict[str, tuple[str, str]] = {}
    for code in codes:
        name = (code.name or "").strip()
        if name:
            lookup[name.casefold()] = (name, code.code_uid)
    return lookup


def _validate_and_resolve_coding_entries(
    raw_entries: list[dict],
    *,
    valid_keys: set[tuple[str, str]],
    codes,
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
      own codebook snapshot (via :func:`_codebook_code_lookup`, case/
      whitespace-insensitive) -- catches an invented or mis-copied code
      name; the canonical spelling AND its stable ``code_uid`` are what
      get stored.
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
    code_lookup = _codebook_code_lookup(codes)
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

        resolved = code_lookup.get(str(entry.get("code") or "").strip().casefold())
        if not resolved:
            counts["rejected_unknown_code"] += len(quotes)
            continue
        canonical_code, code_uid = resolved

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
                    "code_uid": code_uid,
                    "quote": content[start:end],
                    "start_offset": start,
                    "end_offset": end,
                }
            )
            counts["accepted"] += 1

    return rows, counts



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


async def _read_codebook_as_parent(session: AsyncSession, codebook_file_id: int) -> tuple[str, list]:
    """Seal the codebook's head, then read its markdown + code rows.

    Read-as-parent: sealing first is what lets the new coding artifact's
    edge pin exactly which codebook revision was snapshotted -- the one
    genuine cross-file content read in this codebase (see
    ``version_service.py``'s module docstring). Shared by the AI apply
    path and the hand-started path so both pin the same way.
    """
    await version_service.pin_parent(session, codebook_file_id)
    codebook_text = await version_service.read_codebook_markdown(session, codebook_file_id)
    codebook_codes = await version_service.read_codes(session, codebook_file_id)
    if not codebook_text:
        raise ValidationAppError("Cannot apply codebook: codebook not found or empty")
    return codebook_text, codebook_codes


async def _sample_rows_for_coding(
    session: AsyncSession,
    source_file_id: int,
    sample_percentage: float,
    content_scope: str,
) -> tuple[list, list]:
    """Choose which of a source file's rows a new coding artifact will own.

    ``sample_percentage`` chooses *which* rows the artifact contains --
    the artifact then copies exactly those in; no further sampling happens
    downstream.
    """
    include_posts = content_scope in ("both", "posts")
    include_comments = content_scope in ("both", "comments")
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
    return submissions, comments


async def _materialize_coding_artifact(
    session: AsyncSession,
    *,
    user_id: int,
    source_file_id: int,
    codebook_file_id: int,
    codebook_codes: list,
    display_name: str,
    description: str | None,
    project_id: int | None,
    submission_ids: list[str],
    comment_ids: list[str],
    message: str | None = None,
) -> File:
    """Build a self-contained ``coding`` artifact: its own copy of the
    chosen rows (and their memos), its own codebook snapshot, and zero
    coding -- committed as that file's v1.

    The coding editor's only way to create a coding artifact
    (``create_manual_coding``). ``bulk_insert_coding_entries`` is a
    no-op on an empty list, leaving a valid v1 with a full codebook
    snapshot, its own rows, and zero live entries -- which
    ``list_coding_rows`` already renders as uncoded, and which the
    ViewCoding workspace then codes row by row (or via
    ``POST /api/coding/{ref}/recode``).

    Always ``origin=ORIGIN_EDITED`` with no LLM provenance -- see
    ``data_service.create_manual_filtered_data`` for why that claim is
    kept accurate even when the AI recode assistant helped.

    Does not commit -- the caller owns the transaction boundary.
    """
    final_description = (description or "").strip() if description is not None else None
    if final_description == "":
        final_description = None

    new_schema = f"proj_{secrets.token_hex(6)}"
    file_rec = File(
        user_id=user_id,
        filename=display_name,
        schemaname=new_schema,
        file_type="coding",
        description=final_description,
    )
    # The source data file was read earlier in this call and its rows
    # are copied in below -- if a concurrent request deleted it in
    # between, the copy would silently produce zero rows, leaving a
    # coding artifact whose entries point at rows it doesn't have. Fail
    # instead. (A deleted *codebook* is not fatal the same way: its codes
    # were already read into `codebook_codes` by the caller, so the
    # snapshot is complete; only its lineage edge is lost, which
    # `version_service.link_parents` drops on its own.)
    await file_repo.require_existing_file_ids(session, {source_file_id})

    session.add(file_rec)
    await session.flush()

    await raw_data_repo.copy_rows_by_id(
        session,
        source_file_id=source_file_id,
        target_file_id=file_rec.id,
        submission_ids=submission_ids,
        comment_ids=comment_ids,
    )
    # Memos follow their rows, so a note written while filtering is still
    # there when the same post is read in the coding workspace.
    await memo_repo.copy_memos_by_id(
        session,
        source_file_id=source_file_id,
        target_file_id=file_rec.id,
        submission_ids=submission_ids,
        comment_ids=comment_ids,
    )

    # The new coding artifact's OWN codebook snapshot -- codes copied
    # verbatim (code_uid/family_uid preserved) from the applied codebook,
    # so coding_entries.code_uid (written just below) resolves against it
    # immediately.
    snapshot_rows = [
        {
            "code_uid": c.code_uid, "family_uid": c.family_uid, "family_name": c.family_name,
            "name": c.name, "body": c.body, "definition": c.definition, "inclusion": c.inclusion,
            "exclusion": c.exclusion, "keywords": c.keywords, "example": c.example, "position": c.position,
        }
        for c in codebook_codes
    ]
    # ONE version, not two: a coding file's codebook snapshot and its
    # coding_entries share the SAME artifact_versions.version_no (the
    # SCD-2 ranges on coding_entries are keyed against it) -- calling
    # commit_codebook_version then commit_coding_version separately would
    # mint two different version numbers for what is really one atomic
    # commit, leaving coding_entries.valid_from pointing at a version with
    # zero codebook_codes rows. So the codebook commit carries job_id/
    # model/prompts too, and its version_no is what entries are stamped
    # with.
    codebook_version = await version_service.commit_codebook_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin=ORIGIN_EDITED, codes=snapshot_rows,
        message=message,
    )
    await coding_repo.bulk_insert_coding_entries(
        session, file_rec.id, [], version_no=codebook_version.version_no
    )

    await version_service.link_parents(
        session, file_rec.id,
        [
            EdgeSpec(parent_file_id=source_file_id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA),
            EdgeSpec(parent_file_id=codebook_file_id, relation=RELATION_DERIVED_FROM, role=ROLE_CODEBOOK),
        ],
    )

    # Matches the original handler's behavior exactly: link the new coding
    # file to the *source* file's projects, but only when the source is
    # itself a raw_data file (not filtered_data) -- a pre-existing
    # narrowing this stage doesn't change.
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

    return file_rec



async def create_manual_coding(
    session: AsyncSession,
    user_id: int,
    *,
    database: str,
    codebook: str,
    report_name: str,
    description: str | None,
    project_id: int | None,
    content_scope: str = "both",
    sample_percentage: float = 100.0,
    post_ids: list[str] | None = None,
    comment_ids: list[str] | None = None,
) -> tuple[File, dict[str, int]]:
    """Start a coding artifact by hand: copy the chosen rows in and
    snapshot the codebook, but code nothing.

    The coding stage's only entry point. Creates the artifact via
    ``_materialize_coding_artifact`` with no classification, so the
    researcher lands in the ViewCoding workspace with every row uncoded
    and tags them themselves, with ``POST /api/coding/{ref}/recode`` as an
    opt-in assistant on whichever rows they choose.

    ``origin=edited`` with null ``model``/``system_prompt``/``prompt_meta``
    is deliberate and matches ``data_service.create_manual_filtered_data``:
    no model produced this artifact.

    Row selection: explicit ``post_ids``/``comment_ids`` win when either is
    non-empty (letting a caller hand through an exact row set); otherwise
    the rows are sampled by ``sample_percentage`` within ``content_scope``,
    exactly as the AI path samples them.
    """
    if not (report_name or "").strip():
        raise ValidationAppError("report_name is required")

    source_file_id = await file_repo.resolve_file_id(session, database, user_id)
    codebook_file_id = await file_repo.resolve_file_id(
        session, codebook, user_id, file_types=_CODEBOOK_FILE_TYPES
    )

    _codebook_text, codebook_codes = await _read_codebook_as_parent(session, codebook_file_id)

    post_ids = list(post_ids or [])
    comment_ids = list(comment_ids or [])
    if not post_ids and not comment_ids:
        submissions, comments = await _sample_rows_for_coding(
            session, source_file_id, sample_percentage, content_scope
        )
        post_ids = [s.id for s in submissions]
        comment_ids = [c.id for c in comments]

    if not post_ids and not comment_ids:
        raise ValidationAppError(
            "No records were sampled from the selected database. Increase sample size above 0%."
        )

    total = len(post_ids) + len(comment_ids)
    file_rec = await _materialize_coding_artifact(
        session,
        user_id=user_id,
        source_file_id=source_file_id,
        codebook_file_id=codebook_file_id,
        codebook_codes=codebook_codes,
        display_name=report_name.strip(),
        description=description,
        project_id=project_id,
        submission_ids=post_ids,
        comment_ids=comment_ids,
        message=f"Started by hand from {total} rows, uncoded",
    )

    await session.commit()
    await session.refresh(file_rec)
    return file_rec, {"submissions": len(post_ids), "comments": len(comment_ids)}


# ---------------------------------------------------------------------------
# start_recode_items_job: kickoff + handler
# ---------------------------------------------------------------------------


_RECODE_MAX_ITEMS = 500


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
    rows, with a caller-chosen model. The result is a set of *proposals*
    the caller reviews and stages into their own editing session (see
    ``_run_recode_items_job``) -- nothing is written to ``coding_entries``
    from this job any more.
    """
    if not api_key:
        raise ValidationAppError("api_key is required")
    if not item_ids:
        raise ValidationAppError("item_ids is required")
    if len(item_ids) > _RECODE_MAX_ITEMS:
        raise ValidationAppError(f"Cannot recode more than {_RECODE_MAX_ITEMS} rows in one run")

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
    coding artifact is self-contained) and classifies just those rows
    with the caller's chosen model. Returns the classification as
    *proposals* in the job result rather than writing them to
    ``coding_entries`` -- a recode is staged into the same editing
    session as manual tags/codebook edits (see ``useViewCodingPage.js``)
    and only commits when the user clicks Save
    (``coding_service.save_coding_revision``), same as any other pending
    change. A requested row the model no longer applies any code to still
    gets a proposal entry with an empty ``codes`` list, so accepting it
    on Save clears that row rather than leaving it untouched.
    """
    coding_file_id = payload["coding_file_id"]
    item_ids: list[str] = payload["item_ids"]
    methodology = payload.get("methodology") or ""
    model = payload["model"]
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
        codebook_text = await version_service.read_codebook_markdown(session, coding_file_id)
        codebook_codes = await version_service.read_codes(session, coding_file_id)
        if not codebook_text:
            raise ValidationAppError("Cannot recode: this coding artifact has no codebook snapshot")

        submissions = []
        if submission_ids:
            result = await session.execute(
                select(Submission).where(
                    Submission.file_id == coding_file_id, Submission.id.in_(submission_ids), Submission.valid_to.is_(None),
                )
            )
            submissions = list(result.scalars().all())

        comments = []
        if comment_ids:
            result = await session.execute(
                select(Comment).where(
                    Comment.file_id == coding_file_id, Comment.id.in_(comment_ids), Comment.valid_to.is_(None),
                )
            )
            comments = list(result.scalars().all())

        parent_context = await raw_data_repo.parent_post_context_for_comments(session, coding_file_id, comments)
        assembled = _assemble_posts_content(submissions, comments, parent_context=parent_context)
        content_by_key = {(SUBMISSION, s.id): (s.selftext or "") for s in submissions}
        content_by_key.update({(COMMENT, c.id): (c.body or "") for c in comments})

    if not assembled:
        raise ValidationAppError("None of the selected rows were found in this coding artifact")

    raw_entries, system_prompt, rendered_prompt, coverage = await classify_posts(
        codebook_text, assembled, methodology, api_key, model, progress=ProgressTracker(job_id)
    )
    # Restricted to exactly the rows sent this run (not every row the
    # whole coding artifact owns) -- same anti-hallucination gate Apply
    # Codebook uses, see _validate_and_resolve_coding_entries.
    valid_keys = set(content_by_key.keys())
    coding_entries, validation_counts = _validate_and_resolve_coding_entries(
        raw_entries, valid_keys=valid_keys, codes=codebook_codes, content_by_key=content_by_key
    )

    entries_by_item: dict[tuple[str, str], list[dict]] = {}
    for entry in coding_entries:
        entries_by_item.setdefault((entry["row_type"], entry["post_id"]), []).append(
            {
                "code": entry["code"],
                "code_uid": entry["code_uid"],
                "quote": entry["quote"],
                "start_offset": entry["start_offset"],
                "end_offset": entry["end_offset"],
            }
        )

    # Nothing is committed here any more -- a recode is a *proposal* the
    # user reviews and stages into the same editing session as their
    # manual tags (see useViewCodingPage.js), and only
    # ``save_coding_revision`` ever commits a version for a coding
    # artifact. Shaped like ``coding_repo.list_rows_with_codes``'s
    # per-row ``codes`` list so the frontend can drop a proposal straight
    # into ``rows[].codes`` without reshaping it.
    proposals = [
        {
            "item_id": qualify_item_id(row_type, post_id),
            "codes": [
                {
                    "code": entry["code"],
                    "code_uid": entry["code_uid"],
                    "quote": entry["quote"],
                    "start_offset": entry["start_offset"],
                    "end_offset": entry["end_offset"],
                    "notes": None,
                }
                for entry in entries_by_item.get((row_type, post_id), [])
            ],
        }
        for row_type, post_id in requested_keys
    ]

    return {
        "recoded_item_count": len(proposals),
        "proposals": proposals,
        # Surfaced so `assist_service.record_assist_runs` can source a
        # recode run's assist-provenance record from THIS job -- never
        # trusted from the client. See GAP-4/C2.
        "system_prompt": system_prompt,
        "user_instructions": methodology,
        "prompt_meta": version_service.prompt_meta(rendered_prompt, batches=coverage.get("batches_total")),
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
    model: str,
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
    ``artifact_edges`` rows link the new file to BOTH source codings,
    ordered ``side_a``/``side_b``.
    """
    from backend.scripts import summarize_coding as summarize_coding_module
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
        await version_service.pin_parent(session, file_id_a)
        await version_service.pin_parent(session, file_id_b)
        file_a = await session.get(File, file_id_a)
        file_b = await session.get(File, file_id_b)
        text_a = await _read_coding_content(session, file_id_a)
        text_b = await _read_coding_content(session, file_id_b)
        await session.commit()

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
    chosen_model = model

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

        await version_service.commit_blob_version(
            session,
            file_id=file_rec.id,
            author_user_id=user_id,
            origin=ORIGIN_GENERATED,
            content=comparison,
            job_id=job_id,
            model=chosen_model,
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
# summarize_coding: kickoff + handler
# ---------------------------------------------------------------------------


async def start_summarize_coding_job(
    session: AsyncSession,
    user_id: int,
    *,
    coding: str,
    api_key: str,
    model: str,
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
        await version_service.pin_parent(session, source_file_id)
        code_summaries = await coding_repo.code_summary_with_samples(session, source_file_id)
        await session.commit()

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

        await version_service.commit_blob_version(
            session,
            file_id=file_rec.id,
            author_user_id=user_id,
            origin=ORIGIN_GENERATED,
            content=summary,
            job_id=job_id,
            model=model,
            parents=[EdgeSpec(parent_file_id=source_file_id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA)],
        )

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
