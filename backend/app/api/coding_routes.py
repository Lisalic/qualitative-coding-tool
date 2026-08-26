import json

from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas import (
    ApplyCodebookRequest,
    DuplicateCodingRequest,
    RecodeItemsRequest,
    SaveCodingCodebookRequest,
    SaveCodingRowsRequest,
    UpdateCodingMetadataRequest,
    as_form,
)
from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.repositories import artifact_content_repo
from backend.scripts.display_codebook import parse_codebook_to_json
from backend.app.services import coding_service

router = APIRouter()


def _codebook_tree(codebook_text: str) -> list:
    if not codebook_text:
        return []
    try:
        parsed_text = parse_codebook_to_json(codebook_text)
        parsed_obj = json.loads(parsed_text)
        return parsed_obj if isinstance(parsed_obj, list) else []
    except Exception:
        return []


def _file_info(file_rec) -> dict:
    return {
        "id": str(file_rec.id),
        "schema_name": file_rec.schemaname,
        "filename": file_rec.filename,
        "description": file_rec.description,
        "systemprompt": file_rec.systemprompt,
        "userprompt": file_rec.userprompt,
    }


@router.get("/coding/{ref}")
async def get_coding_artifact(
    ref: str,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Metadata for a coding file owned by the authenticated user: its own
    codebook snapshot (text + parsed tree), row/coded counts, and code
    frequency. Row content itself is fetched separately, paged, via
    ``GET /api/coding/{ref}/rows``.
    """
    artifact = await coding_service.get_coding_artifact(db, user_id, ref)
    return JSONResponse(
        {
            "file": _file_info(artifact["file"]),
            "codebook_text": artifact["codebook_text"],
            "codebook_tree": _codebook_tree(artifact["codebook_text"]),
            "total_rows": artifact["total_rows"],
            "total_coded": artifact["total_coded"],
            "code_frequency": artifact["code_frequency"],
        }
    )


@router.get("/coding/{ref}/rows")
async def list_coding_rows(
    ref: str,
    limit: int = 50,
    offset: int = 0,
    only: str = "all",
    code: str = None,
    q: str = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """One page of a coding file's own rows -- every submission/comment it
    owns, coded or not -- each with its codes. ``only`` narrows to
    ``coded``/``uncoded``; ``code`` narrows to rows carrying that exact
    code; ``q`` is a case-insensitive substring search over title/body.
    """
    result = await coding_service.list_coding_rows(
        db, user_id, ref, limit=limit, offset=offset, only=only, code=code, q=q
    )
    return JSONResponse(result)


@router.get("/coding/{ref}/text")
async def get_coding_text(
    ref: str,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Read-only canonical POST_ID/CODE/EVIDENCE text for a coding file,
    generated fresh from ``coding_entries`` -- backs the Text View tab.
    """
    text = await coding_service.get_coding_text(db, user_id, ref)
    return JSONResponse({"text": text})


@router.put("/coding/{ref}/codebook")
async def save_coding_codebook(
    ref: str,
    payload: SaveCodingCodebookRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Overwrite a coding file's own codebook snapshot."""
    file_rec = await coding_service.save_coding_codebook(db, user_id, ref, payload.content)
    return JSONResponse({"message": "Codebook saved", "file": _file_info(file_rec)})


@router.put("/coding/{ref}/rows")
async def save_coding_rows(
    ref: str,
    payload: SaveCodingRowsRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Replace the coding for exactly the rows submitted -- a manual table
    edit's save.
    """
    rows = [row.model_dump() for row in payload.rows]
    file_rec = await coding_service.save_coding_rows(db, user_id, ref, rows)
    return JSONResponse({"message": "Coding saved", "file": _file_info(file_rec)})


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
    return JSONResponse({"message": "Updated", "file": _file_info(file_rec)})


@router.post("/coding/{ref}/duplicate")
async def duplicate_coding(
    ref: str,
    payload: DuplicateCodingRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Fork a whole coding artifact (codebook snapshot, its own rows, its
    coding, lineage, and project links) into a brand-new file.
    """
    file_rec = await coding_service.duplicate_coding(db, user_id, ref, display_name=payload.display_name)
    return JSONResponse({"message": "Duplicated", "file": _file_info(file_rec)})


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
    authenticated user. A coding_comparison is still one
    ``artifact_content`` markdown blob -- unlike a plain coding artifact,
    it isn't restructured by the coding-artifact overhaul.
    """
    file_rec = await coding_service.get_coding_comparison(db, user_id, coding_id)
    content = await artifact_content_repo.read_content(db, file_rec.id)
    if content is None:
        return JSONResponse({"error": "Comparison content not found in file"}, status_code=404)

    return JSONResponse(
        {
            "coding_comparison": content,
            "systemprompt": file_rec.systemprompt,
            "userprompt": file_rec.userprompt,
        }
    )


@router.post("/apply-codebook/")
async def apply_codebook(
    payload: ApplyCodebookRequest = Depends(as_form(ApplyCodebookRequest)),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Kick off a background job that classifies a raw/filtered data
    source against a codebook and persists the result as a self-contained
    coding artifact (its own codebook snapshot, its own copy of the
    sampled rows, and their coding), and return immediately with a job id
    to poll instead of blocking the request on the LLM call (see
    backend/app/jobs/).

    The ``codebook`` field accepts either a numeric File id or a
    ``proj_<hex>`` schema name; this is enforced by
    :class:`ApplyCodebookRequest`.
    """
    job = await coding_service.start_apply_codebook_job(
        db,
        user_id,
        database=payload.database,
        codebook=payload.codebook,
        methodology=payload.methodology,
        api_key=payload.api_key,
        model=payload.model,
        sample_percentage=payload.sample_percentage,
        report_name=payload.report_name,
        project_id=payload.project_id,
        content_scope=payload.content_scope,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)


@router.post("/compare-codings/")
async def compare_codings(
    coding_a: str = Form(...),
    coding_b: str = Form(...),
    api_key: str = Form(...),
    name: str = Form(...),
    model: str = Form(None),
    prompt: str = Form(""),
    description: str = Form(None),
    project_id: int = Form(None),
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
    model: str = Form(None),
    prompt: str = Form(""),
    description: str = Form(None),
    project_id: int = Form(None),
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
