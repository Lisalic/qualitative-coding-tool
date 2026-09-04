"""Repository for bulk operations on ``submissions``/``comments``.

Replaces the per-row insert loops that used to run against a brand-new
Postgres schema per upload/filter/move (``file_routes.py`` upload path,
``data_routes.py::filter_data`` lines ~623-677, ``file_routes.py::move_rows``)
with set-based bulk-insert and insert-from-select operations against the
fixed ``submissions``/``comments`` tables, keyed by ``file_id``.

Every read in this module applies the SCD-2 liveness predicate (see
``storage_models.py``'s ``Submission``/``Comment`` docstrings): a row is
live iff ``valid_to IS NULL``, live *as of* version ``v`` iff
``valid_from <= v AND (valid_to IS NULL OR valid_to >= v)``. This mirrors
``coding_repo.py``'s ``_live``/``entries_as_of`` split for
``coding_entries``.
"""

from __future__ import annotations

import math

from sqlalchemy import and_, func, insert, literal, null, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.storage_models import Comment, Submission

# Columns never copied verbatim between files: `pk` is a per-row
# surrogate identity, `file_id` is supplied by the caller, and
# `valid_from`/`valid_to` are re-stamped against the TARGET file's own
# version sequence rather than carried over from the source's.
_UNCOPIED_COLUMNS = {"pk", "file_id", "valid_from", "valid_to"}


def _live(model, query):
    return query.where(model.valid_to.is_(None))


def _as_of(model, version_no: int):
    return and_(
        model.valid_from <= version_no,
        or_(model.valid_to.is_(None), model.valid_to >= version_no),
    )


def _liveness_condition(model, *, version_no: int | None):
    return _as_of(model, version_no) if version_no is not None else model.valid_to.is_(None)


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
    Every inserted row lands live (``valid_from=1`` via the column
    default, ``valid_to=NULL``) since this is only ever called to
    populate a brand-new file's v1. Returns the count inserted.
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
    """``ceil(total * sample_percentage / 100)`` random LIVE rows for
    ``file_id``, matching the sampling logic in
    ``codebook_routes.py::generate_codebook`` /
    ``coding_routes.py::_assemble_posts_content``.
    """
    total_result = await session.execute(
        _live(Submission, select(func.count()).select_from(Submission).where(Submission.file_id == file_id))
    )
    total = total_result.scalar() or 0
    n = math.ceil(total * sample_percentage / 100.0)
    if n <= 0:
        return []
    result = await session.execute(
        _live(Submission, select(Submission).where(Submission.file_id == file_id))
        .order_by(func.random())
        .limit(n)
    )
    return list(result.scalars().all())


async def sample_comments(
    session: AsyncSession, file_id: int, sample_percentage: float
) -> list[Comment]:
    """Same shape as ``sample_submissions``, over ``comments``."""
    total_result = await session.execute(
        _live(Comment, select(func.count()).select_from(Comment).where(Comment.file_id == file_id))
    )
    total = total_result.scalar() or 0
    n = math.ceil(total * sample_percentage / 100.0)
    if n <= 0:
        return []
    result = await session.execute(
        _live(Comment, select(Comment).where(Comment.file_id == file_id))
        .order_by(func.random())
        .limit(n)
    )
    return list(result.scalars().all())


async def parent_post_context_for_comments(
    session: AsyncSession, file_id: int, comments: list[Comment]
) -> dict[str, dict[str, str]]:
    """``{submission_id: {"title", "selftext"}}`` for every distinct
    ``Comment.link_id`` among ``comments`` that resolves to a LIVE
    submission in ``file_id`` -- one batched query rather than one per
    comment.

    ``link_id`` already has its ``t3_`` prefix stripped at import
    (``backend/scripts/import_db.py``), so it matches ``Submission.id``
    directly. Shared by ``codebook_service`` and ``coding_service`` so a
    comment sent to either the codebook generator or the classifier can
    carry its parent post as context.
    """
    link_ids = {c.link_id for c in comments if c.link_id}
    if not link_ids:
        return {}
    rows = await session.execute(
        _live(
            Submission,
            select(Submission.id, Submission.title, Submission.selftext).where(
                Submission.file_id == file_id,
                Submission.id.in_(link_ids),
            ),
        )
    )
    return {str(r.id): {"title": r.title or "", "selftext": r.selftext or ""} for r in rows}


async def row_ids_as_of(session: AsyncSession, file_id: int, *, version_no: int, table: str) -> set[str]:
    """Every ``id`` live as of ``version_no`` for ``file_id``'s
    ``submissions``/``comments`` -- backs ``core/data_diff.py``'s
    added/removed set comparison, mirroring
    ``coding_repo.entries_as_of``'s as-of read for ``coding_entries``.
    """
    model = Submission if table == "submissions" else Comment
    result = await session.execute(
        select(model.id).where(model.file_id == file_id, _as_of(model, version_no))
    )
    return {row[0] for row in result.all()}


async def copy_rows_by_id(
    session: AsyncSession,
    *,
    source_file_id: int,
    target_file_id: int,
    submission_ids: list[str] | None = None,
    comment_ids: list[str] | None = None,
    target_version_no: int = 1,
    source_version_no: int | None = None,
) -> dict[str, int]:
    """Set-based copy of specific rows from ``source_file_id`` to
    ``target_file_id``, replacing the per-id ``SELECT``+``INSERT`` loops in
    ``data_routes.py::filter_data`` and ``file_routes.py::move_rows``.

    Each id list is skipped entirely (no query run) when ``None``/empty.
    Copied rows are re-stamped ``valid_from=target_version_no,
    valid_to=NULL`` on the target side -- ``valid_from`` is keyed on the
    OWNING file's own version sequence, so carrying the source's range
    across verbatim would be meaningless (mirrors
    ``coding_repo.copy_entries``'s re-stamping for the same reason).
    ``source_version_no`` selects the source rows AS OF that version
    (for restore-from-version); default (``None``) selects the source's
    currently LIVE rows.

    Returns ``{"submissions": n, "comments": m}`` counts actually copied.
    """
    counts = {"submissions": 0, "comments": 0}
    source_condition = _liveness_condition

    if submission_ids:
        non_id_cols = [c for c in Submission.__table__.c if c.name not in _UNCOPIED_COLUMNS]
        col_names = ["file_id", "valid_from", "valid_to"] + [c.name for c in non_id_cols]
        where = and_(
            Submission.file_id == source_file_id,
            Submission.id.in_(submission_ids),
            source_condition(Submission, version_no=source_version_no),
        )

        count_result = await session.execute(select(func.count()).select_from(Submission).where(where))
        n = count_result.scalar() or 0
        if n:
            src_select = select(
                literal(target_file_id).label("file_id"),
                literal(target_version_no).label("valid_from"),
                null().label("valid_to"),
                *non_id_cols,
            ).where(where)
            await session.execute(insert(Submission).from_select(col_names, src_select))
        counts["submissions"] = n

    if comment_ids:
        non_id_cols = [c for c in Comment.__table__.c if c.name not in _UNCOPIED_COLUMNS]
        col_names = ["file_id", "valid_from", "valid_to"] + [c.name for c in non_id_cols]
        where = and_(
            Comment.file_id == source_file_id,
            Comment.id.in_(comment_ids),
            source_condition(Comment, version_no=source_version_no),
        )

        count_result = await session.execute(select(func.count()).select_from(Comment).where(where))
        n = count_result.scalar() or 0
        if n:
            src_select = select(
                literal(target_file_id).label("file_id"),
                literal(target_version_no).label("valid_from"),
                null().label("valid_to"),
                *non_id_cols,
            ).where(where)
            await session.execute(insert(Comment).from_select(col_names, src_select))
        counts["comments"] = n

    return counts


async def copy_all_rows(
    session: AsyncSession,
    *,
    source_file_id: int,
    target_file_id: int,
    target_version_no: int = 1,
    source_version_no: int | None = None,
) -> dict[str, int]:
    """Set-based copy of *every* LIVE (or, with ``source_version_no``,
    every AS-OF-that-version) submission/comment row from
    ``source_file_id`` to ``target_file_id``, with no id filter --
    ``coding_service.duplicate_coding``'s "fork the whole artifact" case
    and ``data_service.duplicate_data``'s data-file restore, as opposed
    to ``copy_rows_by_id``'s selective copy of a chosen subset
    (filtering, moving rows, or sampling into a fresh coding artifact at
    Apply Codebook time). Same re-stamping semantics as
    ``copy_rows_by_id`` -- see its docstring.
    """
    counts = {"submissions": 0, "comments": 0}
    source_condition = _liveness_condition

    sub_non_id_cols = [c for c in Submission.__table__.c if c.name not in _UNCOPIED_COLUMNS]
    sub_col_names = ["file_id", "valid_from", "valid_to"] + [c.name for c in sub_non_id_cols]
    sub_where = and_(Submission.file_id == source_file_id, source_condition(Submission, version_no=source_version_no))
    sub_count = (await session.execute(select(func.count()).select_from(Submission).where(sub_where))).scalar() or 0
    if sub_count:
        src_select = select(
            literal(target_file_id).label("file_id"),
            literal(target_version_no).label("valid_from"),
            null().label("valid_to"),
            *sub_non_id_cols,
        ).where(sub_where)
        await session.execute(insert(Submission).from_select(sub_col_names, src_select))
    counts["submissions"] = sub_count

    com_non_id_cols = [c for c in Comment.__table__.c if c.name not in _UNCOPIED_COLUMNS]
    com_col_names = ["file_id", "valid_from", "valid_to"] + [c.name for c in com_non_id_cols]
    com_where = and_(Comment.file_id == source_file_id, source_condition(Comment, version_no=source_version_no))
    com_count = (await session.execute(select(func.count()).select_from(Comment).where(com_where))).scalar() or 0
    if com_count:
        src_select = select(
            literal(target_file_id).label("file_id"),
            literal(target_version_no).label("valid_from"),
            null().label("valid_to"),
            *com_non_id_cols,
        ).where(com_where)
        await session.execute(insert(Comment).from_select(com_col_names, src_select))
    counts["comments"] = com_count

    return counts
