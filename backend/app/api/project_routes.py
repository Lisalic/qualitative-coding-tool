from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.services import project_service

router = APIRouter()


@router.get("/my-files/")
async def my_projects(
    file_type: str = Query("raw_data"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    result = await project_service.list_files_for_user(db, user_id, file_type)
    return JSONResponse({"projects": result})


@router.post("/create-project/")
async def create_project(
    name: str = Form(...),
    description: str = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Create a new project."""
    proj = await project_service.create_project(db, user_id, name, description)
    return JSONResponse(
        {
            "project": {
                "id": str(proj.id),
                "projectname": proj.projectname,
                "description": proj.description,
                "created_at": proj.created_at.isoformat() if proj.created_at else None,
            }
        }
    )


@router.post("/update-project/")
async def update_project(
    project_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Update a project."""
    proj = await project_service.update_project(db, user_id, project_id, name, description)
    return JSONResponse(
        {
            "project": {
                "id": str(proj.id),
                "projectname": proj.projectname,
                "description": proj.description,
                "created_at": proj.created_at.isoformat() if proj.created_at else None,
            }
        }
    )


@router.get("/projects/")
async def list_projects(
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """List user's projects."""
    result = await project_service.list_projects_with_files(db, user_id)
    return JSONResponse({"projects": result})


@router.post("/rename-file/")
async def rename_project(
    schema_name: str = Form(...),
    display_name: str = Form(...),
    description: str = Form(None),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Rename a file's display_name. Requires authentication and ownership."""
    file_rec = await project_service.rename_file(db, user_id, schema_name, display_name, description)
    return JSONResponse(
        {
            "message": "File renamed",
            "id": str(file_rec.id),
            "display_name": file_rec.filename,
            "description": file_rec.description,
        }
    )
