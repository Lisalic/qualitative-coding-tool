"""Unit tests for backend/app/services/codebook_service.py.

Runs directly against an in-memory async SQLite session (the
``async_sqlite_engine`` fixture from ``tests/conftest.py``), bypassing the
HTTP layer entirely -- ``tests/backend/routes/test_codebook_routes.py`` and
``tests/backend/routes/test_ai_and_raw_sql_routes.py`` cover the
route/auth/response-shape behavior on top of this.
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import File, User
from backend.app.jobs import service as jobs_service
from backend.app.repositories import version_repo
from backend.app.services import codebook_service, version_service
from backend.app.storage_models import Comment, Submission


_ONE_CODE = [
    {"code_uid": "u1", "family_uid": "f1", "family_name": "F", "name": "C", "body": "content", "position": 0}
]


async def _seed_codes(session, file_id: int, user_id: int, text: str = "codebook text") -> None:
    """Seed a `codebook` file's structured code rows for a test -- `text`
    becomes the sole code's `definition`, so it shows up in the
    rendered markdown a test might assert on (see
    ``core/codebook_render.py::render_codes_to_markdown``).
    """
    rows = [{
        "code_uid": "u1", "family_uid": "f1", "family_name": "F", "name": "C",
        "body": f"Definition: {text}", "definition": text, "position": 0,
    }]
    await version_service.commit_codebook_version(
        session, file_id=file_id, author_user_id=user_id, origin="generated", codes=rows,
    )


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def patch_async_session_local(monkeypatch, session_factory):
    """The job handlers open their own session via the module-level
    ``AsyncSessionLocal`` imported into
    ``backend.app.services.codebook_service`` -- point that (and the job
    runner's own session factory) at the in-memory SQLite engine backing
    this test's session.
    """
    monkeypatch.setattr("backend.app.services.codebook_service.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("backend.app.jobs.service.AsyncSessionLocal", session_factory)


async def _make_user(session, email: str = "a@b.com") -> User:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_file(
    session,
    user_id: int,
    *,
    file_type: str = "raw_data",
    schemaname: str = "proj_src",
    filename: str = "f",
) -> File:
    file_rec = File(user_id=user_id, filename=filename, schemaname=schemaname, file_type=file_type)
    session.add(file_rec)
    await session.commit()
    await session.refresh(file_rec)
    return file_rec


async def _wait_for_terminal_status(session, job_id: int, user_id: int, timeout: float = 5.0):
    """Same polling helper as tests/backend/services/test_data_service.py."""
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


# ---------------------------------------------------------------------------
# get_codebook
# ---------------------------------------------------------------------------


class TestGetCodebook:
    async def test_lookup_by_schemaname(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            found = await codebook_service.get_codebook(session, user.id, file_rec.schemaname)
            assert found.id == file_rec.id

    async def test_lookup_by_filename(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(
                session, user.id, file_type="codebook", schemaname="proj_a", filename="my-cb"
            )
            found = await codebook_service.get_codebook(session, user.id, "my-cb")
            assert found.id == file_rec.id

    async def test_lookup_by_id(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            found = await codebook_service.get_codebook(session, user.id, str(file_rec.id))
            assert found.id == file_rec.id

    async def test_includes_codebook_comparison_type(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(
                session, user.id, file_type="codebook_comparison", schemaname="cmp_a"
            )
            found = await codebook_service.get_codebook(session, user.id, file_rec.schemaname)
            assert found.id == file_rec.id

    async def test_no_id_returns_latest(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            second = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            found = await codebook_service.get_codebook(session, user.id, None)
            assert found.id == second.id

    async def test_not_found_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await codebook_service.get_codebook(session, user.id, "nonexistent")

    async def test_no_codebooks_at_all_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await codebook_service.get_codebook(session, user.id, None)

    async def test_scoped_to_calling_user(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_rec = await _make_file(session, owner.id, file_type="codebook", schemaname="proj_a")

            with pytest.raises(NotFoundError):
                await codebook_service.get_codebook(session, other.id, file_rec.schemaname)
            with pytest.raises(NotFoundError):
                await codebook_service.get_codebook(session, other.id, None)

    async def test_raw_data_file_type_is_not_a_codebook(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="raw_data", schemaname="proj_r")
            with pytest.raises(NotFoundError):
                await codebook_service.get_codebook(session, user.id, file_rec.schemaname)


# ---------------------------------------------------------------------------
# list_codebooks
# ---------------------------------------------------------------------------


class TestListCodebooks:
    async def test_excludes_comparisons_and_other_types(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, file_type="codebook", schemaname="proj_a", filename="A")
            await _make_file(
                session, user.id, file_type="codebook_comparison", schemaname="cmp_a", filename="B"
            )
            await _make_file(session, user.id, file_type="raw_data", schemaname="proj_r", filename="C")

            files = await codebook_service.list_codebooks(session, user.id)
            names = sorted(f.filename for f in files)
            assert names == ["A"]

    async def test_scoped_to_calling_user(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            await _make_file(session, owner.id, file_type="codebook", schemaname="proj_a", filename="Mine")
            await _make_file(
                session, other.id, file_type="codebook", schemaname="proj_b", filename="NotMine"
            )

            files = await codebook_service.list_codebooks(session, owner.id)
            assert [f.filename for f in files] == ["Mine"]

    async def test_empty_when_no_codebooks(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            files = await codebook_service.list_codebooks(session, user.id)
            assert files == []


# ---------------------------------------------------------------------------
# save_project_codebook
# ---------------------------------------------------------------------------


class TestSaveProjectCodebook:
    async def test_happy_path_writes_content_and_display_name(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")

            saved = await codebook_service.save_project_codebook(
                session,
                user.id,
                schema_name=file_rec.schemaname,
                codes=_ONE_CODE,
                display_name="renamed",
            )
            assert saved.filename == "renamed"

            codes = await version_service.read_codes(session, file_rec.id)
            assert [c.name for c in codes] == ["C"]

    async def test_no_display_name_leaves_filename_unchanged(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(
                session, user.id, file_type="codebook", schemaname="proj_a", filename="original"
            )
            saved = await codebook_service.save_project_codebook(
                session, user.id, schema_name=file_rec.schemaname, codes=_ONE_CODE, display_name=None
            )
            assert saved.filename == "original"

    async def test_overwrites_existing_content(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            await _seed_codes(session, file_rec.id, user.id, "old")
            await session.commit()

            new_codes = [{"code_uid": "u2", "family_uid": "f2", "family_name": "F2", "name": "New", "body": "new", "position": 0}]
            await codebook_service.save_project_codebook(
                session, user.id, schema_name=file_rec.schemaname, codes=new_codes, display_name=None
            )
            codes = await version_service.read_codes(session, file_rec.id)
            assert [c.name for c in codes] == ["New"]

    async def test_code_missing_identity_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            bad = [{"family_uid": "f1", "family_name": "F", "name": "C", "body": "x"}]
            with pytest.raises(ValidationAppError):
                await codebook_service.save_project_codebook(
                    session, user.id, schema_name=file_rec.schemaname, codes=bad, display_name=None
                )

    async def test_unowned_schema_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_rec = await _make_file(session, owner.id, file_type="codebook", schemaname="proj_a")
            with pytest.raises(NotFoundError):
                await codebook_service.save_project_codebook(
                    session, other.id, schema_name=file_rec.schemaname, codes=_ONE_CODE, display_name=None
                )

    async def test_unknown_schema_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(NotFoundError):
                await codebook_service.save_project_codebook(
                    session, user.id, schema_name="proj_missing", codes=_ONE_CODE, display_name=None
                )


# ---------------------------------------------------------------------------
# duplicate_codebook -- the non-destructive replacement for revert
# ---------------------------------------------------------------------------


class TestDuplicateCodebook:
    async def test_forks_from_head_by_default(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="codebook", schemaname="proj_dup_cb")
            await _seed_codes(session, file_rec.id, user.id, "v1 text")
            await session.commit()

            new_file = await codebook_service.duplicate_codebook(
                session, user.id, "proj_dup_cb", display_name="dup"
            )
            assert new_file.filename == "dup"
            assert new_file.id != file_rec.id

            new_codes = await version_service.read_codes(session, new_file.id)
            assert [c.definition for c in new_codes] == ["v1 text"]
            # code_uid preserved verbatim -- a later diff between original
            # and fork reports no changes, not a wholesale add/remove.
            assert new_codes[0].code_uid == "u1"

            edges = await version_repo.list_parent_edges(session, new_file.id)
            assert len(edges) == 1
            assert edges[0].parent_file_id == file_rec.id
            assert edges[0].relation == "forked_from"
            assert edges[0].role == "fork_origin"

    async def test_forks_from_a_chosen_version_not_head(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id, file_type="codebook", schemaname="proj_dup_cb_v")
            await _seed_codes(session, file_rec.id, user.id, "v1 text")
            await _seed_codes(session, file_rec.id, user.id, "v2 text")
            await session.commit()

            new_file = await codebook_service.duplicate_codebook(
                session, user.id, "proj_dup_cb_v", display_name="from-v1", from_version_no=1
            )
            new_codes = await version_service.read_codes(session, new_file.id)
            assert [c.definition for c in new_codes] == ["v1 text"]

    async def test_unknown_from_version_no_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, file_type="codebook", schemaname="proj_dup_cb_missing")
            with pytest.raises(NotFoundError):
                await codebook_service.duplicate_codebook(
                    session, user.id, "proj_dup_cb_missing", display_name="x", from_version_no=99
                )

    async def test_blank_display_name_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, file_type="codebook", schemaname="proj_dup_cb_blank")
            with pytest.raises(ValidationAppError):
                await codebook_service.duplicate_codebook(
                    session, user.id, "proj_dup_cb_blank", display_name="  "
                )

    async def test_unowned_source_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner-dupcb@x.com")
            other = await _make_user(session, "other-dupcb@x.com")
            await _make_file(session, owner.id, file_type="codebook", schemaname="proj_dup_cb_not_mine")
            with pytest.raises(NotFoundError):
                await codebook_service.duplicate_codebook(
                    session, other.id, "proj_dup_cb_not_mine", display_name="x"
                )


# ---------------------------------------------------------------------------
# start_generate_codebook_job -- validation + enqueue
# ---------------------------------------------------------------------------


class TestStartGenerateCodebookJobValidation:
    async def test_non_proj_database_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError, match="database"):
                await codebook_service.start_generate_codebook_job(
                    session,
                    user.id,
                    database="not_proj",
                    api_key="k",
                    prompt="",
                    name="n",
                    description=None,
                    project_id=None,
                    model=None,
                    sample_percentage=100.0,
                )

    async def test_missing_api_key_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            with pytest.raises(ValidationAppError, match="api_key"):
                await codebook_service.start_generate_codebook_job(
                    session,
                    user.id,
                    database=file_rec.schemaname,
                    api_key="",
                    prompt="",
                    name="n",
                    description=None,
                    project_id=None,
                    model=None,
                    sample_percentage=100.0,
                )

    async def test_unowned_database_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_rec = await _make_file(session, owner.id)
            with pytest.raises(NotFoundError):
                await codebook_service.start_generate_codebook_job(
                    session,
                    other.id,
                    database=file_rec.schemaname,
                    api_key="k",
                    prompt="",
                    name="n",
                    description=None,
                    project_id=None,
                    model=None,
                    sample_percentage=100.0,
                )


class TestStartGenerateCodebookJobEnqueue:
    async def test_enqueues_pending_job_without_persisting_api_key(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)

            job = await codebook_service.start_generate_codebook_job(
                session,
                user.id,
                database=file_rec.schemaname,
                api_key="sk-secret",
                prompt="",
                name="n",
                description=None,
                project_id=None,
                model="some-model",
                sample_percentage=100.0,
            )

            assert job.status == "pending"
            assert job.job_type == "generate_codebook"
            assert job.payload["source_file_id"] == file_rec.id
            assert "api_key" not in job.payload

            await _wait_for_terminal_status(session, job.id, user.id)


# ---------------------------------------------------------------------------
# _run_generate_codebook_job -- end-to-end
# ---------------------------------------------------------------------------


class TestGenerateCodebookJobHandlerEndToEnd:
    async def test_samples_calls_llm_and_persists_new_codebook_file(
        self, session_factory, monkeypatch
    ) -> None:
        generate_mock = AsyncMock(
            return_value=(
                json.dumps(
                    {
                        "codes": [
                            {
                                "family": "F",
                                "name": "generated codebook",
                                "definition": "a def",
                                "inclusion": "when",
                                "exclusion": "not when",
                                "keywords": "kw",
                                "example": "ex",
                            }
                        ]
                    }
                ),
                "sys prompt",
                "user prompt",
            )
        )
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.generate_codebook",
            generate_mock,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            source_file_id = file_rec.id
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="t1", selftext="x1", word_count=5),
                    Comment(file_id=file_rec.id, id="c1", body="b1", word_count=3),
                ]
            )
            await session.commit()

            job = await codebook_service.start_generate_codebook_job(
                session,
                user.id,
                database=file_rec.schemaname,
                api_key="sk-secret",
                prompt="be thorough",
                name="my codebook",
                description="a desc",
                project_id=None,
                model=None,
                sample_percentage=100.0,
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error
            result = finished.result
            assert "generated codebook" in result["codebook"]
            assert result["file"]["filename"] == "my codebook"
            assert result["file"]["description"] == "a desc"

            assert generate_mock.called

            new_file_id = int(result["file"]["id"])
            new_file = await session.get(File, new_file_id)
            assert new_file.file_type == "codebook"
            assert new_file.schemaname.startswith("proj_")

            head = await version_repo.head_version(session, new_file_id)
            assert head.system_prompt == "sys prompt"
            # The rendered prompt is deliberately NOT stored (it embeds the
            # whole sampled corpus) -- only the user's own instructions,
            # plus a length/hash of what was actually sent.
            assert head.user_instructions == "be thorough"
            assert head.prompt_meta["rendered_chars"] == len("user prompt")
            assert head.prompt_meta["rendered_sha256"] == hashlib.sha256(b"user prompt").hexdigest()

            codes = await version_service.read_codes(session, new_file_id)
            assert [c.name for c in codes] == ["generated codebook"]
            assert codes[0].definition == "a def"
            assert codes[0].inclusion == "when"
            assert codes[0].exclusion == "not when"
            assert codes[0].keywords == "kw"
            assert codes[0].example == "ex"

            edges = await version_repo.list_parent_edges(session, new_file_id)
            assert [e.parent_file_id for e in edges] == [source_file_id]
            assert edges[0].relation == "derived_from"
            assert edges[0].role == "source_data"

    async def test_no_records_sampled_marks_job_failed(self, session_factory, monkeypatch) -> None:
        generate_mock = AsyncMock(return_value=("should not run", "", ""))
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.generate_codebook",
            generate_mock,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)  # no submissions/comments

            job = await codebook_service.start_generate_codebook_job(
                session,
                user.id,
                database=file_rec.schemaname,
                api_key="sk-secret",
                prompt="",
                name="n",
                description=None,
                project_id=None,
                model=None,
                sample_percentage=100.0,
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "failed"
            assert "No records were sampled" in finished.error
            assert not generate_mock.called


# ---------------------------------------------------------------------------
# start_compare_codebooks_job -- validation + enqueue
# ---------------------------------------------------------------------------


class TestStartCompareCodebooksJobValidation:
    async def test_non_proj_schema_a_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError, match="codebook_a"):
                await codebook_service.start_compare_codebooks_job(
                    session,
                    user.id,
                    codebook_a="not_proj",
                    codebook_b="proj_b",
                    api_key="k",
                    model=None,
                    prompt="",
                    name="my comparison",
                )

    async def test_non_proj_schema_b_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError, match="codebook_b"):
                await codebook_service.start_compare_codebooks_job(
                    session,
                    user.id,
                    codebook_a="proj_a",
                    codebook_b="not_proj",
                    api_key="k",
                    model=None,
                    prompt="",
                    name="my comparison",
                )

    async def test_missing_api_key_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError, match="api_key"):
                await codebook_service.start_compare_codebooks_job(
                    session,
                    user.id,
                    codebook_a="proj_a",
                    codebook_b="proj_b",
                    api_key="",
                    model=None,
                    prompt="",
                    name="my comparison",
                )

    async def test_blank_name_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError, match="name"):
                await codebook_service.start_compare_codebooks_job(
                    session,
                    user.id,
                    codebook_a="proj_a",
                    codebook_b="proj_b",
                    api_key="k",
                    model=None,
                    prompt="",
                    name="   ",
                )

    async def test_unowned_codebook_a_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_a = await _make_file(session, owner.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, other.id, file_type="codebook", schemaname="proj_b")
            with pytest.raises(NotFoundError):
                await codebook_service.start_compare_codebooks_job(
                    session,
                    other.id,
                    codebook_a=file_a.schemaname,
                    codebook_b=file_b.schemaname,
                    api_key="k",
                    model=None,
                    prompt="",
                    name="my comparison",
                )


class TestStartCompareCodebooksJobEnqueue:
    async def test_enqueues_pending_job_without_persisting_api_key(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")

            job = await codebook_service.start_compare_codebooks_job(
                session,
                user.id,
                codebook_a=file_a.schemaname,
                codebook_b=file_b.schemaname,
                api_key="sk-secret",
                model="some-model",
                prompt="focus on overlaps",
                name="my comparison",
            )

            assert job.status == "pending"
            assert job.job_type == "compare_codebooks"
            assert job.payload["file_id_a"] == file_a.id
            assert job.payload["file_id_b"] == file_b.id
            assert job.payload["name"] == "my comparison"
            assert "api_key" not in job.payload

            await _wait_for_terminal_status(session, job.id, user.id)


# ---------------------------------------------------------------------------
# _run_compare_codebooks_job -- end-to-end
# ---------------------------------------------------------------------------


class TestCompareCodebooksJobHandlerEndToEnd:
    async def test_reads_both_contents_and_calls_llm(self, session_factory, monkeypatch) -> None:
        get_client_mock = AsyncMock(return_value="the comparison text")
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.get_client",
            get_client_mock,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            file_a_id, file_b_id = file_a.id, file_b.id
            await _seed_codes(session, file_a_id, user.id, "codebook A text")
            await _seed_codes(session, file_b_id, user.id, "codebook B text")
            await session.commit()

            job = await codebook_service.start_compare_codebooks_job(
                session,
                user.id,
                codebook_a=file_a.schemaname,
                codebook_b=file_b.schemaname,
                api_key="sk-secret",
                model=None,
                prompt="",
                name="A vs B",
                description="  a nice comparison  ",
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error
            assert finished.result["comparison"] == "the comparison text"
            file_info = finished.result["file"]
            assert file_info["filename"] == "A vs B"
            assert file_info["schema_name"].startswith("cmp_")

            assert get_client_mock.called
            call_args = get_client_mock.call_args.args
            assert "codebook A text" in call_args[1]
            assert "codebook B text" in call_args[1]
            assert call_args[2] == "sk-secret"

            # The new File was actually persisted, with content and
            # FileDependency links to BOTH source codebooks.
            new_file_id = int(file_info["id"])
            result = await session.execute(select(File).where(File.id == new_file_id))
            new_file = result.scalar_one()
            assert new_file.file_type == "codebook_comparison"
            assert new_file.description == "a nice comparison"

            content = await version_service.read_blob(session, new_file_id)
            assert content == "the comparison text"

            edges = await version_repo.list_parent_edges(session, new_file_id)
            parent_ids = {e.parent_file_id for e in edges}
            assert parent_ids == {file_a_id, file_b_id}
            by_role = {e.role: e.parent_file_id for e in edges}
            assert by_role["side_a"] == file_a_id
            assert by_role["side_b"] == file_b_id

    async def test_no_content_marks_job_failed(self, session_factory, monkeypatch) -> None:
        get_client_mock = AsyncMock(return_value="should not be called")
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.get_client",
            get_client_mock,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")

            job = await codebook_service.start_compare_codebooks_job(
                session,
                user.id,
                codebook_a=file_a.schemaname,
                codebook_b=file_b.schemaname,
                api_key="sk-secret",
                model=None,
                prompt="",
                name="A vs B",
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "failed"
            # A codebook file with zero versions at all fails at the
            # read-as-parent seal step (version_service.pin_parent) with a
            # clearer error than the old "no content" -- there's no
            # content to be missing when there's no version history yet.
            assert "No version history" in finished.error
            assert not get_client_mock.called

    async def test_raises_context_budget_error_when_codebooks_dont_fit(self, session_factory, monkeypatch) -> None:
        # Codebooks are compact taxonomies with nothing to aggregate, so a
        # comparison that overflows the window fails loudly rather than
        # leaning on a silent middle-out truncation.
        get_client_mock = AsyncMock(return_value="should not be called")
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.get_client",
            get_client_mock,
        )
        monkeypatch.setattr(
            "backend.app.services.codebook_service.context_window.prompt_fits",
            lambda model, **kwargs: False,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            await _seed_codes(session, file_a.id, user.id, "codebook A text")
            await _seed_codes(session, file_b.id, user.id, "codebook B text")
            await session.commit()

            job = await codebook_service.start_compare_codebooks_job(
                session,
                user.id,
                codebook_a=file_a.schemaname,
                codebook_b=file_b.schemaname,
                api_key="sk-secret",
                model=None,
                prompt="",
                name="A vs B",
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "failed"
            assert "larger-context model" in finished.error
            assert not get_client_mock.called
