from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas import (
    DuplicateCodingRequest,
    ManualCodingRequest,
    RecodeItemsRequest,
    SaveCodingRevisionRequest,
    StarQuoteRequest,
    UpdateCodingMetadataRequest,
    UpdateQuoteNotesRequest,
)
from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.repositories import version_repo
from backend.app.services import coding_service, version_service

router = APIRouter()


def _code_out(code) -> dict:
    return {
        "code_uid": code.code_uid,
        "family_uid": code.family_uid,
        "family_name": code.family_name,
        "name": code.name,
        "body": code.body,
        "definition": code.definition,
        "inclusion": code.inclusion,
        "exclusion": code.exclusion,
        "keywords": code.keywords,
        "example": code.example,
        "position": code.position,
    }


async def _file_info(db: AsyncSession, file_rec) -> dict:
    head = await version_repo.head_version(db, file_rec.id)
    return {
        "id": str(file_rec.id),
        "schema_name": file_rec.schemaname,
        "filename": file_rec.filename,
        "description": file_rec.description,
        "systemprompt": head.system_prompt if head else None,
        "instructions": head.user_instructions if head else None,
        "prompt_meta": head.prompt_meta if head else None,
    }


@router.get("/coding/{ref}")
async def get_coding_artifact(
    ref: str,
    version_no: int | None = Query(None, description="Read the codebook snapshot/counts AS OF this version"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Metadata for a coding file owned by the authenticated user: its own
    codebook snapshot as structured code rows, row/coded counts, and code
    frequency. Row content itself is fetched separately, paged, via
    ``GET /api/coding/{ref}/rows``. ``version_no`` reads every field AS
    OF that version instead of live -- see
    ``coding_service.get_coding_artifact``'s docstring; backs "view a
    previous version" in the version-history UI.
    """
    artifact = await coding_service.get_coding_artifact(db, user_id, ref, version_no=version_no)
    return JSONResponse(
        {
            "file": await _file_info(db, artifact["file"]),
            "codes": [_code_out(c) for c in artifact["codes"]],
            "total_rows": artifact["total_rows"],
            "total_coded": artifact["total_coded"],
            "code_frequency": artifact["code_frequency"],
        }
    )


@router.get("/coding/{ref}/rows")
async def list_coding_rows(
    ref: str,
    # No upper bound: "select all matching" asks for every row at once.
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
    only: str = Query("all", pattern="^(all|coded|uncoded|ai|human)$"),
    code: str | None = Query(None, description="Only rows with at least one entry for this code_uid"),
    q: str = None,
    version_no: int | None = Query(None, description="Read coding entries AS OF this version"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """One page of a coding file's own rows -- every submission/comment it
    owns, coded or not -- each with its codes. ``only`` narrows to
    ``coded``/``uncoded``/``ai`` (any AI-coded entry)/``human`` (coded,
    no AI entry); ``code`` narrows to rows carrying that exact
    code (by display name); ``q`` is a case-insensitive substring search
    over title/body. ``version_no`` pins the coding entries to a historical
    version for the read-only version-history viewer.
    """
    result = await coding_service.list_coding_rows(
        db, user_id, ref, limit=limit, offset=offset, only=only, code=code, q=q,
        version_no=version_no,
    )
    return JSONResponse(result)


@router.get("/coding/{ref}/quotes")
async def list_coding_quotes(
    ref: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    code: str | None = None,
    coder: str | None = None,
    q: str | None = None,
    starred_only: bool = False,
    version_no: int | None = Query(None, description="Read coding entries AS OF this version"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Paginated quote bank for a coding file owned by the authenticated user.
    Each row represents one coded quote with exact character offsets, inspectable
    source text/context, quote notes, coder attribution, and user-scoped starred status.
    """
    result = await coding_service.list_quote_bank(
        db,
        user_id,
        ref,
        code=code,
        coder=coder,
        q=q,
        starred_only=starred_only,
        limit=limit,
        offset=offset,
        version_no=version_no,
    )
    return JSONResponse(result)


@router.put("/coding/{ref}/quotes/{entry_id}/star")
async def set_coding_quote_star(
    ref: str,
    entry_id: int,
    payload: StarQuoteRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Star or unstar a quote entry for the writing draft/evidence shortlist."""
    starred = await coding_service.set_quote_star(
        db,
        user_id,
        ref,
        entry_id,
        payload.starred,
    )
    return JSONResponse({"entry_id": entry_id, "starred": starred})


@router.patch("/coding/{ref}/quotes/{entry_id}/notes")
async def update_coding_quote_notes(
    ref: str,
    entry_id: int,
    payload: UpdateQuoteNotesRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Attach or edit the note on a live coded quote. Saved as a new
    coding version, so the quote comes back under a new ``entry_id``.
    """
    new_entry_id, notes = await coding_service.update_quote_note(
        db,
        user_id,
        ref,
        entry_id,
        payload.notes,
    )
    return JSONResponse({"entry_id": new_entry_id, "notes": notes})


@router.get("/coding/{ref}/text")
async def get_coding_text(
    ref: str,
    version_no: int | None = Query(None, description="Render the text AS OF this version"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Read-only canonical POST_ID/CODE/EVIDENCE text for a coding file,
    generated fresh from ``coding_entries`` -- backs the Text View tab.
    ``version_no`` remains available for pinned text exports.
    """
    text = await coding_service.get_coding_text(db, user_id, ref, version_no=version_no)
    return JSONResponse({"text": text, "version_no": version_no})


@router.put("/coding/{ref}/revision")
async def save_coding_revision(
    ref: str,
    payload: SaveCodingRevisionRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Save a coding artifact's editing session -- an updated codebook
    snapshot, updated row coding (manual edits and/or reviewed AI-recode
    proposals), or both -- as at most one new version. Replaces the old
    separate ``PUT .../codebook`` and ``PUT .../rows`` endpoints, which
    each minted their own version even when both changed together.
    """
    codes = [c.model_dump() for c in payload.codes] if payload.codes else None
    rows = [row.model_dump() for row in payload.rows] if payload.rows else None
    file_rec = await coding_service.save_coding_revision(
        db,
        user_id,
        ref,
        codes=codes,
        rows=rows,
        assist_runs=[run.model_dump() for run in payload.assist_runs],
    )
    return JSONResponse({"message": "Saved", "file": await _file_info(db, file_rec)})


@router.patch("/coding/{ref}")
async def update_coding_metadata(
    ref: str,
    payload: UpdateCodingMetadataRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Rename/re-describe a coding file."""
    file_rec = await coding_service.update_coding_metadata(
        db, user_id, ref, display_name=payload.display_name, description=payload.description
    )
    return JSONResponse({"message": "Updated", "file": await _file_info(db, file_rec)})


@router.post("/coding/manual")
async def create_manual_coding(
    payload: ManualCodingRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Start a coding artifact by hand -- rows copied in and the codebook
    snapshotted, but nothing coded -- so the researcher can tag rows
    themselves in the ViewCoding workspace, using
    ``POST /api/coding/{ref}/recode`` as an opt-in assistant.

    Synchronous (no LLM call, so no job to poll) -- the same asymmetry the
    filter pair has between ``POST /api/filter-preview/`` and
    ``POST /api/filtered-data/manual``.
    """
    file_rec, counts = await coding_service.create_manual_coding(
        db,
        user_id,
        database=payload.database,
        codebook=payload.codebook,
        report_name=payload.report_name,
        description=payload.description,
        project_id=payload.project_id,
        content_scope=payload.content_scope,
        sample_percentage=payload.sample_percentage,
        post_ids=payload.post_ids,
        comment_ids=payload.comment_ids,
    )
    return JSONResponse(
        {"message": "Coding created", "file": await _file_info(db, file_rec), "counts": counts}
    )


@router.post("/coding/{ref}/duplicate")
async def duplicate_coding(
    ref: str,
    payload: DuplicateCodingRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Fork a whole coding artifact (codebook snapshot, its own rows, its
    coding, lineage, and project links) into a brand-new file -- from head
    by default, or from ``from_version_no`` if given (see
    ``coding_service.duplicate_coding``'s docstring).
    """
    file_rec = await coding_service.duplicate_coding(
        db, user_id, ref, display_name=payload.display_name, from_version_no=payload.from_version_no
    )
    return JSONResponse({"message": "Duplicated", "file": await _file_info(db, file_rec)})


@router.post("/coding/{ref}/recode")
async def recode_coding_items(
    ref: str,
    payload: RecodeItemsRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Kick off a background job that re-runs the AI classifier over a
    chosen subset of a coding artifact's own rows with a chosen model,
    replacing only that subset's coding, and return immediately with a
    job id to poll (see backend/app/jobs/).
    """
    job = await coding_service.start_recode_items_job(
        db,
        user_id,
        ref=ref,
        item_ids=payload.item_ids,
        api_key=payload.api_key,
        model=payload.model,
        methodology=payload.methodology,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)


@router.get("/coding-comparison")
async def get_coding_comparison(
    coding_id: str = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Return a coding-comparison file's content, owned by the
    authenticated user. A coding_comparison is still one blob-storage
    artifact -- unlike a plain coding artifact, it isn't restructured by
    the coding-artifact overhaul.
    """
    file_rec = await coding_service.get_coding_comparison(db, user_id, coding_id)
    content = await version_service.read_blob(db, file_rec.id)
    if content is None:
        return JSONResponse({"error": "Comparison content not found in file"}, status_code=404)

    head = await version_repo.head_version(db, file_rec.id)
    return JSONResponse(
        {
            "coding_comparison": content,
            "systemprompt": head.system_prompt if head else None,
            "instructions": head.user_instructions if head else None,
            "prompt_meta": head.prompt_meta if head else None,
        }
    )


@router.post("/compare-codings/")
async def compare_codings(
    coding_a: str = Form(...),
    coding_b: str = Form(...),
    api_key: str = Form(...),
    name: str = Form(...),
    model: str = Form(...),
    prompt: str = Form(""),
    description: str = Form(None),
    project_id: int = Form(...),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Kick off a background job that compares two coding outputs by
    calling the LLM, and return immediately with a job id to poll (see
    backend/app/jobs/).
    """
    job = await coding_service.start_compare_codings_job(
        db,
        user_id,
        coding_a=coding_a,
        coding_b=coding_b,
        api_key=api_key,
        model=model,
        prompt=prompt,
        name=name,
        description=description,
        project_id=project_id,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)


@router.post("/summarize-coding/")
async def summarize_coding(
    coding: str = Form(...),
    api_key: str = Form(...),
    name: str = Form(...),
    model: str = Form(...),
    prompt: str = Form(""),
    description: str = Form(None),
    project_id: int = Form(...),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Kick off a background job to summarize a coding output, and return
    immediately with a job id to poll instead of blocking the request on
    the LLM call (see backend/app/jobs/).
    """
    job = await coding_service.start_summarize_coding_job(
        db,
        user_id,
        coding=coding,
        api_key=api_key,
        model=model,
        prompt=prompt,
        name=name,
        description=description,
        project_id=project_id,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)
