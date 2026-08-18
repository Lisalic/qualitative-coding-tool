"""Full job lifecycle tests: enqueue -> background execution -> terminal
status, plus ``get_job`` ownership checks and startup reconciliation.

Uses a synthetic ``test_noop`` handler (registered here, not in production
code) to prove the whole pipeline end-to-end without any real job type.
"""

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import User
from backend.app.jobs import service
from backend.app.jobs.models import Job
from backend.app.jobs.registry import register_handler


@register_handler("test_noop")
async def _noop_handler(job_id: int, payload: dict) -> dict:
    return {"echo": payload}


@register_handler("test_boom")
async def _boom_handler(job_id: int, payload: dict) -> dict:
    raise ValueError("handler exploded")


async def _yield_to_background_tasks(times: int = 10) -> None:
    for _ in range(times):
        await asyncio.sleep(0)


async def _wait_for_terminal_status(session, job_id: int, user_id: int, timeout: float = 5.0) -> Job:
    """Poll until the background job reaches a terminal status.

    ``aiosqlite`` runs each statement on a worker thread, so a background
    job's DB writes don't necessarily complete within a handful of
    ``asyncio.sleep(0)`` no-op yields -- the event loop needs to actually
    run for a bit to let that thread's result come back. Polling with a
    real (short) sleep and a timeout is more robust than guessing a fixed
    number of ticks.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        _expire_all(session)
        job = await service.get_job(session, job_id, user_id)
        if job.status in ("succeeded", "failed"):
            return job
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"job {job_id} did not reach a terminal status within {timeout}s")
        await asyncio.sleep(0.01)


def _expire_all(session) -> None:
    """``_execute_job`` writes through a *different* session (its own,
    per ``AsyncSessionLocal()``). The test's own ``session`` fixture may
    already have the same row in its identity map from ``enqueue_job``
    (``expire_on_commit=False``), so a plain re-``SELECT`` on it would
    return the stale cached Python object instead of hitting the DB.
    Expire the identity map so the next read is a real fetch.

    NOTE: callers must capture any primary-key ints they need (e.g.
    ``job_id = job.id``) *before* calling this -- accessing an attribute
    on an object expired this way triggers a synchronous lazy-reload that
    isn't valid on an ``AsyncSession`` outside an awaited call.
    """
    session.expire_all()


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def patch_async_session_local(monkeypatch, SessionLocal):
    """``_execute_job``/``reconcile_orphaned_jobs_on_startup`` open their own
    session via the module-level ``AsyncSessionLocal`` imported into
    ``backend.app.jobs.service`` -- point that at the in-memory SQLite
    engine used by this test's own session(s).
    """
    monkeypatch.setattr("backend.app.jobs.service.AsyncSessionLocal", SessionLocal)


@pytest.fixture()
async def session(SessionLocal):
    async with SessionLocal() as s:
        yield s


@pytest.fixture()
async def user_id(session) -> int:
    user = User(email="jobs-test@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


class TestEnqueueJobLifecycle:
    async def test_creates_pending_row_then_succeeds(self, session, user_id) -> None:
        job = await service.enqueue_job(
            session, user_id=user_id, job_type="test_noop", payload={"x": 1}
        )
        assert job.status == "pending"
        assert job.id is not None
        job_id = job.id

        refreshed = await _wait_for_terminal_status(session, job_id, user_id)
        assert refreshed.status == "succeeded"
        assert refreshed.result == {"echo": {"x": 1}}
        assert refreshed.started_at is not None
        assert refreshed.finished_at is not None
        assert refreshed.error is None

    async def test_runtime_extra_reaches_handler_but_not_persisted_payload(
        self, session, user_id
    ) -> None:
        job = await service.enqueue_job(
            session,
            user_id=user_id,
            job_type="test_noop",
            payload={"x": 1},
            runtime_extra={"api_key": "sk-secret"},
        )
        job_id = job.id
        # The persisted row must never contain the secret.
        assert job.payload == {"x": 1}

        refreshed = await _wait_for_terminal_status(session, job_id, user_id)
        # But the handler did receive it, merged into its payload dict.
        assert refreshed.result == {"echo": {"x": 1, "api_key": "sk-secret"}}
        # And the DB row still never got it, even after the job ran.
        assert refreshed.payload == {"x": 1}

    async def test_handler_exception_marks_job_failed(self, session, user_id) -> None:
        job = await service.enqueue_job(
            session, user_id=user_id, job_type="test_boom", payload={}
        )
        job_id = job.id

        refreshed = await _wait_for_terminal_status(session, job_id, user_id)
        assert refreshed.status == "failed"
        assert "handler exploded" in refreshed.error
        assert refreshed.finished_at is not None

    async def test_unregistered_job_type_marks_job_failed(self, session, user_id) -> None:
        job = await service.enqueue_job(
            session, user_id=user_id, job_type="test_never_registered", payload={}
        )
        job_id = job.id

        refreshed = await _wait_for_terminal_status(session, job_id, user_id)
        assert refreshed.status == "failed"
        assert "test_never_registered" in refreshed.error


class TestGetJob:
    async def test_missing_job_raises_not_found(self, session, user_id) -> None:
        with pytest.raises(NotFoundError):
            await service.get_job(session, 999999, user_id)

    async def test_other_users_job_raises_forbidden(self, session, user_id) -> None:
        other = User(email="other-jobs-test@example.com", password="hash")
        session.add(other)
        await session.commit()
        await session.refresh(other)

        job = await service.enqueue_job(
            session, user_id=other.id, job_type="test_noop", payload={}
        )
        job_id = job.id
        await _yield_to_background_tasks()

        with pytest.raises(ForbiddenError):
            await service.get_job(session, job_id, user_id)


class TestReconcileOrphanedJobsOnStartup:
    async def test_empty_table_returns_zero(self, session) -> None:
        assert await service.reconcile_orphaned_jobs_on_startup() == 0

    async def test_flips_pending_and_running_to_failed(self, session, user_id) -> None:
        pending = Job(job_type="test_noop", user_id=user_id, status="pending", payload={})
        running = Job(job_type="test_noop", user_id=user_id, status="running", payload={})
        succeeded = Job(
            job_type="test_noop",
            user_id=user_id,
            status="succeeded",
            payload={},
            result={"ok": True},
        )
        failed = Job(
            job_type="test_noop", user_id=user_id, status="failed", payload={}, error="pre-existing"
        )
        session.add_all([pending, running, succeeded, failed])
        await session.commit()
        await session.refresh(pending)
        await session.refresh(running)
        await session.refresh(succeeded)
        await session.refresh(failed)
        pending_id, running_id, succeeded_id, failed_id = (
            pending.id,
            running.id,
            succeeded.id,
            failed.id,
        )

        count = await service.reconcile_orphaned_jobs_on_startup()
        assert count == 2
        _expire_all(session)

        result = await session.execute(select(Job).where(Job.id == pending_id))
        reconciled_pending = result.scalar_one()
        assert reconciled_pending.status == "failed"
        assert "restarted" in reconciled_pending.error
        assert reconciled_pending.finished_at is not None

        result = await session.execute(select(Job).where(Job.id == running_id))
        reconciled_running = result.scalar_one()
        assert reconciled_running.status == "failed"

        result = await session.execute(select(Job).where(Job.id == succeeded_id))
        untouched_succeeded = result.scalar_one()
        assert untouched_succeeded.status == "succeeded"
        assert untouched_succeeded.result == {"ok": True}

        result = await session.execute(select(Job).where(Job.id == failed_id))
        untouched_failed = result.scalar_one()
        assert untouched_failed.status == "failed"
        assert untouched_failed.error == "pre-existing"
