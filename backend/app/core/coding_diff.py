"""Content diff between two revisions of a coding artifact's own
``coding_entries`` -- what was actually recoded, not the codebook
structure (see ``codebook_diff.py`` for that). Answers the question a
structural codebook diff can't: how many posts/comments changed
classification, and how the count of each code applied changed.

A row is keyed on ``(row_type, post_id)``; its "codes" at a version is
the SET of ``(code_uid, quote, start_offset, end_offset)`` tuples live
for it then. Two applications of the same code via different quotes
count as different codings (a genuinely different evidence choice, not
the same one re-saved), so the set comparison -- not just a code_uid
comparison -- is what "recoded" means here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class CodingCodeCount:
    code_uid: str
    name: str
    from_count: int
    to_count: int

    @property
    def delta(self) -> int:
        return self.to_count - self.from_count


@dataclass
class CodingEntryChange:
    row_type: str
    post_id: str
    code_uid: str
    code: str
    quote: str


@dataclass
class CodingDiff:
    from_total_entries: int = 0
    to_total_entries: int = 0
    from_coded_rows: int = 0
    to_coded_rows: int = 0
    rows_recoded: int = 0
    rows_newly_coded: int = 0
    rows_newly_uncoded: int = 0
    # Only codes whose applied count actually changed between the two
    # versions -- sorted by the size of that change, largest first, so
    # the most consequential recodes surface without a separate sort in
    # the UI.
    code_counts: list[CodingCodeCount] = field(default_factory=list)
    applied: list[CodingEntryChange] = field(default_factory=list)
    removed: list[CodingEntryChange] = field(default_factory=list)

    def is_empty(self) -> bool:
        return self.rows_recoded == 0 and self.from_total_entries == 0 and self.to_total_entries == 0


def _row_key(entry: Any) -> tuple:
    return (entry.row_type, entry.post_id)


def _entry_key(entry: Any) -> tuple:
    return (entry.code_uid, entry.quote, entry.start_offset, entry.end_offset)


def _change(entry: Any) -> CodingEntryChange:
    return CodingEntryChange(
        row_type=entry.row_type,
        post_id=entry.post_id,
        code_uid=entry.code_uid,
        code=entry.code,
        quote=entry.quote,
    )


def _change_sort_key(entry: Any) -> tuple:
    return (entry.row_type, entry.post_id, entry.start_offset, entry.end_offset, entry.code)


def diff_coding_entries(from_entries: Sequence[Any], to_entries: Sequence[Any]) -> CodingDiff:
    """Diff two lists of ``CodingEntry`` ORM rows (or anything duck-typed
    the same way), each already resolved to one version via
    ``coding_repo.entries_as_of``.
    """
    from_by_row: dict[tuple, set] = {}
    to_by_row: dict[tuple, set] = {}
    name_by_uid: dict[str, str] = {}
    from_count_by_uid: dict[str, int] = {}
    to_count_by_uid: dict[str, int] = {}
    from_by_key: dict[tuple, Any] = {}
    to_by_key: dict[tuple, Any] = {}

    for entry in from_entries:
        from_by_row.setdefault(_row_key(entry), set()).add(_entry_key(entry))
        from_by_key[_row_key(entry) + _entry_key(entry)] = entry
        name_by_uid[entry.code_uid] = entry.code
        from_count_by_uid[entry.code_uid] = from_count_by_uid.get(entry.code_uid, 0) + 1

    for entry in to_entries:
        to_by_row.setdefault(_row_key(entry), set()).add(_entry_key(entry))
        to_by_key[_row_key(entry) + _entry_key(entry)] = entry
        name_by_uid[entry.code_uid] = entry.code
        to_count_by_uid[entry.code_uid] = to_count_by_uid.get(entry.code_uid, 0) + 1

    rows_recoded = 0
    rows_newly_coded = 0
    rows_newly_uncoded = 0
    for row in set(from_by_row) | set(to_by_row):
        before = from_by_row.get(row, set())
        after = to_by_row.get(row, set())
        if before == after:
            continue
        rows_recoded += 1
        if not before:
            rows_newly_coded += 1
        elif not after:
            rows_newly_uncoded += 1

    code_counts = [
        CodingCodeCount(
            code_uid=uid,
            name=name_by_uid.get(uid, uid),
            from_count=from_count_by_uid.get(uid, 0),
            to_count=to_count_by_uid.get(uid, 0),
        )
        for uid in set(from_count_by_uid) | set(to_count_by_uid)
        if from_count_by_uid.get(uid, 0) != to_count_by_uid.get(uid, 0)
    ]
    code_counts.sort(key=lambda c: (-abs(c.delta), c.name))

    applied_entries = [to_by_key[key] for key in to_by_key.keys() - from_by_key.keys()]
    removed_entries = [from_by_key[key] for key in from_by_key.keys() - to_by_key.keys()]
    applied = [_change(entry) for entry in sorted(applied_entries, key=_change_sort_key)]
    removed = [_change(entry) for entry in sorted(removed_entries, key=_change_sort_key)]

    return CodingDiff(
        from_total_entries=len(from_entries),
        to_total_entries=len(to_entries),
        from_coded_rows=len(from_by_row),
        to_coded_rows=len(to_by_row),
        rows_recoded=rows_recoded,
        rows_newly_coded=rows_newly_coded,
        rows_newly_uncoded=rows_newly_uncoded,
        code_counts=code_counts,
        applied=applied,
        removed=removed,
    )
