"""Unit tests for deterministic cross-artifact comparisons.

Pins every result category for QC-002:
- added, removed, renamed, redefined, moved, reordered, unchanged.
- unrelated_histories detection and documented normalized name matching.
- coding diff categories (rows recoded, newly coded/uncoded, matching rows, per-code delta).
- strict reversibility: swapping A and B symmetrically reverses all directional fields.
"""

from backend.app.core.codebook_diff import diff_codes
from backend.app.core.coding_diff import diff_coding_entries
from backend.app.storage_models import CodingEntry


def test_codebook_comparison_all_categories_pinned():
    codes_a = [
        {"code_uid": "u_stay", "name": "Stay", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 1},
        {"code_uid": "u_rename", "name": "OldName", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 2},
        {"code_uid": "u_redef", "name": "Redef", "family_uid": "fam1", "family_name": "F1", "body": "old body", "position": 3},
        {"code_uid": "u_move", "name": "Move", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 4},
        {"code_uid": "u_order", "name": "Order", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 5},
        {"code_uid": "u_del", "name": "RemoveMe", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 6},
    ]

    codes_b = [
        {"code_uid": "u_stay", "name": "Stay", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 1},
        {"code_uid": "u_rename", "name": "NewName", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 2},
        {"code_uid": "u_redef", "name": "Redef", "family_uid": "fam1", "family_name": "F1", "body": "new body", "position": 3},
        {"code_uid": "u_move", "name": "Move", "family_uid": "fam2", "family_name": "F2", "body": "same", "position": 4},
        {"code_uid": "u_order", "name": "Order", "family_uid": "fam1", "family_name": "F1", "body": "same", "position": 10},
        {"code_uid": "u_add", "name": "AddMe", "family_uid": "fam1", "family_name": "F1", "body": "new", "position": 7},
    ]

    diff = diff_codes(codes_a, codes_b)

    assert not diff.unrelated_histories
    assert [c["code_uid"] for c in diff.unchanged] == ["u_stay"]
    assert [c["code_uid"] for c in diff.renamed] == ["u_rename"]
    assert diff.renamed[0]["from"]["name"] == "OldName"
    assert diff.renamed[0]["to"]["name"] == "NewName"

    assert [c["code_uid"] for c in diff.redefined] == ["u_redef"]
    assert diff.redefined[0]["from"]["body"] == "old body"
    assert diff.redefined[0]["to"]["body"] == "new body"

    assert [c["code_uid"] for c in diff.moved] == ["u_move"]
    assert diff.moved[0]["from"]["family_uid"] == "fam1"
    assert diff.moved[0]["to"]["family_uid"] == "fam2"

    assert [c["code_uid"] for c in diff.reordered] == ["u_order"]
    assert [c["code_uid"] for c in diff.removed] == ["u_del"]
    assert [c["code_uid"] for c in diff.added] == ["u_add"]


def test_codebook_comparison_unrelated_histories_rule():
    # Disjoint code_uids:
    codes_a = [
        {"code_uid": "a1", "name": "Theme Alpha", "family_uid": "fa", "family_name": "Fa", "body": "A body"},
        {"code_uid": "a2", "name": "Unique A", "family_uid": "fa", "family_name": "Fa", "body": "A only"},
    ]
    codes_b = [
        {"code_uid": "b1", "name": "theme alpha", "family_uid": "fb", "family_name": "Fb", "body": "B body"},
        {"code_uid": "b2", "name": "Unique B", "family_uid": "fb", "family_name": "Fb", "body": "B only"},
    ]

    diff = diff_codes(codes_a, codes_b, match_unrelated=True)
    assert diff.unrelated_histories is True

    # "Theme Alpha" matched across unrelated uids by normalized name rule
    assert len(diff.matched_by_name) == 1
    m = diff.matched_by_name[0]
    assert m["code_uid_from"] == "a1"
    assert m["code_uid_to"] == "b1"
    assert m["redefined"] is True  # bodies differed

    assert [c["code_uid"] for c in diff.removed] == ["a2"]
    assert [c["code_uid"] for c in diff.added] == ["b2"]


def test_codebook_reversibility():
    codes_a = [
        {"code_uid": "u1", "name": "Old", "family_uid": "f1", "family_name": "F1", "body": "body1"},
        {"code_uid": "u2", "name": "Removed", "family_uid": "f1", "family_name": "F1", "body": "b"},
    ]
    codes_b = [
        {"code_uid": "u1", "name": "New", "family_uid": "f1", "family_name": "F1", "body": "body2"},
        {"code_uid": "u3", "name": "Added", "family_uid": "f1", "family_name": "F1", "body": "b"},
    ]

    diff_ab = diff_codes(codes_a, codes_b)
    diff_ba = diff_codes(codes_b, codes_a)

    # added/removed reverse
    assert [c["code_uid"] for c in diff_ab.added] == [c["code_uid"] for c in diff_ba.removed]
    assert [c["code_uid"] for c in diff_ab.removed] == [c["code_uid"] for c in diff_ba.added]

    # renamed reverse
    assert diff_ab.renamed[0]["from"]["name"] == diff_ba.renamed[0]["to"]["name"]
    assert diff_ab.renamed[0]["to"]["name"] == diff_ba.renamed[0]["from"]["name"]


def test_coding_comparison_and_reversibility():
    # Entries for A
    entries_a = [
        CodingEntry(file_id=1, row_type="sub", post_id="p1", code_uid="u1", code="C1", quote="q1", start_offset=0, end_offset=2),
        CodingEntry(file_id=1, row_type="sub", post_id="p2", code_uid="u1", code="C1", quote="q2", start_offset=0, end_offset=2),
    ]
    # Entries for B: p1 stays identical, p2 gets code C2 (recoded), p3 is newly coded
    entries_b = [
        CodingEntry(file_id=2, row_type="sub", post_id="p1", code_uid="u1", code="C1", quote="q1", start_offset=0, end_offset=2),
        CodingEntry(file_id=2, row_type="sub", post_id="p2", code_uid="u2", code="C2", quote="q2", start_offset=0, end_offset=2),
        CodingEntry(file_id=2, row_type="sub", post_id="p3", code_uid="u1", code="C1", quote="q3", start_offset=0, end_offset=2),
    ]

    diff_ab = diff_coding_entries(entries_a, entries_b)
    assert diff_ab.from_total_entries == 2
    assert diff_ab.to_total_entries == 3
    assert diff_ab.matching_rows == 1  # p1 is identical
    assert diff_ab.rows_recoded == 2   # p2 changed, p3 is new
    assert diff_ab.rows_newly_coded == 1  # p3
    assert diff_ab.rows_newly_uncoded == 0

    counts_ab = {c.code_uid: c.delta for c in diff_ab.code_counts}
    # u2: 0 -> 1 (+1), u1: 2 -> 2 (delta 0, so not in code_counts)
    assert counts_ab.get("u2") == 1

    # Reverse diff B -> A
    diff_ba = diff_coding_entries(entries_b, entries_a)
    assert diff_ba.from_total_entries == 3
    assert diff_ba.to_total_entries == 2
    assert diff_ba.matching_rows == 1
    assert diff_ba.rows_recoded == 2
    assert diff_ba.rows_newly_coded == 0
    assert diff_ba.rows_newly_uncoded == 1  # p3 uncoded in A

    counts_ba = {c.code_uid: c.delta for c in diff_ba.code_counts}
    assert counts_ba.get("u2") == -1  # delta reversed!

    # Applied vs removed reversed:
    assert len(diff_ab.applied) == len(diff_ba.removed)
    assert len(diff_ab.removed) == len(diff_ba.applied)
