"""Unit tests for backend/app/services/data_service.py.

Runs directly against an in-memory async SQLite session (the
``async_sqlite_engine`` fixture from ``tests/conftest.py``), bypassing the
HTTP layer entirely -- ``tests/backend/routes/test_ai_and_raw_sql_routes.py``
covers the route/auth/response-shape behavior on top of this.

Note on Postgres-only SQL: the tag-based pre-filter predicate fragments
(``tag_expansion.py::submission_text_tag_predicate_sql``/
``comment_body_tag_predicate_sql``) compile to Postgres's ``position(...)``
function, which SQLite doesn't implement -- so the ``filter_tags``-supplied
path through ``_run_filter_data_job``/``_sample_source_rows`` isn't
exercised here and needs the opt-in Postgres integration suite. Everything
else (word-count binning, file entries, comments, post contents, the
tag-free AI-filter job path, and the SQL-injection regression test) runs
against SQLite.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import File, User
from backend.app.repositories import version_repo
from backend.app.jobs import service as jobs_service
from backend.app.services import data_service
from backend.app.storage_models import Comment, Submission


@pytest.fixture()
def session_factory(async_sqlite_engine):
    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def patch_async_session_local(monkeypatch, session_factory):
    """``_run_filter_data_job`` opens its own session via the module-level
    ``AsyncSessionLocal`` imported into ``backend.app.services.data_service``
    -- point that (and the job runner's own session factory) at the
    in-memory SQLite engine backing this test's session.
    """
    monkeypatch.setattr("backend.app.services.data_service.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("backend.app.jobs.service.AsyncSessionLocal", session_factory)


async def _make_user(session, email: str = "a@b.com") -> User:
    user = User(email=email, password="hash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_file(session, user_id: int, *, file_type: str = "raw_data", schemaname: str = "proj_src") -> File:
    file_rec = File(user_id=user_id, filename="f", schemaname=schemaname, file_type=file_type)
    session.add(file_rec)
    await session.commit()
    await session.refresh(file_rec)
    return file_rec


async def _wait_for_terminal_status(session, job_id: int, user_id: int, timeout: float = 5.0):
    """Same polling helper as tests/backend/services/test_coding_service.py."""
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
# get_word_count_ranges
# ---------------------------------------------------------------------------


class TestGetWordCountRanges:
    async def test_bins_word_counts_in_steps_of_10(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="a", selftext="b", word_count=12),
                    Submission(file_id=file_rec.id, id="s2", title="c", selftext="d", word_count=15),
                    Submission(file_id=file_rec.id, id="s3", title="e", selftext="f", word_count=47),
                    Comment(file_id=file_rec.id, id="c1", body="x", word_count=3),
                ]
            )
            await session.commit()

            ranges = await data_service.get_word_count_ranges(session, user.id, file_rec.schemaname)
            subs_by_bin = {r["min_words"]: r["count"] for r in ranges["submissions"]}
            assert subs_by_bin == {10: 2, 40: 1}
            comm_by_bin = {r["min_words"]: r["count"] for r in ranges["comments"]}
            assert comm_by_bin == {0: 1}

    async def test_word_count_over_1000_excluded(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add(Submission(file_id=file_rec.id, id="s1", word_count=5000))
            await session.commit()

            ranges = await data_service.get_word_count_ranges(session, user.id, file_rec.schemaname)
            assert ranges["submissions"] == []

    async def test_invalid_schema_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await data_service.get_word_count_ranges(session, user.id, "not_proj")

    async def test_unowned_schema_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_rec = await _make_file(session, owner.id)
            with pytest.raises(NotFoundError):
                await data_service.get_word_count_ranges(session, other.id, file_rec.schemaname)


# ---------------------------------------------------------------------------
# get_file_entries
# ---------------------------------------------------------------------------


class TestGetFileEntries:
    async def test_returns_paginated_rows_and_totals(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id=f"s{i}", title=f"t{i}", word_count=1)
                    for i in range(3)
                ]
            )
            await session.commit()

            entries = await data_service.get_file_entries(session, user.id, file_rec.schemaname, limit=2, offset=0)
            assert entries["total_submissions"] == 3
            assert len(entries["submissions"]) == 2
            assert entries["database"] == file_rec.schemaname

            page2 = await data_service.get_file_entries(session, user.id, file_rec.schemaname, limit=2, offset=2)
            assert len(page2["submissions"]) == 1

    async def test_serialized_rows_omit_file_id(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add(Submission(file_id=file_rec.id, id="s1", title="t", word_count=1))
            await session.commit()

            entries = await data_service.get_file_entries(session, user.id, file_rec.schemaname, limit=10, offset=0)
            assert "file_id" not in entries["submissions"][0]
            assert entries["submissions"][0]["id"] == "s1"


# ---------------------------------------------------------------------------
# get_comments_for_submission
# ---------------------------------------------------------------------------


class TestGetCommentsForSubmission:
    async def test_filters_by_link_id(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Comment(file_id=file_rec.id, id="c1", body="hi", link_id="sub1", created_utc=1, word_count=1),
                    Comment(file_id=file_rec.id, id="c2", body="no", link_id="sub2", created_utc=1, word_count=1),
                ]
            )
            await session.commit()

            result = await data_service.get_comments_for_submission(session, user.id, "sub1", file_rec.schemaname)
            assert [c["id"] for c in result["comments"]] == ["c1"]

    async def test_non_proj_schema_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await data_service.get_comments_for_submission(session, user.id, "sub1", "not_proj")


# ---------------------------------------------------------------------------
# get_post_contents -- including the SQL-injection regression test
# ---------------------------------------------------------------------------


class TestGetPostContents:
    async def test_returns_title_and_content_for_matching_ids(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="T1", selftext="B1", word_count=2),
                    Submission(file_id=file_rec.id, id="s2", title="T2", selftext="B2", word_count=2),
                ]
            )
            await session.commit()

            result = await data_service.get_post_contents(session, user.id, file_rec.schemaname, ["s1"])
            assert result["contents"] == {
                "s1": {
                    "type": "submission",
                    "title": "T1",
                    "content": "B1",
                    "parent_id": None,
                    "parent_title": None,
                }
            }

    async def test_resolves_a_qualified_comment_id_with_its_parent_title(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="Parent Post", selftext="B1", word_count=2),
                    Comment(file_id=file_rec.id, id="c1", body="a reply", link_id="s1", word_count=2),
                ]
            )
            await session.commit()

            result = await data_service.get_post_contents(
                session, user.id, file_rec.schemaname, ["t1_c1"]
            )
            assert result["contents"] == {
                "t1_c1": {
                    "type": "comment",
                    "title": None,
                    "content": "a reply",
                    "parent_id": "s1",
                    "parent_title": "Parent Post",
                }
            }

    async def test_legacy_unprefixed_comment_id_falls_back_to_comments_table(
        self, session_factory
    ) -> None:
        # Every coding artifact saved before item types existed stored a
        # bare (unprefixed) id for a coded comment -- split_item_id
        # defaults an unprefixed id to "submission", so the submission
        # lookup misses and this must retry against comments instead of
        # silently returning nothing (the pre-existing bug this fixes).
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add(
                Comment(file_id=file_rec.id, id="c1", body="legacy reply", word_count=2)
            )
            await session.commit()

            result = await data_service.get_post_contents(session, user.id, file_rec.schemaname, ["c1"])
            assert result["contents"] == {
                "c1": {
                    "type": "comment",
                    "title": None,
                    "content": "legacy reply",
                    "parent_id": None,
                    "parent_title": None,
                }
            }

    async def test_comment_with_parent_not_in_file_omits_parent_title(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add(
                Comment(file_id=file_rec.id, id="c1", body="orphaned reply", link_id="missing", word_count=2)
            )
            await session.commit()

            result = await data_service.get_post_contents(
                session, user.id, file_rec.schemaname, ["t1_c1"]
            )
            assert result["contents"]["t1_c1"]["parent_title"] is None
            assert result["contents"]["t1_c1"]["parent_id"] == "missing"

    async def test_missing_schema_or_post_ids_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await data_service.get_post_contents(session, user.id, "", ["1"])
            with pytest.raises(ValidationAppError):
                await data_service.get_post_contents(session, user.id, "proj_a", [])

    @pytest.mark.parametrize(
        "schema",
        [
            "1abc",
            "proj a",
            "proj-a",
            'proj_a"; DROP TABLE submissions; --',
            "not_proj_prefixed",
            "proj_a; DROP TABLE submissions;",
        ],
    )
    async def test_sql_metacharacter_schema_names_rejected_at_service_layer(
        self, session_factory, schema
    ) -> None:
        """Regression test for the original SQL-injection-adjacent gap.

        Proves the rejection survives the full rewrite at the *service*
        layer -- not just the route-level Stage-0 guard clause. Even a
        schema string carrying SQL metacharacters never reaches a query:
        ``require_valid_schema`` rejects it structurally before
        ``file_repo.resolve_file_id`` (and therefore any SQL) runs.
        """
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await data_service.get_post_contents(session, user.id, schema, ["1"])

    async def test_unowned_schema_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_rec = await _make_file(session, owner.id)
            with pytest.raises(NotFoundError):
                await data_service.get_post_contents(session, other.id, file_rec.schemaname, ["1"])


# ---------------------------------------------------------------------------
# start_filter_data_job -- validation + enqueue
# ---------------------------------------------------------------------------


class TestStartFilterDataJobValidation:
    async def test_non_proj_database_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError, match="database"):
                await data_service.start_filter_data_job(
                    session,
                    user.id,
                    database="not_proj",
                    name="n",
                    api_key="k",
                    model=None,
                    prompt="",
                    min_words=0,
                    sample_percentage=100.0,
                    filter_tags=None,
                    description=None,
                    project_id=None,
                )

    async def test_missing_api_key_raises(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            with pytest.raises(ValidationAppError, match="api_key"):
                await data_service.start_filter_data_job(
                    session,
                    user.id,
                    database=file_rec.schemaname,
                    name="n",
                    api_key="",
                    model=None,
                    prompt="",
                    min_words=0,
                    sample_percentage=100.0,
                    filter_tags=None,
                    description=None,
                    project_id=None,
                )

    async def test_unowned_database_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@x.com")
            other = await _make_user(session, "other@x.com")
            file_rec = await _make_file(session, owner.id)
            with pytest.raises(NotFoundError):
                await data_service.start_filter_data_job(
                    session,
                    other.id,
                    database=file_rec.schemaname,
                    name="n",
                    api_key="k",
                    model=None,
                    prompt="",
                    min_words=0,
                    sample_percentage=100.0,
                    filter_tags=None,
                    description=None,
                    project_id=None,
                )


class TestStartFilterDataJobEnqueue:
    async def test_enqueues_pending_job_without_persisting_api_key(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)

            job = await data_service.start_filter_data_job(
                session,
                user.id,
                database=file_rec.schemaname,
                name="filtered",
                api_key="sk-secret",
                model="some-model",
                prompt="",
                min_words=0,
                sample_percentage=100.0,
                filter_tags=None,
                description=None,
                project_id=None,
            )

            assert job.status == "pending"
            assert job.job_type == "filter_data"
            assert job.payload["source_file_id"] == file_rec.id
            assert "api_key" not in job.payload

            await _wait_for_terminal_status(session, job.id, user.id)


# ---------------------------------------------------------------------------
# _run_filter_data_job -- end-to-end (tag-free path; tag-predicate SQL is
# Postgres-only, see module docstring)
# ---------------------------------------------------------------------------


class TestFilterDataJobHandlerEndToEnd:
    async def test_ai_filters_and_materializes_new_file(self, session_factory, monkeypatch) -> None:
        filter_posts_mock = AsyncMock(
            return_value=(["s1"], "sys prompt", "user prompt", {"batches_processed": 1, "batches_total": 1})
        )
        filter_comments_mock = AsyncMock(
            return_value=(["c1"], "", "", {"batches_processed": 1, "batches_total": 1})
        )
        monkeypatch.setattr("backend.scripts.filter_db.filter_posts_with_ai", filter_posts_mock)
        monkeypatch.setattr("backend.scripts.filter_db.filter_comments_with_ai", filter_comments_mock)

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            source_file_id = file_rec.id
            source_schemaname = file_rec.schemaname
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="t1", selftext="x1", word_count=5),
                    Submission(file_id=file_rec.id, id="s2", title="t2", selftext="x2", word_count=5),
                    Comment(file_id=file_rec.id, id="c1", body="b1", word_count=3),
                ]
            )
            await session.commit()

            job = await data_service.start_filter_data_job(
                session,
                user.id,
                database=source_schemaname,
                name="filtered result",
                api_key="sk-secret",
                model=None,
                prompt="keep the good ones",
                min_words=0,
                sample_percentage=100.0,
                filter_tags=None,
                description="a desc",
                project_id=None,
            )
            job_id = job.id

            finished = await _wait_for_terminal_status(session, job_id, user.id)
            assert finished.status == "succeeded", finished.error
            result = finished.result
            assert result["posts_filtered_count"] == 1
            assert result["comments_filtered_count"] == 1
            assert result["file"]["filename"] == "filtered result"

            assert filter_posts_mock.called
            assert filter_comments_mock.called
            assert result["partial"] is False
            assert result["batches_processed"] == {"posts": 1, "comments": 1}
            assert result["batches_total"] == {"posts": 1, "comments": 1}

            new_file_id = int(result["file"]["id"])
            new_file = await session.get(File, new_file_id)
            assert new_file.file_type == "filtered_data"
            assert new_file.description == "a desc"

            copied_subs = (
                await session.execute(select(Submission).where(Submission.file_id == new_file_id))
            ).scalars().all()
            assert [s.id for s in copied_subs] == ["s1"]

            edges = await version_repo.list_parent_edges(session, new_file_id)
            assert [e.parent_file_id for e in edges] == [source_file_id]
            assert edges[0].relation == "derived_from"
            assert edges[0].role == "source_data"

            head = await version_repo.head_version(session, new_file_id)
            assert head.system_prompt == "sys prompt"
            # Only the filter criteria the user typed is kept; the rendered
            # prompt (which embeds every sampled post) is reduced to a
            # length + hash. Both AI calls ran, so batches sums to 2.
            assert head.user_instructions == "keep the good ones"
            assert head.prompt_meta["rendered_chars"] == len("user prompt")
            assert head.prompt_meta["batches"] == 2

    async def test_partial_coverage_from_ai_filter_surfaces_in_result(self, session_factory, monkeypatch) -> None:
        # A free-model batch cap (or a mid-run batch failure) inside
        # filter_db.py means not all sampled content was actually sent to
        # the model -- the job result must say so instead of silently
        # returning an incomplete post/comment set as if it were complete.
        filter_posts_mock = AsyncMock(
            return_value=(["s1"], "sys prompt", "user prompt", {"batches_processed": 3, "batches_total": 8})
        )
        filter_comments_mock = AsyncMock(
            return_value=(["c1"], "", "", {"batches_processed": 1, "batches_total": 1})
        )
        monkeypatch.setattr("backend.scripts.filter_db.filter_posts_with_ai", filter_posts_mock)
        monkeypatch.setattr("backend.scripts.filter_db.filter_comments_with_ai", filter_comments_mock)

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="t1", selftext="x1", word_count=5),
                    Comment(file_id=file_rec.id, id="c1", body="b1", word_count=3),
                ]
            )
            await session.commit()

            job = await data_service.start_filter_data_job(
                session,
                user.id,
                database=file_rec.schemaname,
                name="filtered result",
                api_key="sk-secret",
                model=None,
                prompt="keep the good ones",
                min_words=0,
                sample_percentage=100.0,
                filter_tags=None,
                description=None,
                project_id=None,
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error
            result = finished.result
            assert result["partial"] is True
            assert result["batches_processed"] == {"posts": 3, "comments": 1}
            assert result["batches_total"] == {"posts": 8, "comments": 1}

    async def test_ai_filter_error_marks_job_failed(self, session_factory, monkeypatch) -> None:
        from backend.scripts.filter_db import AIFilterError

        monkeypatch.setattr(
            "backend.scripts.filter_db.filter_posts_with_ai",
            AsyncMock(side_effect=AIFilterError("bad key", code=401)),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add(Submission(file_id=file_rec.id, id="s1", title="t", selftext="x", word_count=5))
            await session.commit()

            job = await data_service.start_filter_data_job(
                session,
                user.id,
                database=file_rec.schemaname,
                name="n",
                api_key="sk-secret",
                model=None,
                prompt="filter please",
                min_words=0,
                sample_percentage=100.0,
                filter_tags=None,
                description=None,
                project_id=None,
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "failed"
            assert "bad key" in finished.error
            assert finished.error_code == 401

    async def test_reports_orphaned_comments_whose_parent_was_filtered_out(
        self, session_factory, monkeypatch
    ) -> None:
        # Filter Data filters posts and comments independently (two
        # separate AI calls) -- if the AI keeps a comment but drops its
        # parent post, the result must say so instead of silently
        # producing an incoherent-looking filtered dataset.
        filter_posts_mock = AsyncMock(
            return_value=([], "sys prompt", "user prompt", {"batches_processed": 1, "batches_total": 1})
        )
        filter_comments_mock = AsyncMock(
            return_value=(["c1"], "", "", {"batches_processed": 1, "batches_total": 1})
        )
        monkeypatch.setattr("backend.scripts.filter_db.filter_posts_with_ai", filter_posts_mock)
        monkeypatch.setattr("backend.scripts.filter_db.filter_comments_with_ai", filter_comments_mock)

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="t1", selftext="x1", word_count=5),
                    Comment(file_id=file_rec.id, id="c1", body="b1", link_id="s1", word_count=3),
                ]
            )
            await session.commit()

            job = await data_service.start_filter_data_job(
                session,
                user.id,
                database=file_rec.schemaname,
                name="filtered result",
                api_key="sk-secret",
                model=None,
                prompt="keep the good ones",
                min_words=0,
                sample_percentage=100.0,
                filter_tags=None,
                description=None,
                project_id=None,
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error
            result = finished.result
            assert result["posts_filtered_count"] == 0
            assert result["comments_filtered_count"] == 1
            assert result["orphaned_comments"] == 1

    async def test_content_scope_posts_only_never_samples_comments(
        self, session_factory, monkeypatch
    ) -> None:
        filter_posts_mock = AsyncMock(
            return_value=(["s1"], "sys prompt", "user prompt", {"batches_processed": 1, "batches_total": 1})
        )
        filter_comments_mock = AsyncMock(return_value=([], "", "", {}))
        monkeypatch.setattr("backend.scripts.filter_db.filter_posts_with_ai", filter_posts_mock)
        monkeypatch.setattr("backend.scripts.filter_db.filter_comments_with_ai", filter_comments_mock)

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=file_rec.id, id="s1", title="t1", selftext="x1", word_count=5),
                    Comment(file_id=file_rec.id, id="c1", body="b1", word_count=3),
                ]
            )
            await session.commit()

            job = await data_service.start_filter_data_job(
                session,
                user.id,
                database=file_rec.schemaname,
                name="posts only",
                api_key="sk-secret",
                model=None,
                prompt="keep the good ones",
                min_words=0,
                sample_percentage=100.0,
                filter_tags=None,
                description=None,
                project_id=None,
                content_scope="posts",
            )

            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error
            result = finished.result
            assert result["posts_filtered_count"] == 1
            assert result["comments_filtered_count"] == 0
            assert not filter_comments_mock.called
