from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas import (
    CompareCodebooksRequest,
    DuplicateCodebookRequest,
    GenerateCodebookRequest,
    ImportCodebookRequest,
    SaveCodebookRequest,
    as_form,
)
from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.repositories import version_repo
from backend.app.services import codebook_service, version_service

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


@router.get("/codebook")
async def get_codebook(
    codebook_id: str = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Return a codebook's current structured code rows, or a codebook
    comparison's markdown content, owned by the authenticated user.
    """
    file_rec = await codebook_service.get_codebook(db, user_id, codebook_id)
    head = await version_repo.head_version(db, file_rec.id)
    if head is None:
        return JSONResponse({"error": "Codebook content not found in file"}, status_code=404)

    if file_rec.file_type == "codebook_comparison":
        return JSONResponse(
            {
                "codebook_comparison": head.content or "",
                "systemprompt": head.system_prompt,
                "instructions": head.user_instructions,
                "prompt_meta": head.prompt_meta,
                "version_no": head.version_no,
            }
        )

    codes = await version_service.read_codes(db, file_rec.id)
    return JSONResponse(
        {
            "codes": [_code_out(c) for c in codes],
            "systemprompt": head.system_prompt,
            "instructions": head.user_instructions,
            "prompt_meta": head.prompt_meta,
            "version_no": head.version_no,
        }
    )


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


@router.put("/codebook/{ref}")
async def save_project_codebook(
    ref: str,
    payload: SaveCodebookRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Save a codebook file's structured code rows, owned by the
    authenticated user. Opens (or extends) a human-edit draft version --
    see ``version_service.py``'s sealing rules.
    """
    file_rec = await codebook_service.save_project_codebook(
        db,
        user_id,
        schema_name=ref,
        codes=[c.model_dump() for c in payload.codes],
        display_name=payload.display_name,
    )
    return JSONResponse(
        {"message": "Codebook saved", "id": str(file_rec.id), "display_name": file_rec.filename}
    )


@router.post("/codebook/{ref}/import")
async def import_codebook_markdown(
    ref: str,
    payload: ImportCodebookRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Parse pasted/uploaded codebook markdown into structured rows and
    commit them as a new version -- the recovery path now that markdown
    is a wire format, not the storage format.
    """
    file_rec = await codebook_service.import_codebook_markdown(db, user_id, ref, markdown=payload.markdown)
    return JSONResponse({"message": "Codebook imported", "id": str(file_rec.id)})


@router.post("/codebook/{ref}/duplicate")
async def duplicate_codebook(
    ref: str,
    payload: DuplicateCodebookRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Fork a whole codebook into a brand-new file -- from head by
    default, or from ``from_version_no`` if given (see
    ``codebook_service.duplicate_codebook``'s docstring; this is the
    non-destructive replacement for the old revert).
    """
    file_rec = await codebook_service.duplicate_codebook(
        db, user_id, ref, display_name=payload.display_name, from_version_no=payload.from_version_no
    )
    return JSONResponse(
        {
            "message": "Duplicated",
            "id": str(file_rec.id),
            "schema_name": file_rec.schemaname,
            "display_name": file_rec.filename,
        }
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
        content_scope=payload.content_scope,
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
