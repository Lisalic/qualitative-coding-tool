import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas import ApplyCodebookRequest, as_form
from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.scripts.display_codebook import parse_codebook_to_json
from backend.app.services import coding_service

router = APIRouter()


@router.get("/coded-data")
async def get_coded_data_query(
    coded_id: str = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return coded data for a File record with file_type='coding' or
    'coding_comparison', owned by the authenticated user. Also includes
    the parent codebook's content/tree, resolved via `file_dependencies`
    (see `coding_service._resolve_parent_codebook_text` -- the redundant
    per-artifact copy of the codebook text this used to read from is
    retired).
    """
    file_rec, coded_data, codebook_text = await coding_service.get_coded_data(db, user_id, coded_id)

    codebook_tree = []
    if codebook_text:
        try:
            parsed_text = parse_codebook_to_json(codebook_text)
            parsed_obj = json.loads(parsed_text)
            if isinstance(parsed_obj, list):
                codebook_tree = parsed_obj
        except Exception:
            codebook_tree = []

    return JSONResponse({
        "coded_data": coded_data,
        "codebook_text": codebook_text,
        "codebook_tree": codebook_tree,
        "systemprompt": file_rec.systemprompt,
        "userprompt": file_rec.userprompt,
    })


@router.post("/save-file-coded-data/")
async def save_project_coded_data(
    request: Request,
    schema_name: str = Form(None),
    content: str = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Save coded content for an owned coding file. Accepts JSON or
    form-data with `schema_name` and `content`.

    A request body may still include a `codebook_text` field for backward
    compatibility with not-yet-updated callers -- it is parsed but
    intentionally ignored: the redundant per-artifact codebook-text copy
    it used to write no longer exists (see
    `coding_service.save_project_coded_data`).
    """
    display_name = None
    try:
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            body = await request.json()
            schema_name = body.get("schema_name")
            content = body.get("content")
            display_name = body.get("display_name")
        else:
            form = await request.form()
            if schema_name is None:
                schema_name = form.get("schema_name")
            if content is None:
                content = form.get("content")
            display_name = form.get("display_name") if "display_name" in form else None
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    file_rec = await coding_service.save_project_coded_data(
        db,
        user_id,
        schema_name=(schema_name or "").strip(),
        content=content,
        display_name=display_name,
    )
    return JSONResponse({
        "message": "File coded data saved",
        "id": str(file_rec.id),
        "filename": file_rec.filename,
    })


@router.post("/save-file-coded-data-duplicate/")
async def save_project_coded_data_duplicate(
    request: Request,
    source_schema_name: str = Form(None),
    content: str = Form(None),
    display_name: str = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Duplicate coding data into a new file. Accepts JSON or form-data
    with source_schema_name, content, and display_name.
    """
    try:
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            body = await request.json()
            source_schema_name = body.get("source_schema_name")
            content = body.get("content")
            display_name = body.get("display_name")
        else:
            form = await request.form()
            if source_schema_name is None:
                source_schema_name = form.get("source_schema_name")
            if content is None:
                content = form.get("content")
            if display_name is None:
                display_name = form.get("display_name")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    file_rec = await coding_service.save_project_coded_data_duplicate(
        db,
        user_id,
        source_schema_name=source_schema_name or "",
        content=content or "",
        display_name=display_name or "",
    )
    return JSONResponse({
        "message": "File coded data duplicated",
        "id": str(file_rec.id),
        "schema_name": file_rec.schemaname,
        "filename": file_rec.filename,
    })


@router.post("/apply-codebook/")
async def apply_codebook(
    payload: ApplyCodebookRequest = Depends(as_form(ApplyCodebookRequest)),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Kick off a background job that classifies a raw/filtered data
    source against a codebook and persists the classification output, and
    return immediately with a job id to poll instead of blocking the
    request on the LLM call (see backend/app/jobs/).

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
    backend/app/jobs/). Also closes the missing-auth gap the old
    synchronous route had (no user check at all).
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
    """Kick off a background job to summarize a coding output stored in a
    Postgres schema, and return immediately with a job id to poll instead
    of blocking the request on the LLM call (see backend/app/jobs/).
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
