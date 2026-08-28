import json

from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.core.exceptions import ValidationAppError
from backend.app.database import get_async_db
from backend.app.services import content_service, version_service

router = APIRouter()


@router.post("/save-comparison/")
async def save_comparison(
    content: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    file_type: str = Form(None),
    project_id: int = Form(None),
    parent_file_ids: str = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    parent_ids: list[int] | None = None
    if parent_file_ids:
        try:
            parsed = json.loads(parent_file_ids) if isinstance(parent_file_ids, str) else parent_file_ids
            parent_ids = [int(pid) for pid in parsed]
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationAppError(f"Invalid parent_file_ids: {exc}") from exc

    file_rec = await content_service.save_comparison(
        db,
        user_id,
        content=content,
        title=title,
        description=description,
        file_type=file_type,
        project_id=project_id,
        parent_file_ids=parent_ids,
    )
    return JSONResponse({"message": "Saved", "file_id": file_rec.id, "schema_name": file_rec.schemaname})


@router.post("/save-summary/")
async def save_summary(
    content: str = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    project_id: int = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Save a generated summary as a `File` record of type 'summary', with
    its content in the fixed `artifact_content` table. Associates the file
    with a project when `project_id` is provided and belongs to the
    authenticated user.
    """
    if not content:
        raise ValidationAppError("content is required")

    file_rec = await content_service.save_summary(
        db,
        user_id,
        content=content,
        name=name,
        description=description,
        project_id=project_id,
    )
    return JSONResponse(
        {
            "message": "Summary saved",
            "file": {
                "id": str(file_rec.id),
                "schema_name": file_rec.schemaname,
                "filename": file_rec.filename,
            },
        }
    )


@router.get("/summary/{summary_id}")
async def get_summary_file(
    summary_id: str = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Return summary content for a `File` record with file_type='summary'
    owned by the authenticated user. Matches by schemaname, filename, or
    numeric id. If no id provided, returns the caller's latest summary.
    """
    file_rec = await content_service.get_summary(db, user_id, summary_id)
    content = await version_service.read_blob(db, file_rec.id)
    if content is None:
        return JSONResponse({"error": "Summary content not found in file"}, status_code=404)

    return JSONResponse(
        {
            "summary": {
                "content": content,
                "display_name": file_rec.filename,
                "description": file_rec.description,
            }
        }
    )
