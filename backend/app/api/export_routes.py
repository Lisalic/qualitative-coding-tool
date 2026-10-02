"""API routes for exporting codebooks, codings (long/wide), code-frequency
summaries, memos, saved summaries/comparisons (``document``), and
deterministic project bundles.

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


@router.get("/{ref}/codebook")
async def export_codebook(
    ref: str,
    format: str = Query("qdc", pattern="^(qdc|csv)$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_codebook(
        db, ref, user_id, version_no=version_no, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/coding")
async def export_coding(
    ref: str,
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
        ref,
        user_id,
        version_no=version_no,
        export_format=format,
        layout=layout,
        include_source_text=include_source_text,
        include_author=include_author,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/memos")
async def export_memos(
    ref: str,
    format: str = Query("md", pattern="^(md|csv)$"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_memos(
        db, ref, user_id, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/summary")
async def export_summary(
    ref: str,
    format: str = Query("md", pattern="^md$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_summary(
        db, ref, user_id, version_no=version_no, export_format=format
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/document")
async def export_document(
    ref: str,
    format: str = Query("md", pattern="^md$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """A saved summary or comparison, as its stored markdown."""
    content, media_type, filename = await export_service.export_document(
        db, ref, user_id, version_no=version_no, export_format=format
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
