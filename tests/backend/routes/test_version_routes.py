"""Tests for backend/app/api/version_routes.py -- the generic version
history/diff/lineage routes shared by every artifact type (GET
.../versions, GET .../diff, GET .../lineage).

There is no revert route and no checkpoint route -- see the module
docstring in backend/app/api/version_routes.py (recovering an old state
is tested as "duplicate from an older version" in
test_coding_service.py / test_codebook_service.py / test_coding_repo.py
instead; the old ``POST .../checkpoint`` route was removed outright,
since it never had anything left to do once every commit is sealed the
instant it's created).
"""

import pytest

from backend.app.repositories import version_repo
from backend.app.services import version_service

pytestmark = pytest.mark.usefixtures("override_async_db")


async def _make_user(session_factory, email: str = "a@b.com"):
    from backend.app.database import User

    async with session_factory() as session:
        user = User(email=email, password="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_file(session_factory, user_id: int, **kwargs):
    from backend.app.database import File

    defaults = dict(filename="cb", schemaname="proj_a", file_type="codebook")
    defaults.update(kwargs)
    async with session_factory() as session:
        file_rec = File(user_id=user_id, **defaults)
        session.add(file_rec)
        await session.commit()
        await session.refresh(file_rec)
        return file_rec


@pytest.fixture()
def session_factory(async_sqlite_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(async_sqlite_engine, expire_on_commit=False)


_CODE_A = [{"code_uid": "u1", "family_uid": "f1", "family_name": "F", "name": "A", "body": "", "position": 0}]
_CODE_A_RENAMED = [{"code_uid": "u1", "family_uid": "f1", "family_name": "F", "name": "A2", "body": "", "position": 0}]


class TestListVersions:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/artifacts/proj_a/versions")
        assert resp.status_code == 401

    async def test_no_owned_file_returns_404(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        resp = client.get(
            "/api/artifacts/proj_missing/versions", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 404

    async def test_lists_versions_newest_first(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_v1")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated", codes=_CODE_A,
            )
            await session.commit()
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited", codes=_CODE_A_RENAMED,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_v1/versions", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        versions = resp.json()["versions"]
        assert [v["version_no"] for v in versions] == [2, 1]
        assert versions[0]["origin"] == "edited"

    async def test_cannot_read_another_users_versions(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner@b.com")
        other = await _make_user(session_factory, "other@b.com")
        await _make_file(session_factory, owner.id, schemaname="proj_owned")

        resp = client.get(
            "/api/artifacts/proj_owned/versions", cookies={"access_token": make_token(sub=str(other.id))}
        )
        assert resp.status_code == 404


class TestDiff:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/artifacts/proj_a/diff?from_no=1&to_no=2")
        assert resp.status_code == 401

    async def test_rename_reads_as_renamed_not_removed_and_added(
        self, client, session_factory, make_token
    ) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_diff")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated", codes=_CODE_A,
            )
            await session.commit()
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited", codes=_CODE_A_RENAMED,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_diff/diff?from_no=1&to_no=2",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        body = resp.json()
        codebook = body["codebook"]
        assert codebook["added"] == []
        assert codebook["removed"] == []
        assert len(codebook["renamed"]) == 1
        assert codebook["renamed"][0]["code_uid"] == "u1"
        assert codebook["renamed"][0]["from"]["name"] == "A"
        assert codebook["renamed"][0]["to"]["name"] == "A2"

    async def test_non_coding_file_has_null_coding_diff(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_diff_cb")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated", codes=_CODE_A,
            )
            await session.commit()
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited", codes=_CODE_A_RENAMED,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_diff_cb/diff?from_no=1&to_no=2",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        assert resp.json()["coding"] is None

    async def test_coding_file_reports_rows_recoded_and_code_counts(
        self, client, session_factory, make_token
    ) -> None:
        from backend.app.repositories import coding_repo
        from backend.app.storage_models import Submission

        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_diff_coding", file_type="coding")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="imported", codes=_CODE_A,
            )
            session.add(Submission(file_id=file_rec.id, id="s1", title="t", selftext="b", word_count=1))
            await session.commit()

            version = await version_service.commit_coding_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited",
            )
            await coding_repo.replace_entries_for_items(
                session, file_rec.id,
                [{"row_type": "submission", "post_id": "s1", "entries": [
                    {"code": "A", "code_uid": "u1", "quote": "b", "start_offset": 0, "end_offset": 1, "notes": None},
                ]}],
                version_no=version.version_no,
            )
            await session.commit()

        resp = client.get(
            f"/api/artifacts/proj_diff_coding/diff?from_no=1&to_no={version.version_no}",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        coding = resp.json()["coding"]
        assert coding is not None
        assert coding["rows_recoded"] == 1
        assert coding["rows_newly_coded"] == 1
        assert coding["from_total_entries"] == 0
        assert coding["to_total_entries"] == 1
        assert coding["code_counts"] == [
            {"code_uid": "u1", "name": "A", "from_count": 0, "to_count": 1, "delta": 1}
        ]
        assert coding["applied"] == [
            {
                "row_type": "submission",
                "post_id": "s1",
                "code_uid": "u1",
                "code": "A",
                "text": "b",
            }
        ]
        assert coding["removed"] == []


class TestDiffData:
    async def test_raw_data_file_reports_rows_added_and_removed(
        self, client, session_factory, make_token
    ) -> None:
        from backend.app.services import file_service
        from backend.app.storage_models import Submission

        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_diff_data", file_type="raw_data")
        async with session_factory() as session:
            await version_service.commit_data_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="imported",
            )
            session.add_all([
                Submission(file_id=file_rec.id, id="s1", title="t1", selftext="b", word_count=1),
                Submission(file_id=file_rec.id, id="s2", title="t2", selftext="b", word_count=1),
            ])
            await session.commit()

            deleted = await file_service.delete_rows(
                session, user.id, schemaname="proj_diff_data", table="submissions", row_ids=["s1"],
            )
            assert deleted == 1

        resp = client.get(
            "/api/artifacts/proj_diff_data/diff?from_no=1&to_no=2",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["coding"] is None
        data = body["data"]
        assert data is not None
        assert data["from_submissions"] == 2
        assert data["to_submissions"] == 1
        assert data["submissions_removed"] == 1
        assert data["submissions_added"] == 0
        assert data["sample_submissions_removed"] == ["s1"]

    async def test_non_data_file_has_null_data_diff(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_diff_cb2")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="generated", codes=_CODE_A,
            )
            await session.commit()
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited", codes=_CODE_A_RENAMED,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_diff_cb2/diff?from_no=1&to_no=2",
            cookies={"access_token": make_token(sub=str(user.id))},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] is None


class TestLineage:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/artifacts/proj_a/lineage")
        assert resp.status_code == 401

    async def test_reports_parents_and_children(self, client, session_factory, make_token) -> None:
        from backend.app.versioning_models import RELATION_DERIVED_FROM, ROLE_SOURCE_DATA

        user = await _make_user(session_factory)
        source = await _make_file(session_factory, user.id, schemaname="proj_src", file_type="raw_data")
        middle = await _make_file(session_factory, user.id, schemaname="proj_mid", file_type="filtered_data")
        derived = await _make_file(session_factory, user.id, schemaname="proj_derived", file_type="codebook")

        async with session_factory() as session:
            await version_repo.add_edge(
                session, child_file_id=middle.id, parent_file_id=source.id, parent_version_id=None,
                relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA,
            )
            await version_repo.add_edge(
                session, child_file_id=derived.id, parent_file_id=middle.id, parent_version_id=None,
                relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_mid/lineage", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["file"]["schema_name"] == "proj_mid"
        assert [p["schema_name"] for p in body["parents"]] == ["proj_src"]
        assert [c["schema_name"] for c in body["children"]] == ["proj_derived"]

    async def test_no_lineage_returns_empty_lists(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        await _make_file(session_factory, user.id, schemaname="proj_isolated", file_type="raw_data")

        resp = client.get(
            "/api/artifacts/proj_isolated/lineage", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["parents"] == []
        assert body["children"] == []

    async def test_parent_pinned_to_generated_version_reports_model_and_prompt(
        self, client, session_factory, make_token
    ) -> None:
        from backend.app.versioning_models import RELATION_DERIVED_FROM, ROLE_SOURCE_DATA

        user = await _make_user(session_factory)
        source = await _make_file(session_factory, user.id, schemaname="proj_gen_src", file_type="summary")
        derived = await _make_file(session_factory, user.id, schemaname="proj_gen_derived", file_type="summary")

        async with session_factory() as session:
            source_version = await version_service.commit_blob_version(
                session,
                file_id=source.id,
                author_user_id=user.id,
                origin="generated",
                content="body",
                model="openai/gpt-4o",
                system_prompt="Summarize the coding.",
                user_instructions="Focus on recurring themes.",
                prompt_meta={"rendered_chars": 120, "batches": 1},
            )
            await session.commit()
            await version_repo.add_edge(
                session,
                child_file_id=derived.id,
                parent_file_id=source.id,
                parent_version_id=source_version.id,
                relation=RELATION_DERIVED_FROM,
                role=ROLE_SOURCE_DATA,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_gen_derived/lineage", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        parent = resp.json()["parents"][0]
        assert parent["parent_version_no"] == 1
        assert parent["models"] == ["openai/gpt-4o"]
        assert len(parent["prompts"]) == 1
        run = parent["prompts"][0]
        assert run["stage"] == "generated"
        assert run["model"] == "openai/gpt-4o"
        assert run["system_prompt"] == "Summarize the coding."
        assert run["user_instructions"] == "Focus on recurring themes."

    async def test_parent_pinned_to_ai_assisted_edit_reports_assist_model_and_prompt(
        self, client, session_factory, make_token
    ) -> None:
        from backend.app.repositories import assist_repo
        from backend.app.versioning_models import RELATION_DERIVED_FROM, ROLE_SOURCE_DATA

        user = await _make_user(session_factory)
        source = await _make_file(session_factory, user.id, schemaname="proj_assist_src")
        derived = await _make_file(session_factory, user.id, schemaname="proj_assist_derived")

        async with session_factory() as session:
            source_version = await version_service.commit_codebook_version(
                session, file_id=source.id, author_user_id=user.id, origin="edited", codes=_CODE_A,
            )
            await session.commit()
            await assist_repo.insert_assist(
                session,
                file_id=source.id,
                version_id=source_version.id,
                stage="codebook",
                job_id=None,
                model="anthropic/claude-sonnet-5",
                system_prompt="Propose codes for these excerpts.",
                user_instructions="Group by sentiment.",
                prompt_meta=None,
                proposed_count=5,
                accepted_count=3,
                dismissed_count=2,
                accepted_refs=None,
            )
            await session.commit()
            await version_repo.add_edge(
                session,
                child_file_id=derived.id,
                parent_file_id=source.id,
                parent_version_id=source_version.id,
                relation=RELATION_DERIVED_FROM,
                role=ROLE_SOURCE_DATA,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_assist_derived/lineage", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        parent = resp.json()["parents"][0]
        # origin="edited" carries no version-level model, so the only
        # provenance is the assist run.
        assert parent["models"] == ["anthropic/claude-sonnet-5"]
        assert len(parent["prompts"]) == 1
        run = parent["prompts"][0]
        assert run["stage"] == "codebook"
        assert run["model"] == "anthropic/claude-sonnet-5"
        assert run["system_prompt"] == "Propose codes for these excerpts."
        assert run["user_instructions"] == "Group by sentiment."


class TestListArtifactAssists:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/artifacts/proj_a/assists")
        assert resp.status_code == 401

    async def test_no_owned_file_returns_404(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        resp = client.get(
            "/api/artifacts/proj_missing/assists", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 404

    async def test_empty_when_nothing_recorded(self, client, session_factory, make_token) -> None:
        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_no_assists")
        async with session_factory() as session:
            await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited", codes=_CODE_A,
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_no_assists/assists", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        assert resp.json() == {"assists": []}

    async def test_lists_a_recorded_assist(self, client, session_factory, make_token) -> None:
        from backend.app.jobs.models import Job
        from backend.app.services import assist_service
        from backend.app.versioning_models import ASSIST_STAGE_CODEBOOK

        user = await _make_user(session_factory)
        file_rec = await _make_file(session_factory, user.id, schemaname="proj_with_assists")
        async with session_factory() as session:
            version = await version_service.commit_codebook_version(
                session, file_id=file_rec.id, author_user_id=user.id, origin="edited", codes=_CODE_A,
            )
            await session.commit()

            job = Job(
                job_type="codebook_preview", user_id=user.id, status="succeeded",
                payload={"source_file_id": file_rec.id, "model": "m"}, result={"system_prompt": "sys"},
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)

            await assist_service.record_assist_runs(
                session, user_id=user.id, file_id=file_rec.id, version_id=version.id,
                stage=ASSIST_STAGE_CODEBOOK, source_file_id=file_rec.id,
                runs=[{"job_id": job.id, "accepted_count": 1}],
            )
            await session.commit()

        resp = client.get(
            "/api/artifacts/proj_with_assists/assists", cookies={"access_token": make_token(sub=str(user.id))}
        )
        assert resp.status_code == 200
        assists = resp.json()["assists"]
        assert len(assists) == 1
        assert assists[0]["model"] == "m"
        assert assists[0]["accepted_count"] == 1
        assert assists[0]["version_no"] == 1

    async def test_cannot_read_another_users_assists(self, client, session_factory, make_token) -> None:
        owner = await _make_user(session_factory, "owner2@b.com")
        other = await _make_user(session_factory, "other2@b.com")
        await _make_file(session_factory, owner.id, schemaname="proj_owned_assists")

        resp = client.get(
            "/api/artifacts/proj_owned_assists/assists", cookies={"access_token": make_token(sub=str(other.id))}
        )
        assert resp.status_code == 404

