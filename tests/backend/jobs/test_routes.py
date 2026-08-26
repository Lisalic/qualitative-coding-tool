"""Tests for ``GET /api/jobs/{id}`` (backend/app/jobs/routes.py)."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.database import User
from backend.app.jobs.models import Job


def _auth_headers(make_token, sub="1"):
    return {"Authorization": f"Bearer {make_token(sub=sub)}"}


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


async def _create_user_and_job(SessionLocal, *, user_email: str, **job_kwargs) -> tuple[int, int]:
    async with SessionLocal() as session:
        user = User(email=user_email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        job_kwargs.setdefault("status", "pending")
        job_kwargs.setdefault("payload", {})
        job = Job(user_id=user.id, job_type="test_noop", **job_kwargs)
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return user.id, job.id


@pytest.mark.usefixtures("override_async_db")
class TestGetJobStatus:
    async def test_requires_auth(self, client, SessionLocal) -> None:
        _, job_id = await _create_user_and_job(SessionLocal, user_email="owner@example.com")
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 401

    async def test_404_for_missing_job(self, client, make_token) -> None:
        resp = client.get("/api/jobs/999999", headers=_auth_headers(make_token, sub="1"))
        assert resp.status_code == 404

    async def test_403_for_someone_elses_job(self, client, make_token, SessionLocal) -> None:
        owner_id, job_id = await _create_user_and_job(SessionLocal, user_email="owner2@example.com")
        # Authenticate as a different user id than the job's owner.
        other_sub = str(owner_id + 1)
        resp = client.get(f"/api/jobs/{job_id}", headers=_auth_headers(make_token, sub=other_sub))
        assert resp.status_code == 403

    async def test_200_with_expected_shape_for_owner(self, client, make_token, SessionLocal) -> None:
        owner_id, job_id = await _create_user_and_job(
            SessionLocal,
            user_email="owner3@example.com",
            status="succeeded",
            result={"echo": {"a": 1}},
        )
        resp = client.get(
            f"/api/jobs/{job_id}", headers=_auth_headers(make_token, sub=str(owner_id))
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == job_id
        assert body["job_type"] == "test_noop"
        assert body["status"] == "succeeded"
        assert body["result"] == {"echo": {"a": 1}}
        assert body["error"] is None
        assert body["error_code"] is None
        assert body["progress"] is None
        assert set(body.keys()) == {
            "id",
            "job_type",
            "status",
            "result",
            "progress",
            "error",
            "error_code",
            "created_at",
            "started_at",
            "finished_at",
        }
