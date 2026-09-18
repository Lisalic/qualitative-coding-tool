"""Unit tests for the entry-level coding version diff."""

from types import SimpleNamespace

from backend.app.core.coding_diff import diff_coding_entries


def _entry(*, quote: str, start: int, code: str = "A", code_uid: str = "u1") -> SimpleNamespace:
    return SimpleNamespace(
        row_type="submission",
        post_id="s1",
        code=code,
        code_uid=code_uid,
        quote=quote,
        start_offset=start,
        end_offset=start + len(quote),
    )


def test_reports_exact_applied_and_removed_coding() -> None:
    before = _entry(quote="old evidence", start=0)
    unchanged = _entry(quote="same evidence", start=20, code="B", code_uid="u2")
    after = _entry(quote="new evidence", start=40)

    diff = diff_coding_entries([before, unchanged], [unchanged, after])

    assert [(entry.quote, entry.code) for entry in diff.applied] == [("new evidence", "A")]
    assert [(entry.quote, entry.code) for entry in diff.removed] == [("old evidence", "A")]
    assert diff.rows_recoded == 1


def test_unchanged_coding_is_not_listed() -> None:
    entry = _entry(quote="same evidence", start=0)

    diff = diff_coding_entries([entry], [entry])

    assert diff.applied == []
    assert diff.removed == []
