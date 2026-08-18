"""Job lifecycle: enqueue, background execution, lookup, startup reconciliation.

``enqueue_job`` is the only entry point routes call; everything else here
is either called by the background runner (``_execute_job``) or by
``main.py``'s lifespan (``reconcile_orphaned_jobs_on_startup``).
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import AsyncSessionLocal
from backend.app.jobs.models import Job
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
    """Create a pending ``Job`` row and kick off background execution.

    ``payload`` is persisted as-is (JSON column) -- callers must not put
    secrets (e.g. API keys) in it. ``runtime_extra`` is merged into the dict
    handed to the handler but is NEVER persisted: it only lives in the
    in-memory closure passed to the runner for this process's lifetime, so
    a job's OpenRouter API key (say) survives a request but not a restart --
    matching ``reconcile_orphaned_jobs_on_startup``'s "fail loudly, don't
    silently resume with a lost secret" behavior.

    Returns immediately with the row still ``status="pending"``; execution
    happens in the background via the module-level job runner.
    """
    job = Job(job_type=job_type, user_id=user_id, status="pending", payload=payload)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    handler_payload = {**payload, **(runtime_extra or {})}
    get_job_runner().submit(_execute_job(job.id, job_type, handler_payload))

    return job


async def _execute_job(job_id: int, job_type: str, payload: dict[str, Any]) -> None:
    """Run the handler registered for ``job_type`` and persist the outcome.

    Opens its own session -- the request that called ``enqueue_job`` will
    have already returned a response and closed its session long before
    this finishes. Never raises: any failure (handler bug, unknown
    ``job_type``, DB error mid-update) is caught and recorded on the job
    row so it can't get stuck at "running" forever.
    """
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="running", started_at=datetime.now(timezone.utc))
            )
            await session.commit()

            handler = get_handler(job_type)
            result = await handler(job_id, payload)

            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="succeeded",
                    result=result,
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="failed",
                    error=str(exc),
                    error_code=getattr(exc, "code", None),
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()


async def get_job(session: AsyncSession, job_id: int, user_id: int) -> Job:
    """Fetch a job by id, scoped to its owner.

    Raises ``NotFoundError`` if no such job exists, ``ForbiddenError`` if it
    exists but belongs to a different user.
    """
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    if job.user_id != user_id:
        raise ForbiddenError("You do not have access to this job")
    return job


async def reconcile_orphaned_jobs_on_startup() -> int:
    """Fail out any job left ``pending``/``running`` from a killed process.

    Called once from ``main.py``'s lifespan, after tables are created, so a
    restarted worker fails loudly instead of leaving the frontend polling a
    job that will never move again. Returns the number of rows reconciled.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(Job)
            .where(Job.status.in_(["pending", "running"]))
            .values(
                status="failed",
                error="Worker restarted before this job finished. Please retry.",
                finished_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        return result.rowcount or 0
