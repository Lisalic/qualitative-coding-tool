"""In-process, fire-and-forget coroutine runner for background jobs.

Sits behind a ``Protocol`` (per global design decision #7 in the refactor
plan) so a future broker-backed implementation (Celery/RQ/...) can replace
``AsyncioJobRunner`` without any caller (``jobs/service.py::enqueue_job``)
changing.
"""

import asyncio
from typing import Any, Awaitable, Protocol


class JobRunner(Protocol):
    def submit(self, coro: Awaitable[None], job_id: int | None = None) -> Any:
        """Schedule ``coro`` to run in the background. Does not await it."""
        ...

    def cancel(self, job_id: int) -> bool:
        """Cancel a running background job task if active."""
        ...


class AsyncioJobRunner:
    """``JobRunner`` backed by ``asyncio.create_task`` with cancellation tracking."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()
        self._tasks_by_job_id: dict[int, asyncio.Task] = {}

    def submit(self, coro: Awaitable[None], job_id: int | None = None) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        if job_id is not None:
            self._tasks_by_job_id[job_id] = task

        def _cleanup(t: asyncio.Task) -> None:
            self._tasks.discard(t)
            if job_id is not None:
                self._tasks_by_job_id.pop(job_id, None)

        task.add_done_callback(_cleanup)
        return task

    def cancel(self, job_id: int) -> bool:
        task = self._tasks_by_job_id.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False


_runner: JobRunner = AsyncioJobRunner()


def get_job_runner() -> JobRunner:
    return _runner
