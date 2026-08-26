"""Progress reporting for long-running, multi-batch job handlers.

A handler already receives its own ``job_id``; ``update_job_progress`` lets
it push interim ``(current, total)`` updates mid-run (e.g. after each batch
in a chunked LLM call) so ``GET /api/jobs/{id}`` can report progress before
the job reaches a terminal status. Batched LLM calls in this codebase run
sequentially (filter_db.py/codebook_apply.py/codebook_generator.py/
summarize_coding.py), so a single ``ProgressTracker`` can accumulate totals
and advances across more than one phase of the same job -- e.g.
filter_data's separate posts-then-comments AI-filter calls -- into one
running figure, with no concurrency bookkeeping needed.
"""

from __future__ import annotations

from sqlalchemy import update

from backend.app.database import AsyncSessionLocal
from backend.app.jobs.models import Job


async def update_job_progress(job_id: int, current: int, total: int, label: str = "batches") -> None:
    """Best-effort progress update for a running job.

    Opens its own short-lived session, independent of whatever session(s)
    the calling handler holds open, and never raises -- a failed progress
    write is a UX nicety lost, not a reason to fail the job itself.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(progress={"current": current, "total": total, "label": label})
            )
            await session.commit()
    except Exception:
        pass


class ProgressTracker:
    """Accumulates batch counts across one or more sequential phases of the
    same job (e.g. filter_data's posts-then-comments AI-filter calls) into
    a single running ``(current, total)`` progress report.

    ``add_total`` is called once a phase knows how many batches it has
    (after any free-model batch capping) and writes that immediately --
    otherwise a job's ``progress`` stays completely blank for as long as
    the first batch's LLM call takes (which for a large batch, a slow
    model, or a retry/backoff cycle can be minutes), leaving no way to
    tell "still waiting on batch 1" apart from "stuck". ``advance`` is
    called after each batch is attempted, regardless of whether it
    succeeded, so the bar keeps moving even through a partial-coverage
    run.
    """

    def __init__(self, job_id: int, label: str = "batches") -> None:
        self._job_id = job_id
        self._label = label
        self.total = 0
        self.current = 0

    async def add_total(self, n: int) -> None:
        self.total += n
        await update_job_progress(self._job_id, self.current, self.total, self._label)

    async def advance(self, n: int = 1) -> None:
        self.current += n
        await update_job_progress(self._job_id, self.current, self.total, self._label)
