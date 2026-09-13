"""Job lifecycle: enqueue, background execution, lookup, cancellation, startup reconciliation.

``enqueue_job`` is the only entry point routes call; everything else here
is either called by the background runner (``_execute_job``) or by
``main.py``'s lifespan (``reconcile_orphaned_jobs_on_startup``).
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import AsyncSessionLocal
from backend.app.external.errors import ExternalServiceError, is_retryable_error
from backend.app.jobs.models import Job, TERMINAL_STATUSES
from backend.app.jobs.progress import (
    JobAccountingTracker,
    set_current_accounting_tracker,
)
from backend.app.jobs.registry import get_handler
from backend.app.jobs.runner import get_job_runner


async def enqueue_job(
    session: AsyncSession,
    *,
    user_id: int,
    job_type: str,
    payload: dict[str, Any],
    runtime_extra: dict[str, Any] | None = None,
) -> Job:
    """Create a pending ``Job`` row and kick off background execution."""
    job = Job(job_type=job_type, user_id=user_id, status="pending", payload=payload)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    handler_payload = {**payload, **(runtime_extra or {})}
    get_job_runner().submit(_execute_job(job.id, job_type, handler_payload), job_id=job.id)

    return job


async def cancel_job(session: AsyncSession, job_id: int, user_id: int) -> Job:
    """Cancel a running or pending job and record cancellation state (QC-006)."""
    job = await get_job(session, job_id, user_id)
    if job.status in TERMINAL_STATUSES:
        return job

    get_job_runner().cancel(job_id)

    now = datetime.now(timezone.utc)
    stmt = (
        update(Job)
        .where(
            Job.id == job_id,
            Job.user_id == user_id,
            Job.status.notin_(TERMINAL_STATUSES),
        )
        .values(
            status="cancelled",
            error="Job was cancelled by user",
            finished_at=now,
        )
    )
    await session.execute(stmt)
    await session.commit()
    await session.refresh(job)
    return job


def _is_empty_output(result: Any) -> bool:
    """Check if result is functionally empty (QC-006: never succeed silently on empty output)."""
    if result is None:
        return True
    if isinstance(result, (str, list, tuple, set, dict)) and len(result) == 0:
        return True
    if isinstance(result, dict) and result.get("is_empty") is True:
        return True
    return False


async def _execute_job(job_id: int, job_type: str, payload: dict[str, Any]) -> None:
    """Run the handler registered for ``job_type`` and persist the outcome.

    Enforces explicit terminal states (QC-006):
    - succeeded / completed: finished with valid output.
    - partial: explicitly returned partial status with salvaged output.
    - retryable_failure: transient external error suitable for retry.
    - failed: permanent error or empty output.
    - cancelled: aborted mid-run.
    """
    tracker = JobAccountingTracker(job_id=job_id, model=payload.get("model", ""))
    set_current_accounting_tracker(tracker)

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    accounting=tracker.to_dict(),
                )
            )
            await session.commit()

            handler = get_handler(job_type)
            result = await handler(job_id, payload)

            now = datetime.now(timezone.utc)
            final_accounting = tracker.to_dict()

            # Inspect result for explicit partial status or empty output
            if isinstance(result, dict) and result.get("status") == "partial":
                salvaged = result.get("salvaged_output") or result.get("salvaged") or result
                reason = result.get("partial_reason") or result.get("error") or "Partial completion"
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status.notin_(TERMINAL_STATUSES))
                    .values(
                        status="partial",
                        result=result,
                        salvaged_output=salvaged,
                        error=reason,
                        accounting=final_accounting,
                        finished_at=now,
                    )
                )
            elif _is_empty_output(result):
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status.notin_(TERMINAL_STATUSES))
                    .values(
                        status="failed",
                        result=result,
                        error="Job produced empty output",
                        accounting=final_accounting,
                        finished_at=now,
                    )
                )
            else:
                salvaged = result.get("salvaged_output") if isinstance(result, dict) else None
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status.notin_(TERMINAL_STATUSES))
                    .values(
                        status="succeeded",
                        result=result,
                        salvaged_output=salvaged,
                        accounting=final_accounting,
                        finished_at=now,
                    )
                )
            await session.commit()

        except asyncio.CancelledError:
            await session.rollback()
            await session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status.notin_(TERMINAL_STATUSES))
                .values(
                    status="cancelled",
                    error="Job was cancelled",
                    accounting=tracker.to_dict(),
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        except Exception as exc:
            await session.rollback()
            now = datetime.now(timezone.utc)
            final_accounting = tracker.to_dict()
            err_str = str(exc)
            err_code = getattr(exc, "code", None)

            salvaged = getattr(exc, "salvaged_output", None)
            if salvaged is not None:
                new_status = "partial"
            elif isinstance(exc, ExternalServiceError) and is_retryable_error(exc):
                new_status = "retryable_failure"
            else:
                new_status = "failed"

            await session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status.notin_(TERMINAL_STATUSES))
                .values(
                    status=new_status,
                    error=err_str,
                    error_code=err_code,
                    salvaged_output=salvaged,
                    accounting=final_accounting,
                    finished_at=now,
                )
            )
            await session.commit()

        finally:
            set_current_accounting_tracker(None)


async def get_job(session: AsyncSession, job_id: int, user_id: int) -> Job:
    """Fetch a job by id, scoped to its owner."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    if job.user_id != user_id:
        raise ForbiddenError(f"Job {job_id} is owned by another user")
    return job


async def reconcile_orphaned_jobs_on_startup() -> int:
    """Mark any jobs left behind by a previous process as failed."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            update(Job)
            .where(Job.status.in_(("pending", "running")))
            .values(
                status="failed",
                error="Server restarted while job was in progress",
                finished_at=now,
            )
        )
        count = result.rowcount
        await session.commit()
        return count
