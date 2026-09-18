"""Tests for backend/app/jobs/progress.py.

``update_job_progress`` opens its own session via the module-level
``AsyncSessionLocal`` imported into ``backend.app.jobs.progress`` -- same
pattern as ``jobs/service.py``'s own handlers -- so these tests point that
at the in-memory SQLite engine the rest of the jobs test suite uses.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import User
from backend.app.jobs.models import Job
from backend.app.jobs.progress import ProgressTracker, update_job_progress


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def patch_async_session_local(monkeypatch, SessionLocal):
    monkeypatch.setattr("backend.app.jobs.progress.AsyncSessionLocal", SessionLocal)


@pytest.fixture()
async def session(SessionLocal):
    async with SessionLocal() as s:
        yield s


@pytest.fixture()
async def job_id(session) -> int:
    user = User(email="progress-test@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    job = Job(job_type="test_progress", user_id=user.id, status="running", payload={})
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job.id


class TestUpdateJobProgress:
    async def test_writes_current_total_and_label(self, session, job_id) -> None:
        await update_job_progress(job_id, 3, 7, label="batches")

        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress == {"current": 3, "total": 7, "label": "batches"}

    async def test_default_label_is_batches(self, session, job_id) -> None:
        await update_job_progress(job_id, 1, 2)

        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress["label"] == "batches"

    async def test_repeated_calls_overwrite_previous_progress(self, session, job_id) -> None:
        await update_job_progress(job_id, 1, 5)
        await update_job_progress(job_id, 5, 5)

        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress == {"current": 5, "total": 5, "label": "batches"}

    async def test_unknown_job_id_does_not_raise(self) -> None:
        # Best-effort: a progress write should never be the reason a job
        # handler's own work fails.
        await update_job_progress(999_999, 1, 1)


class TestProgressTracker:
    async def test_add_total_accumulates_across_phases(self, session, job_id) -> None:
        tracker = ProgressTracker(job_id)
        await tracker.add_total(5)
        await tracker.add_total(2)
        assert tracker.total == 7

    async def test_add_total_writes_immediately_instead_of_waiting_for_first_advance(
        self, session, job_id
    ) -> None:
        # Regression coverage: add_total used to be a plain in-memory
        # counter with no DB write, so `progress` stayed completely blank
        # for as long as the first batch's LLM call was in flight -- which
        # for a large job, a slow model, or a retry/backoff cycle can be
        # minutes, with zero way to tell "waiting on batch 1" apart from
        # "stuck". It must now be visible (as 0/N) the moment batching
        # starts, before any batch has actually completed.
        tracker = ProgressTracker(job_id)
        await tracker.add_total(7)

        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress == {"current": 0, "total": 7, "label": "batches"}

    async def test_advance_increments_current_and_persists(self, session, job_id) -> None:
        tracker = ProgressTracker(job_id)
        await tracker.add_total(3)

        await tracker.advance()
        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress == {"current": 1, "total": 3, "label": "batches"}

        await tracker.advance()
        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress["current"] == 2

    async def test_advance_by_more_than_one(self, session, job_id) -> None:
        tracker = ProgressTracker(job_id)
        await tracker.add_total(10)

        await tracker.advance(4)

        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress["current"] == 4

    async def test_custom_label_is_used(self, session, job_id) -> None:
        tracker = ProgressTracker(job_id, label="posts")
        await tracker.add_total(2)
        await tracker.advance()

        session.expire_all()
        job = await session.get(Job, job_id)
        assert job.progress["label"] == "posts"
