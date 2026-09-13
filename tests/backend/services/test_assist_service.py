"""Unit tests for backend/app/services/assist_service.py -- the C2
AI-assist provenance channel (closes GAP-4).

The trust boundary under test: a caller names a ``job_id`` and its own
accept/dismiss counts; every provenance fact that matters for an audit
(model, prompts) must come from the referenced ``jobs`` row itself, and
a job that doesn't check out (wrong owner, wrong type, wrong artifact,
not yet succeeded) must be rejected outright rather than recorded.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from backend.app.database import File, User
from backend.app.jobs.models import Job
from backend.app.services import assist_service, version_service
from backend.app.versioning_models import (
    ASSIST_STAGE_CODEBOOK,
    ASSIST_STAGE_CODING,
    ASSIST_STAGE_FILTER,
    ASSIST_STAGE_INTEGRATE,
)


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture()
async def session(SessionLocal):
    async with SessionLocal() as s:
        yield s


@pytest.fixture()
async def user_id(session) -> int:
    user = User(email="assist-service-test@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


async def _make_file_with_version(session, owner_id: int, *, schemaname: str = "proj_a") -> tuple[File, int]:
    file_rec = File(user_id=owner_id, filename="f", schemaname=schemaname, file_type="filtered_data")
    session.add(file_rec)
    await session.flush()
    version = await version_service.commit_data_version(
        session, file_id=file_rec.id, author_user_id=owner_id, origin="edited",
        system_prompt=None, user_instructions=None, prompt_meta=None,
    )
    await session.commit()
    return file_rec, version.id


async def _make_job(
    session,
    *,
    user_id: int,
    job_type: str = "filter_preview",
    status: str = "succeeded",
    payload: dict | None = None,
    result: dict | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        user_id=user_id,
        status=status,
        payload=payload or {},
        result=result,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


class TestRecordAssistRuns:
    async def test_records_a_run_sourcing_model_and_prompts_from_the_job(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session,
            user_id=user_id,
            job_type="filter_preview",
            payload={"source_file_id": 99, "model": "anthropic/claude-x"},
            result={"system_prompt": "sys", "user_instructions": "find complaints", "prompt_meta": {"rendered_chars": 10}},
        )

        created = await assist_service.record_assist_runs(
            session,
            user_id=user_id,
            file_id=file_rec.id,
            version_id=version_id,
            stage=ASSIST_STAGE_FILTER,
            source_file_id=99,
            runs=[{"job_id": job.id, "proposed_count": 5, "accepted_count": 3, "dismissed_count": 2, "accepted_refs": ["submission:s1"]}],
        )

        assert len(created) == 1
        assist = created[0]
        assert assist.model == "anthropic/claude-x"
        assert assist.system_prompt == "sys"
        assert assist.user_instructions == "find complaints"
        assert assist.prompt_meta == {"rendered_chars": 10}
        assert assist.proposed_count == 5
        assert assist.accepted_count == 3
        assert assist.dismissed_count == 2
        assert assist.accepted_refs == ["submission:s1"]
        assert assist.stage == ASSIST_STAGE_FILTER
        assert assist.job_id == job.id

    async def test_ignores_model_and_prompts_sent_by_the_caller(self, session, user_id) -> None:
        """A `run` dict is not trusted for provenance -- only `job_id`,
        counts, and `accepted_refs` are read from it (see the module
        docstring's trust boundary).
        """
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session,
            user_id=user_id,
            job_type="filter_preview",
            payload={"source_file_id": 99, "model": "real-model"},
            result={"system_prompt": "real prompt"},
        )

        created = await assist_service.record_assist_runs(
            session,
            user_id=user_id,
            file_id=file_rec.id,
            version_id=version_id,
            stage=ASSIST_STAGE_FILTER,
            source_file_id=99,
            runs=[{"job_id": job.id, "model": "fabricated-model", "system_prompt": "fabricated prompt"}],
        )

        assert created[0].model == "real-model"
        assert created[0].system_prompt == "real prompt"

    async def test_rejects_a_job_owned_by_someone_else(self, session, user_id) -> None:
        other_user = User(email="other@example.com", password="hash")
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(session, user_id=other_user.id, job_type="filter_preview", payload={"source_file_id": 99})

        with pytest.raises(ForbiddenError):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_FILTER, source_file_id=99, runs=[{"job_id": job.id}],
            )

    async def test_rejects_a_nonexistent_job(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        with pytest.raises(NotFoundError):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_FILTER, source_file_id=99, runs=[{"job_id": 999999}],
            )

    async def test_rejects_the_wrong_job_type(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(session, user_id=user_id, job_type="codebook_preview", payload={"source_file_id": 99})

        with pytest.raises(ValidationAppError, match="codebook_preview"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_FILTER, source_file_id=99, runs=[{"job_id": job.id}],
            )

    async def test_rejects_a_job_that_has_not_succeeded(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session, user_id=user_id, job_type="filter_preview", status="pending", payload={"source_file_id": 99}
        )

        with pytest.raises(ValidationAppError, match="not succeeded"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_FILTER, source_file_id=99, runs=[{"job_id": job.id}],
            )

    async def test_rejects_a_job_run_against_a_different_source(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(session, user_id=user_id, job_type="filter_preview", payload={"source_file_id": 12345})

        with pytest.raises(ValidationAppError, match="source data"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_FILTER, source_file_id=99, runs=[{"job_id": job.id}],
            )

    async def test_recode_job_validated_against_coding_file_id_not_source_file_id(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id, schemaname="proj_coding")
        job = await _make_job(
            session, user_id=user_id, job_type="recode_items",
            payload={"coding_file_id": file_rec.id, "model": "m"}, result={},
        )

        created = await assist_service.record_assist_runs(
            session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
            stage=ASSIST_STAGE_CODING, runs=[{"job_id": job.id}],
        )
        assert created[0].model == "m"

    async def test_recode_job_rejected_against_the_wrong_coding_file(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id, schemaname="proj_coding")
        job = await _make_job(session, user_id=user_id, job_type="recode_items", payload={"coding_file_id": 999})

        with pytest.raises(ValidationAppError, match="coding artifact"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_CODING, runs=[{"job_id": job.id}],
            )

    async def test_empty_runs_is_a_noop(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        created = await assist_service.record_assist_runs(
            session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
            stage=ASSIST_STAGE_FILTER, source_file_id=99, runs=[],
        )
        assert created == []

    async def test_missing_job_id_is_rejected(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        with pytest.raises(ValidationAppError, match="job_id"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_FILTER, source_file_id=99, runs=[{}],
            )


class TestRecordAssistRunsIntegrateStage:
    """ASSIST_STAGE_INTEGRATE's job payload carries source_file_ids (a
    set of N source codebooks), not a single source_file_id -- these
    check the set-equality validation is exact, not containment, so a
    submit can't claim a run that covered a different, larger set of
    codebooks than the ones actually being integrated.
    """

    async def test_accepted_when_source_file_ids_match_exactly(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session, user_id=user_id, job_type="integrate_codebook_preview",
            payload={"source_file_ids": [10, 20], "model": "m"}, result={},
        )

        created = await assist_service.record_assist_runs(
            session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
            stage=ASSIST_STAGE_INTEGRATE, source_file_ids=[10, 20], runs=[{"job_id": job.id}],
        )
        assert created[0].model == "m"
        assert created[0].stage == "integrate"

    async def test_accepted_regardless_of_order(self, session, user_id) -> None:
        # Merge inputs are unordered by construction -- unlike compare's
        # load-bearing side_a/side_b -- so the check must be set equality,
        # not a positional list comparison.
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session, user_id=user_id, job_type="integrate_codebook_preview",
            payload={"source_file_ids": [10, 20], "model": "m"}, result={},
        )

        created = await assist_service.record_assist_runs(
            session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
            stage=ASSIST_STAGE_INTEGRATE, source_file_ids=[20, 10], runs=[{"job_id": job.id}],
        )
        assert created[0].model == "m"

    async def test_rejected_when_the_submit_claims_a_strict_superset(self, session, user_id) -> None:
        # Containment would let a submit for {10, 20} claim a run that
        # actually covered {10, 20, 30} -- a false, broader provenance
        # claim. Set equality refuses this.
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session, user_id=user_id, job_type="integrate_codebook_preview",
            payload={"source_file_ids": [10, 20, 30], "model": "m"}, result={},
        )

        with pytest.raises(ValidationAppError, match="source codebooks"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_INTEGRATE, source_file_ids=[10, 20], runs=[{"job_id": job.id}],
            )

    async def test_rejected_when_the_job_covered_a_different_set(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session, user_id=user_id, job_type="integrate_codebook_preview",
            payload={"source_file_ids": [10, 20], "model": "m"}, result={},
        )

        with pytest.raises(ValidationAppError, match="source codebooks"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_INTEGRATE, source_file_ids=[10, 99], runs=[{"job_id": job.id}],
            )

    async def test_rejected_when_source_file_ids_is_missing(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session, user_id=user_id, job_type="integrate_codebook_preview",
            payload={"source_file_ids": [10, 20], "model": "m"}, result={},
        )

        with pytest.raises(ValidationAppError, match="source codebooks"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_INTEGRATE, runs=[{"job_id": job.id}],
            )

    async def test_rejects_a_codebook_preview_job_claimed_as_integrate(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job = await _make_job(
            session, user_id=user_id, job_type="codebook_preview", payload={"source_file_id": 10},
        )

        with pytest.raises(ValidationAppError, match="codebook_preview"):
            await assist_service.record_assist_runs(
                session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
                stage=ASSIST_STAGE_INTEGRATE, source_file_ids=[10], runs=[{"job_id": job.id}],
            )


class TestResolveAiCoderModel:
    async def test_returns_the_jobs_model(self, session, user_id) -> None:
        file_rec, _ = await _make_file_with_version(session, user_id, schemaname="proj_coding")
        job = await _make_job(
            session, user_id=user_id, job_type="recode_items",
            payload={"coding_file_id": file_rec.id, "model": "openai/gpt-x"},
        )
        model = await assist_service.resolve_ai_coder_model(session, user_id=user_id, file_id=file_rec.id, job_id=job.id)
        assert model == "openai/gpt-x"

    async def test_missing_job_id_is_rejected(self, session, user_id) -> None:
        file_rec, _ = await _make_file_with_version(session, user_id)
        with pytest.raises(ValidationAppError, match="assist_job_id"):
            await assist_service.resolve_ai_coder_model(session, user_id=user_id, file_id=file_rec.id, job_id=None)

    async def test_wrong_coding_file_is_rejected(self, session, user_id) -> None:
        file_rec, _ = await _make_file_with_version(session, user_id, schemaname="proj_coding")
        job = await _make_job(session, user_id=user_id, job_type="recode_items", payload={"coding_file_id": 999})
        with pytest.raises(ValidationAppError):
            await assist_service.resolve_ai_coder_model(session, user_id=user_id, file_id=file_rec.id, job_id=job.id)


class TestListAssists:
    async def test_lists_in_creation_order_with_version_no(self, session, user_id) -> None:
        file_rec, version_id = await _make_file_with_version(session, user_id)
        job1 = await _make_job(session, user_id=user_id, job_type="filter_preview", payload={"source_file_id": 99})
        job2 = await _make_job(session, user_id=user_id, job_type="filter_preview", payload={"source_file_id": 99})

        await assist_service.record_assist_runs(
            session, user_id=user_id, file_id=file_rec.id, version_id=version_id,
            stage=ASSIST_STAGE_FILTER, source_file_id=99,
            runs=[{"job_id": job1.id}, {"job_id": job2.id}],
        )
        await session.commit()

        assists = await assist_service.list_assists(session, file_rec.id)
        assert [a["job_id"] for a in assists] == [job1.id, job2.id]
        assert all(a["stage"] == ASSIST_STAGE_FILTER for a in assists)
        assert all("version_no" in a for a in assists)

    async def test_empty_when_nothing_recorded(self, session, user_id) -> None:
        file_rec, _ = await _make_file_with_version(session, user_id)
        assert await assist_service.list_assists(session, file_rec.id) == []
