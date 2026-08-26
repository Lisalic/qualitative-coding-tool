"""``GET /api/jobs/{id}`` -- the single polling endpoint every job-backed
route will point the frontend at.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.jobs import service

router = APIRouter()


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: int,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    job = await service.get_job(db, job_id, user_id)
    return {
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
