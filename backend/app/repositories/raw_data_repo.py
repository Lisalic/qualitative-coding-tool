"""Repository for bulk operations on ``submissions``/``comments``.

Replaces the per-row insert loops that used to run against a brand-new
Postgres schema per upload/filter/move (``file_routes.py`` upload path,
``data_routes.py::filter_data`` lines ~623-677, ``file_routes.py::move_rows``)
with set-based bulk-insert and insert-from-select operations against the
fixed ``submissions``/``comments`` tables, keyed by ``file_id``.
"""

from __future__ import annotations

import math

from sqlalchemy import func, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.storage_models import Comment, Submission


def _word_count(text: str | None) -> int:
    """Count of whitespace-delimited tokens, matching the old
    ``GENERATED ALWAYS AS (...)`` SQL expression this replaces: normalize
    whitespace, split on spaces, count non-empty tokens; 0 for empty text.
    """
    if not text:
        return 0
    return len(text.split())


async def bulk_insert_submissions(session: AsyncSession, file_id: int, rows: list[dict]) -> int:
    """Insert ``rows`` (dicts keyed like ``Submission`` columns, minus
    ``file_id``/``word_count``) in a single executemany-style
    ``INSERT``. ``word_count`` is computed here from ``title``+``selftext``.
    Returns the count inserted.
    """
    if not rows:
        return 0
    payload = []
    for row in rows:
        row = dict(row)
        title = row.get("title") or ""
        selftext = row.get("selftext") or ""
        row["word_count"] = _word_count(f"{title} {selftext}".strip())
        row["file_id"] = file_id
        payload.append(row)
    await session.execute(insert(Submission), payload)
    return len(payload)


async def bulk_insert_comments(session: AsyncSession, file_id: int, rows: list[dict]) -> int:
    """Same shape as ``bulk_insert_submissions``, computing ``word_count``
    from ``body``.
    """
    if not rows:
        return 0
    payload = []
    for row in rows:
        row = dict(row)
        row["word_count"] = _word_count(row.get("body") or "")
        row["file_id"] = file_id
        payload.append(row)
    await session.execute(insert(Comment), payload)
    return len(payload)


async def sample_submissions(
    session: AsyncSession, file_id: int, sample_percentage: float
) -> list[Submission]:
    """``ceil(total * sample_percentage / 100)`` random rows for
    ``file_id``, matching the sampling logic in
    ``codebook_routes.py::generate_codebook`` /
    ``coding_routes.py::_assemble_posts_content``.
    """
    total_result = await session.execute(
        select(func.count()).select_from(Submission).where(Submission.file_id == file_id)
    )
    total = total_result.scalar() or 0
    n = math.ceil(total * sample_percentage / 100.0)
    if n <= 0:
        return []
    result = await session.execute(
        select(Submission).where(Submission.file_id == file_id).order_by(func.random()).limit(n)
    )
    return list(result.scalars().all())


async def sample_comments(
    session: AsyncSession, file_id: int, sample_percentage: float
) -> list[Comment]:
    """Same shape as ``sample_submissions``, over ``comments``."""
    total_result = await session.execute(
        select(func.count()).select_from(Comment).where(Comment.file_id == file_id)
    )
    total = total_result.scalar() or 0
    n = math.ceil(total * sample_percentage / 100.0)
    if n <= 0:
        return []
    result = await session.execute(
        select(Comment).where(Comment.file_id == file_id).order_by(func.random()).limit(n)
    )
    return list(result.scalars().all())


async def copy_rows_by_id(
    session: AsyncSession,
    *,
    source_file_id: int,
    target_file_id: int,
    submission_ids: list[str] | None = None,
    comment_ids: list[str] | None = None,
) -> dict[str, int]:
    """Set-based copy of specific rows from ``source_file_id`` to
    ``target_file_id``, replacing the per-id ``SELECT``+``INSERT`` loops in
    ``data_routes.py::filter_data`` and ``file_routes.py::move_rows``.

    Each id list is skipped entirely (no query run) when ``None``/empty.
    Returns ``{"submissions": n, "comments": m}`` counts actually copied.
    """
    counts = {"submissions": 0, "comments": 0}

    if submission_ids:
        non_id_cols = [c for c in Submission.__table__.c if c.name != "file_id"]
        col_names = ["file_id"] + [c.name for c in non_id_cols]

        count_result = await session.execute(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.file_id == source_file_id,
                Submission.id.in_(submission_ids),
            )
        )
        n = count_result.scalar() or 0
        if n:
            src_select = select(literal(target_file_id).label("file_id"), *non_id_cols).where(
                Submission.file_id == source_file_id,
                Submission.id.in_(submission_ids),
            )
            await session.execute(insert(Submission).from_select(col_names, src_select))
        counts["submissions"] = n

    if comment_ids:
        non_id_cols = [c for c in Comment.__table__.c if c.name != "file_id"]
        col_names = ["file_id"] + [c.name for c in non_id_cols]

        count_result = await session.execute(
            select(func.count())
            .select_from(Comment)
            .where(
                Comment.file_id == source_file_id,
                Comment.id.in_(comment_ids),
            )
        )
        n = count_result.scalar() or 0
        if n:
            src_select = select(literal(target_file_id).label("file_id"), *non_id_cols).where(
                Comment.file_id == source_file_id,
                Comment.id.in_(comment_ids),
            )
            await session.execute(insert(Comment).from_select(col_names, src_select))
        counts["comments"] = n

    return counts
