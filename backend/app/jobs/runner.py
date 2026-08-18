"""In-process, fire-and-forget coroutine runner for background jobs.

Sits behind a ``Protocol`` (per global design decision #7 in the refactor
plan) so a future broker-backed implementation (Celery/RQ/...) can replace
``AsyncioJobRunner`` without any caller (``jobs/service.py::enqueue_job``)
changing.
"""

import asyncio
from typing import Awaitable, Protocol


class JobRunner(Protocol):
    def submit(self, coro: Awaitable[None]) -> None:
        """Schedule ``coro`` to run in the background. Does not await it."""
        ...


class AsyncioJobRunner:
    """``JobRunner`` backed by ``asyncio.create_task``.

    CRITICAL: ``asyncio.create_task`` returns a ``Task`` that is only weakly
    referenced by the event loop -- if nothing else holds a reference to it,
    it can be garbage-collected mid-run, which silently cancels it (a
    well-documented asyncio footgun). This class keeps every created task in
    ``self._tasks`` and removes it via a done-callback once it completes, so
    tasks are never dropped before they finish.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def submit(self, coro: Awaitable[None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


_runner: JobRunner = AsyncioJobRunner()


def get_job_runner() -> JobRunner:
    return _runner
