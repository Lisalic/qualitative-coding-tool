"""Progress and accounting reporting for long-running, multi-batch job handlers.

A handler already receives its own ``job_id``; ``update_job_progress`` lets
it push interim ``(current, total)`` updates mid-run so ``GET /api/jobs/{id}``
can report progress before the job reaches a terminal status.

``JobAccountingTracker`` captures call counts, token counts, duration, and
dollar cost using documented model pricing (QC-005). Token counts and cost
are preserved as ``None`` (unknown) rather than coerced to 0 whenever the
provider didn't report usage.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any
from sqlalchemy import update

from backend.app.core.logging import get_logger
from backend.app.database import AsyncSessionLocal

logger = get_logger(__name__)
from backend.app.external.pricing import calculate_cost
from backend.app.jobs.models import Job


_active_tracker_var: ContextVar[JobAccountingTracker | None] = ContextVar(
    "_active_tracker_var", default=None
)


def get_current_accounting_tracker() -> JobAccountingTracker | None:
    return _active_tracker_var.get()


def set_current_accounting_tracker(tracker: JobAccountingTracker | None) -> None:
    _active_tracker_var.set(tracker)


async def update_job_progress(job_id: int, current: int, total: int, label: str = "batches") -> None:
    """Best-effort progress update for a running job. A failure here must
    never abort the job it's reporting on -- swallowed, but logged so a
    persistently-failing progress channel doesn't go unnoticed.
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
        logger.warning("Failed to update progress for job %s", job_id, exc_info=True)


async def update_job_accounting(job_id: int, accounting: dict[str, Any]) -> None:
    """Best-effort accounting update for a running or finished job. Same
    swallow-but-log rationale as ``update_job_progress``.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(accounting=accounting)
            )
            await session.commit()
    except Exception:
        logger.warning("Failed to update accounting for job %s", job_id, exc_info=True)


@dataclass
class JobAccountingTracker:
    """Accumulates token usage, duration, call counts, and dollar cost."""

    job_id: int
    model: str = ""
    call_count: int = 0
    prompt_tokens: int | None = 0
    completion_tokens: int | None = 0
    total_tokens: int | None = 0
    duration_ms: int = 0
    estimated_cost_usd: float | None = 0.0

    def record_call(
        self,
        *,
        model: str,
        prompt_tokens: int | None = 0,
        completion_tokens: int | None = 0,
        duration_ms: int = 0,
    ) -> None:
        self.call_count += 1
        if model:
            self.model = model

        # Once any call reports unknown usage, the running total is unknown
        # too -- there is no way to partially recover it later.
        if prompt_tokens is None or self.prompt_tokens is None:
            self.prompt_tokens = None
        else:
            self.prompt_tokens += max(0, prompt_tokens)

        if completion_tokens is None or self.completion_tokens is None:
            self.completion_tokens = None
        else:
            self.completion_tokens += max(0, completion_tokens)

        if self.prompt_tokens is None or self.completion_tokens is None:
            self.total_tokens = None
        else:
            self.total_tokens = self.prompt_tokens + self.completion_tokens

        self.duration_ms += max(0, duration_ms or 0)
        self.estimated_cost_usd = calculate_cost(
            self.model, self.prompt_tokens, self.completion_tokens
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    async def flush(self) -> None:
        await update_job_accounting(self.job_id, self.to_dict())


class ProgressTracker:
    """Accumulates batch counts across one or more sequential phases."""

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
