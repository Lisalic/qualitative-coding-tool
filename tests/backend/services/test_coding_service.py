"""Unit tests for backend/app/services/coding_service.py -- the Stage 4
job-queue pilot (``summarize-coding``).

Covers both halves of the pattern this stage establishes (and that later
stages reuse verbatim): the synchronous kickoff/validation function
(``start_summarize_coding_job``) and the background job handler
(``_run_summarize_coding_job``, registered as job_type
``"summarize_coding"``), exercised end-to-end via the real
``jobs/service.py`` pipeline -- same style as
``tests/backend/jobs/test_service.py``, but with the real handler instead
of a synthetic one.
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import File, FileDependency, User
from backend.app.jobs import service as jobs_service
from backend.app.repositories import artifact_content_repo
from backend.app.services import coding_service
from backend.app.storage_models import ArtifactContent, CodingEntry, Submission


async def _wait_for_terminal_status(session, job_id: int, user_id: int, timeout: float = 5.0):
    """Same polling helper as tests/backend/jobs/test_service.py -- see
    that module's docstring for why a real (short) sleep-and-poll loop is
    used instead of a fixed number of no-op yields.
    """
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        session.expire_all()
        job = await jobs_service.get_job(session, job_id, user_id)
        if job.status in ("succeeded", "failed"):
            return job
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"job {job_id} did not reach a terminal status within {timeout}s")
        await asyncio.sleep(0.01)


@pytest.fixture()
def SessionLocal(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def patch_async_session_local(monkeypatch, SessionLocal):
    """``_execute_job`` opens its own session via the module-level
    ``AsyncSessionLocal`` imported into ``backend.app.jobs.service`` --
    point that at the in-memory SQLite engine backing this test's session.
    Stage 8's ``_run_apply_codebook_job``/``_run_compare_codings_job``
    handlers open their own sessions the same way, via the module-level
    ``AsyncSessionLocal`` imported into ``backend.app.services.coding_service``.
    """
    monkeypatch.setattr("backend.app.jobs.service.AsyncSessionLocal", SessionLocal)
    monkeypatch.setattr("backend.app.services.coding_service.AsyncSessionLocal", SessionLocal)


@pytest.fixture()
async def session(SessionLocal):
    async with SessionLocal() as s:
        yield s


@pytest.fixture()
async def user_id(session) -> int:
    user = User(email="coding-service-test@example.com", password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


async def _make_user(session, email: str) -> int:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


async def _make_file(
    session,
    owner_id: int,
    *,
    file_type: str = "coding",
    schemaname: str = "proj_a",
    content: str | None = None,
) -> File:
    """Insert a ``File`` (optionally with an ``artifact_content`` row)
    directly via the ORM, owned by ``owner_id``.
    """
    file_rec = File(user_id=owner_id, filename="f", schemaname=schemaname, file_type=file_type)
    session.add(file_rec)
    await session.flush()
    if content is not None:
        session.add(ArtifactContent(file_id=file_rec.id, content=content))
    await session.commit()
    await session.refresh(file_rec)
    return file_rec


class TestStartSummarizeCodingJobValidation:
    """``start_summarize_coding_job`` must reject bad input with the same
    400-shaped errors the old synchronous route did, before ever touching
    the session or enqueuing a background job.
    """

    async def test_non_proj_schema_raises_before_touching_session(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError, match="proj_"):
            await coding_service.start_summarize_coding_job(
                session,
                user_id,
                coding="not_proj",
                api_key="k",
                model=None,
                prompt="",
                name="my summary",
            )

    async def test_missing_api_key_raises(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError, match="api_key"):
            await coding_service.start_summarize_coding_job(
                session,
                user_id,
                coding="proj_a",
                api_key="",
                model=None,
                prompt="",
                name="my summary",
            )

    async def test_blank_name_raises(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError, match="name"):
            await coding_service.start_summarize_coding_job(
                session,
                user_id,
                coding="proj_a",
                api_key="k",
                model=None,
                prompt="",
                name="   ",
            )

    async def test_unowned_coding_raises_not_found(self, session, user_id) -> None:
        """Regression coverage: the old handler never checked that
        ``coding`` resolved to a file owned by the caller at all -- it
        only validated the ``proj_<id>`` shape and read straight from that
        Postgres schema. Resolving a ``source_file_id`` for the new
        summary's ``FileDependency`` link closes that gap.
        """
        with pytest.raises(NotFoundError):
            await coding_service.start_summarize_coding_job(
                session,
                user_id,
                coding="proj_missing",
                api_key="k",
                model=None,
                prompt="",
                name="my summary",
            )


class TestStartSummarizeCodingJobEnqueue:
    async def test_enqueues_pending_job_without_persisting_api_key(
        self, session, user_id, monkeypatch
    ) -> None:
        source_file = await _make_file(session, user_id, schemaname="proj_a", content="coded rows")
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.summarize_coding",
            AsyncMock(return_value="a summary"),
        )

        job = await coding_service.start_summarize_coding_job(
            session,
            user_id,
            coding="proj_a",
            api_key="sk-secret",
            model="some-model",
            prompt="be concise",
            name="my summary",
        )
        job_id = job.id

        assert job.status == "pending"
        assert job.job_type == "summarize_coding"
        # payload persisted to the jobs table must never contain the key
        assert job.payload == {
            "user_id": user_id,
            "schema": "proj_a",
            "prompt": "be concise",
            "model": "some-model",
            "source_file_id": source_file.id,
            "name": "my summary",
            "description": None,
            "project_id": None,
        }
        assert "api_key" not in job.payload

        # Drain the background task before the test (and its SQLite engine
        # fixture) tears down, so it doesn't race the engine's dispose().
        await _wait_for_terminal_status(session, job_id, user_id)


class TestSummarizeCodingJobHandlerEndToEnd:
    """Runs the real ``_run_summarize_coding_job`` handler through the real
    ``jobs/service.py`` pipeline (enqueue -> background execution ->
    terminal status), with only the LLM call and the raw-SQL content read
    mocked out.
    """

    async def test_succeeds_and_stores_summary_result(self, session, user_id, monkeypatch) -> None:
        source_file = await _make_file(
            session, user_id, schemaname="proj_a", content="post_1: CODE_A - evidence"
        )
        source_file_id = source_file.id
        summarize_mock = AsyncMock(return_value="the final summary")
        monkeypatch.setattr("backend.scripts.summarize_coding.summarize_coding", summarize_mock)

        job = await coding_service.start_summarize_coding_job(
            session,
            user_id,
            coding="proj_a",
            api_key="sk-secret",
            model=None,
            prompt="",
            name="my summary",
            description="  notes  ",
        )
        job_id = job.id

        finished = await _wait_for_terminal_status(session, job_id, user_id)
        assert finished.status == "succeeded", finished.error
        assert finished.result["summary"] == "the final summary"
        file_info = finished.result["file"]
        assert file_info["filename"] == "my summary"
        assert file_info["schema_name"].startswith("sum_")
        assert finished.error is None

        # The mocked LLM call actually received the API key -- proves
        # runtime_extra reached the handler even though it was never
        # persisted on the job row (see the enqueue test above).
        assert summarize_mock.called
        call_args = summarize_mock.call_args.args
        assert call_args[2] == "sk-secret"

        new_file_id = int(file_info["id"])
        new_file = await session.get(File, new_file_id)
        assert new_file.file_type == "summary"
        assert new_file.description == "notes"

        content = await artifact_content_repo.read_content(session, new_file_id)
        assert content == "the final summary"

        deps = (
            await session.execute(
                select(FileDependency).where(FileDependency.child_file_id == new_file_id)
            )
        ).scalars().all()
        assert [d.parent_file_id for d in deps] == [source_file_id]

    async def test_no_content_marks_job_failed(self, session, user_id, monkeypatch) -> None:
        # No `content=` -- the source file has no artifact_content row at all.
        await _make_file(session, user_id, schemaname="proj_a")
        summarize_mock = AsyncMock(return_value="should not be called")
        monkeypatch.setattr("backend.scripts.summarize_coding.summarize_coding", summarize_mock)

        job = await coding_service.start_summarize_coding_job(
            session,
            user_id,
            coding="proj_a",
            api_key="sk-secret",
            model=None,
            prompt="",
            name="my summary",
        )
        job_id = job.id

        finished = await _wait_for_terminal_status(session, job_id, user_id)
        assert finished.status == "failed"
        assert "No content found" in finished.error
        assert not summarize_mock.called


# ---------------------------------------------------------------------------
# get_coded_data (Stage 8)
# ---------------------------------------------------------------------------


class TestGetCodedData:
    async def test_returns_most_recent_when_no_coded_id_given(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_1", content="first")
        second = await _make_file(session, user_id, schemaname="proj_2", content="second")

        file_rec, content, codebook_text = await coding_service.get_coded_data(session, user_id, None)
        assert file_rec.id == second.id
        assert content == "second"
        assert codebook_text == ""

    async def test_resolves_by_schema_name(self, session, user_id) -> None:
        file_rec = await _make_file(session, user_id, schemaname="proj_x", content="x content")

        resolved, content, _ = await coding_service.get_coded_data(session, user_id, "proj_x")
        assert resolved.id == file_rec.id
        assert content == "x content"

    async def test_no_file_raises_not_found(self, session, user_id) -> None:
        with pytest.raises(NotFoundError):
            await coding_service.get_coded_data(session, user_id, None)

    async def test_missing_content_raises_not_found(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_empty", content=None)
        with pytest.raises(NotFoundError):
            await coding_service.get_coded_data(session, user_id, "proj_empty")

    async def test_scoped_to_owner_closing_the_old_cross_user_gap(self, session, user_id) -> None:
        """The old ``_resolve_coding_file_record`` queried across *every*
        user's coding files -- both for a specific ``coded_id`` and for
        the "no id given" most-recent fallback. Both are scoped to
        ``user_id`` now.
        """
        other_id = await _make_user(session, "other-get-coded@example.com")
        await _make_file(session, other_id, schemaname="proj_other", content="not yours")

        with pytest.raises(NotFoundError):
            await coding_service.get_coded_data(session, user_id, "proj_other")
        with pytest.raises(NotFoundError):
            await coding_service.get_coded_data(session, user_id, None)

    async def test_includes_parent_codebook_text_via_file_dependency(self, session, user_id) -> None:
        codebook_file = await _make_file(
            session, user_id, file_type="codebook", schemaname="proj_cb", content="codebook text"
        )
        coding_file = await _make_file(session, user_id, schemaname="proj_c", content="coding text")
        session.add(FileDependency(child_file_id=coding_file.id, parent_file_id=codebook_file.id))
        await session.commit()

        _, content, codebook_text = await coding_service.get_coded_data(session, user_id, "proj_c")
        assert content == "coding text"
        assert codebook_text == "codebook text"


# ---------------------------------------------------------------------------
# save_project_coded_data (Stage 8)
# ---------------------------------------------------------------------------


class TestSaveProjectCodedData:
    async def test_missing_schema_name_raises_validation_error(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError):
            await coding_service.save_project_coded_data(
                session, user_id, schema_name="", content="x", display_name=None
            )

    async def test_missing_content_raises_validation_error(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError):
            await coding_service.save_project_coded_data(
                session, user_id, schema_name="proj_a", content="", display_name=None
            )

    async def test_unowned_schema_raises_not_found(self, session, user_id) -> None:
        other_id = await _make_user(session, "other-save-coded@example.com")
        await _make_file(session, other_id, schemaname="proj_not_yours")

        with pytest.raises(NotFoundError):
            await coding_service.save_project_coded_data(
                session, user_id, schema_name="proj_not_yours", content="x", display_name=None
            )

    async def test_overwrites_content_and_optionally_renames(self, session, user_id) -> None:
        file_rec = await _make_file(session, user_id, schemaname="proj_s", content="old")

        result = await coding_service.save_project_coded_data(
            session, user_id, schema_name="proj_s", content="new content", display_name="renamed"
        )

        assert result.id == file_rec.id
        assert result.filename == "renamed"
        stored = await artifact_content_repo.read_content(session, file_rec.id)
        assert stored == "new content"

    async def test_no_display_name_leaves_filename_unchanged(self, session, user_id) -> None:
        file_rec = await _make_file(session, user_id, schemaname="proj_s2", content="old")

        result = await coding_service.save_project_coded_data(
            session, user_id, schema_name="proj_s2", content="new", display_name=None
        )
        assert result.filename == file_rec.filename


# ---------------------------------------------------------------------------
# save_project_coded_data_duplicate (Stage 8)
# ---------------------------------------------------------------------------


class TestSaveProjectCodedDataDuplicate:
    async def test_missing_fields_raise_validation_error(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError):
            await coding_service.save_project_coded_data_duplicate(
                session, user_id, source_schema_name="", content="x", display_name="y"
            )
        with pytest.raises(ValidationAppError):
            await coding_service.save_project_coded_data_duplicate(
                session, user_id, source_schema_name="proj_a", content="", display_name="y"
            )
        with pytest.raises(ValidationAppError):
            await coding_service.save_project_coded_data_duplicate(
                session, user_id, source_schema_name="proj_a", content="x", display_name=""
            )

    async def test_unowned_source_raises_not_found(self, session, user_id) -> None:
        other_id = await _make_user(session, "other-dup@example.com")
        await _make_file(session, other_id, schemaname="proj_belongs_to_other")

        with pytest.raises(NotFoundError):
            await coding_service.save_project_coded_data_duplicate(
                session,
                user_id,
                source_schema_name="proj_belongs_to_other",
                content="x",
                display_name="y",
            )

    async def test_clones_content_project_links_and_dependencies(self, session, user_id) -> None:
        from backend.app.database import async_link_file_to_project
        from backend.app.database import Project

        codebook_file = await _make_file(session, user_id, file_type="codebook", schemaname="proj_cb2")
        raw_file = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw")
        source_file = await _make_file(session, user_id, schemaname="proj_source", content="src content")
        session.add_all(
            [
                FileDependency(child_file_id=source_file.id, parent_file_id=codebook_file.id),
                FileDependency(child_file_id=source_file.id, parent_file_id=raw_file.id),
            ]
        )
        project = Project(user_id=user_id, projectname="p1")
        session.add(project)
        await session.flush()
        await async_link_file_to_project(session, source_file.id, project.id)
        await session.commit()

        new_file = await coding_service.save_project_coded_data_duplicate(
            session,
            user_id,
            source_schema_name="proj_source",
            content="dup content",
            display_name="dup name",
        )

        assert new_file.filename == "dup name"
        assert new_file.id != source_file.id
        assert new_file.systemprompt == source_file.systemprompt

        stored = await artifact_content_repo.read_content(session, new_file.id)
        assert stored == "dup content"

        deps = (
            await session.execute(select(FileDependency).where(FileDependency.child_file_id == new_file.id))
        ).scalars().all()
        parent_ids = {d.parent_file_id for d in deps}
        # Lineage preserved via copied FileDependency rows -- the source's
        # own parents (codebook + raw data) AND the source file itself --
        # no redundant codebook-text copy involved.
        assert parent_ids == {codebook_file.id, raw_file.id, source_file.id}

        from sqlalchemy.orm import selectinload

        new_file_id = new_file.id
        project_id = project.id
        session.expire_all()
        reloaded = await session.execute(
            select(File).where(File.id == new_file_id).options(selectinload(File.projects))
        )
        new_file_reloaded = reloaded.scalar_one()
        assert {p.id for p in new_file_reloaded.projects} == {project_id}


# ---------------------------------------------------------------------------
# start_apply_codebook_job -- validation + enqueue (Stage 8)
# ---------------------------------------------------------------------------


class TestStartApplyCodebookJobValidation:
    async def test_missing_api_key_raises(self, session, user_id) -> None:
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw2")
        codebook_file = await _make_file(
            session, user_id, file_type="codebook", schemaname="proj_cb3", content="cb"
        )
        with pytest.raises(ValidationAppError, match="api_key"):
            await coding_service.start_apply_codebook_job(
                session,
                user_id,
                database=source.schemaname,
                codebook=str(codebook_file.id),
                methodology="",
                api_key="",
                model=None,
                sample_percentage=100.0,
                report_name="r",
                project_id=None,
            )

    async def test_unowned_database_raises_not_found(self, session, user_id) -> None:
        with pytest.raises(NotFoundError):
            await coding_service.start_apply_codebook_job(
                session,
                user_id,
                database="proj_missing",
                codebook="1",
                methodology="",
                api_key="k",
                model=None,
                sample_percentage=100.0,
                report_name="r",
                project_id=None,
            )

    async def test_unowned_codebook_raises_not_found(self, session, user_id) -> None:
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw3")
        with pytest.raises(NotFoundError):
            await coding_service.start_apply_codebook_job(
                session,
                user_id,
                database=source.schemaname,
                codebook="proj_missing_cb",
                methodology="",
                api_key="k",
                model=None,
                sample_percentage=100.0,
                report_name="r",
                project_id=None,
            )

    async def test_codebook_owned_by_another_user_raises_not_found(self, session, user_id) -> None:
        """The old ``_resolve_codebook_schema`` trusted a ``proj_``-prefixed
        ``codebook`` value with no ownership check at all -- only the
        numeric-id form was ever verified. Both forms are ownership-scoped
        via ``file_repo`` now.
        """
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw3b")
        other_id = await _make_user(session, "other-codebook@example.com")
        other_codebook = await _make_file(
            session, other_id, file_type="codebook", schemaname="proj_not_mine", content="cb"
        )
        with pytest.raises(NotFoundError):
            await coding_service.start_apply_codebook_job(
                session,
                user_id,
                database=source.schemaname,
                codebook=other_codebook.schemaname,
                methodology="",
                api_key="k",
                model=None,
                sample_percentage=100.0,
                report_name="r",
                project_id=None,
            )


class TestStartApplyCodebookJobEnqueue:
    async def test_enqueues_pending_job_without_persisting_api_key(self, session, user_id) -> None:
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw_enq")
        codebook_file = await _make_file(
            session, user_id, file_type="codebook", schemaname="proj_cb_enq", content="cb text"
        )

        job = await coding_service.start_apply_codebook_job(
            session,
            user_id,
            database=source.schemaname,
            codebook=str(codebook_file.id),
            methodology="be thorough",
            api_key="sk-secret",
            model="m",
            sample_percentage=100.0,
            report_name="r",
            project_id=None,
        )

        assert job.status == "pending"
        assert job.job_type == "apply_codebook"
        assert job.payload["source_file_id"] == source.id
        assert job.payload["codebook_file_id"] == codebook_file.id
        assert "api_key" not in job.payload
        # Enqueue behavior is fully asserted above; deliberately not waiting
        # for the background job to finish here -- it would make a real
        # (failing) OpenRouter call with this test's fake api_key. The full
        # execution path, mocked, is covered by
        # TestApplyCodebookJobHandlerEndToEnd below.


# ---------------------------------------------------------------------------
# _run_apply_codebook_job -- end-to-end, including coding_entries (Stage 8)
# ---------------------------------------------------------------------------


class TestApplyCodebookJobHandlerEndToEnd:
    async def test_populates_artifact_content_and_coding_entries(self, session, user_id, monkeypatch) -> None:
        """The realistic multi-post, multi-code case: `classify_posts`'s
        canonical POST_ID:/CODE:/EVIDENCE: output must be parsed into one
        `coding_entries` row per (post_id, code) pair -- proving the
        "no redundant codebook copy, but real structured coding_entries
        now exist" trade this stage makes.
        """
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw4")
        session.add_all(
            [
                Submission(file_id=source.id, id="s1", title="t1", selftext="body1", word_count=5),
                Submission(file_id=source.id, id="s2", title="t2", selftext="body2", word_count=5),
            ]
        )
        await session.commit()

        codebook_file = await _make_file(
            session, user_id, file_type="codebook", schemaname="proj_cb4", content="CODEBOOK TEXT"
        )

        classification_output = (
            "POST_ID: s1\n"
            "CODE: Alpha\n"
            'EVIDENCE: "quote one"\n'
            "CODE: Beta\n"
            'EVIDENCE: "quote two"\n'
            "\n"
            "POST_ID: s2\n"
            "CODE: Alpha\n"
            'EVIDENCE: "quote three"\n'
        )
        classify_mock = AsyncMock(return_value=(classification_output, "sys prompt", "user prompt"))
        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", classify_mock)

        # Capture ids before _wait_for_terminal_status's session.expire_all()
        # -- accessing an ORM attribute on an expired instance afterward
        # triggers an implicit lazy-load that isn't valid on an AsyncSession
        # outside an awaited call (see conftest.py's _expire_all docstring).
        source_id = source.id
        codebook_file_id = codebook_file.id

        job = await coding_service.start_apply_codebook_job(
            session,
            user_id,
            database=source.schemaname,
            codebook=str(codebook_file_id),
            methodology="be thorough",
            api_key="sk-secret",
            model="m",
            sample_percentage=100.0,
            report_name="my report",
            project_id=None,
        )

        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error
        result = finished.result
        assert result["classification_output"] == classification_output
        new_file_id = int(result["file"]["id"])
        assert result["file"]["filename"] == "my report"

        stored_content = await artifact_content_repo.read_content(session, new_file_id)
        assert stored_content == classification_output

        entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file_id))
        ).scalars().all()
        by_key = {(e.post_id, e.code): e.evidence for e in entries}
        assert by_key == {
            ("s1", "Alpha"): '"quote one"',
            ("s1", "Beta"): '"quote two"',
            ("s2", "Alpha"): '"quote three"',
        }

        deps = (
            await session.execute(select(FileDependency).where(FileDependency.child_file_id == new_file_id))
        ).scalars().all()
        parent_ids = {d.parent_file_id for d in deps}
        assert parent_ids == {source_id, codebook_file_id}

        # api_key never persisted to the jobs table, but did reach
        # classify_posts via runtime_extra.
        assert "api_key" not in job.payload
        assert classify_mock.called
        call_args = classify_mock.call_args.args
        assert call_args[0] == "CODEBOOK TEXT"
        assert call_args[3] == "sk-secret"

    async def test_merges_evidence_for_repeated_post_code_pairs(self, session, user_id, monkeypatch) -> None:
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw4b")
        session.add(Submission(file_id=source.id, id="s1", title="t", selftext="b", word_count=2))
        await session.commit()
        codebook_file = await _make_file(
            session, user_id, file_type="codebook", schemaname="proj_cb4b", content="CB"
        )

        classification_output = (
            "POST_ID: s1\n"
            "CODE: Alpha\n"
            'EVIDENCE: "one"\n'
            "POST_ID: s1\n"
            "CODE: Alpha\n"
            'EVIDENCE: "two"\n'
        )
        monkeypatch.setattr(
            "backend.app.services.coding_service.classify_posts",
            AsyncMock(return_value=(classification_output, "", "")),
        )

        job = await coding_service.start_apply_codebook_job(
            session,
            user_id,
            database=source.schemaname,
            codebook=str(codebook_file.id),
            methodology="",
            api_key="k",
            model=None,
            sample_percentage=100.0,
            report_name="r",
            project_id=None,
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error
        new_file_id = int(finished.result["file"]["id"])

        entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file_id))
        ).scalars().all()
        assert len(entries) == 1
        assert entries[0].evidence == '"one"§"two"'

    async def test_empty_codebook_content_marks_job_failed(self, session, user_id, monkeypatch) -> None:
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw5")
        codebook_file = await _make_file(
            session, user_id, file_type="codebook", schemaname="proj_cb5", content=None
        )
        classify_mock = AsyncMock(return_value=("output", "s", "u"))
        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", classify_mock)

        job = await coding_service.start_apply_codebook_job(
            session,
            user_id,
            database=source.schemaname,
            codebook=str(codebook_file.id),
            methodology="",
            api_key="k",
            model=None,
            sample_percentage=100.0,
            report_name="r",
            project_id=None,
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "failed"
        assert "codebook not found or empty" in finished.error
        assert not classify_mock.called


# ---------------------------------------------------------------------------
# start_compare_codings_job -- validation + enqueue (Stage 8)
# ---------------------------------------------------------------------------


class TestStartCompareCodingsJobValidation:
    async def test_non_proj_schema_raises(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError, match="proj_"):
            await coding_service.start_compare_codings_job(
                session,
                user_id,
                coding_a="not_proj",
                coding_b="proj_b",
                api_key="k",
                model=None,
                prompt="",
                name="my comparison",
            )

    async def test_missing_api_key_raises(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError, match="api_key"):
            await coding_service.start_compare_codings_job(
                session,
                user_id,
                coding_a="proj_a",
                coding_b="proj_b",
                api_key="",
                model=None,
                prompt="",
                name="my comparison",
            )

    async def test_blank_name_raises(self, session, user_id) -> None:
        with pytest.raises(ValidationAppError, match="name"):
            await coding_service.start_compare_codings_job(
                session,
                user_id,
                coding_a="proj_a",
                coding_b="proj_b",
                api_key="k",
                model=None,
                prompt="",
                name="   ",
            )

    async def test_unowned_schema_raises_not_found(self, session, user_id) -> None:
        """The old route had no auth check at all -- now both sides must
        resolve to a coding file owned by ``user_id``.
        """
        with pytest.raises(NotFoundError):
            await coding_service.start_compare_codings_job(
                session,
                user_id,
                coding_a="proj_missing_a",
                coding_b="proj_missing_b",
                api_key="k",
                model=None,
                prompt="",
                name="my comparison",
            )


# ---------------------------------------------------------------------------
# _run_compare_codings_job -- end-to-end (Stage 8)
# ---------------------------------------------------------------------------


class TestCompareCodingsJobHandlerEndToEnd:
    async def test_succeeds_with_mocked_llm(self, session, user_id, monkeypatch) -> None:
        file_a = await _make_file(session, user_id, schemaname="proj_cmp_a", content="coding a text")
        file_b = await _make_file(session, user_id, schemaname="proj_cmp_b", content="coding b text")
        file_a_id, file_b_id = file_a.id, file_b.id
        llm_mock = AsyncMock(return_value="the comparison")
        # compare_codings' handler imports get_client via a LOCAL import
        # inside the handler body, so it must be patched at its source
        # module, not on coding_service.
        monkeypatch.setattr("backend.scripts.codebook_generator.get_client", llm_mock)

        job = await coding_service.start_compare_codings_job(
            session,
            user_id,
            coding_a="proj_cmp_a",
            coding_b="proj_cmp_b",
            api_key="sk-secret",
            model=None,
            prompt="be nice",
            name="coding cmp",
            description="notes",
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error
        assert finished.result["comparison"] == "the comparison"
        file_info = finished.result["file"]
        assert file_info["filename"] == "coding cmp"
        assert file_info["schema_name"].startswith("cmp_")
        assert llm_mock.called
        call_args = llm_mock.call_args.args
        assert call_args[2] == "sk-secret"

        new_file_id = int(file_info["id"])
        new_file = await session.get(File, new_file_id)
        assert new_file.file_type == "coding_comparison"
        assert new_file.description == "notes"

        content = await artifact_content_repo.read_content(session, new_file_id)
        assert content == "the comparison"

        deps = (
            await session.execute(
                select(FileDependency).where(FileDependency.child_file_id == new_file_id)
            )
        ).scalars().all()
        assert {d.parent_file_id for d in deps} == {file_a_id, file_b_id}

    async def test_no_content_marks_job_failed(self, session, user_id, monkeypatch) -> None:
        await _make_file(session, user_id, schemaname="proj_cmp_empty_a", content=None)
        await _make_file(session, user_id, schemaname="proj_cmp_empty_b", content=None)
        llm_mock = AsyncMock(return_value="should not run")
        monkeypatch.setattr("backend.scripts.codebook_generator.get_client", llm_mock)

        job = await coding_service.start_compare_codings_job(
            session,
            user_id,
            coding_a="proj_cmp_empty_a",
            coding_b="proj_cmp_empty_b",
            api_key="k",
            model=None,
            prompt="",
            name="coding cmp",
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "failed"
        assert "No content found" in finished.error
        assert not llm_mock.called
