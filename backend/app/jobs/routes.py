"""``GET /api/jobs/{id}`` -- the single polling endpoint every job-backed
route will point the frontend at.

Also provides cancellation (``POST /api/jobs/{id}/cancel``) and upfront batch
cost/time estimation (``GET /api/jobs/estimate``).
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.external.pricing import estimate_batch_cost
from backend.app.jobs import service

router = APIRouter()


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("/jobs/estimate")
async def get_batch_estimate(
    model: str = Query(..., description="OpenRouter model slug"),
    item_count: int = Query(1, ge=1, description="Number of items or batches"),
) -> dict[str, Any]:
    """Provide conservative pre-run cost and duration estimates (QC-005)."""
    return estimate_batch_cost(model, item_count)


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: int,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    job = await service.get_job(db, job_id, user_id)
    resp = {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "result": job.result,
        "progress": job.progress,
        "error": job.error,
        "error_code": job.error_code,
        "created_at": _isoformat(job.created_at),
        "started_at": _isoformat(job.started_at),
        "finished_at": _isoformat(job.finished_at),
    }
    if job.accounting is not None:
        resp["accounting"] = job.accounting
    if job.salvaged_output is not None:
        resp["salvaged_output"] = job.salvaged_output
    return resp


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Cancel a running background job (QC-006)."""
    job = await service.cancel_job(db, job_id, user_id)
    return {
        "id": job.id,
        "status": job.status,
        "error": job.error,
        "finished_at": _isoformat(job.finished_at),
    }
