"""Unit tests for backend/app/services/coding_service.py.

Covers ``summarize_coding``/``apply_codebook``/``compare_codings``/
``recode_items``'s kickoff-plus-background-job-handler pairs (exercised
end-to-end via the real ``jobs/service.py`` pipeline, same style as
``tests/backend/jobs/test_service.py``), plus the plain read/write
service functions backing the coding-artifact editor
(``get_coding_artifact``, ``list_coding_rows``, ``get_coding_text``,
``save_coding_revision``, ``update_coding_metadata``,
``duplicate_coding``, ``get_coding_comparison``). ``recode_items``'s
handler no longer commits anything itself -- it returns classification
proposals in the job result, which only ``save_coding_revision`` (a
user-triggered Save) ever turns into a version.

Since the coding-artifact overhaul, a ``coding`` file is self-contained:
its own codebook snapshot (``artifact_content``), its own copy of every
sampled submission/comment, and its coding (``coding_entries``, the sole
source of truth -- there is no more classification blob to fall back to).
Per CLAUDE.md's early-prototyping rule there is no compatibility shim for
the old blob-backed behavior; tests exercise the new shape directly.
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.codebook_render import parse_markdown_to_codes
from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import File, User
from backend.app.repositories import version_repo
from backend.app.jobs import service as jobs_service
from backend.app.services import coding_service, file_service, version_service
from backend.app.storage_models import CodingEntry, Submission
from backend.app.versioning_models import ArtifactVersion, CodebookCode


async def _seed_codebook_markdown(session, file_id: int, user_id: int, markdown: str) -> None:
    """Seed a `codebook`/`coding` file's v1 by actually PARSING real
    ``### Code Family:``/``#### Code Name:`` markdown, unlike
    ``_make_file``'s ``content=`` (which wraps arbitrary placeholder text
    as a single fake code's body) -- for tests that need real, separately
    NAMED codes an apply/recode run can reference by name.
    """
    rows = [dict(r) for r in parse_markdown_to_codes(markdown)]
    await version_service.commit_codebook_version(
        session, file_id=file_id, author_user_id=user_id, origin="generated", codes=rows,
    )


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
    ``coding_service``'s job handlers (``_run_apply_codebook_job``/
    ``_run_compare_codings_job``/``_run_summarize_coding_job``/
    ``_run_recode_items_job``) open their own sessions the same way, via
    the module-level ``AsyncSessionLocal`` imported into
    ``backend.app.services.coding_service``.
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
    skip_version: bool = False,
) -> File:
    """Insert a ``File`` directly via the ORM, owned by ``owner_id``, and
    (unless ``skip_version=True``) always give it a v1 -- matching the
    real production invariant that every ``coding``/``codebook`` file is
    created through a job handler that commits one immediately (there is
    no path that creates a bare codebook/coding ``File`` row with zero
    version history). For ``coding``/``codebook``, ``content`` becomes
    the sole seeded code's ``body`` (empty codes list when ``content`` is
    ``None`` -- an "empty codebook", not "no version at all", which is
    what a test asserting on the actual empty-content failure path
    wants); for any other type it's a blob version (``""`` when
    ``content`` is ``None``).

    ``skip_version=True`` opts back into the old "no version at all"
    fixture shape, for the handful of tests that specifically exercise
    what happens when a referenced file has no version history to pin at
    all (a genuinely different failure mode from "empty content").
    """
    file_rec = File(user_id=owner_id, filename="f", schemaname=schemaname, file_type=file_type)
    session.add(file_rec)
    await session.flush()
    if not skip_version:
        if file_type in ("coding", "codebook"):
            codes = (
                [{"code_uid": "u1", "family_uid": "f1", "family_name": "F", "name": "C", "body": content, "position": 0}]
                if content is not None else []
            )
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=owner_id, origin="generated", codes=codes,
            )
        else:
            await version_service.commit_blob_version(
                session, file_id=file_rec.id, author_user_id=owner_id, origin="generated", content=content or "",
            )
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
        source_file = await _make_file(session, user_id, schemaname="proj_a")
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.summarize_coding",
            AsyncMock(return_value=("a summary", {"batches_processed": 1, "batches_total": 1, "error": None})),
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
        # This coding file has no coding_entries rows, so the drained job
        # will actually finish "failed" -- irrelevant here, only draining
        # matters.
        await _wait_for_terminal_status(session, job_id, user_id)


class TestSummarizeCodingJobHandlerEndToEnd:
    """Runs the real ``_run_summarize_coding_job`` handler through the real
    ``jobs/service.py`` pipeline (enqueue -> background execution ->
    terminal status), with only the LLM call mocked out.
    """

    async def test_succeeds_and_stores_summary_result(self, session, user_id, monkeypatch) -> None:
        source_file = await _make_file(session, user_id, schemaname="proj_a")
        source_file_id = source_file.id
        session.add(CodingEntry(file_id=source_file.id, post_id="p1", code="CODE_A", code_uid="CODE_A-uid", quote="e", start_offset=0, end_offset=1))
        await session.commit()

        summarize_mock = AsyncMock(return_value=("the final summary", {"batches_processed": 1, "batches_total": 1, "error": None}))
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

        content = await version_service.read_blob(session, new_file_id)
        assert content == "the final summary"

        edges = await version_repo.list_parent_edges(session, new_file_id)
        assert [e.parent_file_id for e in edges] == [source_file_id]
        assert edges[0].relation == "derived_from"
        assert edges[0].role == "source_data"

    async def test_uses_aggregated_coding_data_from_structured_entries(
        self, session, user_id, monkeypatch
    ) -> None:
        # coding_entries is the sole source of truth for a coding
        # artifact's classification -- the handler builds its LLM input
        # from the SQL-aggregated summary (exact counts + sampled
        # evidence), never from a stored blob.
        source_file = await _make_file(session, user_id, schemaname="proj_a")
        session.add(CodingEntry(file_id=source_file.id, post_id="p1", code="CODE_A", code_uid="CODE_A-uid", quote="e1", start_offset=0, end_offset=2))
        session.add(CodingEntry(file_id=source_file.id, post_id="p2", code="CODE_A", code_uid="CODE_A-uid", quote="e2", start_offset=0, end_offset=2))
        await session.commit()

        summarize_mock = AsyncMock(return_value=("the final summary", {"batches_processed": 1, "batches_total": 1, "error": None}))
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

        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error

        coding_data_arg = summarize_mock.call_args.args[0]
        assert "CODE: CODE_A (used 2 times)" in coding_data_arg
        assert "POST_ID:" not in coding_data_arg

    async def test_no_content_marks_job_failed(self, session, user_id, monkeypatch) -> None:
        # No coding_entries rows at all for this file.
        await _make_file(session, user_id, schemaname="proj_a")
        summarize_mock = AsyncMock(return_value=("should not be called", {"batches_processed": 1, "batches_total": 1, "error": None}))
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
        assert "No coded content found" in finished.error
        assert not summarize_mock.called


# ---------------------------------------------------------------------------
# get_coding_artifact / list_coding_rows / get_coding_text (read paths)
# ---------------------------------------------------------------------------


class TestGetCodingArtifact:
    async def test_returns_codebook_snapshot_and_counts(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_read1", content="codebook snapshot")
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        session.add(CodingEntry(file_id=coding_file.id, post_id="s1", code="A", code_uid="A-uid", quote="e", start_offset=0, end_offset=1))
        await session.commit()

        artifact = await coding_service.get_coding_artifact(session, user_id, "proj_read1")
        assert artifact["file"].id == coding_file.id
        assert [c.body for c in artifact["codes"]] == ["codebook snapshot"]
        assert artifact["total_rows"] == 1
        assert artifact["total_coded"] == 1
        assert artifact["code_frequency"] == [{"code": "A", "count": 1}]

    async def test_no_owned_file_raises_not_found(self, session, user_id) -> None:
        with pytest.raises(NotFoundError):
            await coding_service.get_coding_artifact(session, user_id, "proj_missing")

    async def test_scoped_to_owner(self, session, user_id) -> None:
        other_id = await _make_user(session, "other-artifact@example.com")
        await _make_file(session, other_id, schemaname="proj_not_mine")
        with pytest.raises(NotFoundError):
            await coding_service.get_coding_artifact(session, user_id, "proj_not_mine")

    async def test_version_no_reads_codebook_and_counts_as_of_that_version(self, session, user_id) -> None:
        """`version_no` backs "view a previous version": every field in
        the response (codes, total_coded, code_frequency) must reflect
        the SAME version, not a mix of as-of codes and live counts.
        """
        coding_file = await _make_file(session, user_id, schemaname="proj_asof1", content="v1 code")
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        session.add(Submission(file_id=coding_file.id, id="s2", title="t2", selftext="b2", word_count=1))
        await session.commit()

        v1_entry = CodingEntry(
            file_id=coding_file.id, post_id="s1", code="A", code_uid="A-uid",
            quote="e", start_offset=0, end_offset=1, valid_from=1,
        )
        session.add(v1_entry)
        await session.commit()

        # v2: close the v1 entry, apply a different code to s2 instead,
        # and change the codebook snapshot -- a real "what changed"
        # scenario, not just a bookkeeping version bump.
        v2 = await version_service.commit_codebook_version(
            session, file_id=coding_file.id, author_user_id=user_id, origin="edited",
            codes=[
                {
                    "code_uid": "A-uid", "family_uid": "f1", "family_name": "Fam", "name": "A",
                    "body": "v2 code", "position": 0,
                }
            ],
        )
        v1_entry.valid_to = v2.version_no - 1
        session.add(CodingEntry(
            file_id=coding_file.id, post_id="s2", code="A", code_uid="A-uid",
            quote="e2", start_offset=0, end_offset=2, valid_from=v2.version_no,
        ))
        await session.commit()

        as_of_v1 = await coding_service.get_coding_artifact(session, user_id, "proj_asof1", version_no=1)
        assert [c.body for c in as_of_v1["codes"]] == ["v1 code"]
        assert as_of_v1["total_coded"] == 1
        assert as_of_v1["code_frequency"] == [{"code": "A", "count": 1}]

        live = await coding_service.get_coding_artifact(session, user_id, "proj_asof1")
        assert [c.body for c in live["codes"]] == ["v2 code"]
        assert live["total_coded"] == 1
        assert live["code_frequency"] == [{"code": "A", "count": 1}]
        # total_rows (the coding file's own copied submissions) never
        # changes with version -- it's identical either way.
        assert as_of_v1["total_rows"] == live["total_rows"] == 2


class TestListCodingRows:
    async def test_lists_every_row_coded_or_not(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_rows1")
        session.add(Submission(file_id=coding_file.id, id="s1", title="Coded", selftext="b1", word_count=1))
        session.add(Submission(file_id=coding_file.id, id="s2", title="Uncoded", selftext="b2", word_count=1))
        session.add(CodingEntry(file_id=coding_file.id, post_id="s1", code="A", code_uid="A-uid", quote="e", start_offset=0, end_offset=1))
        await session.commit()

        result = await coding_service.list_coding_rows(session, user_id, "proj_rows1")
        assert result["total"] == 2
        by_item = {row["item_id"]: row for row in result["rows"]}
        assert by_item["t3_s1"]["codes"] == [
            {"code": "A", "code_uid": "A-uid", "quote": "e", "start_offset": 0, "end_offset": 1, "notes": None}
        ]
        assert by_item["t3_s2"]["codes"] == []

    async def test_search_filters_by_title_and_content(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_rows2")
        session.add(Submission(file_id=coding_file.id, id="s1", title="apple pie", selftext="", word_count=1))
        session.add(Submission(file_id=coding_file.id, id="s2", title="banana bread", selftext="", word_count=1))
        await session.commit()

        result = await coding_service.list_coding_rows(session, user_id, "proj_rows2", q="apple")
        assert result["total"] == 1
        assert result["rows"][0]["item_id"] == "t3_s1"

    async def test_no_owned_file_raises_not_found(self, session, user_id) -> None:
        with pytest.raises(NotFoundError):
            await coding_service.list_coding_rows(session, user_id, "proj_missing")


class TestGetCodingText:
    async def test_renders_from_coding_entries(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_text1")
        session.add(CodingEntry(file_id=coding_file.id, post_id="s1", code="A", code_uid="A-uid", quote="e", start_offset=0, end_offset=1, notes="n"))
        await session.commit()

        text = await coding_service.get_coding_text(session, user_id, "proj_text1")
        assert "POST_ID: t3_s1" in text
        assert "CODE: A" in text
        assert "NOTES: n" in text
        assert "EVIDENCE: e" in text

    async def test_empty_when_nothing_coded(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_text2")
        assert await coding_service.get_coding_text(session, user_id, "proj_text2") == ""


# ---------------------------------------------------------------------------
# save_coding_revision / update_coding_metadata
# ---------------------------------------------------------------------------


class TestSaveCodingRevisionCodebookOnly:
    async def test_overwrites_snapshot(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_cb", content="old")
        new_codes = [{"code_uid": "u2", "family_uid": "f2", "family_name": "F2", "name": "New", "body": "new text"}]
        result = await coding_service.save_coding_revision(session, user_id, "proj_save_cb", codes=new_codes, rows=None)
        assert result.id == coding_file.id
        codes = await version_service.read_codes(session, coding_file.id)
        assert [c.name for c in codes] == ["New"]

    async def test_no_codes_and_no_rows_raises_validation_error(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_save_cb2")
        with pytest.raises(ValidationAppError):
            await coding_service.save_coding_revision(session, user_id, "proj_save_cb2", codes=None, rows=None)

    async def test_unowned_raises_not_found(self, session, user_id) -> None:
        other_id = await _make_user(session, "other-save-cb@example.com")
        await _make_file(session, other_id, schemaname="proj_not_mine_cb")
        with pytest.raises(NotFoundError):
            await coding_service.save_coding_revision(
                session, user_id, "proj_not_mine_cb",
                codes=[{"code_uid": "u", "family_uid": "f", "family_name": "F", "name": "N"}], rows=None,
            )

    async def test_identical_codes_are_a_no_op_and_mint_no_version(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_cb_noop", content="body")
        codes = await version_service.read_codes(session, coding_file.id)
        same_codes = [
            {
                "code_uid": c.code_uid, "family_uid": c.family_uid, "family_name": c.family_name,
                "name": c.name, "body": c.body,
            }
            for c in codes
        ]
        head_before = await version_repo.head_version(session, coding_file.id)
        result = await coding_service.save_coding_revision(session, user_id, "proj_save_cb_noop", codes=same_codes, rows=None)
        assert result.id == coding_file.id
        head_after = await version_repo.head_version(session, coding_file.id)
        assert head_after.version_no == head_before.version_no


class TestSaveCodingRevisionRowsOnly:
    async def test_replaces_coding_for_given_rows(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_rows", content="body")
        codes = await version_service.read_codes(session, coding_file.id)
        new_uid = codes[0].code_uid  # the sole seeded code, named "C"
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        session.add(CodingEntry(file_id=coding_file.id, post_id="s1", code="OLD", code_uid="OLD-uid", quote="e", start_offset=0, end_offset=1))
        await session.commit()

        await coding_service.save_coding_revision(
            session,
            user_id,
            "proj_save_rows",
            codes=None,
            rows=[
                {
                    "item_id": "t3_s1",
                    "entries": [{"code_uid": new_uid, "quote": "e2", "start_offset": 0, "end_offset": 2, "notes": None}],
                }
            ],
        )

        # The OLD entry is CLOSED (SCD-2), not deleted -- history survives
        # across the version boundary this save opened.
        live_entries = (
            await session.execute(
                select(CodingEntry).where(CodingEntry.file_id == coding_file.id, CodingEntry.valid_to.is_(None))
            )
        ).scalars().all()
        assert [(e.code, e.code_uid, e.quote) for e in live_entries] == [("C", new_uid, "e2")]

        closed_entries = (
            await session.execute(
                select(CodingEntry).where(CodingEntry.file_id == coding_file.id, CodingEntry.valid_to.is_not(None))
            )
        ).scalars().all()
        assert [(e.code, e.valid_from, e.valid_to) for e in closed_entries] == [("OLD", 1, 1)]

    async def test_unknown_code_uid_raises_validation_error(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_rows_bad_uid", content="body")
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        await session.commit()

        with pytest.raises(ValidationAppError):
            await coding_service.save_coding_revision(
                session,
                user_id,
                "proj_save_rows_bad_uid",
                codes=None,
                rows=[
                    {
                        "item_id": "t3_s1",
                        "entries": [{"code_uid": "nonexistent", "quote": "e2", "start_offset": 0, "end_offset": 2}],
                    }
                ],
            )

    async def test_blank_code_entry_is_dropped(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_rows_blank")
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        await session.commit()

        await coding_service.save_coding_revision(
            session,
            user_id,
            "proj_save_rows_blank",
            codes=None,
            rows=[{"item_id": "t3_s1", "entries": [{"code_uid": "  ", "quote": "e", "start_offset": 0, "end_offset": 1}]}],
        )

        entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == coding_file.id))
        ).scalars().all()
        assert entries == []

    async def test_no_codes_and_no_rows_raises_validation_error(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_save_rows2")
        with pytest.raises(ValidationAppError):
            await coding_service.save_coding_revision(session, user_id, "proj_save_rows2", codes=None, rows=[])

    async def test_row_only_save_does_not_re_materialize_the_snapshot(self, session, user_id) -> None:
        """A row-only edit doesn't touch the codebook, so it must not
        copy a fresh codebook_codes row set -- see
        version_service.commit_coding_version's docstring and
        ArtifactVersion.codes_materialized. The snapshot must still read
        correctly (via the nearest materialized ancestor), but the row
        COUNT in codebook_codes must not grow with every save.
        """
        coding_file = await _make_file(session, user_id, schemaname="proj_save_rows_mat", content="body")
        v1_codes = await version_service.read_codes(session, coding_file.id)
        uid = v1_codes[0].code_uid
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        await session.commit()

        for i in range(3):
            await coding_service.save_coding_revision(
                session, user_id, "proj_save_rows_mat", codes=None,
                rows=[{"item_id": "t3_s1", "entries": [{"code_uid": uid, "quote": "e", "start_offset": 0, "end_offset": 1, "notes": str(i)}]}],
            )

        head = await version_repo.head_version(session, coding_file.id)
        assert head.version_no == 4  # v1 (apply) + 3 saves
        assert head.codes_materialized is False

        # Only v1 ever got a real CodebookCode row set -- the space this
        # change exists to stop wasting.
        all_codebook_codes = (
            await session.execute(select(CodebookCode).where(CodebookCode.version_id.in_(
                select(ArtifactVersion.id).where(ArtifactVersion.file_id == coding_file.id)
            )))
        ).scalars().all()
        assert len(all_codebook_codes) == 1

        # But read_codes on the (unmaterialized) head still resolves
        # correctly, via the nearest materialized ancestor (v1).
        head_codes = await version_service.read_codes(session, coding_file.id)
        assert [c.code_uid for c in head_codes] == [uid]
        v2_codes = await version_service.read_codes(session, coding_file.id, version_no=2)
        assert [c.code_uid for c in v2_codes] == [uid]


class TestSaveCodingRevisionCodesAndRowsTogether:
    async def test_one_save_mints_exactly_one_version(self, session, user_id) -> None:
        """The whole point of the merge: a codebook edit and a row edit
        submitted in the same call must land on the SAME new version, not
        two.
        """
        coding_file = await _make_file(session, user_id, schemaname="proj_save_both", content="body")
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        await session.commit()
        head_before = await version_repo.head_version(session, coding_file.id)

        new_codes = [{"code_uid": "u2", "family_uid": "f2", "family_name": "F2", "name": "New", "body": ""}]
        await coding_service.save_coding_revision(
            session, user_id, "proj_save_both",
            codes=new_codes,
            rows=[{"item_id": "t3_s1", "entries": [{"code_uid": "u2", "quote": "e", "start_offset": 0, "end_offset": 1}]}],
        )

        head_after = await version_repo.head_version(session, coding_file.id)
        assert head_after.version_no == head_before.version_no + 1

        live_entries = (
            await session.execute(
                select(CodingEntry).where(CodingEntry.file_id == coding_file.id, CodingEntry.valid_to.is_(None))
            )
        ).scalars().all()
        assert [(e.code_uid, e.valid_from) for e in live_entries] == [("u2", head_after.version_no)]

    async def test_code_created_in_this_save_resolves_for_a_row_in_the_same_save(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_both_new_code", content="body")
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        await session.commit()

        await coding_service.save_coding_revision(
            session, user_id, "proj_save_both_new_code",
            codes=[{"is_new": True, "family_is_new": True, "family_name": "F", "name": "Brand New"}],
            rows=[{"item_id": "t3_s1", "entries": []}],  # codes must resolve before rows are even attempted
        )
        codes = await version_service.read_codes(session, coding_file.id)
        assert [c.name for c in codes] == ["Brand New"]

    async def test_code_removed_in_this_save_is_rejected_on_a_submitted_row(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_both_removed", content="body")
        codes = await version_service.read_codes(session, coding_file.id)
        old_uid = codes[0].code_uid
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        await session.commit()

        with pytest.raises(ValidationAppError):
            await coding_service.save_coding_revision(
                session, user_id, "proj_save_both_removed",
                codes=[{"is_new": True, "family_is_new": True, "family_name": "F", "name": "Replacement"}],
                rows=[{"item_id": "t3_s1", "entries": [{"code_uid": old_uid, "quote": "e", "start_offset": 0, "end_offset": 1}]}],
            )

    async def test_code_removed_in_this_save_closes_entries_on_an_unsubmitted_row(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_save_both_orphan", content="body")
        codes = await version_service.read_codes(session, coding_file.id)
        old_uid = codes[0].code_uid
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        session.add(CodingEntry(file_id=coding_file.id, post_id="s1", code="C", code_uid=old_uid, quote="e", start_offset=0, end_offset=1))
        await session.commit()

        # codebook-only change, dropping the sole code -- s1's live entry
        # references it but is not itself included in `rows`.
        await coding_service.save_coding_revision(
            session, user_id, "proj_save_both_orphan",
            codes=[{"is_new": True, "family_is_new": True, "family_name": "F", "name": "Replacement"}],
            rows=None,
        )

        live_entries = (
            await session.execute(
                select(CodingEntry).where(CodingEntry.file_id == coding_file.id, CodingEntry.valid_to.is_(None))
            )
        ).scalars().all()
        assert live_entries == []


class TestUpdateCodingMetadata:
    async def test_renames_and_updates_description(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_meta")
        result = await coding_service.update_coding_metadata(
            session, user_id, "proj_meta", display_name="renamed", description="notes"
        )
        assert result.filename == "renamed"
        assert result.description == "notes"

    async def test_blank_description_clears_it(self, session, user_id) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_meta2")
        coding_file.description = "old"
        await session.commit()

        result = await coding_service.update_coding_metadata(
            session, user_id, "proj_meta2", display_name=None, description="  "
        )
        assert result.description is None


# ---------------------------------------------------------------------------
# duplicate_coding
# ---------------------------------------------------------------------------


class TestDuplicateCoding:
    async def test_forks_codebook_rows_entries_and_lineage(self, session, user_id) -> None:
        codebook_file = await _make_file(session, user_id, file_type="codebook", schemaname="proj_dup_cb")
        source_file = await _make_file(session, user_id, schemaname="proj_dup_src", content="codebook text")
        await version_repo.add_edge(
            session, child_file_id=source_file.id, parent_file_id=codebook_file.id, parent_version_id=None,
            relation="derived_from", role="codebook",
        )
        session.add(Submission(file_id=source_file.id, id="s1", title="t", selftext="b", word_count=1))
        source_codes = await version_service.read_codes(session, source_file.id)
        source_uid = source_codes[0].code_uid
        session.add(CodingEntry(file_id=source_file.id, post_id="s1", code="C", code_uid=source_uid, quote="e", start_offset=0, end_offset=1))
        await session.commit()

        new_file = await coding_service.duplicate_coding(session, user_id, "proj_dup_src", display_name="dup")

        assert new_file.filename == "dup"
        assert new_file.id != source_file.id
        new_codes = await version_service.read_codes(session, new_file.id)
        assert [c.body for c in new_codes] == ["codebook text"]
        # code_uid is preserved verbatim across the fork -- the payoff of
        # stable ids.
        assert new_codes[0].code_uid == source_uid

        copied_subs = (
            await session.execute(select(Submission).where(Submission.file_id == new_file.id))
        ).scalars().all()
        assert [s.id for s in copied_subs] == ["s1"]

        copied_entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file.id))
        ).scalars().all()
        assert [(e.post_id, e.code, e.code_uid) for e in copied_entries] == [("s1", "C", source_uid)]

        edges = await version_repo.list_parent_edges(session, new_file.id)
        assert {e.parent_file_id for e in edges} == {codebook_file.id, source_file.id}
        by_parent = {e.parent_file_id: e for e in edges}
        assert by_parent[codebook_file.id].role == "codebook"
        assert by_parent[source_file.id].relation == "forked_from"
        assert by_parent[source_file.id].role == "fork_origin"

    async def test_forks_from_a_chosen_version_not_head(self, session, user_id) -> None:
        """The non-destructive replacement for revert: forking from an
        older version reads that version's codebook snapshot AND the
        coding_entries live set AS OF that version -- not head's -- via
        version_service.read_codes(version_no=...) and
        coding_repo.copy_entries(as_of_version_no=...).
        """
        source_file = await _make_file(session, user_id, schemaname="proj_dup_v", content="v1 body")
        v1_codes = await version_service.read_codes(session, source_file.id)
        v1_uid = v1_codes[0].code_uid
        session.add(
            CodingEntry(
                file_id=source_file.id, post_id="s1", code="C", code_uid=v1_uid,
                quote="e", start_offset=0, end_offset=1, valid_from=1, valid_to=None,
            )
        )
        await session.commit()

        # A later edit (v2): the v1 entry is superseded (closed at v1, per
        # the SCD-2 invariant) and a new one takes its place.
        v2 = await version_service.commit_coding_version(session, file_id=source_file.id, author_user_id=user_id, origin="edited")
        assert v2.version_no == 2
        await session.execute(
            CodingEntry.__table__.update()
            .where(CodingEntry.file_id == source_file.id, CodingEntry.valid_to.is_(None))
            .values(valid_to=1)
        )
        session.add(
            CodingEntry(
                file_id=source_file.id, post_id="s1", code="C", code_uid=v1_uid,
                quote="edited", start_offset=0, end_offset=6, valid_from=2, valid_to=None,
            )
        )
        await session.commit()

        new_file = await coding_service.duplicate_coding(
            session, user_id, "proj_dup_v", display_name="from-v1", from_version_no=1
        )

        new_codes = await version_service.read_codes(session, new_file.id)
        assert [c.body for c in new_codes] == ["v1 body"]

        copied_entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file.id))
        ).scalars().all()
        # The v1 quote, not the v2 edit -- and re-stamped as the fork's own v1.
        assert [(e.quote, e.valid_from, e.valid_to) for e in copied_entries] == [("e", 1, None)]

    async def test_blank_display_name_raises_validation_error(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_dup_blank")
        with pytest.raises(ValidationAppError):
            await coding_service.duplicate_coding(session, user_id, "proj_dup_blank", display_name="  ")

    async def test_unowned_source_raises_not_found(self, session, user_id) -> None:
        other_id = await _make_user(session, "other-dup2@example.com")
        await _make_file(session, other_id, schemaname="proj_not_mine_dup")
        with pytest.raises(NotFoundError):
            await coding_service.duplicate_coding(session, user_id, "proj_not_mine_dup", display_name="x")

    async def test_unknown_from_version_no_raises_not_found(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_dup_missing_v")
        with pytest.raises(NotFoundError):
            await coding_service.duplicate_coding(
                session, user_id, "proj_dup_missing_v", display_name="x", from_version_no=99
            )


# ---------------------------------------------------------------------------
# get_coding_comparison
# ---------------------------------------------------------------------------


class TestGetCodingComparison:
    async def test_resolves_by_schema_name(self, session, user_id) -> None:
        file_rec = await _make_file(
            session, user_id, file_type="coding_comparison", schemaname="cmp_x", content="comparison text"
        )
        resolved = await coding_service.get_coding_comparison(session, user_id, "cmp_x")
        assert resolved.id == file_rec.id

    async def test_returns_most_recent_when_no_ref_given(self, session, user_id) -> None:
        await _make_file(session, user_id, file_type="coding_comparison", schemaname="cmp_1")
        second = await _make_file(session, user_id, file_type="coding_comparison", schemaname="cmp_2")
        resolved = await coding_service.get_coding_comparison(session, user_id, None)
        assert resolved.id == second.id

    async def test_no_file_raises_not_found(self, session, user_id) -> None:
        with pytest.raises(NotFoundError):
            await coding_service.get_coding_comparison(session, user_id, None)


# ---------------------------------------------------------------------------
# start_apply_codebook_job -- validation + enqueue
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
# _run_apply_codebook_job -- end-to-end, including coding_entries and the
# coding artifact's own copy of its sampled rows
# ---------------------------------------------------------------------------


_CODEBOOK_WITH_ALPHA_BETA = (
    "### Code Family: F\n"
    "#### Code Name: Alpha\n"
    "Definition: about alpha\n"
    "#### Code Name: Beta\n"
    "Definition: about beta\n"
)


class TestApplyCodebookJobHandlerParentDeletedMidRun:
    """A user can delete an artifact while a job that reads it is still
    waiting on its (minutes-long) LLM call. The two parents are deliberately
    NOT treated the same: the codebook's codes were already read into the
    new artifact's own snapshot, so only its lineage edge is lost, while
    the source data file's rows have yet to be copied in -- proceeding
    there would ship a coding artifact whose entries reference rows it
    never received.

    Both tests delete the parent from inside the `classify_posts` mock,
    which is exactly the window the real handler leaves open.
    """

    async def _seed(self, session, user_id):
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_rawmid")
        session.add(
            Submission(file_id=source.id, id="s1", title="t1", selftext="quote one here", word_count=3)
        )
        await session.commit()
        codebook_file = await _make_file(session, user_id, file_type="codebook", schemaname="proj_cbmid")
        await _seed_codebook_markdown(session, codebook_file.id, user_id, _CODEBOOK_WITH_ALPHA_BETA)
        # SQLite hands a deleted row's id to the next INSERT, so without
        # a file sitting above the one these tests delete, the coding
        # artifact the job creates would be born holding the very id its
        # deleted parent had -- and every assertion below would compare
        # the new artifact against itself. Postgres never reuses a
        # sequence value, so this filler exists only to make the SQLite
        # fixture behave like the real database.
        await _make_file(session, user_id, file_type="raw_data", schemaname="proj_idfiller")
        return source, codebook_file

    async def test_codebook_deleted_mid_run_keeps_the_artifact_and_drops_the_edge(
        self, session, user_id, monkeypatch, SessionLocal
    ) -> None:
        source, codebook_file = await self._seed(session, user_id)
        # Captured before `_wait_for_terminal_status`'s `expire_all()` --
        # see the note in `TestApplyCodebookJobHandlerEndToEnd`.
        source_schema, codebook_id = source.schemaname, codebook_file.schemaname

        async def _classify_then_delete(*args, **kwargs):
            async with SessionLocal() as other:
                await file_service.delete_database(other, user_id, codebook_id)
            return (
                [{"item_id": "t3_s1", "code": "Alpha", "quotes": ["quote one"]}],
                "sys prompt",
                "user prompt",
                {"batches_processed": 1, "batches_total": 1, "error": None},
            )

        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", _classify_then_delete)

        job = await coding_service.start_apply_codebook_job(
            session, user_id, database=source_schema, codebook=codebook_id,
            methodology="", api_key="sk-secret", model="m", sample_percentage=100.0,
            report_name="survives", project_id=None,
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error

        new_file_id = int(finished.result["file"]["id"])
        # The snapshot is complete even though the codebook is gone.
        assert [c.name for c in await version_service.read_codes(session, new_file_id)] == ["Alpha", "Beta"]
        entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file_id))
        ).scalars().all()
        assert [(e.post_id, e.code) for e in entries] == [("s1", "Alpha")]
        # Only the source edge remains; no edge points at the deleted codebook.
        # No edge points at the deleted codebook -- only the source
        # remains. Compared by schemaname, not id: SQLite hands the
        # deleted row's id straight to the next INSERT, so an id
        # comparison here would silently be comparing the new artifact
        # against itself.
        edges = await version_repo.list_parent_edges(session, new_file_id)
        parents = (
            await session.execute(select(File.schemaname).where(File.id.in_([e.parent_file_id for e in edges])))
        ).scalars().all()
        assert parents == [source_schema]

    async def test_source_data_deleted_mid_run_fails_the_job(
        self, session, user_id, monkeypatch, SessionLocal
    ) -> None:
        source, codebook_file = await self._seed(session, user_id)
        source_schema = source.schemaname

        async def _classify_then_delete(*args, **kwargs):
            async with SessionLocal() as other:
                await file_service.delete_database(other, user_id, source_schema)
            return (
                [{"item_id": "t3_s1", "code": "Alpha", "quotes": ["quote one"]}],
                "sys prompt",
                "user prompt",
                {"batches_processed": 1, "batches_total": 1, "error": None},
            )

        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", _classify_then_delete)

        job = await coding_service.start_apply_codebook_job(
            session, user_id, database=source_schema, codebook=codebook_file.schemaname,
            methodology="", api_key="sk-secret", model="m", sample_percentage=100.0,
            report_name="doomed", project_id=None,
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "failed"
        assert "no longer exists" in (finished.error or "")

        # No half-built artifact left behind.
        codings = (
            await session.execute(select(File).where(File.user_id == user_id, File.filename == "doomed"))
        ).scalars().all()
        assert codings == []


class TestApplyCodebookJobHandlerEndToEnd:
    async def test_populates_own_rows_codebook_snapshot_and_coding_entries(
        self, session, user_id, monkeypatch
    ) -> None:
        """The realistic multi-post, multi-code case: `classify_posts`'s
        structured `{item_id, code, quotes}` output must pass the
        anti-hallucination gate (item exists, code exists in the codebook,
        quote exists in the item's own text) and land as one
        `coding_entries` row per quote, the sampled submissions must be
        copied into the new file's own `submissions` table, and
        `artifact_content` must hold the codebook snapshot (not any raw AI
        output -- that is never stored at all now).
        """
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw4")
        session.add_all(
            [
                Submission(file_id=source.id, id="s1", title="t1", selftext="quote one and quote two", word_count=5),
                Submission(file_id=source.id, id="s2", title="t2", selftext="quote three appears here", word_count=5),
            ]
        )
        await session.commit()

        codebook_file = await _make_file(session, user_id, file_type="codebook", schemaname="proj_cb4")
        await _seed_codebook_markdown(session, codebook_file.id, user_id, _CODEBOOK_WITH_ALPHA_BETA)

        raw_entries = [
            {"item_id": "t3_s1", "code": "Alpha", "quotes": ["quote one"]},
            {"item_id": "t3_s1", "code": "Beta", "quotes": ["quote two"]},
            {"item_id": "t3_s2", "code": "Alpha", "quotes": ["quote three"]},
        ]
        classify_mock = AsyncMock(return_value=(raw_entries, "sys prompt", "user prompt", {"batches_processed": 1, "batches_total": 1, "error": None}))
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
        assert result["accepted"] == 3
        assert result["rejected_unknown_item"] == 0
        assert result["rejected_unknown_code"] == 0
        assert result["rejected_quote_not_found"] == 0
        new_file_id = int(result["file"]["id"])
        assert result["file"]["filename"] == "my report"

        # The new coding artifact's own codebook snapshot holds the
        # applied codebook's codes (code_uid preserved), not any raw AI
        # output -- nothing unverified is ever stored.
        stored_codes = await version_service.read_codes(session, new_file_id)
        assert [c.name for c in stored_codes] == ["Alpha", "Beta"]

        # The coding artifact owns its own copy of every sampled row.
        copied_subs = (
            await session.execute(select(Submission).where(Submission.file_id == new_file_id))
        ).scalars().all()
        assert {s.id for s in copied_subs} == {"s1", "s2"}

        entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file_id))
        ).scalars().all()
        by_key = {(e.post_id, e.code): (e.quote, e.start_offset, e.end_offset) for e in entries}
        assert by_key == {
            ("s1", "Alpha"): ("quote one", 0, 9),
            ("s1", "Beta"): ("quote two", 14, 23),
            ("s2", "Alpha"): ("quote three", 0, 11),
        }

        edges = await version_repo.list_parent_edges(session, new_file_id)
        parent_ids = {e.parent_file_id for e in edges}
        assert parent_ids == {source_id, codebook_file_id}
        by_parent = {e.parent_file_id: e for e in edges}
        assert by_parent[source_id].role == "source_data"
        assert by_parent[codebook_file_id].role == "codebook"
        # The codebook edge is pinned to the exact revision applied.
        codebook_head = await version_repo.head_version(session, codebook_file_id)
        assert by_parent[codebook_file_id].parent_version_id == codebook_head.id

        # api_key never persisted to the jobs table, but did reach
        # classify_posts via runtime_extra.
        assert "api_key" not in job.payload
        assert classify_mock.called
        call_args = classify_mock.call_args.args
        assert call_args[0] == _CODEBOOK_WITH_ALPHA_BETA.strip()
        assert call_args[3] == "sk-secret"

    async def test_rejects_hallucinated_item_code_and_quote(self, session, user_id, monkeypatch) -> None:
        """Every entry here fails a different check -- none of them reach
        coding_entries, and the job result reports exactly why.
        """
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw4c")
        session.add(Submission(file_id=source.id, id="s1", title="t", selftext="the real content", word_count=3))
        await session.commit()
        codebook_file = await _make_file(session, user_id, file_type="codebook", schemaname="proj_cb4c")
        await _seed_codebook_markdown(session, codebook_file.id, user_id, _CODEBOOK_WITH_ALPHA_BETA)

        raw_entries = [
            # unknown item -- not in the run's valid_keys
            {"item_id": "t3_ghost", "code": "Alpha", "quotes": ["the real content"]},
            # unknown code -- not in the codebook
            {"item_id": "t3_s1", "code": "NotACode", "quotes": ["the real content"]},
            # quote never appears in s1's content
            {"item_id": "t3_s1", "code": "Alpha", "quotes": ["never appears anywhere"]},
        ]
        monkeypatch.setattr(
            "backend.app.services.coding_service.classify_posts",
            AsyncMock(return_value=(raw_entries, "", "", {"batches_processed": 1, "batches_total": 1, "error": None})),
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
        assert finished.result["accepted"] == 0
        assert finished.result["rejected_unknown_item"] == 1
        assert finished.result["rejected_unknown_code"] == 1
        assert finished.result["rejected_quote_not_found"] == 1

        new_file_id = int(finished.result["file"]["id"])
        entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == new_file_id))
        ).scalars().all()
        assert entries == []

    async def test_each_quote_for_a_repeated_post_code_pair_gets_its_own_row(
        self, session, user_id, monkeypatch
    ) -> None:
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw4b")
        session.add(Submission(file_id=source.id, id="s1", title="t", selftext="one and two both here", word_count=5))
        await session.commit()
        codebook_file = await _make_file(session, user_id, file_type="codebook", schemaname="proj_cb4b")
        await _seed_codebook_markdown(session, codebook_file.id, user_id, _CODEBOOK_WITH_ALPHA_BETA)

        raw_entries = [{"item_id": "t3_s1", "code": "Alpha", "quotes": ["one", "two"]}]
        monkeypatch.setattr(
            "backend.app.services.coding_service.classify_posts",
            AsyncMock(return_value=(raw_entries, "", "", {"batches_processed": 1, "batches_total": 1, "error": None})),
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
        assert len(entries) == 2
        assert {e.quote for e in entries} == {"one", "two"}
        assert all(e.code == "Alpha" for e in entries)

    async def test_empty_codebook_content_marks_job_failed(self, session, user_id, monkeypatch) -> None:
        source = await _make_file(session, user_id, file_type="raw_data", schemaname="proj_raw5")
        codebook_file = await _make_file(
            session, user_id, file_type="codebook", schemaname="proj_cb5", content=None
        )
        classify_mock = AsyncMock(return_value=("output", "s", "u", {"batches_processed": 1, "batches_total": 1, "error": None}))
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
# start_recode_items_job -- validation + enqueue, and the handler end-to-end
# ---------------------------------------------------------------------------


class TestStartRecodeItemsJobValidation:
    async def test_missing_api_key_raises(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_recode_val")
        with pytest.raises(ValidationAppError, match="api_key"):
            await coding_service.start_recode_items_job(
                session,
                user_id,
                ref="proj_recode_val",
                item_ids=["t3_s1"],
                api_key="",
                model=None,
                methodology=None,
            )

    async def test_missing_item_ids_raises(self, session, user_id) -> None:
        await _make_file(session, user_id, schemaname="proj_recode_val2")
        with pytest.raises(ValidationAppError, match="item_ids"):
            await coding_service.start_recode_items_job(
                session,
                user_id,
                ref="proj_recode_val2",
                item_ids=[],
                api_key="k",
                model=None,
                methodology=None,
            )

    async def test_unowned_ref_raises_not_found(self, session, user_id) -> None:
        with pytest.raises(NotFoundError):
            await coding_service.start_recode_items_job(
                session,
                user_id,
                ref="proj_missing",
                item_ids=["t3_s1"],
                api_key="k",
                model=None,
                methodology=None,
            )


class TestRecodeItemsJobHandlerEndToEnd:
    async def test_recodes_only_the_selected_rows(self, session, user_id, monkeypatch) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_recode1")
        await _seed_codebook_markdown(
            session, coding_file.id, user_id, _CODEBOOK_WITH_ALPHA_BETA + "#### Code Name: NEW\n"
        )
        session.add_all(
            [
                Submission(file_id=coding_file.id, id="s1", title="t1", selftext="something new appears", word_count=3),
                Submission(file_id=coding_file.id, id="s2", title="t2", selftext="b2", word_count=1),
            ]
        )
        session.add(CodingEntry(file_id=coding_file.id, post_id="s1", code="OLD", code_uid="OLD-uid", quote="old", start_offset=0, end_offset=3))
        session.add(CodingEntry(file_id=coding_file.id, post_id="s2", code="UNCHANGED", code_uid="UNCHANGED-uid", quote="e", start_offset=0, end_offset=1))
        await session.commit()

        classify_mock = AsyncMock(
            return_value=(
                [{"item_id": "t3_s1", "code": "NEW", "quotes": ["new"]}],
                "sys",
                "usr",
                {"batches_processed": 1, "batches_total": 1, "error": None},
            )
        )
        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", classify_mock)

        coding_file_id = coding_file.id
        head_before = await version_repo.head_version(session, coding_file_id)
        job = await coding_service.start_recode_items_job(
            session,
            user_id,
            ref="proj_recode1",
            item_ids=["t3_s1"],
            api_key="sk",
            model="m",
            methodology="",
        )

        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error
        assert finished.result["recoded_item_count"] == 1
        assert finished.result["accepted"] == 1

        # A recode is a proposal, not a write -- neither s1's existing
        # entry nor s2's untouched one changed, and no new version was
        # minted. The proposal for s1 is in the job result, shaped like
        # `list_rows_with_codes`'s per-row `codes` list.
        assert finished.result["proposals"] == [
            {
                "item_id": "t3_s1",
                "codes": [
                    {
                        "code": "NEW", "code_uid": finished.result["proposals"][0]["codes"][0]["code_uid"],
                        "quote": "new", "start_offset": 10, "end_offset": 13, "notes": None,
                    }
                ],
            }
        ]

        entries = (
            await session.execute(select(CodingEntry).where(CodingEntry.file_id == coding_file_id))
        ).scalars().all()
        by_post = {e.post_id: e.code for e in entries}
        assert by_post == {"s1": "OLD", "s2": "UNCHANGED"}

        head_after = await version_repo.head_version(session, coding_file_id)
        assert head_after.version_no == head_before.version_no

        assert classify_mock.called
        call_args = classify_mock.call_args.args
        assert "NEW" in call_args[0]
        assert "t3_s1" in call_args[1]
        assert "s2" not in call_args[1]  # the unselected row was never sent
        assert call_args[3] == "sk"

    async def test_ai_dropping_an_item_proposes_an_empty_codes_list(self, session, user_id, monkeypatch) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_recode2", content="CB")
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        session.add(CodingEntry(file_id=coding_file.id, post_id="s1", code="OLD", code_uid="OLD-uid", quote="e", start_offset=0, end_offset=1))
        await session.commit()

        # The model returns nothing for s1 -- the proposal should clear
        # it (an empty codes list), but nothing is written until Save.
        monkeypatch.setattr(
            "backend.app.services.coding_service.classify_posts",
            AsyncMock(return_value=([], "sys", "usr", {"batches_processed": 1, "batches_total": 1, "error": None})),
        )

        coding_file_id = coding_file.id
        job = await coding_service.start_recode_items_job(
            session,
            user_id,
            ref="proj_recode2",
            item_ids=["t3_s1"],
            api_key="sk",
            model=None,
            methodology=None,
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error
        assert finished.result["proposals"] == [{"item_id": "t3_s1", "codes": []}]

        # The old entry is untouched -- still live, since nothing was
        # committed by the job itself.
        live_entries = (
            await session.execute(
                select(CodingEntry).where(CodingEntry.file_id == coding_file_id, CodingEntry.valid_to.is_(None))
            )
        ).scalars().all()
        assert [(e.code, e.code_uid) for e in live_entries] == [("OLD", "OLD-uid")]

    async def test_no_codebook_snapshot_marks_job_failed(self, session, user_id, monkeypatch) -> None:
        coding_file = await _make_file(session, user_id, schemaname="proj_recode3")  # no content
        session.add(Submission(file_id=coding_file.id, id="s1", title="t", selftext="b", word_count=1))
        await session.commit()
        classify_mock = AsyncMock(return_value=("output", "s", "u", {"batches_processed": 1, "batches_total": 1, "error": None}))
        monkeypatch.setattr("backend.app.services.coding_service.classify_posts", classify_mock)

        job = await coding_service.start_recode_items_job(
            session,
            user_id,
            ref="proj_recode3",
            item_ids=["t3_s1"],
            api_key="sk",
            model=None,
            methodology=None,
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "failed"
        assert "codebook snapshot" in finished.error
        assert not classify_mock.called


# ---------------------------------------------------------------------------
# start_compare_codings_job -- validation + enqueue
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
# _run_compare_codings_job -- end-to-end
#
# A coding file's comparison input is now generated fresh from its
# coding_entries (coding_repo.render_coding_text), not read from a stored
# blob -- these tests seed coding_entries directly rather than an
# artifact_content row.
# ---------------------------------------------------------------------------


class TestCompareCodingsJobHandlerEndToEnd:
    async def test_succeeds_with_mocked_llm(self, session, user_id, monkeypatch) -> None:
        file_a = await _make_file(session, user_id, schemaname="proj_cmp_a")
        file_b = await _make_file(session, user_id, schemaname="proj_cmp_b")
        session.add(CodingEntry(file_id=file_a.id, post_id="p1", code="CODE_A", code_uid="CODE_A-uid", quote="ev-a", start_offset=0, end_offset=4))
        session.add(CodingEntry(file_id=file_b.id, post_id="p1", code="CODE_B", code_uid="CODE_B-uid", quote="ev-b", start_offset=0, end_offset=4))
        await session.commit()
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

        content = await version_service.read_blob(session, new_file_id)
        assert content == "the comparison"

        edges = await version_repo.list_parent_edges(session, new_file_id)
        assert {e.parent_file_id for e in edges} == {file_a_id, file_b_id}
        by_role = {e.role: e.parent_file_id for e in edges}
        assert by_role["side_a"] == file_a_id
        assert by_role["side_b"] == file_b_id

    async def test_no_content_marks_job_failed(self, session, user_id, monkeypatch) -> None:
        await _make_file(session, user_id, schemaname="proj_cmp_empty_a")
        await _make_file(session, user_id, schemaname="proj_cmp_empty_b")
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

    async def test_sends_raw_codings_unchanged_when_they_fit(self, session, user_id, monkeypatch) -> None:
        # When the rendered codings fit the window, they're sent as-is --
        # aggregation only kicks in on overflow.
        file_a = await _make_file(session, user_id, schemaname="proj_cmp_raw_a")
        file_b = await _make_file(session, user_id, schemaname="proj_cmp_raw_b")
        session.add(CodingEntry(file_id=file_a.id, post_id="p1", code="CODE_A", code_uid="CODE_A-uid", quote="ev1", start_offset=0, end_offset=3))
        session.add(CodingEntry(file_id=file_b.id, post_id="p1", code="CODE_B", code_uid="CODE_B-uid", quote="ev-b1", start_offset=0, end_offset=5))
        await session.commit()

        monkeypatch.setattr(
            "backend.app.services.coding_service.context_window.prompt_fits",
            lambda model, **kwargs: True,
        )
        llm_mock = AsyncMock(return_value="cmp")
        monkeypatch.setattr("backend.scripts.codebook_generator.get_client", llm_mock)

        job = await coding_service.start_compare_codings_job(
            session,
            user_id,
            coding_a="proj_cmp_raw_a",
            coding_b="proj_cmp_raw_b",
            api_key="sk",
            model=None,
            prompt="",
            name="cmp",
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error

        sent_prompt = llm_mock.call_args.args[1]
        assert "POST_ID: t3_p1" in sent_prompt
        assert "CODE: CODE_A" in sent_prompt
        assert "CODE: CODE_B" in sent_prompt
        assert "used" not in sent_prompt  # not aggregated

    async def test_falls_back_to_aggregated_codings_when_raw_overflows(self, session, user_id, monkeypatch) -> None:
        # Force the raw-rendered-text candidate to reject and the
        # aggregated candidate to accept, regardless of actual length --
        # a coding artifact's rendered text is proportional to how much
        # was coded, not an arbitrarily large blob, so this is exercised
        # by call order rather than a size threshold.
        file_a = await _make_file(session, user_id, schemaname="proj_cmp_agg_a")
        file_b = await _make_file(session, user_id, schemaname="proj_cmp_agg_b")
        session.add(CodingEntry(file_id=file_a.id, post_id="p1", code="CODE_A", code_uid="CODE_A-uid", quote="ev-a1", start_offset=0, end_offset=5))
        session.add(CodingEntry(file_id=file_a.id, post_id="p2", code="CODE_A", code_uid="CODE_A-uid", quote="ev-a2", start_offset=0, end_offset=5))
        session.add(CodingEntry(file_id=file_b.id, post_id="p1", code="CODE_B", code_uid="CODE_B-uid", quote="ev-b1", start_offset=0, end_offset=5))
        await session.commit()

        fits_calls: list[dict] = []

        def _prompt_fits(model, **kwargs):
            fits_calls.append(kwargs)
            return len(fits_calls) > 1

        monkeypatch.setattr("backend.app.services.coding_service.context_window.prompt_fits", _prompt_fits)
        llm_mock = AsyncMock(return_value="the comparison")
        monkeypatch.setattr("backend.scripts.codebook_generator.get_client", llm_mock)

        job = await coding_service.start_compare_codings_job(
            session,
            user_id,
            coding_a="proj_cmp_agg_a",
            coding_b="proj_cmp_agg_b",
            api_key="sk",
            model=None,
            prompt="",
            name="cmp",
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "succeeded", finished.error

        sent_prompt = llm_mock.call_args.args[1]
        assert "CODE_A (used 2 times)" in sent_prompt
        assert "CODE_B (used 1 times)" in sent_prompt
        assert "POST_ID:" not in sent_prompt  # the raw rendered text was NOT sent

    async def test_raises_context_budget_error_when_even_aggregated_overflows(self, session, user_id, monkeypatch) -> None:
        # Nothing fits, ever -- not the raw rendered text and not its
        # compacted form -- so the job fails loudly instead of silently
        # truncating.
        file_a = await _make_file(session, user_id, schemaname="proj_cmp_of_a")
        file_b = await _make_file(session, user_id, schemaname="proj_cmp_of_b")
        session.add(CodingEntry(file_id=file_a.id, post_id="p1", code="CODE_A", code_uid="CODE_A-uid", quote="ev1", start_offset=0, end_offset=3))
        await session.commit()

        monkeypatch.setattr(
            "backend.app.services.coding_service.context_window.prompt_fits",
            lambda model, **kwargs: False,
        )
        llm_mock = AsyncMock(return_value="should not run")
        monkeypatch.setattr("backend.scripts.codebook_generator.get_client", llm_mock)

        job = await coding_service.start_compare_codings_job(
            session,
            user_id,
            coding_a="proj_cmp_of_a",
            coding_b="proj_cmp_of_b",
            api_key="sk",
            model=None,
            prompt="",
            name="cmp",
        )
        finished = await _wait_for_terminal_status(session, job.id, user_id)
        assert finished.status == "failed"
        assert "larger-context model" in finished.error
        assert not llm_mock.called
