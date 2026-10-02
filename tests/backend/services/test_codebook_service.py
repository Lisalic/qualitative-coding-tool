"""Unit tests for backend/app/services/codebook_service.py.

Runs directly against an in-memory async SQLite session (the
``async_sqlite_engine`` fixture from ``tests/conftest.py``), bypassing the
HTTP layer entirely -- ``tests/backend/routes/test_codebook_routes.py`` and
``tests/backend/routes/test_ai_and_raw_sql_routes.py`` cover the
route/auth/response-shape behavior on top of this.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import File, User
from backend.app.jobs import service as jobs_service
from backend.app.jobs.models import TERMINAL_STATUSES
from backend.app.repositories import version_repo
from backend.app.services import codebook_service, version_service
from backend.app.services.version_service import EdgeSpec
from backend.app.storage_models import Comment, Submission
from backend.app.versioning_models import RELATION_COMPARED, ROLE_SIDE_A, ROLE_SIDE_B


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
        if job.status in TERMINAL_STATUSES:
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


# ---------------------------------------------------------------------------
# codebook_preview + create_manual_codebook (the /codebook-editor pair)
# ---------------------------------------------------------------------------


def _proposal_json(*names: str) -> str:
    return json.dumps(
        {
            "codes": [
                {
                    "family": "F",
                    "name": name,
                    "definition": "a def",
                    "inclusion": "when",
                    "exclusion": "not when",
                    "keywords": "kw",
                    "example": "ex",
                }
                for name in names
            ]
        }
    )


async def _seed_source(session, user) -> File:
    file_rec = await _make_file(session, user.id)
    session.add_all(
        [
            Submission(file_id=file_rec.id, id="s1", title="t1", selftext="x1", word_count=5),
            Comment(file_id=file_rec.id, id="c1", body="b1", word_count=3),
        ]
    )
    await session.commit()
    return file_rec


class TestCodebookPreviewJob:
    async def test_returns_proposals_and_creates_nothing(self, session_factory, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.generate_codebook",
            AsyncMock(return_value=(_proposal_json("Bullying", "Exclusion"), "sys", "user")),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _seed_source(session, user)

            files_before = len((await session.execute(select(File))).scalars().all())

            job = await codebook_service.start_codebook_preview_job(
                session,
                user.id,
                database=file_rec.schemaname,
                api_key="sk-secret",
                model=None,
                prompt="be thorough",
                sample_percentage=100.0,
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error

            assert [p["name"] for p in finished.result["proposals"]] == ["Bullying", "Exclusion"]
            assert finished.result["proposals"][0]["definition"] == "a def"

            # A proposal is not an artifact: no File, and no version on any
            # file, is created by a preview run.
            session.expire_all()
            files_after = (await session.execute(select(File))).scalars().all()
            assert len(files_after) == files_before
            for existing in files_after:
                assert await version_repo.head_version(session, existing.id) is None

    async def test_drops_a_proposal_the_draft_already_covers(self, session_factory, monkeypatch) -> None:
        """The prompt asks the model not to restate an existing code, but a
        prompt is not a guarantee -- and a run started before the researcher
        added a code must not be able to re-propose it on return."""
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.generate_codebook",
            AsyncMock(return_value=(_proposal_json("Bullying", "Exclusion"), "sys", "user")),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _seed_source(session, user)

            job = await codebook_service.start_codebook_preview_job(
                session,
                user.id,
                database=file_rec.schemaname,
                api_key="sk-secret",
                model=None,
                prompt="",
                sample_percentage=100.0,
                # Same code, differently cased and padded -- the dedupe key
                # is normalized, and must agree with the client's.
                existing_codes=[{"family_name": " f ", "name": "BULLYING"}],
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error
            assert [p["name"] for p in finished.result["proposals"]] == ["Exclusion"]

    async def test_sends_the_draft_to_the_model_as_existing_codes(
        self, session_factory, monkeypatch
    ) -> None:
        generate_mock = AsyncMock(return_value=(_proposal_json("Exclusion"), "sys", "user"))
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.generate_codebook",
            generate_mock,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _seed_source(session, user)

            job = await codebook_service.start_codebook_preview_job(
                session,
                user.id,
                database=file_rec.schemaname,
                api_key="sk-secret",
                model=None,
                prompt="",
                sample_percentage=100.0,
                existing_codes=[{"family_name": "F", "name": "Bullying", "definition": "a def"}],
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error

            system_prompt = generate_mock.await_args.kwargs["existing_codes"]
            assert "F :: Bullying -- a def" in system_prompt

    async def test_no_records_sampled_marks_job_failed(self, session_factory, monkeypatch) -> None:
        generate_mock = AsyncMock(return_value=("should not run", "", ""))
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.generate_codebook",
            generate_mock,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)  # no submissions/comments

            job = await codebook_service.start_codebook_preview_job(
                session,
                user.id,
                database=file_rec.schemaname,
                api_key="sk-secret",
                model=None,
                prompt="",
                sample_percentage=100.0,
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "failed"
            assert "No records were sampled" in finished.error
            assert not generate_mock.called

    async def test_api_key_is_required_and_never_persisted(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _seed_source(session, user)

            with pytest.raises(ValidationAppError):
                await codebook_service.start_codebook_preview_job(
                    session,
                    user.id,
                    database=file_rec.schemaname,
                    api_key="",
                    model=None,
                    prompt="",
                    sample_percentage=100.0,
                )

    async def test_source_must_be_owned_by_the_caller(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_rec = await _seed_source(session, owner)

            with pytest.raises(NotFoundError):
                await codebook_service.start_codebook_preview_job(
                    session,
                    other.id,
                    database=file_rec.schemaname,
                    api_key="sk-secret",
                    model=None,
                    prompt="",
                    sample_percentage=100.0,
                )


class TestCreateManualCodebook:
    _CODES = [
        {
            "code_uid": "u1", "family_uid": "f1", "family_name": "Harm", "name": "Bullying",
            "is_new": True, "family_is_new": True, "definition": "a def", "position": 0,
        },
        {
            "code_uid": "u2", "family_uid": "f1", "family_name": "Harm", "name": "Exclusion",
            "is_new": True, "definition": "another def", "position": 1,
        },
    ]

    async def test_creates_a_codebook_with_edited_provenance(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            source = await _seed_source(session, user)

            file_rec = await codebook_service.create_manual_codebook(
                session,
                user.id,
                database=source.schemaname,
                name="hand written",
                description="notes",
                project_id=None,
                codes=list(self._CODES),
            )

            assert file_rec.file_type == "codebook"
            assert file_rec.filename == "hand written"
            assert file_rec.description == "notes"
            assert file_rec.schemaname.startswith("proj_")

            codes = await version_service.read_codes(session, file_rec.id)
            assert [c.name for c in codes] == ["Bullying", "Exclusion"]
            # Client-minted identity is used as-is rather than re-minted, so
            # a later edit reads as an edit and not a delete-plus-add.
            assert [c.code_uid for c in codes] == ["u1", "u2"]
            assert {c.family_uid for c in codes} == {"f1"}

    async def test_records_no_model_provenance(self, session_factory) -> None:
        """An assist during editing is not the claim that a model produced
        the artifact -- overstating it would make these fields useless for
        auditing which artifacts an LLM actually generated."""
        async with session_factory() as session:
            user = await _make_user(session)
            source = await _seed_source(session, user)

            file_rec = await codebook_service.create_manual_codebook(
                session, user.id, database=source.schemaname, name="hand written",
                description=None, project_id=None, codes=list(self._CODES),
            )

            head = await version_repo.head_version(session, file_rec.id)
            assert head.origin == "edited"
            assert head.version_no == 1
            assert head.model is None
            assert head.system_prompt is None
            assert head.user_instructions is None
            assert head.prompt_meta is None
            assert "Composed by hand from 2 codes" in head.message

    async def test_links_lineage_back_to_the_source_data(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            source = await _seed_source(session, user)

            file_rec = await codebook_service.create_manual_codebook(
                session, user.id, database=source.schemaname, name="hand written",
                description=None, project_id=None, codes=list(self._CODES),
            )

            edges = await version_repo.list_parent_edges(session, file_rec.id)
            assert [e.parent_file_id for e in edges] == [source.id]
            assert edges[0].relation == "derived_from"
            assert edges[0].role == "source_data"

    async def test_rejects_a_code_with_no_identity(self, session_factory) -> None:
        """`_resolve_code_rows` refuses to silently mint an identity -- the
        same guard the hand-edit save path relies on."""
        async with session_factory() as session:
            user = await _make_user(session)
            source = await _seed_source(session, user)

            with pytest.raises(ValidationAppError):
                await codebook_service.create_manual_codebook(
                    session, user.id, database=source.schemaname, name="x",
                    description=None, project_id=None,
                    codes=[{"family_name": "Harm", "name": "Bullying"}],
                )

    async def test_source_must_be_owned_by_the_caller(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            source = await _seed_source(session, owner)

            with pytest.raises(NotFoundError):
                await codebook_service.create_manual_codebook(
                    session, other.id, database=source.schemaname, name="x",
                    description=None, project_id=None, codes=list(self._CODES),
                )


class TestCreateManualCodebookAssistProvenance:
    """C2: assist_runs records what a codebook_preview job contributed,
    without changing the version's own origin/model -- pairs with
    ``TestCreateManualCodebook.test_records_no_model_provenance``.
    """

    _CODES = TestCreateManualCodebook._CODES

    async def _make_succeeded_job(self, session, *, user_id: int, source_file_id: int):
        from backend.app.jobs.models import Job

        job = Job(
            job_type="codebook_preview", user_id=user_id, status="succeeded",
            payload={"source_file_id": source_file_id, "model": "openai/gpt-x"},
            result={"system_prompt": "sys", "user_instructions": "find codes", "prompt_meta": None},
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job

    async def test_records_an_assist_run_without_touching_version_provenance(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            source = await _seed_source(session, user)
            job = await self._make_succeeded_job(session, user_id=user.id, source_file_id=source.id)

            file_rec = await codebook_service.create_manual_codebook(
                session, user.id, database=source.schemaname, name="hand written",
                description=None, project_id=None, codes=list(self._CODES),
                assist_runs=[{"job_id": job.id, "proposed_count": 3, "accepted_count": 2, "dismissed_count": 1, "accepted_refs": ["u1", "u2"]}],
            )

            head = await version_repo.head_version(session, file_rec.id)
            assert head.origin == "edited"
            assert head.model is None

            from backend.app.services import assist_service
            assists = await assist_service.list_assists(session, file_rec.id)
            assert len(assists) == 1
            assert assists[0]["model"] == "openai/gpt-x"
            assert assists[0]["accepted_refs"] == ["u1", "u2"]

    async def test_rejects_a_job_from_a_different_source(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            source = await _seed_source(session, user)
            other_source = await _seed_source(session, user)
            job = await self._make_succeeded_job(session, user_id=user.id, source_file_id=other_source.id)

            with pytest.raises(ValidationAppError):
                await codebook_service.create_manual_codebook(
                    session, user.id, database=source.schemaname, name="hand written",
                    description=None, project_id=None, codes=list(self._CODES),
                    assist_runs=[{"job_id": job.id}],
                )



# ---------------------------------------------------------------------------
# integrate_codebooks -- the AI-assist preview + manual submit pair, one
# level up from codebook_preview/create_manual_codebook: instead of
# proposing codes from raw data, this proposes codes merged from two or
# more existing codebooks. See tests/backend/services/test_assist_service.py
# for the ASSIST_STAGE_INTEGRATE-specific provenance checks.
# ---------------------------------------------------------------------------


def _merge_proposal_json(*entries: tuple[str, list[dict]]) -> str:
    """Build an integrate-preview JSON body. Each entry is
    ``(name, sources)`` where ``sources`` is a list of
    ``{"codebook": i, "family": f, "name": n}`` dicts."""
    return json.dumps(
        {
            "codes": [
                {
                    "family": "F",
                    "name": name,
                    "definition": "a def",
                    "inclusion": "when",
                    "exclusion": "not when",
                    "keywords": "kw",
                    "example": "ex",
                    "sources": sources,
                    "rationale": "" if len(sources) < 2 else "merged from multiple sources",
                }
                for name, sources in entries
            ]
        }
    )


class TestStartIntegrateCodebookJobValidation:
    async def test_non_proj_schema_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError, match="codebooks"):
                await codebook_service.start_integrate_codebook_job(
                    session, user.id, codebooks=["not_proj", "proj_b"], api_key="k", model=None, prompt="",
                )

    async def test_a_single_codebook_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            with pytest.raises(ValidationAppError, match="at least two"):
                await codebook_service.start_integrate_codebook_job(
                    session, user.id, codebooks=[file_a.schemaname], api_key="k", model=None, prompt="",
                )

    async def test_two_refs_deduping_to_one_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            with pytest.raises(ValidationAppError, match="at least two"):
                await codebook_service.start_integrate_codebook_job(
                    session,
                    user.id,
                    codebooks=[file_a.schemaname, file_a.schemaname],
                    api_key="k",
                    model=None,
                    prompt="",
                )

    async def test_missing_api_key_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            with pytest.raises(ValidationAppError, match="api_key"):
                await codebook_service.start_integrate_codebook_job(
                    session,
                    user.id,
                    codebooks=[file_a.schemaname, file_b.schemaname],
                    api_key="",
                    model=None,
                    prompt="",
                )

    async def test_unowned_codebook_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_a = await _make_file(session, owner.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, other.id, file_type="codebook", schemaname="proj_b")
            with pytest.raises(NotFoundError):
                await codebook_service.start_integrate_codebook_job(
                    session,
                    other.id,
                    codebooks=[file_a.schemaname, file_b.schemaname],
                    api_key="k",
                    model=None,
                    prompt="",
                )

    async def test_a_non_codebook_ref_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            raw = await _make_file(session, user.id, file_type="raw_data", schemaname="proj_raw")
            with pytest.raises(NotFoundError):
                await codebook_service.start_integrate_codebook_job(
                    session,
                    user.id,
                    codebooks=[file_a.schemaname, raw.schemaname],
                    api_key="k",
                    model=None,
                    prompt="",
                )


class TestStartIntegrateCodebookJobEnqueue:
    async def test_enqueues_pending_job_without_persisting_api_key(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")

            job = await codebook_service.start_integrate_codebook_job(
                session,
                user.id,
                codebooks=[file_a.schemaname, file_b.schemaname],
                api_key="sk-secret",
                model="some-model",
                prompt="merge carefully",
            )

            assert job.status == "pending"
            assert job.job_type == "integrate_codebook_preview"
            assert job.payload["source_file_ids"] == [file_a.id, file_b.id]
            assert "api_key" not in job.payload

            await _wait_for_terminal_status(session, job.id, user.id)


class TestIntegrateCodebookJobHandlerEndToEnd:
    async def test_verifies_and_dedupes_proposals(self, session_factory, monkeypatch) -> None:
        # Three proposals: one with two resolvable sources (a real merge),
        # one claiming a source that doesn't exist (bogus codebook index),
        # and one that duplicates a code already in the researcher's draft.
        # _seed_codes seeds one code per file: family "F", name "C".
        result_json = _merge_proposal_json(
            ("Merged Code", [
                {"codebook": 1, "family": "F", "name": "C"},
                {"codebook": 2, "family": "F", "name": "C"},
            ]),
            ("Invented Code", [{"codebook": 99, "family": "F", "name": "Nope"}]),
            ("Already Covered", [{"codebook": 1, "family": "F", "name": "C"}]),
        )
        integrate_mock = AsyncMock(return_value=(result_json, "sys", "user"))
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.integrate_codebooks",
            integrate_mock,
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            file_a_id, file_b_id = file_a.id, file_b.id
            file_a_schema, file_b_schema = file_a.schemaname, file_b.schemaname
            await _seed_codes(session, file_a_id, user.id, "codebook A text")
            await _seed_codes(session, file_b_id, user.id, "codebook B text")
            await session.commit()

            files_before = len((await session.execute(select(File))).scalars().all())

            job = await codebook_service.start_integrate_codebook_job(
                session,
                user.id,
                codebooks=[file_a_schema, file_b_schema],
                api_key="sk-secret",
                model=None,
                prompt="",
                existing_codes=[{"family_name": "F", "name": "Already Covered"}],
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error

            proposals = {p["name"]: p for p in finished.result["proposals"]}
            assert set(proposals) == {"Merged Code", "Invented Code"}

            merged = proposals["Merged Code"]
            assert len(merged["sources"]) == 2
            source_codebooks = {s["codebook"] for s in merged["sources"]}
            assert source_codebooks == {file_a_schema, file_b_schema}

            invented = proposals["Invented Code"]
            assert invented["sources"] == []

            assert finished.result["system_prompt"] == "sys"
            assert finished.result["user_instructions"] == ""

            # A proposal is not an artifact -- no new File is created by a
            # preview run (file_a/file_b already have their seeded v1 from
            # setup above, so this checks the file COUNT rather than
            # "no file has a version").
            session.expire_all()
            files_after = (await session.execute(select(File))).scalars().all()
            assert len(files_after) == files_before

    async def test_raises_context_budget_error_when_codebooks_dont_fit(self, session_factory, monkeypatch) -> None:
        integrate_mock = AsyncMock(return_value=("should not be called", "", ""))
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.integrate_codebooks",
            integrate_mock,
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

            job = await codebook_service.start_integrate_codebook_job(
                session,
                user.id,
                codebooks=[file_a.schemaname, file_b.schemaname],
                api_key="sk-secret",
                model=None,
                prompt="",
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "failed"
            assert "too large to integrate" in finished.error
            assert not integrate_mock.called


class TestIntegrateCodebookWithComparison:
    """A Compare Codebook report chosen in the integrate workspace goes to
    the model as merge guidance -- ownership- and type-checked, never
    accepted as a source codebook."""

    async def _seed(self, session, owner_id: int):
        file_a = await _make_file(session, owner_id, file_type="codebook", schemaname="proj_a")
        file_b = await _make_file(session, owner_id, file_type="codebook", schemaname="proj_b")
        await _seed_codes(session, file_a.id, owner_id, "codebook A text")
        await _seed_codes(session, file_b.id, owner_id, "codebook B text")
        cmp_file = await _make_file(
            session, owner_id, file_type="codebook_comparison", schemaname="cmp_ab", filename="A vs B",
        )
        await version_service.commit_blob_version(
            session, file_id=cmp_file.id, author_user_id=owner_id, origin="generated",
            content="Merge C from both; they overlap heavily.",
        )
        await session.commit()
        return file_a, file_b, cmp_file

    async def test_comparison_text_reaches_the_prompt(self, session_factory, monkeypatch) -> None:
        integrate_mock = AsyncMock(return_value=(_merge_proposal_json(), "sys", "user"))
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.integrate_codebooks",
            integrate_mock,
        )
        async with session_factory() as session:
            user = await _make_user(session)
            file_a, file_b, cmp_file = await self._seed(session, user.id)

            job = await codebook_service.start_integrate_codebook_job(
                session,
                user.id,
                codebooks=[file_a.schemaname, file_b.schemaname],
                api_key="k",
                model=None,
                prompt="keep C separate",
                comparisons=[cmp_file.schemaname, cmp_file.schemaname],
            )
            assert job.payload["comparison_file_ids"] == [cmp_file.id]

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error

        blocks = integrate_mock.call_args.kwargs["comparison_blocks"]
        assert "--- COMPARISON REPORT: A vs B ---" in blocks
        assert "Merge C from both" in blocks

    async def test_no_comparison_sends_empty_blocks(self, session_factory, monkeypatch) -> None:
        integrate_mock = AsyncMock(return_value=(_merge_proposal_json(), "sys", "user"))
        monkeypatch.setattr(
            "backend.app.services.codebook_service.codebook_generator_module.integrate_codebooks",
            integrate_mock,
        )
        async with session_factory() as session:
            user = await _make_user(session)
            file_a, file_b, _ = await self._seed(session, user.id)
            job = await codebook_service.start_integrate_codebook_job(
                session, user.id, codebooks=[file_a.schemaname, file_b.schemaname],
                api_key="k", model=None, prompt="",
            )
            assert job.payload["comparison_file_ids"] == []
            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error

        assert integrate_mock.call_args.kwargs["comparison_blocks"] == ""

    async def test_a_codebook_passed_as_comparison_is_rejected(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a, file_b, _ = await self._seed(session, user.id)
            with pytest.raises(ValidationAppError, match="comparisons"):
                await codebook_service.start_integrate_codebook_job(
                    session, user.id, codebooks=[file_a.schemaname, file_b.schemaname],
                    api_key="k", model=None, prompt="", comparisons=[file_a.schemaname],
                )

    async def test_another_users_comparison_is_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            _, _, cmp_file = await self._seed(session, owner.id)
            other_a = await _make_file(session, other.id, file_type="codebook", schemaname="proj_oa")
            other_b = await _make_file(session, other.id, file_type="codebook", schemaname="proj_ob")
            with pytest.raises(NotFoundError):
                await codebook_service.start_integrate_codebook_job(
                    session, other.id, codebooks=[other_a.schemaname, other_b.schemaname],
                    api_key="k", model=None, prompt="", comparisons=[cmp_file.schemaname],
                )


class TestCreateIntegratedCodebook:
    _CODES = [
        {
            "code_uid": "u1", "family_uid": "f1", "family_name": "Harm", "name": "Bullying",
            "is_new": True, "family_is_new": True, "definition": "a def", "position": 0,
        },
        {
            "code_uid": "u2", "family_uid": "f1", "family_name": "Harm", "name": "Exclusion",
            "is_new": True, "definition": "another def", "position": 1,
        },
    ]

    async def test_creates_a_codebook_with_edited_provenance(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            await _seed_codes(session, file_a.id, user.id, "a")
            await _seed_codes(session, file_b.id, user.id, "b")
            await session.commit()

            file_rec = await codebook_service.create_integrated_codebook(
                session,
                user.id,
                codebooks=[file_a.schemaname, file_b.schemaname],
                name="integrated",
                description=None,
                project_id=None,
                codes=list(self._CODES),
            )

            assert file_rec.file_type == "codebook"
            assert file_rec.schemaname.startswith("proj_")

            head = await version_repo.head_version(session, file_rec.id)
            assert head.origin == "edited"
            assert head.version_no == 1
            assert head.model is None
            assert head.system_prompt is None
            assert "Integrated from 2 codebooks" in head.message

    async def test_links_n_merge_input_edges_in_order(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            file_c = await _make_file(session, user.id, file_type="codebook", schemaname="proj_c")
            for f in (file_a, file_b, file_c):
                await _seed_codes(session, f.id, user.id, f.schemaname)
            await session.commit()

            file_rec = await codebook_service.create_integrated_codebook(
                session,
                user.id,
                codebooks=[file_a.schemaname, file_b.schemaname, file_c.schemaname],
                name="integrated",
                description=None,
                project_id=None,
                codes=list(self._CODES),
            )

            edges = await version_repo.list_parent_edges(session, file_rec.id)
            assert [e.parent_file_id for e in edges] == [file_a.id, file_b.id, file_c.id]
            assert all(e.relation == "merged_from" for e in edges)
            assert all(e.role == "merge_input" for e in edges)
            assert [e.position for e in edges] == [0, 1, 2]

    async def test_rejects_a_code_with_no_identity(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            await _seed_codes(session, file_a.id, user.id, "a")
            await _seed_codes(session, file_b.id, user.id, "b")
            await session.commit()

            with pytest.raises(ValidationAppError):
                await codebook_service.create_integrated_codebook(
                    session,
                    user.id,
                    codebooks=[file_a.schemaname, file_b.schemaname],
                    name="x",
                    description=None,
                    project_id=None,
                    codes=[{"family_name": "Harm", "name": "Bullying"}],
                )

    async def test_records_assist_provenance_with_integrate_stage(self, session_factory) -> None:
        from backend.app.jobs.models import Job

        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            await _seed_codes(session, file_a.id, user.id, "a")
            await _seed_codes(session, file_b.id, user.id, "b")
            await session.commit()

            job = Job(
                job_type="integrate_codebook_preview",
                user_id=user.id,
                status="succeeded",
                payload={"source_file_ids": [file_a.id, file_b.id], "model": "openai/gpt-x"},
                result={"system_prompt": "sys", "user_instructions": "merge", "prompt_meta": None},
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)

            file_rec = await codebook_service.create_integrated_codebook(
                session,
                user.id,
                codebooks=[file_a.schemaname, file_b.schemaname],
                name="integrated",
                description=None,
                project_id=None,
                codes=list(self._CODES),
                assist_runs=[
                    {"job_id": job.id, "proposed_count": 3, "accepted_count": 2, "dismissed_count": 1, "accepted_refs": ["u1", "u2"]}
                ],
            )

            from backend.app.services import assist_service
            assists = await assist_service.list_assists(session, file_rec.id)
            assert len(assists) == 1
            assert assists[0]["stage"] == "integrate"
            assert assists[0]["model"] == "openai/gpt-x"

    async def test_source_must_be_owned_by_the_caller(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_a = await _make_file(session, owner.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, owner.id, file_type="codebook", schemaname="proj_b")
            await _seed_codes(session, file_a.id, owner.id, "a")
            await _seed_codes(session, file_b.id, owner.id, "b")
            await session.commit()

            with pytest.raises(NotFoundError):
                await codebook_service.create_integrated_codebook(
                    session,
                    other.id,
                    codebooks=[file_a.schemaname, file_b.schemaname],
                    name="x",
                    description=None,
                    project_id=None,
                    codes=list(self._CODES),
                )


# ---------------------------------------------------------------------------
# list_comparisons_between
# ---------------------------------------------------------------------------


class TestListComparisonsBetween:
    """Only comparisons made between two of the selected codebooks count --
    one against an unselected codebook does not."""

    async def _comparison(self, session, owner_id: int, schemaname: str, side_a: File, side_b: File) -> File:
        cmp_file = await _make_file(session, owner_id, file_type="codebook_comparison", schemaname=schemaname)
        await version_service.commit_blob_version(
            session, file_id=cmp_file.id, author_user_id=owner_id, origin="generated", content="report",
            parents=[
                EdgeSpec(parent_file_id=side_a.id, relation=RELATION_COMPARED, role=ROLE_SIDE_A, position=0),
                EdgeSpec(parent_file_id=side_b.id, relation=RELATION_COMPARED, role=ROLE_SIDE_B, position=1),
            ],
        )
        await session.commit()
        return cmp_file

    async def test_returns_only_comparisons_between_selected(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            file_c = await _make_file(session, user.id, file_type="codebook", schemaname="proj_c")
            file_d = await _make_file(session, user.id, file_type="codebook", schemaname="proj_d")
            cmp_bc = await self._comparison(session, user.id, "cmp_bc", file_b, file_c)
            await self._comparison(session, user.id, "cmp_ad", file_a, file_d)

            found = await codebook_service.list_comparisons_between(
                session, user.id, [file_a.schemaname, file_b.schemaname, file_c.schemaname]
            )
            assert [f.id for f in found] == [cmp_bc.id]

    async def test_empty_when_only_compared_with_outside_codebooks(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            file_b = await _make_file(session, user.id, file_type="codebook", schemaname="proj_b")
            file_c = await _make_file(session, user.id, file_type="codebook", schemaname="proj_c")
            await self._comparison(session, user.id, "cmp_ac", file_a, file_c)

            found = await codebook_service.list_comparisons_between(
                session, user.id, [file_a.schemaname, file_b.schemaname]
            )
            assert found == []

    async def test_rejects_non_codebook_ref(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_a = await _make_file(session, user.id, file_type="codebook", schemaname="proj_a")
            await _make_file(session, user.id, file_type="raw_data", schemaname="proj_raw")

            with pytest.raises(NotFoundError):
                await codebook_service.list_comparisons_between(session, user.id, [file_a.schemaname, "proj_raw"])
