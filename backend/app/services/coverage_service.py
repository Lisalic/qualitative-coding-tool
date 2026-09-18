"""Service layer for qualitative coding coverage metrics.

Retrieves artifact rows, entries, and codebook snapshot for either the
current head or a specified historical version (using SCD-2 valid_from/valid_to),
then computes descriptive coverage metrics via ``core.coverage_metrics``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.coverage_metrics import compute_coverage_metrics
from backend.app.core.exceptions import NotFoundError
from backend.app.repositories import coding_repo, file_repo, version_repo
from backend.app.services import version_service


async def get_coding_coverage(
    session: AsyncSession,
    user_id: int,
    ref: str,
    *,
    version_no: int | None = None,
) -> dict[str, Any]:
    """Retrieve coverage statistics for a coding artifact.

    If ``version_no`` is provided, metrics are calculated historically as of
    that version using SCD-2 entries and the versioned codebook snapshot.
    Otherwise, the current head state is used.
    """
    file_rec = await file_repo.get_owned_file(session, ref, user_id, file_types=("coding",))

    if version_no is not None:
        version = await version_repo.get_version_by_no(session, file_rec.id, version_no)
        if version is None:
            raise NotFoundError(f"Version {version_no} not found for coding file {file_rec.id}")
        resolved_version_no = version.version_no
        entries = await coding_repo.entries_as_of(session, file_rec.id, version_no=version_no)
    else:
        head = await version_repo.head_version(session, file_rec.id)
        resolved_version_no = head.version_no if head else 1
        entries = await coding_repo.get_coding_entries(session, file_rec.id)

    total_rows = await coding_repo.count_rows(session, file_rec.id, version_no=version_no)
    codes = await version_service.read_codes(session, file_rec.id, version_no=version_no)

    coverage = compute_coverage_metrics(
        total_rows=total_rows,
        entries=entries,
        codes=codes,
    )

    return {
        "file_id": file_rec.id,
        "filename": file_rec.filename,
        "version_no": resolved_version_no,
        **coverage,
    }
