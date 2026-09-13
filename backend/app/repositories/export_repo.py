"""Repository layer for export operations.

Encapsulates data queries for coding rows (submissions/comments), coding
entries, codebook codes, memos, and project-bundle lineage.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import File, project_files_table
from backend.app.repositories import coding_repo, memo_repo, version_repo
from backend.app.storage_models import Comment, RowMemo, Submission
from backend.app.versioning_models import CodebookCode


async def get_all_rows_for_coding(
    session: AsyncSession,
    file_id: int,
    *,
    version_no: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve all live submissions and comments owned by a coding file.

    Crucial for wide-format exports to include uncoded rows.
    Returns rows sorted deterministically by (row_type, post_id).
    """
    subm_stmt = select(Submission).where(Submission.file_id == file_id)
    if version_no is None:
        subm_stmt = subm_stmt.where(Submission.valid_to.is_(None))
    else:
        subm_stmt = subm_stmt.where(
            Submission.valid_from <= version_no,
            or_(Submission.valid_to.is_(None), Submission.valid_to >= version_no),
        )

    comm_stmt = select(Comment).where(Comment.file_id == file_id)
    if version_no is None:
        comm_stmt = comm_stmt.where(Comment.valid_to.is_(None))
    else:
        comm_stmt = comm_stmt.where(
            Comment.valid_from <= version_no,
            or_(Comment.valid_to.is_(None), Comment.valid_to >= version_no),
        )

    subm_result = await session.execute(subm_stmt)
    comm_result = await session.execute(comm_stmt)

    rows: list[dict[str, Any]] = []

    for s in subm_result.scalars().all():
        title_text = s.title or ""
        body_text = s.selftext or ""
        if title_text and body_text:
            source = f"{title_text}\n\n{body_text}"
        else:
            source = title_text or body_text

        rows.append(
            {
                "row_type": "submission",
                "post_id": str(s.id),
                "source_text": source,
                "author": s.author,
                "created_utc": s.created_utc,
                "word_count": s.word_count,
            }
        )

    for c in comm_result.scalars().all():
        rows.append(
            {
                "row_type": "comment",
                "post_id": str(c.id),
                "source_text": c.body or "",
                "author": c.author,
                "created_utc": c.created_utc,
                "word_count": c.word_count,
            }
        )

    rows.sort(key=lambda r: (r["row_type"], str(r["post_id"])))
    return rows


async def get_coding_entries(
    session: AsyncSession,
    file_id: int,
    *,
    version_no: int | None = None,
) -> list[Any]:
    """Retrieve coding entries live or as of historical ``version_no``.

    Deterministic sort: (row_type, post_id, start_offset, end_offset,
    code_uid, id).
    """
    if version_no is not None:
        entries = await coding_repo.entries_as_of(session, file_id, version_no)
    else:
        entries = await coding_repo.get_coding_entries(session, file_id)

    return sorted(
        entries,
        key=lambda e: (
            e.row_type or "",
            str(e.post_id or ""),
            e.start_offset if e.start_offset is not None else 0,
            e.end_offset if e.end_offset is not None else 0,
            e.code_uid or "",
            e.id or 0,
        ),
    )


async def get_code_frequencies_by_uid(
    session: AsyncSession,
    file_id: int,
    *,
    codes: list[CodebookCode],
    version_no: int | None = None,
) -> list[dict[str, Any]]:
    """Frequency and document counts grouped strictly by ``code_uid``, not
    by code name -- stable against renames across versions (a renamed
    code keeps its identity here; grouping by name would silently split
    or merge history at the rename point).

    Takes the codebook's codes as an argument rather than fetching them
    itself: resolving them is ``version_service.read_codes``'s job (codec
    delta application against the nearest materialized ancestor), and a
    repository must not import the service layer -- see
    ``export_service.py``'s ``_get_sorted_codebook_codes``, the one place
    that calls it.
    """
    entries = await get_coding_entries(session, file_id, version_no=version_no)

    code_meta_by_uid: dict[str, dict[str, Any]] = {
        c.code_uid: {
            "name": c.name or "",
            "family_uid": c.family_uid or "",
            "family_name": c.family_name or "",
        }
        for c in codes
        if c.code_uid
    }

    counts: dict[str, int] = {}
    doc_sets: dict[str, set[tuple[str, str]]] = {}
    observed_names: dict[str, str] = {}

    for e in entries:
        uid = e.code_uid or ""
        if not uid:
            continue
        counts[uid] = counts.get(uid, 0) + 1
        doc_sets.setdefault(uid, set()).add((e.row_type or "", str(e.post_id or "")))
        if uid not in observed_names and e.code:
            observed_names[uid] = e.code

    # Every codebook code appears even at zero frequency; an orphaned
    # entry (code_uid no longer in the codebook) still surfaces via its
    # observed name rather than being silently dropped.
    all_uids = set(code_meta_by_uid.keys()) | set(counts.keys())
    results: list[dict[str, Any]] = []

    for uid in all_uids:
        meta = code_meta_by_uid.get(uid, {})
        results.append(
            {
                "code_uid": uid,
                "name": meta.get("name") or observed_names.get(uid, ""),
                "family_uid": meta.get("family_uid", ""),
                "family_name": meta.get("family_name", ""),
                "frequency": counts.get(uid, 0),
                "document_count": len(doc_sets.get(uid, set())),
            }
        )

    results.sort(key=lambda s: (-s["frequency"], s["code_uid"]))
    return results


async def get_row_memos(session: AsyncSession, file_id: int) -> list[RowMemo]:
    """Row memos for an artifact, deterministically sorted."""
    memos = await memo_repo.list_memos(session, file_id)
    return sorted(memos, key=lambda m: (m.row_type or "", str(m.row_id or ""), m.id or 0))


async def get_project_files(session: AsyncSession, project_id: int) -> list[File]:
    """Every file belonging to a project, deterministically sorted by id."""
    stmt = (
        select(File)
        .join(project_files_table, File.id == project_files_table.c.file_id)
        .where(project_files_table.c.project_id == project_id)
        .order_by(File.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_project_lineage_graph(session: AsyncSession, project_files: list[File]) -> dict[str, Any]:
    """One-hop-per-file lineage graph (versions + parent/child edges) for
    every artifact in a project bundle.
    """
    files_data = []

    for f in project_files:
        versions = await version_repo.list_versions(session, f.id)
        parent_edges = await version_repo.list_parent_edges(session, f.id)
        child_edges = await version_repo.list_child_edges(session, f.id)

        files_data.append(
            {
                "file_id": f.id,
                "filename": f.filename,
                "schemaname": f.schemaname,
                "file_type": f.file_type,
                "versions": [
                    {
                        "version_no": v.version_no,
                        "origin": v.origin,
                        "created_at": v.created_at.isoformat() if v.created_at else None,
                        "model": v.model,
                        # The human-authored fragment only -- see
                        # ArtifactVersion.user_instructions's docstring;
                        # there is no separately-stored rendered prompt.
                        "user_instructions": v.user_instructions,
                    }
                    for v in sorted(versions, key=lambda v: v.version_no)
                ],
                "parents": [
                    {
                        "parent_file_id": pe.parent_file_id,
                        "parent_version_id": pe.parent_version_id,
                        "relation": pe.relation,
                        "role": pe.role,
                        "position": pe.position,
                    }
                    for pe in sorted(parent_edges, key=lambda e: (e.position or 0, e.id))
                ],
                "children": [
                    {
                        "child_file_id": ce.child_file_id,
                        "relation": ce.relation,
                        "role": ce.role,
                        "position": ce.position,
                    }
                    for ce in sorted(child_edges, key=lambda e: (e.position or 0, e.id))
                ],
            }
        )

    return {
        "files_count": len(files_data),
        "artifacts": sorted(files_data, key=lambda x: x["file_id"]),
    }
