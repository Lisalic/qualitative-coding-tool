import json

from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas import (
    CompareCodebooksRequest,
    GenerateCodebookRequest,
    as_form,
)
from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.repositories import artifact_content_repo
from backend.app.services import codebook_service
from backend.scripts.display_codebook import parse_codebook_to_json

router = APIRouter()


@router.get("/codebook")
async def get_codebook(
    codebook_id: str = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Return a codebook (or codebook comparison) file's content, owned by
    the authenticated user.
    """
    file_rec = await codebook_service.get_codebook(db, user_id, codebook_id)
    content = await artifact_content_repo.read_content(db, file_rec.id)
    if content is None:
        return JSONResponse({"error": "Codebook content not found in file"}, status_code=404)

    return JSONResponse(
        {
            "codebook": content,
            "systemprompt": file_rec.systemprompt,
            "userprompt": file_rec.userprompt,
        }
    )


@router.get("/parse-codebook")
async def parse_codebook(
    codebook_id: str = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Return a parsed JSON structure for a codebook file using the
    display_codebook helper. The response will be { "parsed": [ ... ] }
    where parsed is an array of families with codes.
    """
    _file_rec, raw = await codebook_service.parse_codebook(db, user_id, codebook_id)
    try:
        parsed_text = parse_codebook_to_json(raw)
        parsed_obj = json.loads(parsed_text)
        return JSONResponse({"parsed": parsed_obj})
    except Exception as e:
        return JSONResponse({"error": f"Failed to parse codebook: {e}", "raw": raw}, status_code=500)


@router.get("/list-codebooks")
async def list_codebooks(
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """List every codebook/codebook-comparison file owned by the
    authenticated user.
    """
    files = await codebook_service.list_codebooks(db, user_id)
    codebooks = [
        {
            "id": str(f.id),
            "name": f.filename,
            "metadata": {
                "schema": f.schemaname,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "file_type": f.file_type,
            },
            "description": f.description,
            "source": "file",
        }
        for f in files
    ]
    codebooks.sort(key=lambda x: x.get("name") or x.get("id"))
    return JSONResponse({"codebooks": codebooks})


@router.post("/save-file-codebook/")
async def save_project_codebook(
    schema_name: str = Form(...),
    content: str = Form(...),
    display_name: str = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Save codebook content to a file owned by the authenticated user."""
    file_rec = await codebook_service.save_project_codebook(
        db,
        user_id,
        schema_name=schema_name,
        content=content,
        display_name=display_name,
    )
    return JSONResponse(
        {"message": "File codebook saved", "id": str(file_rec.id), "display_name": file_rec.filename}
    )


@router.post("/generate-codebook/")
async def generate_codebook(
    payload: GenerateCodebookRequest = Depends(as_form(GenerateCodebookRequest)),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Kick off a background job that samples a raw-data file, asks the LLM
    to build a codebook, and persists it as a new ``codebook`` file -- and
    return immediately with a job id to poll instead of blocking the
    request. See backend/app/jobs/.
    """
    job = await codebook_service.start_generate_codebook_job(
        db,
        user_id,
        database=payload.database,
        api_key=payload.api_key,
        prompt=payload.prompt or "",
        name=payload.name,
        description=payload.description,
        project_id=payload.project_id,
        model=payload.model,
        sample_percentage=payload.sample_percentage,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)


@router.post("/compare-codebooks/")
async def compare_codebooks(
    payload: CompareCodebooksRequest = Depends(as_form(CompareCodebooksRequest)),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Kick off a background job that compares two codebooks owned by the
    authenticated user via the LLM, and return immediately with a job id
    to poll instead of blocking the request.
    """
    job = await codebook_service.start_compare_codebooks_job(
        db,
        user_id,
        codebook_a=payload.codebook_a,
        codebook_b=payload.codebook_b,
        api_key=payload.api_key,
        model=payload.model,
        prompt=payload.prompt or "",
        name=payload.name,
        description=payload.description,
        project_id=payload.project_id,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)
