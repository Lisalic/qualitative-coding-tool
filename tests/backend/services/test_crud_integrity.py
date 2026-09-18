"""Cross-artifact CRUD invariants: deleting or editing one artifact must
never leave another one referencing something that isn't there.

These tests build a realistic pipeline graph (raw_data -> filtered_data
-> codebook -> coding -> summary, plus a fork) through the real service
functions, then delete pieces of it and assert two things after each
delete:

1. **No dangling references** -- ``_assert_no_dangling_references`` joins
   every table that carries a ``file_id``/``version_id``/``code_uid``
   against its target and requires zero orphans. The fixtures enforce
   foreign keys (``tests/conftest.py::_enable_sqlite_foreign_keys``), so
   most of these would also fail as an ``IntegrityError`` at write time
   -- the explicit join is here to catch the cases a nullable FK or a
   set-null cascade would let through quietly.

2. **Surviving artifacts still read correctly.** The point of a
   self-contained ``coding`` artifact (its own codebook snapshot, its own
   copied rows, its own ``coding_entries``) is that deleting the codebook
   it was applied from costs it a lineage edge and nothing else. That is
   asserted through the real read path, not by inspecting tables.
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.database import File, Project, User, async_link_file_to_project
from backend.app.repositories import coding_repo, file_repo, raw_data_repo
from backend.app.services import (
    coding_service,
    file_service,
    project_service,
    version_service,
)
from backend.app.services.version_service import EdgeSpec
from backend.app.storage_models import CodingEntry, Submission
from backend.app.versioning_models import (
    ORIGIN_GENERATED,
    RELATION_DERIVED_FROM,
    ROLE_CODEBOOK,
    ROLE_SOURCE_DATA,
)

_CODE = {
    "code_uid": "c1",
    "family_uid": "f1",
    "family_name": "Fam",
    "name": "Code One",
    "body": "b",
    "position": 0,
}


@pytest.fixture()
async def session(async_sqlite_engine):
    async with async_sessionmaker(async_sqlite_engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture()
async def uid(session) -> int:
    user = User(email="crud-integrity@example.com", password="hash")
    session.add(user)
    await session.commit()
    return user.id


async def _make_file(session, uid: int, file_type: str, schemaname: str) -> File:
    file_rec = File(
        user_id=uid, filename=f"{file_type}-{schemaname}", schemaname=schemaname, file_type=file_type
    )
    session.add(file_rec)
    await session.flush()
    return file_rec


@pytest.fixture()
async def graph(session, uid) -> dict[str, File]:
    """raw_data -> filtered_data -> codebook -> coding -> summary, with
    one submission carried all the way down and one coded entry on it.
    """
    raw = await _make_file(session, uid, "raw_data", "proj_raw")
    await version_service.commit_data_version(
        session, file_id=raw.id, author_user_id=uid, origin="imported"
    )
    await raw_data_repo.bulk_insert_submissions(
        session,
        raw.id,
        [
            {
                "id": "s1", "subreddit": "r", "title": "T", "selftext": "body one",
                "author": "a", "created_utc": 1, "score": 1, "num_comments": 0,
            }
        ],
    )
    await session.commit()

    filtered = await _make_file(session, uid, "filtered_data", "proj_filt")
    await version_service.commit_data_version(
        session, file_id=filtered.id, author_user_id=uid, origin=ORIGIN_GENERATED,
        parents=[EdgeSpec(parent_file_id=raw.id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA)],
    )
    await raw_data_repo.copy_all_rows(session, source_file_id=raw.id, target_file_id=filtered.id)
    await session.commit()

    codebook = await _make_file(session, uid, "codebook", "proj_cb")
    await version_service.commit_codebook_version(
        session, file_id=codebook.id, author_user_id=uid, origin=ORIGIN_GENERATED, codes=[dict(_CODE)],
        parents=[EdgeSpec(parent_file_id=filtered.id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA)],
    )
    await session.commit()

    coding = await _make_file(session, uid, "coding", "proj_cod")
    await version_service.commit_codebook_version(
        session, file_id=coding.id, author_user_id=uid, origin=ORIGIN_GENERATED, codes=[dict(_CODE)],
        parents=[
            EdgeSpec(parent_file_id=filtered.id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA),
            EdgeSpec(parent_file_id=codebook.id, relation=RELATION_DERIVED_FROM, role=ROLE_CODEBOOK),
        ],
    )
    await raw_data_repo.copy_all_rows(session, source_file_id=filtered.id, target_file_id=coding.id)
    await coding_repo.replace_entries_for_items(
        session,
        coding.id,
        [
            {
                "row_type": "submission",
                "post_id": "s1",
                "entries": [
                    {
                        "code": "Code One", "code_uid": "c1", "quote": "body",
                        "start_offset": 0, "end_offset": 4, "notes": None,
                    }
                ],
            }
        ],
        version_no=1,
    )
    await session.commit()

    summary = await _make_file(session, uid, "summary", "proj_sum")
    await version_service.commit_blob_version(
        session, file_id=summary.id, author_user_id=uid, origin=ORIGIN_GENERATED, content="# Summary",
        parents=[EdgeSpec(parent_file_id=coding.id, relation=RELATION_DERIVED_FROM, role=ROLE_SOURCE_DATA)],
    )
    await session.commit()

    return {"raw": raw, "filtered": filtered, "codebook": codebook, "coding": coding, "summary": summary}


_ORPHAN_QUERIES = {
    "edge -> child file": (
        "SELECT count(*) FROM artifact_edges e "
        "LEFT JOIN files f ON f.id = e.child_file_id WHERE f.id IS NULL"
    ),
    "edge -> parent file": (
        "SELECT count(*) FROM artifact_edges e "
        "LEFT JOIN files f ON f.id = e.parent_file_id WHERE f.id IS NULL"
    ),
    "edge -> pinned parent version": (
        "SELECT count(*) FROM artifact_edges e "
        "LEFT JOIN artifact_versions v ON v.id = e.parent_version_id "
        "WHERE e.parent_version_id IS NOT NULL AND v.id IS NULL"
    ),
    "version -> file": (
        "SELECT count(*) FROM artifact_versions v "
        "LEFT JOIN files f ON f.id = v.file_id WHERE f.id IS NULL"
    ),
    "version -> parent version": (
        "SELECT count(*) FROM artifact_versions v "
        "LEFT JOIN artifact_versions p ON p.id = v.parent_version_id "
        "WHERE v.parent_version_id IS NOT NULL AND p.id IS NULL"
    ),
    "code -> version": (
        "SELECT count(*) FROM codebook_codes c "
        "LEFT JOIN artifact_versions v ON v.id = c.version_id WHERE v.id IS NULL"
    ),
    "submission -> file": (
        "SELECT count(*) FROM submissions s LEFT JOIN files f ON f.id = s.file_id WHERE f.id IS NULL"
    ),
    "comment -> file": (
        "SELECT count(*) FROM comments c LEFT JOIN files f ON f.id = c.file_id WHERE f.id IS NULL"
    ),
    "coding entry -> file": (
        "SELECT count(*) FROM coding_entries e LEFT JOIN files f ON f.id = e.file_id WHERE f.id IS NULL"
    ),
    "project link -> file": (
        "SELECT count(*) FROM project_files pf LEFT JOIN files f ON f.id = pf.file_id WHERE f.id IS NULL"
    ),
    "project link -> project": (
        "SELECT count(*) FROM project_files pf "
        "LEFT JOIN projects p ON p.id = pf.project_id WHERE p.id IS NULL"
    ),
    "file table -> file": (
        "SELECT count(*) FROM file_tables t LEFT JOIN files f ON f.id = t.file_id WHERE f.id IS NULL"
    ),
}


async def _assert_no_dangling_references(session) -> None:
    orphans = {}
    for label, sql in _ORPHAN_QUERIES.items():
        count = (await session.execute(text(sql))).scalar() or 0
        if count:
            orphans[label] = count
    assert not orphans, f"dangling references after delete: {orphans}"


async def _assert_coding_reads_intact(session, uid: int, coding: File) -> None:
    artifact = await coding_service.get_coding_artifact(session, uid, coding.schemaname)
    assert [c.name for c in artifact["codes"]] == ["Code One"]
    assert artifact["total_rows"] == 1
    assert artifact["total_coded"] == 1
    rows = await coding_service.list_coding_rows(session, uid, coding.schemaname)
    assert rows["total"] == 1
    assert "Code One" in await coding_service.get_coding_text(session, uid, coding.schemaname)


class TestDeleteLeavesNoDanglingReferences:
    """The headline invariant: deleting any artifact in the graph leaves
    every other artifact whole and every reference resolvable.
    """

    async def test_deleting_the_codebook_does_not_compromise_the_coding(self, session, uid, graph) -> None:
        await file_service.delete_database(session, uid, graph["codebook"].schemaname)

        await _assert_no_dangling_references(session)
        # The coding artifact owns its own snapshot of the codebook, so
        # its codes, rows and text all survive the codebook's deletion.
        await _assert_coding_reads_intact(session, uid, graph["coding"])

    async def test_deleting_the_source_data_does_not_compromise_the_coding(self, session, uid, graph) -> None:
        await file_service.delete_database(session, uid, graph["filtered"].schemaname)

        await _assert_no_dangling_references(session)
        await _assert_coding_reads_intact(session, uid, graph["coding"])

    async def test_deleting_raw_data_does_not_compromise_the_filtered_copy(self, session, uid, graph) -> None:
        await file_service.delete_database(session, uid, graph["raw"].schemaname)

        await _assert_no_dangling_references(session)
        rows = (
            await session.execute(select(Submission).where(Submission.file_id == graph["filtered"].id))
        ).scalars().all()
        assert len(rows) == 1

    async def test_deleting_the_coding_does_not_compromise_its_summary(self, session, uid, graph) -> None:
        await file_service.delete_database(session, uid, graph["coding"].schemaname)

        await _assert_no_dangling_references(session)
        assert await version_service.read_blob(session, graph["summary"].id) == "# Summary"

    async def test_deleting_a_fork_origin_does_not_compromise_the_fork(self, session, uid, graph) -> None:
        # A fork's lineage points back at the artifact it was duplicated
        # from -- including, historically, a cross-file
        # `parent_version_id` -- so this is the delete most likely to
        # leave a pointer into nothing.
        fork = await coding_service.duplicate_coding(
            session, uid, graph["coding"].schemaname, display_name="fork"
        )
        await file_service.delete_database(session, uid, graph["coding"].schemaname)

        await _assert_no_dangling_references(session)
        await _assert_coding_reads_intact(session, uid, fork)

    async def test_deleting_a_project_linked_file_unlinks_it(self, session, uid, graph) -> None:
        project = Project(user_id=uid, projectname="P")
        session.add(project)
        await session.flush()
        await async_link_file_to_project(session, graph["coding"].id, project.id)
        await session.commit()

        await file_service.delete_database(session, uid, graph["coding"].schemaname)

        await _assert_no_dangling_references(session)
        listing = await project_service.list_projects_with_files(session, uid)
        assert [f["schema_name"] for p in listing for f in p["files"]] == []

    async def test_cannot_delete_another_users_file(self, session, uid, graph) -> None:
        other = User(email="other@example.com", password="hash")
        session.add(other)
        await session.commit()

        with pytest.raises(NotFoundError):
            await file_service.delete_database(session, other.id, graph["coding"].schemaname)


class TestLinkParentsToleratesADeletedParent:
    """``link_parents`` runs at the END of a background job, minutes after
    that job read its parents -- long enough for a user to delete one. It
    must drop the edge rather than write a reference to a file that is
    gone (which Postgres rejects outright, taking the finished artifact
    and its LLM output down with it).
    """

    async def test_edge_to_deleted_parent_is_skipped_not_written(self, session, uid, graph) -> None:
        codebook_id = graph["codebook"].id
        await file_service.delete_database(session, uid, graph["codebook"].schemaname)

        derived = await _make_file(session, uid, "coding", "proj_new")
        await version_service.commit_codebook_version(
            session, file_id=derived.id, author_user_id=uid, origin=ORIGIN_GENERATED, codes=[dict(_CODE)],
        )
        await version_service.link_parents(
            session,
            derived.id,
            [EdgeSpec(parent_file_id=codebook_id, relation=RELATION_DERIVED_FROM, role=ROLE_CODEBOOK)],
        )
        await session.commit()

        await _assert_no_dangling_references(session)

    async def test_surviving_parents_are_still_linked(self, session, uid, graph) -> None:
        codebook_id = graph["codebook"].id
        await file_service.delete_database(session, uid, graph["codebook"].schemaname)

        derived = await _make_file(session, uid, "coding", "proj_new")
        await version_service.commit_codebook_version(
            session, file_id=derived.id, author_user_id=uid, origin=ORIGIN_GENERATED, codes=[dict(_CODE)],
        )
        await version_service.link_parents(
            session,
            derived.id,
            [
                EdgeSpec(parent_file_id=codebook_id, relation=RELATION_DERIVED_FROM, role=ROLE_CODEBOOK),
                EdgeSpec(
                    parent_file_id=graph["filtered"].id,
                    relation=RELATION_DERIVED_FROM,
                    role=ROLE_SOURCE_DATA,
                ),
            ],
        )
        await session.commit()

        from backend.app.repositories import version_repo

        edges = await version_repo.list_parent_edges(session, derived.id)
        assert [e.parent_file_id for e in edges] == [graph["filtered"].id]

    async def test_source_deleted_mid_job_fails_loudly(self, session, uid, graph) -> None:
        # Unlike a lineage-only parent, a source whose ROWS get copied
        # into the new artifact cannot be silently dropped: doing so
        # would ship an artifact whose coding entries point at rows it
        # never received.
        source_id = graph["filtered"].id
        await file_service.delete_database(session, uid, graph["filtered"].schemaname)

        with pytest.raises(NotFoundError, match="no longer exists"):
            await file_repo.require_existing_file_ids(session, {source_id})


class TestAmbiguousRefsStayResolvable:
    """``files.filename`` is a user-chosen display name with no uniqueness
    constraint, and rename/duplicate both let two files share one. A
    lookup by that name must stay usable rather than raising
    ``MultipleResultsFound`` -- which used to 500 and lock the user out
    of reading, renaming OR deleting either colliding file.
    """

    async def test_lookup_by_shared_filename_resolves_to_the_oldest(self, session, uid) -> None:
        first = await _make_file(session, uid, "coding", "proj_x")
        second = await _make_file(session, uid, "coding", "proj_y")
        await session.commit()
        await project_service.rename_file(session, uid, "proj_x", "dupe", None)
        await project_service.rename_file(session, uid, "proj_y", "dupe", None)

        assert await file_repo.resolve_file_id(session, "dupe", uid) == first.id
        # Both stay individually addressable by their own schemaname.
        assert await file_repo.resolve_file_id(session, "proj_y", uid) == second.id

    async def test_both_colliding_files_stay_deletable(self, session, uid) -> None:
        first = await _make_file(session, uid, "raw_data", "proj_x")
        second = await _make_file(session, uid, "raw_data", "proj_y")
        first.filename = second.filename = "dupe"
        await session.commit()

        await file_service.delete_database(session, uid, "proj_x")
        await file_service.delete_database(session, uid, "proj_y")
        remaining = (await session.execute(select(File.id).where(File.user_id == uid))).scalars().all()
        assert remaining == []

    async def test_merge_name_guard_reports_the_collision(self, session, uid) -> None:
        first = await _make_file(session, uid, "raw_data", "proj_x")
        second = await _make_file(session, uid, "raw_data", "proj_y")
        first.filename = second.filename = "dupe"
        await session.commit()

        # The "name already taken" guard must return its own 400, not
        # break on the very collision it exists to detect.
        with pytest.raises(ValidationAppError, match="already exists"):
            await file_service.merge_databases(
                session, uid, name="dupe", description=None, source_schemas=[], project_id=None
            )


class TestCodingEntriesNeverReferenceAMissingCode:
    """Within a coding artifact, every live ``coding_entries`` row must
    resolve to a code in that artifact's current codebook snapshot --
    the same "no missing references" rule applied one level down.
    """

    async def test_removing_a_code_closes_the_entries_using_it(self, session, uid, graph) -> None:
        await coding_service.save_coding_revision(
            session,
            uid,
            graph["coding"].schemaname,
            codes=[dict(_CODE, code_uid="c2", name="Code Two")],
            rows=None,
        )

        live = (
            await session.execute(
                select(CodingEntry).where(
                    CodingEntry.file_id == graph["coding"].id, CodingEntry.valid_to.is_(None)
                )
            )
        ).scalars().all()
        current = {c.code_uid for c in await version_service.read_codes(session, graph["coding"].id)}
        assert all(entry.code_uid in current for entry in live)

    async def test_saving_a_row_against_a_removed_code_is_rejected(self, session, uid, graph) -> None:
        with pytest.raises(ValidationAppError, match="current codebook snapshot"):
            await coding_service.save_coding_revision(
                session,
                uid,
                graph["coding"].schemaname,
                codes=[dict(_CODE, code_uid="c2", name="Code Two")],
                rows=[{"item_id": "submission:s1", "entries": [{"code_uid": "c1"}]}],
            )


class TestRowDeletionIsScopedToItsOwnArtifact:
    async def test_deleting_source_rows_leaves_the_coding_copy_alone(self, session, uid, graph) -> None:
        closed = await file_service.delete_rows(
            session, uid, schemaname=graph["filtered"].schemaname, table="submissions", row_ids=["s1"]
        )
        assert closed == 1

        await _assert_no_dangling_references(session)
        await _assert_coding_reads_intact(session, uid, graph["coding"])
