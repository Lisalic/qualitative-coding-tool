"""Service layer for deterministic cross-artifact comparisons.

Provides computed comparisons between two codebooks or two coding artifacts:
- Stable-identity matches (renamed, redefined, moved, reordered, unchanged).
- Unrelated-history detection with documented normalized name matching.
- Coding differences (recoded rows, newly coded/uncoded, per-code counts with delta,
  and applied/removed evidence entries).
- Reversibility: swapping A and B symmetrically inverts directional quantities.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.codebook_diff import diff_codes
from backend.app.core.coding_diff import diff_coding_entries
from backend.app.core.exceptions import NotFoundError
from backend.app.repositories import coding_repo, file_repo, version_repo
from backend.app.services import version_service


async def compare_codebooks(
    session: AsyncSession,
    user_id: int,
    file_a: str,
    file_b: str,
    *,
    version_a: int | None = None,
    version_b: int | None = None,
) -> dict[str, Any]:
    """Compare two codebook artifacts deterministically."""
    rec_a = await file_repo.get_owned_file(session, file_a, user_id, file_types=("codebook", "coding"))
    rec_b = await file_repo.get_owned_file(session, file_b, user_id, file_types=("codebook", "coding"))

    head_a = await version_repo.head_version(session, rec_a.id)
    resolved_va = version_a if version_a is not None else (head_a.version_no if head_a else 1)

    head_b = await version_repo.head_version(session, rec_b.id)
    resolved_vb = version_b if version_b is not None else (head_b.version_no if head_b else 1)

    codes_a = await version_service.read_codes(session, rec_a.id, version_no=version_a)
    codes_b = await version_service.read_codes(session, rec_b.id, version_no=version_b)

    diff = diff_codes(codes_a, codes_b, match_unrelated=True)

    return {
        "file_a": {
            "id": rec_a.id,
            "filename": rec_a.filename,
            "version_no": resolved_va,
        },
        "file_b": {
            "id": rec_b.id,
            "filename": rec_b.filename,
            "version_no": resolved_vb,
        },
        "unrelated_histories": diff.unrelated_histories,
        "added": diff.added,
        "removed": diff.removed,
        "renamed": diff.renamed,
        "redefined": diff.redefined,
        "moved": diff.moved,
        "reordered": diff.reordered,
        "unchanged": diff.unchanged,
        "matched_by_name": diff.matched_by_name,
        "is_empty": diff.is_empty(),
    }


async def compare_codings(
    session: AsyncSession,
    user_id: int,
    file_a: str,
    file_b: str,
    *,
    version_a: int | None = None,
    version_b: int | None = None,
) -> dict[str, Any]:
    """Compare two coding artifacts deterministically."""
    rec_a = await file_repo.get_owned_file(session, file_a, user_id, file_types=("coding",))
    rec_b = await file_repo.get_owned_file(session, file_b, user_id, file_types=("coding",))

    head_a = await version_repo.head_version(session, rec_a.id)
    resolved_va = version_a if version_a is not None else (head_a.version_no if head_a else 1)

    head_b = await version_repo.head_version(session, rec_b.id)
    resolved_vb = version_b if version_b is not None else (head_b.version_no if head_b else 1)

    if version_a is not None:
        entries_a = await coding_repo.entries_as_of(session, rec_a.id, version_a)
    else:
        entries_a = await coding_repo.get_coding_entries(session, rec_a.id)

    if version_b is not None:
        entries_b = await coding_repo.entries_as_of(session, rec_b.id, version_b)
    else:
        entries_b = await coding_repo.get_coding_entries(session, rec_b.id)

    diff = diff_coding_entries(entries_a, entries_b)

    return {
        "file_a": {
            "id": rec_a.id,
            "filename": rec_a.filename,
            "version_no": resolved_va,
        },
        "file_b": {
            "id": rec_b.id,
            "filename": rec_b.filename,
            "version_no": resolved_vb,
        },
        "from_total_entries": diff.from_total_entries,
        "to_total_entries": diff.to_total_entries,
        "from_coded_rows": diff.from_coded_rows,
        "to_coded_rows": diff.to_coded_rows,
        "matching_rows": diff.matching_rows,
        "rows_recoded": diff.rows_recoded,
        "rows_newly_coded": diff.rows_newly_coded,
        "rows_newly_uncoded": diff.rows_newly_uncoded,
        "unrelated_corpus": diff.unrelated_corpus,
        "code_counts": [
            {
                "code_uid": c.code_uid,
                "name": c.name,
                "from_count": c.from_count,
                "to_count": c.to_count,
                "delta": c.delta,
            }
            for c in diff.code_counts
        ],
        "applied": [
            {
                "row_type": c.row_type,
                "post_id": c.post_id,
                "code_uid": c.code_uid,
                "code": c.code,
                "quote": c.quote,
            }
            for c in diff.applied
        ],
        "removed": [
            {
                "row_type": c.row_type,
                "post_id": c.post_id,
                "code_uid": c.code_uid,
                "code": c.code,
                "quote": c.quote,
            }
            for c in diff.removed
        ],
        "is_empty": diff.is_empty(),
    }
