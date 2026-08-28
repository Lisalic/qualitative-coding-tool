"""Repository for structured coding output (``coding_entries``) and for
reading the rows (``submissions``/``comments``) a coding artifact owns.

One ``coding_entries`` row per *quote* -- a single code applied to an item
on the strength of several distinct quotes gets several rows, each
carrying its own ``start_offset``/``end_offset`` into that item's own body
text (see ``storage_models.CodingEntry`` and
``backend/app/core/evidence_match.py``). Enables a real
``SELECT code, COUNT(*) ... GROUP BY code``, impossible without pulling
and re-parsing a blob client-side.

Since the coding-artifact overhaul, ``coding_entries`` is the *sole*
source of truth for a coding artifact's classification -- there is no
parallel ``artifact_content`` blob to keep in sync, and (since the
quotes-with-offsets change) no unverified free-text evidence column
either: every row here already passed the existence/presence checks in
``backend/app/services/coding_service.py``. A coding artifact's
``submissions``/``comments`` rows (copied in at Apply Codebook time via
``raw_data_repo.copy_rows_by_id``, keyed by the coding file's own
``file_id``) are what View Coding lists -- ``list_rows_with_codes``/
``count_rows`` page over all of them (coded or not), left-joined against
``coding_entries``.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import and_, delete, exists, func, insert, literal, null, or_, select, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.item_types import COMMENT, SUBMISSION, qualify_item_id
from backend.app.storage_models import Comment, CodingEntry, Submission

RowFilter = Literal["all", "coded", "uncoded"]


def _live(query):
    """Apply the SCD-2 liveness predicate (``valid_to IS NULL``) to a
    query already filtered to a ``CodingEntry.file_id`` -- every read in
    this module routes through this rather than repeating the predicate,
    so a version boundary correctly hides closed (superseded) rows
    without a query missing it and showing stale/duplicate history as if
    it were still current (see ``storage_models.py::CodingEntry``'s range
    invariant).
    """
    return query.where(CodingEntry.valid_to.is_(None))


async def bulk_insert_coding_entries(
    session: AsyncSession, file_id: int, entries: list[dict], *, version_no: int = 1
) -> int:
    """Insert ``entries`` (dicts with ``post_id``, ``code``, ``code_uid``,
    ``quote``, ``start_offset``, ``end_offset``, and optionally
    ``row_type``/``notes`` keys) in a single executemany-style
    ``INSERT``. Returns the count inserted.

    ``version_no`` stamps every inserted row's ``valid_from`` -- the
    version of this coding artifact these entries were written under
    (see ``storage_models.py::CodingEntry``'s SCD-2 docstring). A brand
    new coding artifact (apply-codebook, duplicate) always passes ``1``;
    a later edit passes whatever version ``version_service.commit_coding_version``
    opened for it.

    Every entry here is expected to have already passed
    ``coding_service``'s existence/presence checks (item exists, code
    exists in the codebook, quote resolves to real offsets in the item's
    own text) -- this function does no validation of its own, it only
    persists.
    """
    if not entries:
        return 0
    payload = [
        {
            "file_id": file_id,
            "row_type": entry.get("row_type") or "submission",
            "post_id": entry["post_id"],
            "code": entry["code"],
            "code_uid": entry["code_uid"],
            "quote": entry["quote"],
            "start_offset": entry["start_offset"],
            "end_offset": entry["end_offset"],
            "notes": entry.get("notes"),
            "valid_from": version_no,
            "valid_to": None,
        }
        for entry in entries
    ]
    await session.execute(insert(CodingEntry), payload)
    return len(payload)


async def replace_entries_for_items(
    session: AsyncSession, file_id: int, items: list[dict], *, version_no: int = 1
) -> None:
    """Replace the ``coding_entries`` rows for exactly the given
    ``(row_type, post_id)`` keys as of version ``version_no`` -- the
    primitive behind ``coding_service.save_coding_revision``, the single
    write path for a coding artifact's rows (accepted AI recode
    proposals and manual tags alike replace a chosen set of items' coding
    wholesale rather than diffing individual codes).

    ``items`` is ``[{"row_type", "post_id", "entries": [{"code",
    "code_uid", "quote", "start_offset", "end_offset", "notes"}]}]`` --
    one entry per quote. An item with an empty ``entries`` list still has
    its old codes cleared and correctly ends up with zero live codes
    (e.g. the AI decided no code applies, or a user cleared every code
    from a row) -- it is not left untouched.

    SCD-2, in three steps, per ``storage_models.py::CodingEntry``'s range
    invariant:

    1. DELETE rows already born in ``version_no`` itself -- these never
       existed in any sealed, historical version (this call's own
       version is still open), so removing them outright is not history
       loss; it's what makes "in-place edits within an unsealed draft"
       not pile up dead ranges (hundreds of per-highlight saves would
       otherwise leave hundreds of open-then-closed-in-the-same-version
       rows behind).
    2. UPDATE (close) rows inherited from a sealed ancestor version --
       ``valid_to = version_no - 1``, never deleted, so a query "as of"
       an earlier version still sees them.
    3. INSERT the new entries, ``valid_from = version_no, valid_to = NULL``.
    """
    if not items:
        return

    keys = [(item["row_type"], item["post_id"]) for item in items]
    key_condition = or_(*[and_(CodingEntry.row_type == rt, CodingEntry.post_id == pid) for rt, pid in keys])

    await session.execute(
        delete(CodingEntry).where(
            CodingEntry.file_id == file_id, key_condition, CodingEntry.valid_from == version_no,
        )
    )
    await session.execute(
        update(CodingEntry)
        .where(
            CodingEntry.file_id == file_id, key_condition,
            CodingEntry.valid_to.is_(None), CodingEntry.valid_from < version_no,
        )
        .values(valid_to=version_no - 1)
    )

    payload = []
    for item in items:
        for entry in item.get("entries") or []:
            payload.append(
                {
                    "file_id": file_id,
                    "row_type": item["row_type"],
                    "post_id": item["post_id"],
                    "code": entry["code"],
                    "code_uid": entry["code_uid"],
                    "quote": entry["quote"],
                    "start_offset": entry["start_offset"],
                    "end_offset": entry["end_offset"],
                    "notes": entry.get("notes"),
                    "valid_from": version_no,
                    "valid_to": None,
                }
            )
    if payload:
        await session.execute(insert(CodingEntry), payload)


async def close_entries_for_code_uid(session: AsyncSession, file_id: int, code_uid: str, *, version_no: int) -> int:
    """Close (``valid_to = version_no - 1``) every live entry carrying
    ``code_uid`` -- used when a code is removed from a coding artifact's
    own codebook snapshot (``coding_service.save_coding_revision``):
    under SCD-2 the entries referencing it can't be deleted, and every
    live entry's ``code_uid`` must keep resolving to a code that still
    exists in the current snapshot.
    """
    result = await session.execute(
        CodingEntry.__table__.update()
        .where(CodingEntry.file_id == file_id, CodingEntry.code_uid == code_uid, CodingEntry.valid_to.is_(None))
        .values(valid_to=version_no - 1)
    )
    return result.rowcount or 0


async def copy_entries(
    session: AsyncSession, *, source_file_id: int, target_file_id: int, as_of_version_no: int | None = None
) -> int:
    """Copy ``source_file_id``'s coding_entries into ``target_file_id`` --
    the ``coding_entries`` half of forking a whole coding artifact
    (``coding_service.duplicate_coding`` also copies the codebook
    snapshot via ``version_service.commit_codebook_version`` and the
    submissions/comments rows via ``raw_data_repo.copy_all_rows``).

    Default (``as_of_version_no=None``) copies every currently LIVE row
    (``valid_to IS NULL``) -- fork from head. Passing ``as_of_version_no``
    instead copies the live set AS OF that version, per the SCD-2 range
    invariant (``valid_from <= as_of_version_no <= coalesce(valid_to,
    infinity)``) -- fork from a chosen point in history, non-destructively
    (this is what a "revert" becomes: fork a new artifact from an old
    version rather than truncating the original's history).

    The fork always starts its own history at v1 (see
    ``version_service.fork_lineage``'s docstring for why: copying the
    source's whole version chain would duplicate every ``codebook_codes``
    row for every version), so ``valid_from``/``valid_to`` are NOT copied
    verbatim -- every copied row is re-stamped ``valid_from=1,
    valid_to=NULL``, not the source's original range.
    """
    non_id_cols = [
        c for c in CodingEntry.__table__.c if c.name not in ("id", "file_id", "valid_from", "valid_to")
    ]
    col_names = ["file_id", "valid_from", "valid_to"] + [c.name for c in non_id_cols]
    condition = (
        and_(
            CodingEntry.valid_from <= as_of_version_no,
            or_(CodingEntry.valid_to.is_(None), CodingEntry.valid_to >= as_of_version_no),
        )
        if as_of_version_no is not None
        else CodingEntry.valid_to.is_(None)
    )
    count_result = await session.execute(
        select(func.count()).select_from(CodingEntry).where(CodingEntry.file_id == source_file_id, condition)
    )
    n = count_result.scalar() or 0
    if n:
        src_select = select(
            literal(target_file_id).label("file_id"),
            literal(1).label("valid_from"),
            null().label("valid_to"),
            *non_id_cols,
        ).where(CodingEntry.file_id == source_file_id, condition)
        await session.execute(insert(CodingEntry).from_select(col_names, src_select))
    return n


async def get_coding_entries(
    session: AsyncSession, file_id: int, code: str | None = None
) -> list[CodingEntry]:
    """All LIVE coding entries for ``file_id``, optionally filtered to
    one ``code``.
    """
    stmt = _live(select(CodingEntry).where(CodingEntry.file_id == file_id))
    if code is not None:
        stmt = stmt.where(CodingEntry.code == code)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def entries_as_of(session: AsyncSession, file_id: int, version_no: int) -> list[CodingEntry]:
    """Every entry live AS OF ``version_no``, per the SCD-2 range
    invariant (``valid_from <= version_no <= coalesce(valid_to,
    infinity)``) -- same condition ``copy_entries`` uses to fork from a
    point in history, but reading in place rather than copying. Backs
    ``version_service.diff_coding``: comparing two calls at different
    version numbers is what lets the coding-content diff (rows recoded,
    code counts) see a version's coding as it actually was, not just its
    current live state.
    """
    condition = and_(
        CodingEntry.file_id == file_id,
        CodingEntry.valid_from <= version_no,
        or_(CodingEntry.valid_to.is_(None), CodingEntry.valid_to >= version_no),
    )
    result = await session.execute(select(CodingEntry).where(condition))
    return list(result.scalars().all())


async def code_frequency(session: AsyncSession, file_id: int) -> list[tuple[str, int]]:
    """``(code, count)`` pairs for ``file_id``, most frequent first.

    ``count`` is the number of ``coding_entries`` rows for that code --
    since a row is now one quote (not one item, see
    ``storage_models.CodingEntry``), this counts *references* (how many
    quoted excerpts carry the code), the standard meaning of "code
    frequency" in qualitative coding tools -- not distinct items. An item
    with the same code applied via two separate quotes counts twice.
    """
    result = await session.execute(
        _live(select(CodingEntry.code, func.count()).where(CodingEntry.file_id == file_id))
        .group_by(CodingEntry.code)
        .order_by(func.count().desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def code_summary_with_samples(
    session: AsyncSession, file_id: int, *, max_evidence_per_code: int = 5
) -> list[dict]:
    """``[{code, count, sample_evidence}]`` for ``file_id``, most frequent
    code first -- ``count`` is an exact ``GROUP BY COUNT(*)`` (via
    ``code_frequency``) and ``sample_evidence`` is a capped sample of that
    code's evidence text, one bounded query per distinct code rather than
    loading every ``coding_entries`` row for the file. Used to build a
    thematic-summary prompt input that's O(distinct codes) instead of
    O(total coded rows), for datasets too large to hand the LLM verbatim.
    """
    freq = await code_frequency(session, file_id)
    summaries = []
    for code, count in freq:
        result = await session.execute(
            _live(select(CodingEntry.quote).where(CodingEntry.file_id == file_id, CodingEntry.code == code))
            .limit(max_evidence_per_code)
        )
        sample_evidence = [row[0] for row in result.all() if row[0]]
        summaries.append({"code": code, "count": count, "sample_evidence": sample_evidence})
    return summaries


# ---------------------------------------------------------------------------
# Row listing -- every submission/comment a coding artifact owns, coded or
# not, left-joined against coding_entries.
# ---------------------------------------------------------------------------


def _rows_union_subquery(file_id: int):
    """One row per submission/comment owned by ``file_id``, in a common
    ``(row_type, item_id, title, body)`` shape -- ``title`` is ``NULL``
    for a comment. Kept as a reusable subquery so listing and counting
    apply the exact same filters.
    """
    submissions_select = select(
        literal(SUBMISSION).label("row_type"),
        Submission.id.label("item_id"),
        Submission.title.label("title"),
        Submission.selftext.label("body"),
    ).where(Submission.file_id == file_id)
    comments_select = select(
        literal(COMMENT).label("row_type"),
        Comment.id.label("item_id"),
        null().label("title"),
        Comment.body.label("body"),
    ).where(Comment.file_id == file_id)
    return union_all(submissions_select, comments_select).subquery("coding_rows")


def _apply_row_filters(query, rows, file_id: int, *, only: RowFilter, code: str | None, q: str | None):
    has_coding = exists().where(
        and_(
            CodingEntry.file_id == file_id,
            CodingEntry.row_type == rows.c.row_type,
            CodingEntry.post_id == rows.c.item_id,
            CodingEntry.valid_to.is_(None),
        )
    )
    if only == "coded":
        query = query.where(has_coding)
    elif only == "uncoded":
        query = query.where(~has_coding)

    if code:
        query = query.where(
            exists().where(
                and_(
                    CodingEntry.file_id == file_id,
                    CodingEntry.row_type == rows.c.row_type,
                    CodingEntry.post_id == rows.c.item_id,
                    CodingEntry.code == code,
                    CodingEntry.valid_to.is_(None),
                )
            )
        )

    if q:
        pattern = f"%{q}%"
        query = query.where(or_(rows.c.title.ilike(pattern), rows.c.body.ilike(pattern)))

    return query


async def count_rows(
    session: AsyncSession,
    file_id: int,
    *,
    only: RowFilter = "all",
    code: str | None = None,
    q: str | None = None,
) -> int:
    """Count of a coding artifact's own submissions+comments matching the
    same ``only``/``code``/``q`` filters ``list_rows_with_codes`` applies
    -- used to compute total pages for View Coding's row list.
    """
    rows = _rows_union_subquery(file_id)
    query = _apply_row_filters(select(func.count()).select_from(rows), rows, file_id, only=only, code=code, q=q)
    result = await session.execute(query)
    return result.scalar() or 0


async def list_rows_with_codes(
    session: AsyncSession,
    file_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
    only: RowFilter = "all",
    code: str | None = None,
    q: str | None = None,
) -> list[dict]:
    """One page of a coding artifact's own submissions+comments -- every
    row it owns, coded or not -- each with its list of ``{code, quote,
    start_offset, end_offset, notes}`` entries (empty for an uncoded row,
    one entry per quote for a code supported by more than one).

    ``only`` narrows to ``"coded"``/``"uncoded"`` rows; ``code`` narrows to
    rows carrying that exact code; ``q`` is a case-insensitive substring
    match against title/body. Ordered by ``(row_type, item_id)`` for a
    stable, deterministic page boundary.
    """
    rows = _rows_union_subquery(file_id)
    query = _apply_row_filters(
        select(rows.c.row_type, rows.c.item_id, rows.c.title, rows.c.body),
        rows,
        file_id,
        only=only,
        code=code,
        q=q,
    ).order_by(rows.c.row_type, rows.c.item_id).limit(limit).offset(offset)

    page_rows = (await session.execute(query)).all()
    if not page_rows:
        return []

    keys = [(r.row_type, r.item_id) for r in page_rows]
    entries_condition = or_(*[and_(CodingEntry.row_type == rt, CodingEntry.post_id == pid) for rt, pid in keys])
    entries = (
        await session.execute(_live(select(CodingEntry).where(CodingEntry.file_id == file_id, entries_condition)))
    ).scalars().all()

    codes_by_key: dict[tuple[str, str], list[dict]] = {}
    for entry in entries:
        codes_by_key.setdefault((entry.row_type, entry.post_id), []).append(
            {
                "code": entry.code,
                "code_uid": entry.code_uid,
                "quote": entry.quote,
                "start_offset": entry.start_offset,
                "end_offset": entry.end_offset,
                "notes": entry.notes,
            }
        )

    return [
        {
            "row_type": r.row_type,
            "post_id": r.item_id,
            "item_id": qualify_item_id(r.row_type, r.item_id),
            "title": r.title,
            "content": r.body,
            "codes": codes_by_key.get((r.row_type, r.item_id), []),
        }
        for r in page_rows
    ]


async def render_coding_text(session: AsyncSession, file_id: int) -> str:
    """Canonical ``POST_ID:``/``CODE:``/``NOTES:``/``EVIDENCE:`` text for
    the read-only Text View, generated from ``coding_entries`` rows --
    the sole source of truth for a coding artifact's classification, so
    there is no separate stored blob to drift from this rendering.

    One ``coding_entries`` row is one quote, so a code supported by
    several quotes for the same item renders as several
    ``CODE:``/``EVIDENCE:`` blocks in a row -- simplest lossless rendering,
    and consistent with how ``list_rows_with_codes`` already returns one
    entry per quote rather than merging them.
    """
    result = await session.execute(
        _live(select(CodingEntry).where(CodingEntry.file_id == file_id))
        .order_by(CodingEntry.row_type, CodingEntry.post_id, CodingEntry.code)
    )
    entries = result.scalars().all()
    if not entries:
        return ""

    grouped: dict[tuple[str, str], list[CodingEntry]] = {}
    order: list[tuple[str, str]] = []
    for entry in entries:
        key = (entry.row_type, entry.post_id)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(entry)

    out_lines: list[str] = []
    for row_type, post_id in order:
        out_lines.append(f"POST_ID: {qualify_item_id(row_type, post_id)}")
        for entry in grouped[(row_type, post_id)]:
            out_lines.append(f"CODE: {entry.code}")
            if entry.notes:
                out_lines.append(f"NOTES: {entry.notes}")
            out_lines.append(f"EVIDENCE: {entry.quote}")
        out_lines.append("")

    return "\n".join(out_lines).strip()
