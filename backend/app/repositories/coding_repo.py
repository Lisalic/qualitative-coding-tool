"""Repository for structured coding output (``coding_entries``).

One row per ``(file_id, post_id, code)`` -- populated from the same
POST_ID/CODE/EVIDENCE parse ``backend/scripts/codebook_apply.py`` already
does, so this persists structure that used to be discarded when the
classification output was flattened back into one opaque blob. Enables a
real ``SELECT code, COUNT(*) ... GROUP BY code``, impossible today without
pulling and re-parsing a blob client-side.
"""

from __future__ import annotations

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.storage_models import CodingEntry


async def bulk_insert_coding_entries(
    session: AsyncSession, file_id: int, entries: list[dict]
) -> int:
    """Insert ``entries`` (dicts with ``post_id``, ``code``, ``evidence``
    keys) in a single executemany-style ``INSERT``. Returns the count
    inserted.
    """
    if not entries:
        return 0
    payload = [
        {
            "file_id": file_id,
            "post_id": entry["post_id"],
            "code": entry["code"],
            "evidence": entry.get("evidence"),
        }
        for entry in entries
    ]
    await session.execute(insert(CodingEntry), payload)
    return len(payload)


async def get_coding_entries(
    session: AsyncSession, file_id: int, code: str | None = None
) -> list[CodingEntry]:
    """All coding entries for ``file_id``, optionally filtered to one
    ``code``.
    """
    stmt = select(CodingEntry).where(CodingEntry.file_id == file_id)
    if code is not None:
        stmt = stmt.where(CodingEntry.code == code)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def code_frequency(session: AsyncSession, file_id: int) -> list[tuple[str, int]]:
    """``(code, count)`` pairs for ``file_id``, most frequent first."""
    result = await session.execute(
        select(CodingEntry.code, func.count())
        .where(CodingEntry.file_id == file_id)
        .group_by(CodingEntry.code)
        .order_by(func.count().desc())
    )
    return [(row[0], row[1]) for row in result.all()]
