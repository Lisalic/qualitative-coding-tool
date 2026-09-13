"""Tests for QC-006: explicit partial-job semantics, cancellation, and empty output handling."""

import asyncio
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import User
from backend.app.external.errors import ExternalServiceError
from backend.app.jobs import service
from backend.app.jobs.models import Job, TERMINAL_STATUSES
from backend.app.jobs.registry import register_handler

pytestmark = pytest.mark.usefixtures("override_async_db")


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def patch_all_sessions(monkeypatch, SessionLocal):
    monkeypatch.setattr("backend.app.jobs.service.AsyncSessionLocal", SessionLocal)
    monkeypatch.setattr("backend.app.jobs.progress.AsyncSessionLocal", SessionLocal)


@pytest.fixture()
async def session(SessionLocal):
    async with SessionLocal() as s:
        yield s


@pytest.fixture()
async def user_id(session) -> int:
    user = User(email="partial-user@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


@register_handler("test_partial_salvage")
async def _partial_handler(job_id: int, payload: dict) -> dict:
    return {
        "status": "partial",
        "salvaged_output": [{"id": 1, "text": "salvaged entry"}],
        "partial_reason": "Batch 2 timed out; salvaged 1 batch",
    }


@register_handler("test_empty_output")
async def _empty_output_handler(job_id: int, payload: dict) -> dict:
    return {}


@register_handler("test_transient_error")
async def _transient_handler(job_id: int, payload: dict) -> dict:
    raise ExternalServiceError("Rate limit exceeded", code=429)


@register_handler("test_slow_cancelable")
async def _slow_handler(job_id: int, payload: dict) -> dict:
    await asyncio.sleep(5.0)
    return {"done": True}


async def _wait_terminal(session, job_id: int, user_id: int, timeout: float = 3.0) -> Job:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        session.expire_all()
        job = await service.get_job(session, job_id, user_id)
        if job.status in ("succeeded", "completed", "partial", "retryable_failure", "failed", "cancelled"):
            return job
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"Job {job_id} did not complete within {timeout}s")
        await asyncio.sleep(0.01)


async def test_job_partial_status_preserves_salvaged_output(session, user_id):
    job = await service.enqueue_job(
        session, user_id=user_id, job_type="test_partial_salvage", payload={}
    )
    refreshed = await _wait_terminal(session, job.id, user_id)
    assert refreshed.status == "partial"
    assert refreshed.salvaged_output == [{"id": 1, "text": "salvaged entry"}]
    assert "salvaged 1 batch" in refreshed.error


async def test_job_empty_output_fails_loudly(session, user_id):
    job = await service.enqueue_job(
        session, user_id=user_id, job_type="test_empty_output", payload={}
    )
    refreshed = await _wait_terminal(session, job.id, user_id)
    assert refreshed.status == "failed"
    assert "empty output" in refreshed.error.lower()


async def test_job_retryable_transient_error(session, user_id):
    job = await service.enqueue_job(
        session, user_id=user_id, job_type="test_transient_error", payload={}
    )
    refreshed = await _wait_terminal(session, job.id, user_id)
    assert refreshed.status == "retryable_failure"
    assert refreshed.error_code == 429


async def test_job_cancellation(session, user_id):
    job = await service.enqueue_job(
        session, user_id=user_id, job_type="test_slow_cancelable", payload={}
    )
    await asyncio.sleep(0.05)
    cancelled = await service.cancel_job(session, job.id, user_id)
    assert cancelled.status == "cancelled"

    refreshed = await _wait_terminal(session, job.id, user_id)
    assert refreshed.status == "cancelled"


async def test_cancel_job_does_not_relabel_partial_job(session, user_id):
    """Regression test: cancel_job must not relabel a terminal 'partial' job as 'cancelled'."""
    job = await service.enqueue_job(
        session, user_id=user_id, job_type="test_partial_salvage", payload={}
    )
    refreshed = await _wait_terminal(session, job.id, user_id)
    assert refreshed.status == "partial"

    # Attempt to cancel after reaching partial terminal state
    attempted_cancel = await service.cancel_job(session, job.id, user_id)
    assert attempted_cancel.status == "partial"
    assert attempted_cancel.salvaged_output == [{"id": 1, "text": "salvaged entry"}]


async def test_cancel_job_does_not_relabel_retryable_failure_job(session, user_id):
    """Regression test: cancel_job must not relabel a terminal 'retryable_failure' job as 'cancelled'."""
    job = await service.enqueue_job(
        session, user_id=user_id, job_type="test_transient_error", payload={}
    )
    refreshed = await _wait_terminal(session, job.id, user_id)
    assert refreshed.status == "retryable_failure"

    # Attempt to cancel after reaching retryable_failure terminal state
    attempted_cancel = await service.cancel_job(session, job.id, user_id)
    assert attempted_cancel.status == "retryable_failure"
    assert attempted_cancel.error_code == 429


async def test_cancellation_race_condition_does_not_corrupt_terminal_state(session, user_id):
    """Regression test: if a job reaches terminal state or is cancelled concurrently,
    conditional updates prevent relabeling.
    """
    job = Job(job_type="test_manual", user_id=user_id, status="partial", payload={})
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Calling cancel_job on terminal state is guarded
    result = await service.cancel_job(session, job.id, user_id)
    assert result.status == "partial"

    # Direct atomic check: Job.status.notin_(TERMINAL_STATUSES) prevents update
    stmt = (
        update(Job)
        .where(
            Job.id == job.id,
            Job.user_id == user_id,
            Job.status.notin_(TERMINAL_STATUSES),
        )
        .values(status="succeeded")
    )
    res = await session.execute(stmt)
    assert res.rowcount == 0  # Not updated because job was already terminal
