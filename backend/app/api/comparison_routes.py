"""FastAPI routes for deterministic cross-artifact comparisons.

Provides computed comparisons between two codebooks or two coding artifacts:
- ``GET /api/comparison/codebooks``
- ``GET /api/comparison/codings``

Requires no LLM / API keys; provides deterministic outer-join diffs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.services import comparison_service

router = APIRouter()


@router.get("/comparison/codebooks")
async def compare_codebooks(
    file_a: str = Query(..., description="Ref or ID of first codebook"),
    file_b: str = Query(..., description="Ref or ID of second codebook"),
    version_a: int | None = Query(None, description="Optional version number for codebook A"),
    version_b: int | None = Query(None, description="Optional version number for codebook B"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Deterministic comparison between two codebooks."""
    res = await comparison_service.compare_codebooks(
        db,
        user_id,
        file_a,
        file_b,
        version_a=version_a,
        version_b=version_b,
    )
    return JSONResponse(res)


@router.get("/comparison/codings")
async def compare_codings(
    file_a: str = Query(..., description="Ref or ID of first coding artifact"),
    file_b: str = Query(..., description="Ref or ID of second coding artifact"),
    version_a: int | None = Query(None, description="Optional version number for coding artifact A"),
    version_b: int | None = Query(None, description="Optional version number for coding artifact B"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Deterministic comparison between two coding artifacts."""
    res = await comparison_service.compare_codings(
        db,
        user_id,
        file_a,
        file_b,
        version_a=version_a,
        version_b=version_b,
    )
    return JSONResponse(res)
