"""Repository for ``row_memos`` -- user-authored memos on a data row.

Deliberately narrow: one memo per ``(file_id, row_type, row_id)``, so
the write path is an upsert rather than an insert, and a blank body is
a delete rather than an empty row (see ``upsert_memo``).

The two copy functions mirror
``repositories/raw_data_repo.py``'s ``copy_rows_by_id``/``copy_all_rows``
exactly -- same set-based ``INSERT ... SELECT`` shape, same
"``id``/``file_id`` are never copied verbatim" rule -- because they are
always called immediately alongside them: a memo follows its row into
every derived artifact. Keeping the two modules structurally identical
is what makes "did this call site copy memos too?" a one-line check at
each of the five row-copy sites.

Dumb by design, like ``version_repo``: no ownership checks (that is
``services/memo_service.py``'s job, via ``file_repo.resolve_file_id``)
and no ``session.commit()`` calls.
"""

from __future__ import annotations

from sqlalchemy import and_, delete, func, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.storage_models import RowMemo

# Never copied verbatim between files: ``id`` is a surrogate identity and
# ``file_id`` is supplied by the caller. Everything else (row identity,
# body, authorship, timestamps) carries across unchanged -- the memo's
# text and its provenance are exactly what the copy is preserving.
_UNCOPIED_COLUMNS = {"id", "file_id"}


async def get_memo(
    session: AsyncSession, *, file_id: int, row_type: str, row_id: str
) -> RowMemo | None:
    """The memo on one row of one artifact, or ``None`` if it has none."""
    result = await session.execute(
        select(RowMemo).where(
            RowMemo.file_id == file_id,
            RowMemo.row_type == row_type,
            RowMemo.row_id == row_id,
        )
    )
    return result.scalar_one_or_none()


async def list_memos(session: AsyncSession, file_id: int) -> list[RowMemo]:
    """Every memo on ``file_id``, ordered by row.

    Read whole rather than paged: only rows a human actually wrote about
    have a memo at all, so this stays small even for a file with 100k
    submissions -- which is what lets the data table fetch memos once per
    database instead of one request per visible row.
    """
    result = await session.execute(
        select(RowMemo)
        .where(RowMemo.file_id == file_id)
        .order_by(RowMemo.row_type, RowMemo.row_id)
    )
    return list(result.scalars().all())


async def upsert_memo(
    session: AsyncSession,
    *,
    file_id: int,
    row_type: str,
    row_id: str,
    body: str,
    author_user_id: int | None,
) -> RowMemo | None:
    """Create, update, or (on a blank ``body``) delete the memo on one row.

    Blank means deleted rather than stored-as-empty so that "has a memo"
    stays a simple row-exists test everywhere downstream -- the table
    view's indicator, ``list_memos``, and the copy functions all get the
    right answer without a ``body != ''`` predicate. Returns the stored
    memo, or ``None`` when the blank body deleted it.
    """
    body = (body or "").strip()
    existing = await get_memo(session, file_id=file_id, row_type=row_type, row_id=row_id)

    if not body:
        if existing is not None:
            await session.delete(existing)
        return None

    if existing is not None:
        existing.body = body
        existing.author_user_id = author_user_id
        # Flush + refresh so `updated_at` holds the value the database
        # actually generated (`onupdate=func.now()` is server-side, so
        # before the UPDATE lands the in-memory attribute is still the
        # PREVIOUS edit's timestamp -- and the caller renders it as
        # "Last edited ..."). Doing it here rather than after the
        # caller's commit also keeps the read inside the async context;
        # a post-commit refresh of a server-generated column raises
        # `MissingGreenlet` under the async engine.
        await session.flush()
        await session.refresh(existing)
        return existing

    memo = RowMemo(
        file_id=file_id,
        row_type=row_type,
        row_id=row_id,
        body=body,
        author_user_id=author_user_id,
    )
    session.add(memo)
    await session.flush()
    await session.refresh(memo)
    return memo


def _copy_select(target_file_id: int, where):
    """The shared ``INSERT ... SELECT`` projection for both copy paths."""
    non_id_cols = [c for c in RowMemo.__table__.c if c.name not in _UNCOPIED_COLUMNS]
    col_names = ["file_id"] + [c.name for c in non_id_cols]
    src_select = select(literal(target_file_id).label("file_id"), *non_id_cols).where(where)
    return col_names, src_select


async def copy_memos_by_id(
    session: AsyncSession,
    *,
    source_file_id: int,
    target_file_id: int,
    submission_ids: list[str] | None = None,
    comment_ids: list[str] | None = None,
) -> int:
    """Copy the memos on specific rows from one file to another.

    The memo counterpart of ``raw_data_repo.copy_rows_by_id`` and always
    called with the same id lists, so exactly the rows that survived a
    filter/move keep their memos. Each id list is skipped entirely (no
    query run) when ``None``/empty. Returns the number of memos copied.
    """
    copied = 0
    for row_type, ids in (("submission", submission_ids), ("comment", comment_ids)):
        if not ids:
            continue
        where = and_(
            RowMemo.file_id == source_file_id,
            RowMemo.row_type == row_type,
            RowMemo.row_id.in_(ids),
        )
        n = (await session.execute(select(func.count()).select_from(RowMemo).where(where))).scalar() or 0
        if n:
            col_names, src_select = _copy_select(target_file_id, where)
            await session.execute(insert(RowMemo).from_select(col_names, src_select))
        copied += n
    return copied


async def copy_all_memos(
    session: AsyncSession, *, source_file_id: int, target_file_id: int
) -> int:
    """Copy every memo from one file to another, with no id filter.

    The memo counterpart of ``raw_data_repo.copy_all_rows`` -- the
    fork/duplicate case, where the target receives the whole artifact.
    """
    where = RowMemo.file_id == source_file_id
    n = (await session.execute(select(func.count()).select_from(RowMemo).where(where))).scalar() or 0
    if n:
        col_names, src_select = _copy_select(target_file_id, where)
        await session.execute(insert(RowMemo).from_select(col_names, src_select))
    return n


async def delete_memos_for_file(session: AsyncSession, file_id: int) -> None:
    """Drop every memo belonging to ``file_id``.

    The ``ON DELETE CASCADE`` on ``row_memos.file_id`` already covers a
    real ``DELETE FROM files``; this exists for the same reason
    ``version_repo.delete_versions_for_file`` does -- ``file_service``
    tears an artifact down explicitly rather than relying on the
    database's cascade ordering.
    """
    await session.execute(delete(RowMemo).where(RowMemo.file_id == file_id))
