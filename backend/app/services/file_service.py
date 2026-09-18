"""Service layer for raw-data file lifecycle (upload / merge / delete /
row edit / row move) -- backs backend/app/api/file_routes.py.

Moves the five handlers off per-upload dynamic Postgres schemas
(``CREATE SCHEMA "proj_<hex>"`` holding ``submissions``/``comments``) onto
the fixed, indexed ``submissions``/``comments`` tables in
``backend/app/storage_models.py``, keyed by ``file_id``, via
``repositories/raw_data_repo.py``.

Streaming-import decision (see ``upload_zst`` docstring): keeps
``backend.scripts.import_db.stream_zst_to_postgres`` unchanged (still
writes into a throwaway dynamic schema), then copies that schema's rows
into the fixed tables and drops the now-redundant dynamic schema -- see
the docstring for the reasoning (this was "option (b)" in the plan).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import tempfile

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ForbiddenError, ValidationAppError
from backend.app.database import File, FileTable, async_link_file_to_project
from backend.app.repositories import file_repo, memo_repo, project_repo, raw_data_repo, version_repo
from backend.app.services import version_service
from backend.app.services.version_service import EdgeSpec
from backend.app.storage_models import Comment, CodingEntry, Submission
from backend.app.versioning_models import (
    ArtifactVersion,
    CodebookCode,
    ORIGIN_EDITED,
    ORIGIN_IMPORTED,
    RELATION_MERGED_FROM,
    ROLE_MERGE_INPUT,
)
from backend.scripts.import_db import stream_zst_to_postgres

# Columns read from the old dynamic per-upload schema (mirrors
# `backend/scripts/migrate_to_fixed_tables.py`'s `_fetch_submissions`/
# `_fetch_comments` -- everything except the generated `word_count`
# column, which `raw_data_repo.bulk_insert_*` computes itself).
_SUBMISSION_SOURCE_COLUMNS = (
    "id", "subreddit", "title", "selftext", "author", "created_utc", "score", "num_comments",
)
_COMMENT_SOURCE_COLUMNS = (
    "id", "subreddit", "body", "author", "created_utc", "score", "link_id", "parent_id",
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _dynamic_table_exists(session: AsyncSession, schemaname: str, table: str) -> bool:
    result = await session.execute(
        text("SELECT to_regclass(:tbl)"), {"tbl": f'"{schemaname}"."{table}"'}
    )
    return result.scalar() is not None


async def _fetch_dynamic_rows(
    session: AsyncSession, schemaname: str, table: str, columns: tuple[str, ...]
) -> list[dict]:
    """Read every row of ``table`` out of the old dynamic schema
    ``schemaname`` (raw SQL -- reading FROM the old per-artifact schemas
    is still expected/fine, only writing into new ones is retired). Empty
    list if the table doesn't exist in that schema.
    """
    if not await _dynamic_table_exists(session, schemaname, table):
        return []
    cols_sql = ", ".join(columns)
    result = await session.execute(text(f'SELECT {cols_sql} FROM "{schemaname}"."{table}"'))
    return [dict(row) for row in result.mappings().all()]


async def _get_owned_file_by_schemaname(session: AsyncSession, schemaname: str, user_id: int) -> File:
    """Exact-match lookup by ``schemaname`` only (no filename/id fallback),
    matching the old ``delete_row``/``move_rows`` handlers' own query.
    Raises ``ForbiddenError`` (not ``NotFoundError``) on a miss, matching
    those handlers' existing 403 (not 404) response for "not found or not
    owned" -- kept distinct from ``file_repo.get_owned_file`` (used by
    ``delete_database``, which returns 404 for the same situation) so
    behavior doesn't shift under either caller.
    """
    result = await session.execute(
        select(File).where(File.schemaname == schemaname, File.user_id == user_id)
    )
    file_rec = result.scalar_one_or_none()
    if file_rec is None:
        raise ForbiddenError("File not found or not owned by user")
    return file_rec


async def _drop_dynamic_schema(session: AsyncSession, schemaname: str) -> None:
    """Drop a throwaway per-upload dynamic schema after its rows have
    been copied into the fixed tables. Split out as its own function (as
    opposed to inlining the ``text(...)`` call) purely so unit tests can
    monkeypatch it -- it's Postgres-only DDL, unrunnable against the
    in-memory SQLite engine the non-integration test suite uses.
    """
    await session.execute(text(f'DROP SCHEMA IF EXISTS "{schemaname}" CASCADE'))


async def _upsert_file_table_count(session: AsyncSession, file_id: int, table: str, row_count: int) -> None:
    result = await session.execute(
        select(FileTable).where(FileTable.file_id == file_id, FileTable.tablename == table)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        row.row_count = row_count
    else:
        session.add(FileTable(file_id=file_id, tablename=table, row_count=row_count))


# ---------------------------------------------------------------------------
# upload_zst
# ---------------------------------------------------------------------------


async def upload_zst(
    session: AsyncSession,
    user_id: int,
    *,
    file_content: bytes,
    filename: str,
    data_type: str,
    subreddits: list[str] | None,
    name: str | None,
    description: str | None,
    project_id: int | None,
) -> tuple[File, dict]:
    """Stream a ``.zst`` file's rows into the fixed ``submissions``/
    ``comments`` tables for a new ``File`` row.

    ``data_type`` here is the already-mapped internal value
    (``"submissions"`` or ``"comments"``) -- the posts/comments ->
    submissions/comments mapping and the ``.zst``/JSON/data_type format
    checks stay in the route (pure request validation, no DB/IO).

    Streaming-import decision: **option (b)** from the plan --
    ``stream_zst_to_postgres`` is left untouched, still writing into a
    throwaway ``CREATE SCHEMA IF NOT EXISTS "proj_<hex>"`` (it has its own
    batching/memory-management already tuned for large files; rewriting
    it to write the fixed tables directly, inside a background thread,
    would mean either handing it an ``AsyncSession`` across a thread
    boundary -- not safe -- or a second, parallel sync-write path into the
    fixed tables, doubling the surface area for a script this plan
    otherwise doesn't need to touch). After streaming completes, this
    function reads that throwaway schema's rows back out (still-cheap raw
    SQL, same technique ``migrate_to_fixed_tables.py`` uses to read FROM
    old dynamic schemas) and bulk-copies them into the fixed tables for
    this upload's ``file_id`` via ``raw_data_repo.bulk_insert_*``. The
    throwaway schema is then dropped -- once copied, nothing else ever
    reads it, so leaving it around would just be schema-sprawl for a
    schema that was never anything but a landing pad.
    """
    base_name = name if name is not None else filename.replace(".zst", "")
    schema_name = f"proj_{secrets.token_hex(6)}"

    file_rec = File(
        user_id=user_id,
        filename=base_name,
        schemaname=schema_name,
        file_type="raw_data",
        description=(description or None),
    )
    session.add(file_rec)
    await session.flush()

    # raw_data's actual content is the submissions/comments rows
    # streamed in below (a range table, not a blob) -- this v1 exists so
    # downstream derivation edges (filtered_data, codebook, coding) have
    # a parent_version_id to pin, and so later deletes/moves have a v1
    # to be versioned against.
    await version_service.commit_data_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin=ORIGIN_IMPORTED,
    )

    if project_id is not None:
        project = await project_repo.get_owned_project(session, project_id, user_id)
        await async_link_file_to_project(session, file_rec.id, project.id)
        await session.flush()

    await session.commit()

    tmp_path: str | None = None
    inserted_counts = {"submissions": 0, "comments": 0}
    try:
        with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        inserted_counts = await asyncio.to_thread(
            stream_zst_to_postgres, tmp_path, schema_name, data_type, subreddits, 1000,
        )

        if inserted_counts.get("submissions", 0) > 0:
            rows = await _fetch_dynamic_rows(session, schema_name, "submissions", _SUBMISSION_SOURCE_COLUMNS)
            copied = await raw_data_repo.bulk_insert_submissions(session, file_rec.id, rows)
            await _upsert_file_table_count(session, file_rec.id, "submissions", copied)

        if inserted_counts.get("comments", 0) > 0:
            rows = await _fetch_dynamic_rows(session, schema_name, "comments", _COMMENT_SOURCE_COLUMNS)
            copied = await raw_data_repo.bulk_insert_comments(session, file_rec.id, rows)
            await _upsert_file_table_count(session, file_rec.id, "comments", copied)

        # Drop the now-redundant throwaway schema (see docstring).
        await _drop_dynamic_schema(session, schema_name)
        await session.commit()
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    response = {
        "display_name": base_name,
        "description": (description or None),
        "schema_name": schema_name,
        "inserted_counts": inserted_counts,
    }
    return file_rec, response


# ---------------------------------------------------------------------------
# merge_databases
# ---------------------------------------------------------------------------


async def _fetch_fixed_rows(
    session: AsyncSession, file_id: int, table: str, columns: tuple[str, ...]
) -> list[dict]:
    """Read the source columns of ``table`` (``submissions``/``comments``)
    out of the fixed tables for ``file_id``, mirroring
    ``_fetch_dynamic_rows``'s column set/shape so ``_merge_table_into_target``
    doesn't need to know which storage a row came from.
    """
    model = Submission if table == "submissions" else Comment
    cols = [getattr(model, c) for c in columns]
    result = await session.execute(select(*cols).where(model.file_id == file_id))
    return [dict(zip(columns, row)) for row in result.all()]


async def _read_source_tables(session: AsyncSession, source_file_id: int) -> dict[str, list[dict]]:
    """Read the ``submissions``/``comments`` rows for one already
    ownership-checked source ``File.id`` out of the fixed tables.

    Reads from the fixed ``submissions``/``comments`` tables (keyed by
    ``file_id``) rather than the old dynamic ``proj_*`` Postgres schema:
    every raw-data file has already been copied into the fixed tables by
    the storage migration, so the dynamic schema is a stale duplicate,
    not the source of truth -- see known-issues.md #5.
    """
    return {
        "submissions": await _fetch_fixed_rows(session, source_file_id, "submissions", _SUBMISSION_SOURCE_COLUMNS),
        "comments": await _fetch_fixed_rows(session, source_file_id, "comments", _COMMENT_SOURCE_COLUMNS),
    }


async def _merge_table_into_target(
    session: AsyncSession,
    *,
    target_file_id: int,
    rows: list[dict],
    seen_ids: set[str],
    table: str,
) -> int:
    """De-duplicate ``rows`` against ids already copied into
    ``target_file_id`` **during this merge run** (tracked in ``seen_ids``,
    mutated in place) and bulk-insert the rest.

    Unlike the old per-schema ``INSERT ... SELECT ... EXCEPT SELECT``
    temp-table dance (needed because the old target table could already
    hold rows from a *previous* merge/upload sharing that same dynamic
    schema), this doesn't need to query the database at all: a brand-new
    ``file_id``'s row-space starts empty, so the only possible collision
    is between two *source* schemas being merged together in the same
    call, which a plain in-memory id set already catches -- one dedup
    pass across sources instead of one SQL round-trip per source.
    """
    new_rows = [row for row in rows if row["id"] not in seen_ids]
    for row in new_rows:
        seen_ids.add(row["id"])
    if not new_rows:
        return 0
    if table == "submissions":
        return await raw_data_repo.bulk_insert_submissions(session, target_file_id, new_rows)
    return await raw_data_repo.bulk_insert_comments(session, target_file_id, new_rows)


async def _finalize_merge(
    session: AsyncSession,
    *,
    file_rec: File,
    user_id: int,
    source_schemas: list,
    total_counts: dict[str, int],
    project_id: int | None,
) -> None:
    """Link ``artifact_edges`` (``relation="merged_from"``,
    ``role="merge_input"``) for every source schema that resolves to a
    file owned by ``user_id`` (matches the old handler: looked up by
    schemaname across the *entire* original ``source_schemas`` list, not
    just the ones that contributed rows, and silently skipped when not
    found/not owned -- no error raised), write ``FileTable`` row-count
    metadata, and link the target project if given.

    ``position`` is assigned from the FILTERED sequence (only schemas
    that actually resolved), not from ``source_schemas``'s raw index --
    a skipped entry must not leave a gap in the ordering.
    """
    parents: list[EdgeSpec] = []
    for schema in source_schemas:
        if not isinstance(schema, str):
            continue
        result = await session.execute(
            select(File).where(File.schemaname == schema, File.user_id == user_id)
        )
        parent_file = result.scalar_one_or_none()
        if parent_file is not None:
            parents.append(
                EdgeSpec(
                    parent_file_id=parent_file.id, relation=RELATION_MERGED_FROM,
                    role=ROLE_MERGE_INPUT, position=len(parents),
                )
            )
    if parents:
        await version_service.link_parents(session, file_rec.id, parents)

    if total_counts["submissions"] > 0:
        session.add(FileTable(file_id=file_rec.id, tablename="submissions", row_count=total_counts["submissions"]))
    if total_counts["comments"] > 0:
        session.add(FileTable(file_id=file_rec.id, tablename="comments", row_count=total_counts["comments"]))

    if project_id is not None:
        project = await project_repo.get_owned_project(session, project_id, user_id)
        await async_link_file_to_project(session, file_rec.id, project.id)


async def merge_databases(
    session: AsyncSession,
    user_id: int,
    *,
    source_schemas: list,
    name: str,
    description: str | None,
    project_id: int | None,
) -> tuple[File | None, dict]:
    """Merge N raw-data files' ``submissions``/``comments`` rows into one
    brand-new fixed-table ``file_id``.

    Each ``source_schemas`` entry is resolved to a ``raw_data`` file
    *owned by* ``user_id`` via ``file_repo.get_owned_file`` before it's
    read -- fixes a pre-existing gap (see known-issues.md #5) where rows
    were read from any ``proj_*``-prefixed schema regardless of ownership,
    with only the resulting ``FileDependency`` link ownership-scoped. A
    source naming a file the caller doesn't own (or that doesn't exist)
    now raises ``NotFoundError`` instead of silently contributing no rows.

    Returns ``(None, response_dict)`` -- not a ``File`` -- for the
    "nothing to migrate" case, matching the old handler's own empty-merge
    response, which never created a ``File`` row at all.
    """
    if not name or not name.strip():
        raise ValidationAppError("Database name is required")

    # `.first()`, not `scalar_one_or_none()`: `filename` isn't unique, so
    # a user who already has two files sharing `name` would have hit
    # `MultipleResultsFound` (an unhandled 500) instead of this check's
    # own 400 -- the name-collision guard must not itself break on a
    # name collision.
    existing = await session.execute(
        select(File.id).where(
            File.user_id == user_id,
            or_(File.filename == name, File.schemaname == name),
        ).limit(1)
    )
    if existing.scalars().first() is not None:
        raise ValidationAppError(f"A file with name '{name}' already exists")

    schema_name = f"proj_{secrets.token_hex(6)}"

    file_rec = File(
        user_id=user_id,
        filename=name,
        schemaname=schema_name,
        file_type="raw_data",
        description=(description or None),
    )
    session.add(file_rec)
    await session.flush()

    await version_service.commit_data_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin=ORIGIN_IMPORTED,
    )

    seen_submission_ids: set[str] = set()
    seen_comment_ids: set[str] = set()
    total_counts = {"submissions": 0, "comments": 0}

    for db_name in source_schemas:
        if not isinstance(db_name, str) or not db_name.startswith("proj_"):
            continue
        source_file = await file_repo.get_owned_file(session, db_name, user_id, file_types=("raw_data",))
        source_tables = await _read_source_tables(session, source_file.id)
        total_counts["submissions"] += await _merge_table_into_target(
            session,
            target_file_id=file_rec.id,
            rows=source_tables["submissions"],
            seen_ids=seen_submission_ids,
            table="submissions",
        )
        total_counts["comments"] += await _merge_table_into_target(
            session,
            target_file_id=file_rec.id,
            rows=source_tables["comments"],
            seen_ids=seen_comment_ids,
            table="comments",
        )

    total_rows = total_counts["submissions"] + total_counts["comments"]

    if total_rows == 0:
        await session.rollback()
        return None, {
            "message": "No rows found in selected databases; nothing migrated",
            "database": name,
            "total_submissions": 0,
            "total_comments": 0,
            "file_migrated": False,
        }

    await _finalize_merge(
        session,
        file_rec=file_rec,
        user_id=user_id,
        source_schemas=source_schemas,
        total_counts=total_counts,
        project_id=project_id,
    )

    await session.commit()
    await session.refresh(file_rec)

    return file_rec, {
        "message": f"Merged into file schema '{schema_name}'",
        "file": {
            "id": str(file_rec.id),
            "schema_name": schema_name,
            "display_name": name,
            "description": (description or None),
        },
        "file_migrated": True,
    }


# ---------------------------------------------------------------------------
# delete_database
# ---------------------------------------------------------------------------


async def delete_database(session: AsyncSession, user_id: int, file_ref: str) -> str:
    """Delete a ``File`` row and everything that references its
    ``file_id``: ``artifact_edges`` (as either parent or child),
    ``artifact_versions``/``codebook_codes``, ``FileTable`` metadata, and
    its rows in every fixed content table (``submissions``/``comments``/
    ``coding_entries``/``row_memos`` -- a given file only ever has rows
    in the subset matching its ``file_type``, so deleting from all of
    them is simplest and harmless).

    Ordering matters for the new tables in a way it didn't for the old
    single ``FileDependency`` table: a FORK's v1 ``ArtifactVersion`` can
    point cross-file at this file's head (``parent_version_id`` -- see
    ``versioning_models.ArtifactVersion``'s docstring for why), so any
    such pointer must be nulled out before this file's own versions are
    deleted, or the FK raises. Edges must go before versions (edges FK
    into versions), and codes must go before versions too (codes FK into
    versions).

    **What survives.** Artifacts derived from this one are not touched
    and stay fully readable: every derived type owns a complete copy of
    what it needs (a ``coding`` file carries its own codebook snapshot,
    its own submissions/comments and its own ``coding_entries``; a
    summary/comparison carries its own markdown blob), so deleting a
    codebook cannot compromise a coding produced from it. What they lose
    is the recorded *lineage* -- the ``artifact_edges`` rows naming this
    file as their parent go with it, because ``parent_file_id`` is a
    NOT NULL foreign key with nothing sensible to point at afterwards.
    ``ProjectFilesSection.jsx`` names the affected artifacts in the
    delete confirmation so that is a decision rather than a surprise.

    Per the plan, this **replaces** the old ``DROP SCHEMA ... CASCADE`` --
    it no longer touches the old dynamic Postgres schema at all (left in
    place, as design decision #3 intends, until the final cleanup stage).
    Returns the deleted file's ``filename`` so the route can build its
    confirmation message.
    """
    file_rec = await file_repo.get_owned_file(session, file_ref, user_id)
    file_id = file_rec.id
    filename = file_rec.filename

    await version_repo.delete_edges_for_file(session, file_id)
    version_ids_subq = select(ArtifactVersion.id).where(ArtifactVersion.file_id == file_id)
    await session.execute(delete(CodebookCode).where(CodebookCode.version_id.in_(version_ids_subq)))
    await version_repo.null_parent_version_pointers_into_file(session, file_id)
    await version_repo.delete_versions_for_file(session, file_id)

    await session.execute(delete(FileTable).where(FileTable.file_id == file_id))
    await session.execute(delete(Submission).where(Submission.file_id == file_id))
    await session.execute(delete(Comment).where(Comment.file_id == file_id))
    await session.execute(delete(CodingEntry).where(CodingEntry.file_id == file_id))
    await memo_repo.delete_memos_for_file(session, file_id)
    await session.delete(file_rec)
    await session.commit()

    return filename


# ---------------------------------------------------------------------------
# delete_rows
# ---------------------------------------------------------------------------


async def delete_rows(session: AsyncSession, user_id: int, *, schemaname: str, table: str, row_ids: list[str]) -> int:
    """Close (SCD-2 ``valid_to``, never a hard ``DELETE``) the given
    rows in ``submissions``/``comments`` for one owned file, minting a
    single ``artifact_versions`` row for the whole batch via
    ``version_service.commit_data_version`` -- deleting 12 rows in one
    call is one version, not twelve (mirrors
    ``coding_repo.replace_entries_for_items``'s "one save, one version"
    policy for ``coding_entries``).

    Replaces the old single-row ``delete_row`` (hard ``DELETE FROM
    "<schema>"."<table>" WHERE id = :id`` raw SQL, no version, no
    trail) -- per CLAUDE.md's early-prototyping/no-legacy-compatibility
    rule, this is a straight replacement, not an addition. Returns the
    number of rows actually closed (0 if none matched, in which case no
    version is minted at all -- ``commit_data_version`` has no no-op
    suppression of its own, so this checks BEFORE minting one rather
    than minting-then-rolling-back: a session-wide rollback would also
    discard anything else the caller had already staged on the same
    session, which ``version_service``'s own module docstring flags as
    exactly the hazard to avoid).
    """
    schema = (schemaname or "").strip()
    if schema.endswith(".db"):
        schema = schema[:-3]
    row_ids = list(row_ids or [])
    if not row_ids:
        return 0

    file_rec = await _get_owned_file_by_schemaname(session, schema, user_id)
    file_id = file_rec.id
    model = Submission if table == "submissions" else Comment
    match_condition = (model.file_id == file_id, model.id.in_(row_ids), model.valid_to.is_(None))

    matching = (
        await session.execute(select(func.count()).select_from(model).where(*match_condition))
    ).scalar() or 0
    if matching == 0:
        return 0

    version = await version_service.commit_data_version(
        session, file_id=file_id, author_user_id=user_id, origin=ORIGIN_EDITED,
        message=f"Deleted {matching} {table}",
    )
    result = await session.execute(
        update(model).where(*match_condition).values(valid_to=version.version_no - 1)
    )
    closed = int(result.rowcount or 0)
    await session.commit()

    # Best-effort FileTable row-count refresh -- non-fatal, matching the
    # old handler's own "continue even if metadata update fails" comment.
    try:
        count_result = await session.execute(
            select(func.count()).select_from(model).where(model.file_id == file_id, model.valid_to.is_(None))
        )
        await _upsert_file_table_count(session, file_id, table, int(count_result.scalar() or 0))
        await session.commit()
    except Exception:
        await session.rollback()

    return closed


# ---------------------------------------------------------------------------
# move_rows
# ---------------------------------------------------------------------------


async def move_rows(
    session: AsyncSession,
    user_id: int,
    *,
    source_schema: str,
    target_schema: str,
    table: str,
    row_ids: list,
) -> int:
    """Move (copy then close-in-source, never hard-delete) specific rows
    between two owned files' fixed tables, via
    ``raw_data_repo.copy_rows_by_id`` (set-based) instead of the old
    per-id ``SELECT``+``INSERT`` Python loop. Mints one
    ``artifact_versions`` row on EACH side (target gets the rows first,
    so the copy can stamp them with the target's own new version number;
    source then closes its copies under its own new version) -- both
    sides' history says something happened, even though neither side's
    own row *content* changed shape. A pre-check for "any source row
    actually matches" runs BEFORE either version is minted, so a
    no-match call touches no version history at all rather than minting
    then rolling back (a session-wide rollback would also discard
    anything else the caller had staged -- see ``delete_rows``'s
    docstring for the same reasoning). Returns the moved row count.
    """
    source = (source_schema or "").strip()
    target = (target_schema or "").strip()
    if source.endswith(".db"):
        source = source[:-3]
    if target.endswith(".db"):
        target = target[:-3]

    file_src = await _get_owned_file_by_schemaname(session, source, user_id)
    file_tgt = await _get_owned_file_by_schemaname(session, target, user_id)
    model = Submission if table == "submissions" else Comment

    matching = (
        await session.execute(
            select(func.count()).select_from(model).where(
                model.file_id == file_src.id, model.id.in_(row_ids), model.valid_to.is_(None)
            )
        )
    ).scalar() or 0
    if matching == 0:
        return 0

    target_version = await version_service.commit_data_version(
        session, file_id=file_tgt.id, author_user_id=user_id, origin=ORIGIN_EDITED,
        message=f"Received {matching} {table} from {file_src.filename}",
    )

    id_kwarg = {"submission_ids": row_ids} if table == "submissions" else {"comment_ids": row_ids}
    counts = await raw_data_repo.copy_rows_by_id(
        session, source_file_id=file_src.id, target_file_id=file_tgt.id,
        target_version_no=target_version.version_no, **id_kwarg,
    )
    moved = counts["submissions"] if table == "submissions" else counts["comments"]
    # Memos travel with their rows (see `repositories/memo_repo.py`). The
    # source's copies are left in place rather than deleted: the source
    # row itself is only soft-closed below, so its memo stays readable in
    # that file's history exactly as the row does.
    await memo_repo.copy_memos_by_id(
        session, source_file_id=file_src.id, target_file_id=file_tgt.id, **id_kwarg,
    )

    source_version = await version_service.commit_data_version(
        session, file_id=file_src.id, author_user_id=user_id, origin=ORIGIN_EDITED,
        message=f"Moved {moved} {table} to {file_tgt.filename}",
    )
    await session.execute(
        update(model)
        .where(model.file_id == file_src.id, model.id.in_(row_ids), model.valid_to.is_(None))
        .values(valid_to=source_version.version_no - 1)
    )

    # Best-effort FileTable row-count refresh for both sides -- non-fatal,
    # matching the old handler's own try/except-and-continue behavior.
    try:
        src_count = (
            await session.execute(
                select(func.count()).select_from(model).where(model.file_id == file_src.id, model.valid_to.is_(None))
            )
        ).scalar() or 0
        tgt_count = (
            await session.execute(
                select(func.count()).select_from(model).where(model.file_id == file_tgt.id, model.valid_to.is_(None))
            )
        ).scalar() or 0
        await _upsert_file_table_count(session, file_src.id, table, int(src_count))
        await _upsert_file_table_count(session, file_tgt.id, table, int(tgt_count))
    except Exception:
        pass

    await session.commit()
    return moved
