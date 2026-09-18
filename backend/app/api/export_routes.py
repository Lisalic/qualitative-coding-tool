"""API routes for exporting codebooks, codings (long/wide), summaries,
memos, and deterministic project bundles.

Each endpoint accepts only the two formats that suit its artifact, not a
blanket CSV/JSON pair -- codebook ``qdc|csv``, coding ``csv|json``,
memos ``md|csv``, and summary ``md`` alone. See
``services/export_service.py``'s module docstring for why each pair was
chosen; the ``format`` patterns below are the enforcement point, so a
dropped format 422s rather than silently falling through to the default.
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{file_id}/codebook")
async def export_codebook(
    file_id: int,
    format: str = Query("qdc", pattern="^(qdc|csv)$"),
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
    layout: str = Query("long", pattern="^(long|wide)$"),
    version_no: int | None = Query(None, ge=1),
    include_source_text: bool = Query(False, description="Include each quote's full source text (off by default)"),
    include_author: bool = Query(False, description="Include each row's author (off by default)"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_coding(
        db,
        file_id,
        user_id,
        version_no=version_no,
        export_format=format,
        layout=layout,
        include_source_text=include_source_text,
        include_author=include_author,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{file_id}/memos")
async def export_memos(
    file_id: int,
    format: str = Query("md", pattern="^(md|csv)$"),
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
    format: str = Query("md", pattern="^md$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_summary(
        db, file_id, user_id, version_no=version_no, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/projects/{project_id}/bundle")
async def export_project_bundle(
    project_id: int,
    include_source_text: bool = Query(False, description="Include each quote's full source text (off by default)"),
    include_author: bool = Query(False, description="Include each row's author (off by default)"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_project_bundle(
        db,
        project_id,
        user_id,
        include_source_text=include_source_text,
        include_author=include_author,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)
