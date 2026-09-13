"""API routes for exporting codebooks, codings, memos, and summaries as CSV/JSON."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{file_id}/codebook")
async def export_codebook(
    file_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_codebook(
        db, file_id, user_id, version_no=version_no, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{file_id}/coding")
async def export_coding(
    file_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_coding(
        db, file_id, user_id, version_no=version_no, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{file_id}/memos")
async def export_memos(
    file_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_memos(
        db, file_id, user_id, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{file_id}/summary")
async def export_summary(
    file_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_summary(
        db, file_id, user_id, version_no=version_no, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)
