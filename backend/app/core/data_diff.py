"""Content diff between two versions of a ``raw_data``/``filtered_data``
artifact's own ``submissions``/``comments`` rows -- the data-file
counterpart to ``coding_diff.py``'s coding-content diff. Answers "how
many rows were added/removed between these two versions", not a
structural codebook diff (which is meaningless for a file with no
codebook at all -- see ``version_routes.py``).

Computed entirely in SQL via ``repositories/raw_data_repo.py::count_as_of``/
``row_ids_as_of`` rather than by pulling every row into Python: a diff
only ever needs counts and small samples, never the full row set.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Cap on how many added/removed ids are carried in the diff -- enough to
# show a meaningful sample without materializing (or serializing) a
# potentially enormous row set.
SAMPLE_CAP = 50


@dataclass
class DataDiff:
    from_submissions: int = 0
    to_submissions: int = 0
    from_comments: int = 0
    to_comments: int = 0
    submissions_added: int = 0
    submissions_removed: int = 0
    comments_added: int = 0
    comments_removed: int = 0
    sample_submissions_added: list[str] = field(default_factory=list)
    sample_submissions_removed: list[str] = field(default_factory=list)
    sample_comments_added: list[str] = field(default_factory=list)
    sample_comments_removed: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            self.from_submissions == 0 and self.to_submissions == 0
            and self.from_comments == 0 and self.to_comments == 0
        )


def _diff_ids(from_ids: set[str], to_ids: set[str]) -> tuple[int, int, list[str], list[str]]:
    added = to_ids - from_ids
    removed = from_ids - to_ids
    return (
        len(added), len(removed),
        sorted(added)[:SAMPLE_CAP], sorted(removed)[:SAMPLE_CAP],
    )


def diff_row_ids(
    *,
    from_submission_ids: set[str],
    to_submission_ids: set[str],
    from_comment_ids: set[str],
    to_comment_ids: set[str],
) -> DataDiff:
    """Build a ``DataDiff`` from the two versions' full id sets. Split
    out from the async DB read (``version_service.diff_data``) so the
    actual diffing logic is plain, synchronous, and unit-testable.
    """
    subs_added, subs_removed, subs_added_sample, subs_removed_sample = _diff_ids(
        from_submission_ids, to_submission_ids
    )
    comm_added, comm_removed, comm_added_sample, comm_removed_sample = _diff_ids(
        from_comment_ids, to_comment_ids
    )
    return DataDiff(
        from_submissions=len(from_submission_ids),
        to_submissions=len(to_submission_ids),
        from_comments=len(from_comment_ids),
        to_comments=len(to_comment_ids),
        submissions_added=subs_added,
        submissions_removed=subs_removed,
        comments_added=comm_added,
        comments_removed=comm_removed,
        sample_submissions_added=subs_added_sample,
        sample_submissions_removed=subs_removed_sample,
        sample_comments_added=comm_added_sample,
        sample_comments_removed=comm_removed_sample,
    )
