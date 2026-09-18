"""FastAPI routes for qualitative coding coverage metrics.

Provides the ``GET /coding/{file_id}/coverage`` endpoint for reading descriptive
corpus coverage statistics (coded vs uncoded row counts, codes-per-row distribution,
code density buckets, and code family rollups) for either current head or a historical
version snapshot.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.services import coverage_service

router = APIRouter()


@router.get("/coding/{file_id}/coverage")
async def get_coding_coverage(
    file_id: str,
    version_no: int | None = Query(None, description="Read coverage metrics AS OF this version"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Retrieve descriptive coverage metrics for a coding artifact.

    If ``version_no`` is specified, calculates coverage metrics historically as of
    that version snapshot via SCD-2 entries.
    """
    coverage = await coverage_service.get_coding_coverage(
        db,
        user_id,
        file_id,
        version_no=version_no,
    )
    return JSONResponse(coverage)
