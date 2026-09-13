"""Unit tests for backend/app/services/data_service.py.

Runs directly against an in-memory async SQLite session (the
``async_sqlite_engine`` fixture from ``tests/conftest.py``), bypassing the
HTTP layer entirely -- ``tests/backend/routes/test_ai_and_raw_sql_routes.py``
covers the route/auth/response-shape behavior on top of this.

Note on Postgres-only SQL: the tag-based pre-filter predicate fragments
(``tag_expansion.py::submission_text_tag_predicate_sql``/
``comment_body_tag_predicate_sql``) compile to Postgres's ``position(...)``
function, which SQLite doesn't implement -- so the ``filter_tags``-supplied
path through ``_run_ai_filter``/``_sample_source_rows`` isn't exercised
here and needs the opt-in Postgres integration suite. Everything else
(word-count binning, file entries, comments, post contents, the tag-free
AI-filter job path, and the SQL-injection regression test) runs against
SQLite.
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
    """The filter editor's job handlers (``_run_filter_preview_job``, and
    ``_run_ai_filter`` underneath it) open their own session via the
    module-level ``AsyncSessionLocal`` imported into
    ``backend.app.services.data_service`` -- point that (and the job
    runner's own session factory) at the in-memory SQLite engine backing
    this test's session.
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
            assert "pk" not in entries["submissions"][0]
            assert "valid_from" not in entries["submissions"][0]
            assert "valid_to" not in entries["submissions"][0]
            assert entries["submissions"][0]["id"] == "s1"

    async def test_version_no_reads_the_file_as_of_that_version(self, session_factory) -> None:
        """A row closed by a later delete still shows up when reading as
        of an earlier version (time travel over the SCD-2 range) --
        omitting ``version_no`` reads the current LIVE state instead.
        """
        from backend.app.services import file_service

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await data_service.version_service.commit_data_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="imported",
            )
            session.add(Submission(file_id=file_rec.id, id="s1", title="t", word_count=1))
            await session.commit()

            await file_service.delete_rows(
                session, user.id, schemaname=file_rec.schemaname, table="submissions", row_ids=["s1"],
            )

            live = await data_service.get_file_entries(session, user.id, file_rec.schemaname, limit=10, offset=0)
            assert live["total_submissions"] == 0
            assert live["version_no"] is None

            as_of_v1 = await data_service.get_file_entries(
                session, user.id, file_rec.schemaname, limit=10, offset=0, version_no=1
            )
            assert as_of_v1["total_submissions"] == 1
            assert as_of_v1["submissions"][0]["id"] == "s1"
            assert as_of_v1["version_no"] == 1


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
# duplicate_data
# ---------------------------------------------------------------------------


class TestDuplicateData:
    async def test_forks_live_rows_and_lineage_from_head(self, session_factory) -> None:
        from backend.app.repositories import version_repo as _version_repo
        from backend.app.services import file_service

        async with session_factory() as session:
            user = await _make_user(session)
            source = await _make_file(session, user.id, schemaname="proj_src")
            await data_service.version_service.commit_data_version(
                session, file_id=source.id, author_user_id=user.id, origin="imported",
            )
            session.add_all([
                Submission(file_id=source.id, id="s1", title="t1", word_count=1),
                Submission(file_id=source.id, id="s2", title="t2", word_count=1),
            ])
            await session.commit()

            # Close one row so head != v1's row set.
            await file_service.delete_rows(
                session, user.id, schemaname="proj_src", table="submissions", row_ids=["s1"],
            )

            forked = await data_service.duplicate_data(session, user.id, "proj_src", display_name="Copy of src")
            assert forked.file_type == "raw_data"
            assert forked.filename == "Copy of src"

            live = (
                await session.execute(select(Submission).where(Submission.file_id == forked.id))
            ).scalars().all()
            assert [r.id for r in live] == ["s2"]
            assert live[0].valid_from == 1
            assert live[0].valid_to is None

            head = await _version_repo.head_version(session, forked.id)
            assert head.version_no == 1
            assert head.origin == "forked"

    async def test_from_version_no_forks_the_state_as_of_that_version(self, session_factory) -> None:
        from backend.app.services import file_service

        async with session_factory() as session:
            user = await _make_user(session)
            source = await _make_file(session, user.id, schemaname="proj_src2")
            await data_service.version_service.commit_data_version(
                session, file_id=source.id, author_user_id=user.id, origin="imported",
            )
            session.add(Submission(file_id=source.id, id="s1", title="t1", word_count=1))
            await session.commit()

            await file_service.delete_rows(
                session, user.id, schemaname="proj_src2", table="submissions", row_ids=["s1"],
            )

            forked = await data_service.duplicate_data(
                session, user.id, "proj_src2", display_name="Restored", from_version_no=1
            )
            live = (
                await session.execute(select(Submission).where(Submission.file_id == forked.id))
            ).scalars().all()
            assert [r.id for r in live] == ["s1"]

    async def test_blank_display_name_raises_validation_error(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, schemaname="proj_src3")
            with pytest.raises(ValidationAppError):
                await data_service.duplicate_data(session, user.id, "proj_src3", display_name="  ")

    async def test_missing_version_raises_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id, schemaname="proj_src4")
            with pytest.raises(NotFoundError):
                await data_service.duplicate_data(
                    session, user.id, "proj_src4", display_name="x", from_version_no=99
                )


# ---------------------------------------------------------------------------
# Filter editor: sampling exclusions, the preview job, and the manual submit
# ---------------------------------------------------------------------------


async def _seed_rows(session, file_id: int, *, submissions: int = 0, comments: int = 0) -> None:
    session.add_all(
        [
            Submission(file_id=file_id, id=f"s{i}", title=f"t{i}", selftext=f"x{i}", word_count=5)
            for i in range(1, submissions + 1)
        ]
        + [
            Comment(file_id=file_id, id=f"c{i}", body=f"b{i}", word_count=3)
            for i in range(1, comments + 1)
        ]
    )
    await session.commit()


class TestSampleSourceRowsExclusions:
    """The rule that makes the filter editor's AI tool re-runnable: rows
    the user already ruled on are never sampled again.
    """

    async def _sample(self, session, file_id: int, **kwargs):
        return await data_service._sample_source_rows(
            session,
            source_file_id=file_id,
            min_words=0,
            sub_tag_sql="",
            sub_tag_bind={},
            com_tag_sql="",
            com_tag_bind={},
            pct=100.0,
            use_ai_posts=True,
            use_ai_comments=True,
            **kwargs,
        )

    async def test_without_exclusions_every_row_is_a_candidate(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=3, comments=2)

            sub_rows, comm_rows, _, _ = await self._sample(session, file_rec.id)
            assert sorted(r.id for r in sub_rows) == ["s1", "s2", "s3"]
            assert sorted(r.id for r in comm_rows) == ["c1", "c2"]

    async def test_excluded_ids_are_never_sampled(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=3, comments=2)

            sub_rows, comm_rows, _, _ = await self._sample(
                session,
                file_rec.id,
                exclude_submission_ids=["s1", "s3"],
                exclude_comment_ids=["c1"],
            )
            assert [r.id for r in sub_rows] == ["s2"]
            assert [r.id for r in comm_rows] == ["c2"]

    async def test_excluded_ids_do_not_consume_sample_slots(self, session_factory) -> None:
        """The exclusion narrows the pool BEFORE ``ceil(eligible * pct)``,
        so a 50% sample of 4 undecided rows sends 2 of them -- not 2 of
        the 6 rows that includes the decided ones.
        """
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=6)

            sub_rows, _, _, _ = await data_service._sample_source_rows(
                session,
                source_file_id=file_rec.id,
                min_words=0,
                sub_tag_sql="",
                sub_tag_bind={},
                com_tag_sql="",
                com_tag_bind={},
                pct=50.0,
                use_ai_posts=True,
                use_ai_comments=False,
                include_comments=False,
                exclude_submission_ids=["s1", "s2"],
            )
            assert len(sub_rows) == 2
            assert {r.id for r in sub_rows} <= {"s3", "s4", "s5", "s6"}

    async def test_excluding_everything_yields_no_candidates(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=2)

            sub_rows, _, submissions_text, _ = await self._sample(
                session, file_rec.id, exclude_submission_ids=["s1", "s2"]
            )
            assert sub_rows == []
            assert submissions_text == ""


class TestStartFilterPreviewJob:
    async def test_rejects_a_malformed_schema(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await data_service.start_filter_preview_job(
                    session, user.id, database="not-a-schema", api_key="sk", model="m",
                    include_prompt="p", exclude_prompt=None, use_examples=False,
                    min_words=0, sample_percentage=100.0, filter_tags=None,
                )

    async def test_rejects_a_missing_api_key(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id)
            with pytest.raises(ValidationAppError):
                await data_service.start_filter_preview_job(
                    session, user.id, database="proj_src", api_key="", model="m",
                    include_prompt="p", exclude_prompt=None, use_examples=False,
                    min_words=0, sample_percentage=100.0, filter_tags=None,
                )

    async def test_rejects_another_users_file(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@b.com")
            await _make_file(session, owner.id)
            intruder = await _make_user(session, "intruder@b.com")
            with pytest.raises(NotFoundError):
                await data_service.start_filter_preview_job(
                    session, intruder.id, database="proj_src", api_key="sk", model="m",
                    include_prompt="p", exclude_prompt=None, use_examples=False,
                    min_words=0, sample_percentage=100.0, filter_tags=None,
                )

    async def test_rejects_no_criteria_and_no_examples(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id)
            with pytest.raises(ValidationAppError):
                await data_service.start_filter_preview_job(
                    session, user.id, database="proj_src", api_key="sk", model="m",
                    include_prompt=None, exclude_prompt=None, use_examples=False,
                    min_words=0, sample_percentage=100.0, filter_tags=None,
                )

    async def test_rejects_autofill_with_nothing_decided_yet(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id)
            with pytest.raises(ValidationAppError):
                await data_service.start_filter_preview_job(
                    session, user.id, database="proj_src", api_key="sk", model="m",
                    include_prompt=None, exclude_prompt=None, use_examples=True,
                    min_words=0, sample_percentage=100.0, filter_tags=None,
                )

    async def test_api_key_is_never_persisted_on_the_job_row(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            await _make_file(session, user.id)
            job = await data_service.start_filter_preview_job(
                session, user.id, database="proj_src", api_key="sk-secret", model="m",
                include_prompt="p", exclude_prompt=None, use_examples=False,
                min_words=0, sample_percentage=100.0, filter_tags=None,
                included_post_ids=["s1"],
            )
            assert "api_key" not in job.payload
            assert "sk-secret" not in str(job.payload)
            assert job.payload["include_post_ids"] == ["s1"]


class TestFilterPreviewJobHandler:
    async def test_returns_ids_without_creating_anything(self, session_factory, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_posts_with_ai",
            AsyncMock(return_value=(["s2"], ["s1"], "sys", "user", {"batches_processed": 1, "batches_total": 1})),
        )
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_comments_with_ai",
            AsyncMock(return_value=([], [], "", "", {"batches_processed": 1, "batches_total": 1})),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=3, comments=1)
            files_before = len((await session.execute(select(File))).scalars().all())

            job = await data_service.start_filter_preview_job(
                session, user.id, database=file_rec.schemaname, api_key="sk", model="m",
                include_prompt="keep the good ones", exclude_prompt=None, use_examples=False,
                min_words=0, sample_percentage=100.0, filter_tags=None,
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)

            assert finished.status == "succeeded", finished.error
            assert finished.result["include_post_ids"] == ["s2"]
            assert finished.result["exclude_post_ids"] == ["s1"]
            assert finished.result["include_comment_ids"] == []
            assert finished.result["exclude_comment_ids"] == []
            assert finished.result["partial"] is False
            assert "file" not in finished.result

            files_after = len((await session.execute(select(File))).scalars().all())
            assert files_after == files_before, "a preview must never create an artifact"

    async def test_decided_rows_are_withheld_from_the_model(self, session_factory, monkeypatch) -> None:
        posts_mock = AsyncMock(
            return_value=([], [], "sys", "user", {"batches_processed": 1, "batches_total": 1})
        )
        monkeypatch.setattr("backend.scripts.filter_db.triage_posts_with_ai", posts_mock)
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_comments_with_ai",
            AsyncMock(return_value=([], [], "", "", {"batches_processed": 1, "batches_total": 1})),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=3)

            job = await data_service.start_filter_preview_job(
                session, user.id, database=file_rec.schemaname, api_key="sk", model="m",
                include_prompt="p", exclude_prompt=None, use_examples=False,
                min_words=0, sample_percentage=100.0, filter_tags=None,
                included_post_ids=["s1"], excluded_post_ids=["s2"],
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error

            sent_blob = posts_mock.await_args.args[3]
            assert "[s3]" in sent_blob
            assert "[s1]" not in sent_blob and "[s2]" not in sent_blob

    async def test_use_examples_builds_examples_block_and_drops_prompts(
        self, session_factory, monkeypatch
    ) -> None:
        posts_mock = AsyncMock(
            return_value=([], [], "sys", "user", {"batches_processed": 1, "batches_total": 1})
        )
        monkeypatch.setattr("backend.scripts.filter_db.triage_posts_with_ai", posts_mock)
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_comments_with_ai",
            AsyncMock(return_value=([], [], "", "", {"batches_processed": 1, "batches_total": 1})),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=3)

            job = await data_service.start_filter_preview_job(
                session, user.id, database=file_rec.schemaname, api_key="sk", model="m",
                include_prompt="should be ignored", exclude_prompt=None, use_examples=True,
                min_words=0, sample_percentage=100.0, filter_tags=None,
                included_post_ids=["s1"], excluded_post_ids=["s2"],
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)
            assert finished.status == "succeeded", finished.error

            # Called as (include_prompt, exclude_prompt, examples_block, content, ...)
            call_args = posts_mock.await_args.args
            assert call_args[0] == "" and call_args[1] == ""
            examples_block = call_args[2]
            assert "INCLUDED" in examples_block
            assert "EXCLUDED" in examples_block
            assert "should be ignored" not in finished.result["user_instructions"]

    async def test_no_examples_when_use_examples_false(self, session_factory, monkeypatch) -> None:
        posts_mock = AsyncMock(
            return_value=(["s3"], [], "sys", "user", {"batches_processed": 1, "batches_total": 1})
        )
        monkeypatch.setattr("backend.scripts.filter_db.triage_posts_with_ai", posts_mock)
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_comments_with_ai",
            AsyncMock(return_value=([], [], "", "", {"batches_processed": 1, "batches_total": 1})),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=3)

            job = await data_service.start_filter_preview_job(
                session, user.id, database=file_rec.schemaname, api_key="sk", model="m",
                include_prompt="criteria", exclude_prompt=None, use_examples=False,
                min_words=0, sample_percentage=100.0, filter_tags=None,
                included_post_ids=["s1"], excluded_post_ids=["s2"],
            )
            await _wait_for_terminal_status(session, job.id, user.id)

            examples_block = posts_mock.await_args.args[2]
            assert examples_block == ""

    async def test_partial_coverage_from_a_batch_cap_surfaces_in_result(
        self, session_factory, monkeypatch
    ) -> None:
        # A free-model batch cap (as opposed to a mid-run error) means not
        # all sampled content was actually sent to the model -- the job
        # result must say so instead of silently returning an incomplete
        # post/comment set as if it were complete.
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_posts_with_ai",
            AsyncMock(
                return_value=(["s1"], [], "sys", "user", {"batches_processed": 3, "batches_total": 8})
            ),
        )
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_comments_with_ai",
            AsyncMock(return_value=([], [], "", "", {"batches_processed": 1, "batches_total": 1})),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=1, comments=1)

            job = await data_service.start_filter_preview_job(
                session, user.id, database=file_rec.schemaname, api_key="sk", model="m",
                include_prompt="p", exclude_prompt=None, use_examples=False,
                min_words=0, sample_percentage=100.0, filter_tags=None,
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)

            assert finished.status == "succeeded", finished.error
            assert finished.result["partial"] is True
            assert finished.result["batches_processed"] == {"posts": 3, "comments": 1}
            assert finished.result["batches_total"] == {"posts": 8, "comments": 1}

    async def test_content_scope_posts_only_never_samples_comments(
        self, session_factory, monkeypatch
    ) -> None:
        posts_mock = AsyncMock(
            return_value=(["s1"], [], "sys", "user", {"batches_processed": 1, "batches_total": 1})
        )
        comments_mock = AsyncMock(return_value=([], [], "", "", {}))
        monkeypatch.setattr("backend.scripts.filter_db.triage_posts_with_ai", posts_mock)
        monkeypatch.setattr("backend.scripts.filter_db.triage_comments_with_ai", comments_mock)

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=1, comments=1)

            job = await data_service.start_filter_preview_job(
                session, user.id, database=file_rec.schemaname, api_key="sk", model="m",
                include_prompt="p", exclude_prompt=None, use_examples=False,
                min_words=0, sample_percentage=100.0, filter_tags=None,
                content_scope="posts",
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)

            assert finished.status == "succeeded", finished.error
            assert finished.result["include_post_ids"] == ["s1"]
            assert finished.result["include_comment_ids"] == []
            assert not comments_mock.called

    async def test_surfaces_a_partial_runs_real_error(self, session_factory, monkeypatch) -> None:
        """Regression: the per-type coverage dict's ``error`` used to be
        dropped, so every partial run was blamed on a free model's batch
        cap even when an API error stopped it.
        """
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_posts_with_ai",
            AsyncMock(
                return_value=(
                    ["s1"], [], "sys", "user",
                    {"batches_processed": 1, "batches_total": 3, "error": "upstream 429"},
                )
            ),
        )
        monkeypatch.setattr(
            "backend.scripts.filter_db.triage_comments_with_ai",
            AsyncMock(return_value=([], [], "", "", {"batches_processed": 1, "batches_total": 1})),
        )

        async with session_factory() as session:
            user = await _make_user(session)
            file_rec = await _make_file(session, user.id)
            await _seed_rows(session, file_rec.id, submissions=2, comments=1)

            job = await data_service.start_filter_preview_job(
                session, user.id, database=file_rec.schemaname, api_key="sk", model="m",
                include_prompt="p", exclude_prompt=None, use_examples=False,
                min_words=0, sample_percentage=100.0, filter_tags=None,
            )
            finished = await _wait_for_terminal_status(session, job.id, user.id)

            assert finished.result["partial"] is True
            assert finished.result["partial_error"] == "upstream 429"


class TestCreateManualFilteredData:
    async def _setup(self, session):
        user = await _make_user(session)
        file_rec = await _make_file(session, user.id)
        await _seed_rows(session, file_rec.id, submissions=3, comments=2)
        return user, file_rec

    async def test_copies_exactly_the_chosen_rows(self, session_factory) -> None:
        async with session_factory() as session:
            user, source = await self._setup(session)

            new_file, counts = await data_service.create_manual_filtered_data(
                session, user.id, database=source.schemaname, name="hand picked",
                description="chosen by hand", project_id=None,
                post_ids=["s1", "s3"], comment_ids=["c2"],
            )

            assert counts["submissions"] == 2
            assert counts["comments"] == 1
            assert new_file.file_type == "filtered_data"
            assert new_file.filename == "hand picked"
            assert new_file.description == "chosen by hand"

            subs = (
                await session.execute(
                    select(Submission).where(Submission.file_id == new_file.id).order_by(Submission.id)
                )
            ).scalars().all()
            comms = (
                await session.execute(select(Comment).where(Comment.file_id == new_file.id))
            ).scalars().all()
            assert [s.id for s in subs] == ["s1", "s3"]
            assert [c.id for c in comms] == ["c2"]

    async def test_records_an_edited_origin_with_no_llm_provenance(self, session_factory) -> None:
        """An AI assist while editing is not the same claim as "a model
        produced this" -- ``model``/``system_prompt`` must stay usable for
        auditing which artifacts an LLM actually generated.
        """
        async with session_factory() as session:
            user, source = await self._setup(session)

            new_file, _ = await data_service.create_manual_filtered_data(
                session, user.id, database=source.schemaname, name="hand picked",
                description=None, project_id=None, post_ids=["s1"], comment_ids=[],
            )

            head = await version_repo.head_version(session, new_file.id)
            assert head.version_no == 1
            assert head.origin == "edited"
            assert head.system_prompt is None
            assert head.model is None
            assert head.prompt_meta is None
            assert head.sealed_at is not None

    async def test_pins_lineage_to_the_source(self, session_factory) -> None:
        async with session_factory() as session:
            user, source = await self._setup(session)

            new_file, _ = await data_service.create_manual_filtered_data(
                session, user.id, database=source.schemaname, name="hand picked",
                description=None, project_id=None, post_ids=["s1"], comment_ids=[],
            )

            edges = await version_repo.list_parent_edges(session, new_file.id)
            assert [(e.parent_file_id, e.relation, e.role) for e in edges] == [
                (source.id, "derived_from", "source_data")
            ]

    async def test_carries_memos_on_the_chosen_rows(self, session_factory) -> None:
        from backend.app.repositories import memo_repo

        async with session_factory() as session:
            user, source = await self._setup(session)
            for row_id, body in (("s1", "kept, and noted"), ("s2", "dropped, and noted")):
                await memo_repo.upsert_memo(
                    session, file_id=source.id, row_type="submission", row_id=row_id,
                    body=body, author_user_id=user.id,
                )
            await session.commit()

            new_file, counts = await data_service.create_manual_filtered_data(
                session, user.id, database=source.schemaname, name="hand picked",
                description=None, project_id=None, post_ids=["s1"], comment_ids=[],
            )

            assert counts["memos"] == 1
            memos = await memo_repo.list_memos(session, new_file.id)
            assert [(m.row_id, m.body) for m in memos] == [("s1", "kept, and noted")]

    async def test_flags_comments_kept_without_their_parent_post(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            source = await _make_file(session, user.id)
            session.add_all(
                [
                    Submission(file_id=source.id, id="s1", title="t", selftext="x", word_count=5),
                    Comment(file_id=source.id, id="c1", body="b", link_id="s1", word_count=3),
                    Comment(file_id=source.id, id="c2", body="b", link_id="s9", word_count=3),
                ]
            )
            await session.commit()

            _, counts = await data_service.create_manual_filtered_data(
                session, user.id, database=source.schemaname, name="hand picked",
                description=None, project_id=None, post_ids=["s1"], comment_ids=["c1", "c2"],
            )
            assert counts["orphaned_comments"] == 1

    async def test_rejects_a_malformed_schema(self, session_factory) -> None:
        async with session_factory() as session:
            user = await _make_user(session)
            with pytest.raises(ValidationAppError):
                await data_service.create_manual_filtered_data(
                    session, user.id, database="not-a-schema", name="x",
                    description=None, project_id=None, post_ids=["s1"], comment_ids=[],
                )

    async def test_rejects_another_users_file(self, session_factory) -> None:
        async with session_factory() as session:
            owner = await _make_user(session, "owner@b.com")
            source = await _make_file(session, owner.id)
            intruder = await _make_user(session, "intruder@b.com")
            with pytest.raises(NotFoundError):
                await data_service.create_manual_filtered_data(
                    session, intruder.id, database=source.schemaname, name="x",
                    description=None, project_id=None, post_ids=["s1"], comment_ids=[],
                )


class TestCreateManualFilteredDataAssistProvenance:
    """C2: assist_runs records what a filter_preview job contributed,
    without changing the version's own origin/model -- the pairing this
    guards is with
    ``TestCreateManualFilteredData.test_records_an_edited_origin_with_no_llm_provenance``.
    """

    async def _setup(self, session):
        user = await _make_user(session)
        file_rec = await _make_file(session, user.id)
        await _seed_rows(session, file_rec.id, submissions=3, comments=2)
        return user, file_rec

    async def _make_succeeded_job(self, session, *, user_id: int, source_file_id: int):
        from backend.app.jobs.models import Job

        job = Job(
            job_type="filter_preview", user_id=user_id, status="succeeded",
            payload={"source_file_id": source_file_id, "model": "anthropic/claude-x"},
            result={"system_prompt": "sys", "user_instructions": "keep complaints", "prompt_meta": {"rendered_chars": 5}},
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job

    async def test_records_an_assist_run_without_touching_version_provenance(self, session_factory) -> None:
        async with session_factory() as session:
            user, source = await self._setup(session)
            job = await self._make_succeeded_job(session, user_id=user.id, source_file_id=source.id)

            new_file, _ = await data_service.create_manual_filtered_data(
                session, user.id, database=source.schemaname, name="hand picked",
                description=None, project_id=None, post_ids=["s1"], comment_ids=[],
                assist_runs=[{"job_id": job.id, "proposed_count": 4, "accepted_count": 1, "dismissed_count": 3}],
            )

            head = await version_repo.head_version(session, new_file.id)
            assert head.origin == "edited"
            assert head.model is None
            assert head.system_prompt is None

            from backend.app.services import assist_service
            assists = await assist_service.list_assists(session, new_file.id)
            assert len(assists) == 1
            assert assists[0]["model"] == "anthropic/claude-x"
            assert assists[0]["system_prompt"] == "sys"
            assert assists[0]["accepted_count"] == 1
            assert assists[0]["dismissed_count"] == 3

    async def test_rejects_a_job_run_against_a_different_source(self, session_factory) -> None:
        async with session_factory() as session:
            user, source = await self._setup(session)
            other_source = await _make_file(session, user.id, schemaname="proj_other")
            job = await self._make_succeeded_job(session, user_id=user.id, source_file_id=other_source.id)

            with pytest.raises(ValidationAppError):
                await data_service.create_manual_filtered_data(
                    session, user.id, database=source.schemaname, name="hand picked",
                    description=None, project_id=None, post_ids=["s1"], comment_ids=[],
                    assist_runs=[{"job_id": job.id}],
                )

