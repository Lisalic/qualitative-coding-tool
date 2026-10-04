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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.coder_rollup import roll_up
from backend.app.core.exceptions import NotFoundError
from backend.app.core.item_types import COMMENT, SUBMISSION, qualify_item_id
from backend.app.core.sql_filters import LIKE_ESCAPE, contains_pattern
from backend.app.repositories.raw_data_repo import _liveness_condition
from backend.app.storage_models import CODER_AI, CODER_HUMAN, Comment, CodingEntry, StarredQuote, Submission

RowFilter = Literal["all", "coded", "uncoded", "ai", "human"]


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
            "coder": entry.get("coder") or CODER_HUMAN,
            "coder_model": entry.get("coder_model"),
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
                    "coder": entry.get("coder") or CODER_HUMAN,
                    "coder_model": entry.get("coder_model"),
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

    ``coder``/``coder_model`` (B1's per-quote attribution) ARE copied
    verbatim, along with every other column -- ``non_id_cols`` below is
    generic over the table's columns, so a fork preserves who coded each
    quote without this function needing to know those columns exist.
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


async def code_frequency(session: AsyncSession, file_id: int) -> list[tuple[str, str, int]]:
    """``(code_uid, code, count)`` triples for ``file_id``, most frequent
    first. Grouped by ``code_uid``, the stable identity: an entry's
    ``code`` is the name as of its own last write, so after a rename
    grouping by name would split one code's count in two (and merge two
    same-named codes from different families). ``code`` is one of those
    stored names, a fallback for callers that don't resolve the current
    name from the codebook snapshot.

    ``count`` is the number of ``coding_entries`` rows for that code --
    since a row is now one quote (not one item, see
    ``storage_models.CodingEntry``), this counts *references* (how many
    quoted excerpts carry the code), the standard meaning of "code
    frequency" in qualitative coding tools -- not distinct items. An item
    with the same code applied via two separate quotes counts twice.
    """
    result = await session.execute(
        _live(
            select(CodingEntry.code_uid, func.max(CodingEntry.code), func.count()).where(
                CodingEntry.file_id == file_id
            )
        )
        .group_by(CodingEntry.code_uid)
        .order_by(func.count().desc(), CodingEntry.code_uid)
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


async def code_summary_with_samples(
    session: AsyncSession,
    file_id: int,
    *,
    name_by_uid: dict[str, str] | None = None,
    max_evidence_per_code: int = 5,
) -> list[dict]:
    """``[{code, count, sample_evidence}]`` for ``file_id``, most frequent
    code first -- ``count`` is an exact ``GROUP BY COUNT(*)`` (via
    ``code_frequency``) and ``sample_evidence`` is a capped sample of that
    code's evidence text, one bounded query per distinct code rather than
    loading every ``coding_entries`` row for the file. Used to build a
    thematic-summary prompt input that's O(distinct codes) instead of
    O(total coded rows), for datasets too large to hand the LLM verbatim.
    ``name_by_uid`` (the current codebook snapshot) supplies each code's
    current name; see ``code_frequency`` for why entries' own names can't.
    """
    freq = await code_frequency(session, file_id)
    summaries = []
    for code_uid, stored_name, count in freq:
        result = await session.execute(
            _live(select(CodingEntry.quote).where(CodingEntry.file_id == file_id, CodingEntry.code_uid == code_uid))
            .limit(max_evidence_per_code)
        )
        sample_evidence = [row[0] for row in result.all() if row[0]]
        code = (name_by_uid or {}).get(code_uid) or stored_name
        summaries.append({"code": code, "count": count, "sample_evidence": sample_evidence})
    return summaries


# ---------------------------------------------------------------------------
# Row listing -- every submission/comment a coding artifact owns, coded or
# not, left-joined against coding_entries.
# ---------------------------------------------------------------------------


def _rows_union_subquery(file_id: int):
    """One row per LIVE submission/comment owned by ``file_id`` (see
    ``storage_models.py``'s ``Submission``/``Comment`` SCD-2 docstrings),
    in a common ``(row_type, item_id, title, body)`` shape -- ``title``
    is ``NULL`` for a comment. Kept as a reusable subquery so listing and
    counting apply the exact same filters. A coding artifact's own rows
    are copied in once at Apply Codebook time and never edited/deleted
    afterward in practice, so this filter is defensive consistency with
    ``raw_data_repo.py`` rather than something that currently changes
    any real result.
    """
    submissions_select = select(
        literal(SUBMISSION).label("row_type"),
        Submission.id.label("item_id"),
        Submission.title.label("title"),
        Submission.selftext.label("body"),
    ).where(Submission.file_id == file_id, Submission.valid_to.is_(None))
    comments_select = select(
        literal(COMMENT).label("row_type"),
        Comment.id.label("item_id"),
        null().label("title"),
        Comment.body.label("body"),
    ).where(Comment.file_id == file_id, Comment.valid_to.is_(None))
    return union_all(submissions_select, comments_select).subquery("coding_rows")


def _entry_version_condition(file_id: int, version_no: int | None):
    conditions = [CodingEntry.file_id == file_id]
    if version_no is None:
        conditions.append(CodingEntry.valid_to.is_(None))
    else:
        conditions.extend(
            [
                CodingEntry.valid_from <= version_no,
                or_(CodingEntry.valid_to.is_(None), CodingEntry.valid_to >= version_no),
            ]
        )
    return and_(*conditions)


def _apply_row_filters(
    query,
    rows,
    file_id: int,
    *,
    only: RowFilter,
    code: str | None,
    q: str | None,
    version_no: int | None = None,
):
    entry_scope = _entry_version_condition(file_id, version_no)
    has_coding = exists().where(
        and_(
            entry_scope,
            CodingEntry.row_type == rows.c.row_type,
            CodingEntry.post_id == rows.c.item_id,
        )
    )
    has_ai_coding = exists().where(
        and_(
            entry_scope,
            CodingEntry.row_type == rows.c.row_type,
            CodingEntry.post_id == rows.c.item_id,
            CodingEntry.coder == CODER_AI,
        )
    )
    if only == "coded":
        query = query.where(has_coding)
    elif only == "uncoded":
        query = query.where(~has_coding)
    elif only == "ai":
        query = query.where(has_ai_coding)
    elif only == "human":
        query = query.where(has_coding, ~has_ai_coding)

    if code:
        query = query.where(
            exists().where(
                and_(
                    entry_scope,
                    CodingEntry.row_type == rows.c.row_type,
                    CodingEntry.post_id == rows.c.item_id,
                    CodingEntry.code_uid == code,
                )
            )
        )

    if q:
        pattern = contains_pattern(q)
        query = query.where(
            or_(rows.c.title.ilike(pattern, escape=LIKE_ESCAPE), rows.c.body.ilike(pattern, escape=LIKE_ESCAPE))
        )

    return query


async def count_rows(
    session: AsyncSession,
    file_id: int,
    *,
    only: RowFilter = "all",
    code: str | None = None,
    q: str | None = None,
    version_no: int | None = None,
) -> int:
    """Count of a coding artifact's own submissions+comments matching the
    same ``only``/``code``/``q`` filters ``list_rows_with_codes`` applies
    -- used to compute total pages for View Coding's row list.
    """
    rows = _rows_union_subquery(file_id)
    query = _apply_row_filters(
        select(func.count()).select_from(rows), rows, file_id,
        only=only, code=code, q=q, version_no=version_no,
    )
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
    version_no: int | None = None,
) -> list[dict]:
    """One page of a coding artifact's own submissions+comments -- every
    row it owns, coded or not -- each with its list of ``{code, quote,
    start_offset, end_offset, notes, coder, coder_model}`` entries (empty
    for an uncoded row, one entry per quote for a code supported by more
    than one), plus a row-level ``coder`` rollup (``core/coder_rollup.py``
    -- ``"ai"``/``"human"``/``"both"``/``None`` for uncoded) so the
    document list can badge a row without re-deriving it client-side.

    ``only`` narrows to ``"coded"``/``"uncoded"`` rows, ``"ai"`` (at least
    one AI-coded entry -- the review queue) or ``"human"`` (coded, with no
    AI entry); ``code`` narrows to rows carrying that exact code; ``q`` is
    a case-insensitive substring match against title/body. Ordered by ``(row_type, item_id)`` for a
    stable, deterministic page boundary. ``version_no`` applies the SCD-2
    validity range to both filtering and returned code evidence.
    """
    rows = _rows_union_subquery(file_id)
    query = _apply_row_filters(
        select(rows.c.row_type, rows.c.item_id, rows.c.title, rows.c.body),
        rows,
        file_id,
        only=only,
        code=code,
        q=q,
        version_no=version_no,
    ).order_by(rows.c.row_type, rows.c.item_id).limit(limit).offset(offset)

    page_rows = (await session.execute(query)).all()
    if not page_rows:
        return []

    keys = [(r.row_type, r.item_id) for r in page_rows]
    entries_condition = or_(*[and_(CodingEntry.row_type == rt, CodingEntry.post_id == pid) for rt, pid in keys])
    entries = (
        await session.execute(
            select(CodingEntry).where(
                _entry_version_condition(file_id, version_no), entries_condition
            )
        )
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
                "coder": entry.coder,
                "coder_model": entry.coder_model,
            }
        )

    result = []
    for r in page_rows:
        row_codes = codes_by_key.get((r.row_type, r.item_id), [])
        result.append(
            {
                "row_type": r.row_type,
                "post_id": r.item_id,
                "item_id": qualify_item_id(r.row_type, r.item_id),
                "title": r.title,
                "content": r.body,
                "codes": row_codes,
                "coder": roll_up(entry["coder"] for entry in row_codes),
            }
        )
    return result


async def render_coding_text(session: AsyncSession, file_id: int, *, version_no: int | None = None) -> str:
    """Canonical ``POST_ID:``/``CODE:``/``CODER:``/``NOTES:``/
    ``EVIDENCE:`` text for the read-only Text View, generated from
    ``coding_entries`` rows -- the sole source of truth for a coding
    artifact's classification, so there is no separate stored blob to
    drift from this rendering. Safe to extend with ``CODER:`` because
    this text is read-only and never parsed back into rows (unlike the
    codebook markdown DSL) -- see ``frontend/src/lib/codingViewHelpers.js``.

    One ``coding_entries`` row is one quote, so a code supported by
    several quotes for the same item renders as several
    ``CODE:``/``EVIDENCE:`` blocks in a row -- simplest lossless rendering,
    and consistent with how ``list_rows_with_codes`` already returns one
    entry per quote rather than merging them.

    ``version_no``, when given, renders the text AS OF that version
    (the SCD-2 range invariant ``valid_from <= version_no <=
    coalesce(valid_to, infinity)``, same condition ``entries_as_of``
    uses) instead of the current LIVE set.
    """
    condition = (
        and_(
            CodingEntry.valid_from <= version_no,
            or_(CodingEntry.valid_to.is_(None), CodingEntry.valid_to >= version_no),
        )
        if version_no is not None
        else CodingEntry.valid_to.is_(None)
    )
    result = await session.execute(
        select(CodingEntry)
        .where(CodingEntry.file_id == file_id, condition)
        # `.id` is the final tiebreak: several quotes for the same code on
        # the same item share every other column here, and without it
        # their relative order (and so the rendered text's bytes) is
        # undefined rather than merely alphabetical.
        .order_by(CodingEntry.row_type, CodingEntry.post_id, CodingEntry.code, CodingEntry.id)
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
            coder_line = entry.coder_model and f"{entry.coder} ({entry.coder_model})" or entry.coder
            out_lines.append(f"CODER: {coder_line}")
            if entry.notes:
                out_lines.append(f"NOTES: {entry.notes}")
            out_lines.append(f"EVIDENCE: {entry.quote}")
        out_lines.append("")

    return "\n".join(out_lines).strip()


# ---------------------------------------------------------------------------
# Quote Bank & Shortlist repository methods (QC-008)
# ---------------------------------------------------------------------------


def _source_context_subquery(file_id: int, version_no: int | None):
    """Source rows (submission or comment) with title, content (selftext/body),
    author, subreddit, created_utc for quote bank inspection -- live, or
    live as of ``version_no`` so a historical read keeps a quote whose
    source row was later removed.
    """
    submissions_select = select(
        literal(SUBMISSION).label("row_type"),
        Submission.id.label("item_id"),
        Submission.title.label("title"),
        Submission.selftext.label("selftext"),
        Submission.author.label("author"),
        Submission.subreddit.label("subreddit"),
        Submission.created_utc.label("created_utc"),
    ).where(Submission.file_id == file_id, _liveness_condition(Submission, version_no=version_no))

    comments_select = select(
        literal(COMMENT).label("row_type"),
        Comment.id.label("item_id"),
        null().label("title"),
        Comment.body.label("selftext"),
        Comment.author.label("author"),
        Comment.subreddit.label("subreddit"),
        Comment.created_utc.label("created_utc"),
    ).where(Comment.file_id == file_id, _liveness_condition(Comment, version_no=version_no))

    return union_all(submissions_select, comments_select).subquery("source_context")


def _star_matches_entry(user_id: int):
    """Join condition from ``CodingEntry`` to this user's ``StarredQuote``
    on the quote's stable identity (see the ``StarredQuote`` docstring).
    """
    return and_(
        StarredQuote.user_id == user_id,
        StarredQuote.file_id == CodingEntry.file_id,
        StarredQuote.row_type == CodingEntry.row_type,
        StarredQuote.post_id == CodingEntry.post_id,
        StarredQuote.code_uid == CodingEntry.code_uid,
        StarredQuote.start_offset == CodingEntry.start_offset,
        StarredQuote.end_offset == CodingEntry.end_offset,
    )


async def list_quote_bank(
    session: AsyncSession,
    file_id: int,
    user_id: int,
    *,
    code: str | None = None,
    coder: str | None = None,
    q: str | None = None,
    starred_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    version_no: int | None = None,
) -> tuple[list[dict], int]:
    """Paginated list of quotes for the Quote Bank view with metadata,
    source context, and user-scoped starring status.

    Filters:
    - ``code``: narrows to code display name or code_uid
    - ``coder``: narrows to 'human' or 'ai' (or all)
    - ``q``: substring search across quote text, notes, or source document text/title
    - ``starred_only``: returns only quotes shortlisted/starred by this user
    - ``version_no``: pins SCD-2 validity to the requested version
    """
    source_rows = _source_context_subquery(file_id, version_no)
    entry_cond = _entry_version_condition(file_id, version_no)

    stmt = (
        select(
            CodingEntry,
            source_rows.c.title,
            source_rows.c.selftext.label("content"),
            source_rows.c.author,
            source_rows.c.subreddit,
            source_rows.c.created_utc,
            StarredQuote.id.label("starred_id"),
        )
        .select_from(CodingEntry)
        .join(
            source_rows,
            and_(
                CodingEntry.row_type == source_rows.c.row_type,
                CodingEntry.post_id == source_rows.c.item_id,
            ),
        )
        .outerjoin(StarredQuote, _star_matches_entry(user_id))
        .where(entry_cond)
    )

    if starred_only:
        stmt = stmt.where(StarredQuote.id.is_not(None))

    if code:
        stmt = stmt.where(or_(CodingEntry.code == code, CodingEntry.code_uid == code))

    if coder and coder in ("human", "ai"):
        stmt = stmt.where(CodingEntry.coder == coder)

    if q:
        pattern = contains_pattern(q)
        stmt = stmt.where(
            or_(
                CodingEntry.quote.ilike(pattern, escape=LIKE_ESCAPE),
                CodingEntry.notes.ilike(pattern, escape=LIKE_ESCAPE),
                source_rows.c.selftext.ilike(pattern, escape=LIKE_ESCAPE),
                source_rows.c.title.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total_count = (await session.execute(count_stmt)).scalar() or 0

    paginated_stmt = stmt.order_by(
        CodingEntry.row_type,
        CodingEntry.post_id,
        CodingEntry.start_offset,
        CodingEntry.id,
    ).limit(limit).offset(offset)

    rows = (await session.execute(paginated_stmt)).all()
    items = []
    for r in rows:
        entry = r[0]
        items.append(
            {
                "id": entry.id,
                "file_id": entry.file_id,
                "row_type": entry.row_type,
                "post_id": entry.post_id,
                "item_id": qualify_item_id(entry.row_type, entry.post_id),
                "code": entry.code,
                "code_uid": entry.code_uid,
                "quote": entry.quote,
                "start_offset": entry.start_offset,
                "end_offset": entry.end_offset,
                "notes": entry.notes,
                "coder": entry.coder,
                "coder_model": entry.coder_model,
                "starred": r.starred_id is not None,
                "title": r.title,
                "content": r.content,
                "author": r.author,
                "subreddit": r.subreddit,
                "created_utc": r.created_utc,
            }
        )

    return items, total_count


async def get_entry_for_file(session: AsyncSession, file_id: int, entry_id: int) -> CodingEntry:
    """``entry_id`` if it belongs to ``file_id``, else ``NotFoundError``."""
    entry = await session.get(CodingEntry, entry_id)
    if not entry or entry.file_id != file_id:
        raise NotFoundError(f"Coding entry {entry_id} not found for file {file_id}")
    return entry


async def set_quote_star(
    session: AsyncSession,
    user_id: int,
    file_id: int,
    entry_id: int,
    starred: bool,
) -> bool:
    """Star or unstar the quote ``entry_id`` for ``user_id``. Idempotent
    either way, including under a concurrent duplicate star (the unique
    constraint wins; the losing insert is rolled back to its savepoint).
    """
    entry = await get_entry_for_file(session, file_id, entry_id)
    identity = {
        "user_id": user_id,
        "file_id": file_id,
        "row_type": entry.row_type,
        "post_id": entry.post_id,
        "code_uid": entry.code_uid,
        "start_offset": entry.start_offset,
        "end_offset": entry.end_offset,
    }

    if not starred:
        await session.execute(
            delete(StarredQuote).where(*[getattr(StarredQuote, k) == v for k, v in identity.items()])
        )
        return False

    existing = await session.execute(
        select(StarredQuote.id).where(*[getattr(StarredQuote, k) == v for k, v in identity.items()])
    )
    if existing.scalar_one_or_none() is None:
        try:
            async with session.begin_nested():
                session.add(StarredQuote(**identity))
        except IntegrityError:
            pass
    return True


async def live_entries_for_item(
    session: AsyncSession, file_id: int, row_type: str, post_id: str
) -> list[CodingEntry]:
    """Every live entry on one item, in stable order."""
    result = await session.execute(
        select(CodingEntry)
        .where(
            CodingEntry.file_id == file_id,
            CodingEntry.row_type == row_type,
            CodingEntry.post_id == post_id,
            CodingEntry.valid_to.is_(None),
        )
        .order_by(CodingEntry.start_offset, CodingEntry.id)
    )
    return list(result.scalars().all())
