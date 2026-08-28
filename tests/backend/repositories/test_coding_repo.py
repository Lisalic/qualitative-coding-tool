from backend.app.database import File
from backend.app.repositories.coding_repo import (
    bulk_insert_coding_entries,
    code_frequency,
    code_summary_with_samples,
    copy_entries,
    count_rows,
    get_coding_entries,
    list_rows_with_codes,
    render_coding_text,
    replace_entries_for_items,
)
from backend.app.storage_models import Comment, Submission

from .conftest import make_user


async def _make_file(session, user, schemaname: str = "coding_a") -> File:
    f = File(user_id=user.id, filename=f"{schemaname}.txt", schemaname=schemaname, file_type="coding")
    session.add(f)
    await session.commit()
    return f


def _entry(post_id: str, code: str, quote: str = "q", *, row_type: str | None = None, notes: str | None = None) -> dict:
    """A minimal, well-formed coding_entries insert dict -- one row per
    quote, offsets computed from the quote's own length since these tests
    don't exercise evidence_match (that's core/test_evidence_match.py's
    job) and just need internally-consistent placeholder offsets.
    """
    entry = {
        "post_id": post_id, "code": code, "code_uid": f"{code}-uid", "quote": quote,
        "start_offset": 0, "end_offset": len(quote),
    }
    if row_type is not None:
        entry["row_type"] = row_type
    if notes is not None:
        entry["notes"] = notes
    return entry


class TestBulkInsertCodingEntries:
    async def test_inserts_entries(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            entries = [
                _entry("p1", "CODE_A", "quote 1"),
                _entry("p1", "CODE_B", "quote 2"),
                _entry("p2", "CODE_A", "quote 3"),
            ]
            n = await bulk_insert_coding_entries(session, f.id, entries)
            await session.commit()
            assert n == 3

    async def test_empty_entries_is_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            n = await bulk_insert_coding_entries(session, f.id, [])
            assert n == 0

    async def test_missing_notes_defaults_to_none(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("p1", "CODE_A")])
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert entries[0].notes is None


class TestGetCodingEntries:
    async def test_all_entries_for_file(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry("p1", "CODE_A", "e1"), _entry("p2", "CODE_B", "e2")],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert {(e.post_id, e.code) for e in entries} == {("p1", "CODE_A"), ("p2", "CODE_B")}

    async def test_filtered_by_code(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry("p1", "CODE_A", "e1"), _entry("p2", "CODE_B", "e2"), _entry("p3", "CODE_A", "e3")],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id, code="CODE_A")
            assert {e.post_id for e in entries} == {"p1", "p3"}

    async def test_scoped_to_file_id(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f1 = await _make_file(session, user, "coding_a")
            f2 = await _make_file(session, user, "coding_b")
            await bulk_insert_coding_entries(session, f1.id, [_entry("p1", "CODE_A", "e1")])
            await bulk_insert_coding_entries(session, f2.id, [_entry("p1", "CODE_X", "e2")])
            await session.commit()

            entries = await get_coding_entries(session, f1.id)
            assert len(entries) == 1
            assert entries[0].code == "CODE_A"


class TestCodeFrequency:
    async def test_counts_grouped_and_ordered_desc(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [
                    _entry("p1", "CODE_A", "e1"),
                    _entry("p2", "CODE_A", "e2"),
                    _entry("p3", "CODE_A", "e3"),
                    _entry("p1", "CODE_B", "e4"),
                ],
            )
            await session.commit()

            freq = await code_frequency(session, f.id)
            assert freq[0] == ("CODE_A", 3)
            assert freq[1] == ("CODE_B", 1)

    async def test_counts_every_quote_row_not_distinct_items(self, session_factory) -> None:
        # count is per coding_entries row (one row per quote) -- an item
        # coded twice for the same code via two separate quotes counts
        # twice, the standard "references" meaning of code frequency in
        # qualitative coding tools.
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry("p1", "CODE_A", "quote a"), _entry("p1", "CODE_A", "quote b")],
            )
            await session.commit()

            freq = await code_frequency(session, f.id)
            assert freq == [("CODE_A", 2)]

    async def test_empty_returns_empty_list(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            freq = await code_frequency(session, f.id)
            assert freq == []


class TestCodeSummaryWithSamples:
    async def test_counts_and_ordering_match_code_frequency(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [
                    _entry("p1", "CODE_A", "e1"),
                    _entry("p2", "CODE_A", "e2"),
                    _entry("p3", "CODE_A", "e3"),
                    _entry("p1", "CODE_B", "e4"),
                ],
            )
            await session.commit()

            summaries = await code_summary_with_samples(session, f.id)
            assert summaries[0]["code"] == "CODE_A"
            assert summaries[0]["count"] == 3
            assert summaries[1]["code"] == "CODE_B"
            assert summaries[1]["count"] == 1

    async def test_evidence_sample_is_capped(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry(f"p{i}", "CODE_A", f"e{i}") for i in range(10)],
            )
            await session.commit()

            summaries = await code_summary_with_samples(session, f.id, max_evidence_per_code=3)
            assert summaries[0]["count"] == 10
            assert len(summaries[0]["sample_evidence"]) == 3

    async def test_empty_returns_empty_list(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            summaries = await code_summary_with_samples(session, f.id)
            assert summaries == []


class TestRowType:
    async def test_defaults_to_submission_when_omitted(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("p1", "CODE_A", "e1")])
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert entries[0].row_type == "submission"

    async def test_a_post_and_a_comment_sharing_an_id_coexist(self, session_factory) -> None:
        # Submission and comment ids share one bare-string namespace (both
        # strip their Reddit fullname prefix at import), so a genuine
        # collision between the two tables must not silently merge into
        # one coding_entries row.
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [
                    _entry("abc123", "CODE_A", "post evidence", row_type="submission"),
                    _entry("abc123", "CODE_A", "comment evidence", row_type="comment"),
                ],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert len(entries) == 2
            by_type = {e.row_type: e.quote for e in entries}
            assert by_type == {"submission": "post evidence", "comment": "comment evidence"}


class TestReplaceEntriesForItems:
    async def test_deletes_and_reinserts_for_the_given_keys_only(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry("p1", "OLD", "old ev"), _entry("p2", "UNTOUCHED", "e2")],
            )
            await session.commit()

            await replace_entries_for_items(
                session,
                f.id,
                [
                    {
                        "row_type": "submission",
                        "post_id": "p1",
                        "entries": [{"code": "NEW", "code_uid": "NEW-uid", "quote": "new ev", "start_offset": 0, "end_offset": 6}],
                    }
                ],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            by_post = {(e.post_id, e.code): e.quote for e in entries}
            assert by_post == {("p1", "NEW"): "new ev", ("p2", "UNTOUCHED"): "e2"}

    async def test_empty_entries_list_leaves_the_row_with_zero_codes(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("p1", "A", "e")])
            await session.commit()

            await replace_entries_for_items(
                session, f.id, [{"row_type": "submission", "post_id": "p1", "entries": []}]
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert entries == []

    async def test_empty_items_list_is_a_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("p1", "A", "e")])
            await session.commit()

            await replace_entries_for_items(session, f.id, [])
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert len(entries) == 1

    async def test_carries_notes_through(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            await replace_entries_for_items(
                session,
                f.id,
                [
                    {
                        "row_type": "submission",
                        "post_id": "p1",
                        "entries": [
                            {"code": "A", "code_uid": "A-uid", "quote": "e", "start_offset": 0, "end_offset": 1, "notes": "n"}
                        ],
                    }
                ],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert entries[0].notes == "n"

    async def test_one_code_can_carry_several_quote_rows(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)

            await replace_entries_for_items(
                session,
                f.id,
                [
                    {
                        "row_type": "submission",
                        "post_id": "p1",
                        "entries": [
                            {"code": "A", "code_uid": "A-uid", "quote": "one", "start_offset": 0, "end_offset": 3},
                            {"code": "A", "code_uid": "A-uid", "quote": "two", "start_offset": 10, "end_offset": 13},
                        ],
                    }
                ],
            )
            await session.commit()

            entries = await get_coding_entries(session, f.id)
            assert len(entries) == 2
            assert {e.quote for e in entries} == {"one", "two"}
            assert all(e.code == "A" for e in entries)


class TestCopyEntries:
    async def test_copies_every_row_to_the_target_file(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "coding_src")
            target = await _make_file(session, user, "coding_target")
            await bulk_insert_coding_entries(
                session,
                source.id,
                [_entry("p1", "A", "e1"), _entry("p2", "B", "e2")],
            )
            await session.commit()

            n = await copy_entries(session, source_file_id=source.id, target_file_id=target.id)
            await session.commit()

            assert n == 2
            copied = await get_coding_entries(session, target.id)
            assert {(e.post_id, e.code) for e in copied} == {("p1", "A"), ("p2", "B")}
            # source rows are untouched, not moved
            assert len(await get_coding_entries(session, source.id)) == 2
            # each copied row gets its own surrogate id, not the source's
            source_ids = {e.id for e in await get_coding_entries(session, source.id)}
            copied_ids = {e.id for e in copied}
            assert source_ids.isdisjoint(copied_ids)

    async def test_empty_source_is_a_noop(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "coding_src_empty")
            target = await _make_file(session, user, "coding_target_empty")

            n = await copy_entries(session, source_file_id=source.id, target_file_id=target.id)
            assert n == 0
            assert await get_coding_entries(session, target.id) == []

    async def test_as_of_version_no_copies_the_live_set_from_that_version_not_head(
        self, session_factory
    ) -> None:
        """``as_of_version_no`` is what a codebook/coding fork uses to
        recover a past state (see version_service.py's module docstring:
        history is append-only, so "revert" is "duplicate from an older
        version" instead of a truncating rewind). v1: p1=A. v2: p1
        recoded to B (A closed at valid_to=1). Forking as-of v1 must copy
        A, not B -- and leave the source's own rows untouched.
        """
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "coding_src_asof")
            target = await _make_file(session, user, "coding_target_asof")
            await bulk_insert_coding_entries(session, source.id, [_entry("p1", "A", "e1")], version_no=1)
            await session.commit()
            await replace_entries_for_items(
                session, source.id,
                [{"row_type": "submission", "post_id": "p1", "entries": [_entry("p1", "B", "e2")]}],
                version_no=2,
            )
            await session.commit()

            n = await copy_entries(session, source_file_id=source.id, target_file_id=target.id, as_of_version_no=1)
            await session.commit()

            assert n == 1
            copied = await get_coding_entries(session, target.id)
            assert [e.code for e in copied] == ["A"]
            # Re-stamped as the fork's own v1, not the source's version_no=1.
            assert copied[0].valid_from == 1
            assert copied[0].valid_to is None

            # Source is untouched: A is still closed at 1, B is still live.
            from sqlalchemy import select as _select
            from backend.app.storage_models import CodingEntry as _CodingEntry

            source_rows = (
                await session.execute(_select(_CodingEntry).where(_CodingEntry.file_id == source.id))
            ).scalars().all()
            assert len(source_rows) == 2

    async def test_as_of_version_no_includes_an_item_untouched_since_that_version(
        self, session_factory
    ) -> None:
        # p2 was never touched by the v1->v2 edit and is still live at v2
        # -- forking as-of v1 must still include it (it was live then too).
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "coding_src_asof2")
            target = await _make_file(session, user, "coding_target_asof2")
            await bulk_insert_coding_entries(
                session, source.id, [_entry("p1", "A", "e1"), _entry("p2", "Z", "e9")], version_no=1,
            )
            await session.commit()
            await replace_entries_for_items(
                session, source.id,
                [{"row_type": "submission", "post_id": "p1", "entries": [_entry("p1", "B", "e2")]}],
                version_no=2,
            )
            await session.commit()

            await copy_entries(session, source_file_id=source.id, target_file_id=target.id, as_of_version_no=1)
            await session.commit()

            copied = await get_coding_entries(session, target.id)
            assert {(e.post_id, e.code) for e in copied} == {("p1", "A"), ("p2", "Z")}

    async def test_as_of_empty_target_version_copies_zero_entries(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            source = await _make_file(session, user, "coding_src_asof3")
            target = await _make_file(session, user, "coding_target_asof3")
            # v1 is empty (no entries at all); v2 codes p1.
            await replace_entries_for_items(
                session, source.id,
                [{"row_type": "submission", "post_id": "p1", "entries": [_entry("p1", "A", "e1")]}],
                version_no=2,
            )
            await session.commit()

            n = await copy_entries(session, source_file_id=source.id, target_file_id=target.id, as_of_version_no=1)
            await session.commit()

            assert n == 0
            assert await get_coding_entries(session, target.id) == []


class TestSCD2Ranges:
    """``replace_entries_for_items``'s three-step algorithm --
    storage_models.py::CodingEntry's range invariant, exercised directly
    against real version-number arguments rather than through the
    service layer.
    """

    async def test_row_born_in_the_same_open_version_is_deleted_not_closed(self, session_factory) -> None:
        # A row created within version 2 and replaced again still under
        # version 2 (an in-place edit of an unsealed draft) never existed
        # in a sealed version -- removing it outright is not history loss.
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("p1", "A", "e1")], version_no=2)
            await session.commit()

            await replace_entries_for_items(
                session, f.id, [{"row_type": "submission", "post_id": "p1", "entries": []}], version_no=2,
            )
            await session.commit()

            all_rows = await get_coding_entries(session, f.id)
            assert all_rows == []  # gone entirely, not closed -- never existed at any sealed version

    async def test_row_inherited_from_a_sealed_ancestor_is_closed_not_deleted(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("p1", "A", "e1")], version_no=1)
            await session.commit()

            await replace_entries_for_items(
                session, f.id,
                [{"row_type": "submission", "post_id": "p1", "entries": [_entry("p1", "B", "e2")]}],
                version_no=2,
            )
            await session.commit()

            from sqlalchemy import select as _select
            from backend.app.storage_models import CodingEntry as _CodingEntry

            all_rows = (
                await session.execute(_select(_CodingEntry).where(_CodingEntry.file_id == f.id))
            ).scalars().all()
            by_code = {r.code: r for r in all_rows}
            assert by_code["A"].valid_from == 1
            assert by_code["A"].valid_to == 1  # closed at version_no - 1, never deleted
            assert by_code["B"].valid_from == 2
            assert by_code["B"].valid_to is None  # live

    async def test_live_reads_see_only_the_current_version(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("p1", "A", "e1")], version_no=1)
            await session.commit()

            await replace_entries_for_items(
                session, f.id,
                [{"row_type": "submission", "post_id": "p1", "entries": [_entry("p1", "B", "e2")]}],
                version_no=2,
            )
            await session.commit()

            # get_coding_entries, code_frequency: both route through _live()
            # and must show only "B", even though "A" still physically
            # exists as closed history.
            live = await get_coding_entries(session, f.id)
            assert [e.code for e in live] == ["B"]

            freq = await code_frequency(session, f.id)
            assert freq == [("B", 1)]

    async def test_untouched_items_keep_their_range_across_a_version_boundary(self, session_factory) -> None:
        # Editing item p1 under version 2 must not touch item p2's
        # version-1 range at all.
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session, f.id, [_entry("p1", "A", "e1"), _entry("p2", "Z", "e9")], version_no=1,
            )
            await session.commit()

            await replace_entries_for_items(
                session, f.id,
                [{"row_type": "submission", "post_id": "p1", "entries": [_entry("p1", "B", "e2")]}],
                version_no=2,
            )
            await session.commit()

            from sqlalchemy import select as _select
            from backend.app.storage_models import CodingEntry as _CodingEntry

            p2_row = (
                await session.execute(
                    _select(_CodingEntry).where(_CodingEntry.file_id == f.id, _CodingEntry.post_id == "p2")
                )
            ).scalar_one()
            assert p2_row.valid_from == 1
            assert p2_row.valid_to is None


class TestRenderCodingText:
    async def test_renders_canonical_post_id_code_evidence_notes(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry("s1", "A", "quote", notes="my note")],
            )
            await session.commit()

            text = await render_coding_text(session, f.id)
            assert text == "POST_ID: t3_s1\nCODE: A\nNOTES: my note\nEVIDENCE: quote"

    async def test_omits_notes_line_when_absent(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(session, f.id, [_entry("s1", "A", "e")])
            await session.commit()

            text = await render_coding_text(session, f.id)
            assert "NOTES:" not in text

    async def test_comment_row_type_gets_t1_prefix(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry("c1", "A", "e", row_type="comment")],
            )
            await session.commit()

            text = await render_coding_text(session, f.id)
            assert text.startswith("POST_ID: t1_c1")

    async def test_multiple_quotes_for_the_same_code_each_get_their_own_block(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await bulk_insert_coding_entries(
                session,
                f.id,
                [_entry("s1", "A", "quote one"), _entry("s1", "A", "quote two")],
            )
            await session.commit()

            text = await render_coding_text(session, f.id)
            assert text.count("CODE: A") == 2
            assert "EVIDENCE: quote one" in text
            assert "EVIDENCE: quote two" in text

    async def test_empty_when_nothing_coded(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            assert await render_coding_text(session, f.id) == ""


class TestListRowsWithCodesAndCountRows:
    async def _seed(self, session, file_id):
        session.add_all(
            [
                Submission(file_id=file_id, id="s1", title="Coded submission", selftext="body one", word_count=2),
                Submission(file_id=file_id, id="s2", title="Uncoded submission", selftext="body two", word_count=2),
                Comment(file_id=file_id, id="c1", body="a comment body", link_id="s1", word_count=3),
            ]
        )
        await bulk_insert_coding_entries(
            session, file_id, [_entry("s1", "A", "e", row_type="submission")]
        )
        await session.commit()

    async def test_lists_every_submission_and_comment_coded_or_not(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await self._seed(session, f.id)

            rows = await list_rows_with_codes(session, f.id)
            assert {r["item_id"] for r in rows} == {"t3_s1", "t3_s2", "t1_c1"}
            by_item = {r["item_id"]: r for r in rows}
            assert by_item["t3_s1"]["codes"] == [
                {"code": "A", "code_uid": "A-uid", "quote": "e", "start_offset": 0, "end_offset": 1, "notes": None}
            ]
            assert by_item["t3_s2"]["codes"] == []
            assert by_item["t1_c1"]["title"] is None

            total = await count_rows(session, f.id)
            assert total == 3

    async def test_only_coded_filter(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await self._seed(session, f.id)

            rows = await list_rows_with_codes(session, f.id, only="coded")
            assert [r["item_id"] for r in rows] == ["t3_s1"]
            assert await count_rows(session, f.id, only="coded") == 1

    async def test_only_uncoded_filter(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await self._seed(session, f.id)

            rows = await list_rows_with_codes(session, f.id, only="uncoded")
            assert {r["item_id"] for r in rows} == {"t3_s2", "t1_c1"}
            assert await count_rows(session, f.id, only="uncoded") == 2

    async def test_code_filter(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await self._seed(session, f.id)

            rows = await list_rows_with_codes(session, f.id, code="A")
            assert [r["item_id"] for r in rows] == ["t3_s1"]

    async def test_search_matches_title_or_body_case_insensitively(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await self._seed(session, f.id)

            rows = await list_rows_with_codes(session, f.id, q="COMMENT")
            assert [r["item_id"] for r in rows] == ["t1_c1"]

    async def test_pagination_limit_and_offset(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            await self._seed(session, f.id)

            page1 = await list_rows_with_codes(session, f.id, limit=1, offset=0)
            page2 = await list_rows_with_codes(session, f.id, limit=1, offset=1)
            assert len(page1) == 1
            assert len(page2) == 1
            assert page1[0]["item_id"] != page2[0]["item_id"]

    async def test_empty_file_returns_no_rows(self, session_factory) -> None:
        async with session_factory() as session:
            user = await make_user(session)
            f = await _make_file(session, user)
            assert await list_rows_with_codes(session, f.id) == []
            assert await count_rows(session, f.id) == 0
