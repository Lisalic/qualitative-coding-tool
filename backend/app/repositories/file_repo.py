"""Repository for looking up and resolving ``File`` rows.

Consolidates the 3-way schemaname/filename/id lookup and the
user-ownership-check block duplicated across route files (e.g.
``codebook_routes.py::get_codebook``, the ownership-check blocks in
``file_routes.py``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.exceptions import NotFoundError
from backend.app.database import File


async def _lookup_file(
    session: AsyncSession,
    ref: str,
    user_id: int,
    *,
    file_types: tuple[str, ...] | None = None,
) -> File | None:
    """Resolve ``ref`` by schemaname, then filename, then id.

    Every pass takes the LOWEST-id match rather than requiring a unique
    one. ``files.filename`` is a user-chosen display name with no
    uniqueness constraint (rename and duplicate both let two of a user's
    files share one), so a ``scalar_one_or_none()`` here raised
    ``MultipleResultsFound`` -- an unhandled 500 that locked the user out
    of reading, renaming OR deleting *either* colliding file. Picking the
    oldest match keeps a given ref resolving to the same file over time
    (a newly created namesake never steals an existing ref) and, unlike
    raising, always leaves both files reachable by schemaname and id.
    """
    base = select(File).where(File.user_id == user_id)
    if file_types:
        base = base.where(File.file_type.in_(file_types))

    for condition in (File.schemaname == ref, File.filename == ref):
        result = await session.execute(base.where(condition).order_by(File.id).limit(1))
        file_rec = result.scalars().first()
        if file_rec is not None:
            return file_rec

    try:
        file_id = int(ref)
    except (TypeError, ValueError):
        return None

    result = await session.execute(base.where(File.id == file_id))
    return result.scalar_one_or_none()


async def resolve_file_id(
    session: AsyncSession,
    ref: str,
    user_id: int,
    *,
    file_types: tuple[str, ...] | None = None,
) -> int:
    """Resolve ``ref`` (a schemaname, a filename, or a numeric-id string)
    to a ``File.id`` owned by ``user_id``, trying schemaname, then
    filename, then (if ``ref`` parses as ``int``) id, in that order.
    Raises ``NotFoundError`` if nothing matches.
    """
    file_rec = await _lookup_file(session, ref, user_id, file_types=file_types)
    if file_rec is None:
        raise NotFoundError(f"File not found: {ref}")
    return file_rec.id


async def get_owned_file(
    session: AsyncSession,
    ref: str,
    user_id: int,
    *,
    file_types: tuple[str, ...] | None = None,
) -> File:
    """Same lookup as ``resolve_file_id``, returning the full ORM row.

    Note: unlike ``project_repo.get_owned_project``, there is no separate
    "found but not owned" -> ``ForbiddenError`` outcome here. Ownership is
    baked into the query itself -- ``File.user_id == user_id`` is applied
    *before* any of the three lookup passes -- so a file owned by another
    user is indistinguishable, from this function's point of view, from a
    file that doesn't exist at all; both raise ``NotFoundError``. This is
    a deliberate choice matching how the duplicated lookup code it
    replaces already behaved (e.g. ``codebook_routes.py::get_codebook``
    scopes its query the same way), not an oversight -- ``File.id`` isn't
    a stable public identifier the way ``Project.id`` is, so there's no
    "tell the caller which case it was" step worth doing here.
    """
    file_rec = await _lookup_file(session, ref, user_id, file_types=file_types)
    if file_rec is None:
        raise NotFoundError(f"File not found: {ref}")
    return file_rec


async def list_files_with_tables(session: AsyncSession, user_id: int) -> list[File]:
    """All of ``user_id``'s files, with ``.tables`` eagerly loaded via
    ``selectinload`` -- a small constant number of queries regardless of
    file count. Parent lineage is no longer an ORM relationship read
    this way; see ``repositories/version_repo.py::list_parent_edges_for_files``
    and ``filter_owned_ids`` below, called separately by
    ``services/project_service.py``.
    """
    result = await session.execute(
        select(File).where(File.user_id == user_id).options(selectinload(File.tables))
    )
    return list(result.scalars().all())


async def existing_file_ids(session: AsyncSession, file_ids: set[int]) -> set[int]:
    """Of ``file_ids``, the subset that still has a ``files`` row.

    Deliberately NOT ownership-scoped -- this answers "does the row the
    FK points at exist", which is what a caller about to write a
    ``file_id`` foreign key needs to know. Ownership is a separate
    question, already settled upstream by whoever chose these ids; use
    ``filter_owned_ids`` when the ids come from an untrusted source.
    """
    if not file_ids:
        return set()
    result = await session.execute(select(File.id).where(File.id.in_(file_ids)))
    return set(result.scalars().all())


async def require_existing_file_ids(session: AsyncSession, file_ids: set[int]) -> None:
    """Raise ``NotFoundError`` if any of ``file_ids`` no longer exists.

    For the case a background job hits when the artifact it is about to
    read *content* out of was deleted during its (minutes-long) LLM call:
    apply-codebook and filter both copy their source file's rows into the
    artifact they are creating, at the very end of the run. A source that
    vanished mid-run copies zero rows, which would otherwise ship a
    finished-looking artifact whose coding entries reference rows it
    doesn't have. Failing the job with a clear message is the only
    honest outcome -- unlike a missing *lineage* parent, which
    ``version_service.link_parents`` can safely skip.
    """
    missing = set(file_ids) - await existing_file_ids(session, set(file_ids))
    if missing:
        raise NotFoundError(
            "Source file no longer exists (deleted while this job was running): "
            + ", ".join(str(i) for i in sorted(missing))
        )


async def filter_owned_ids(session: AsyncSession, file_ids: set[int], user_id: int) -> set[int]:
    """Of ``file_ids``, the subset actually owned by ``user_id``. Used
    wherever a caller has a set of file ids from an untrusted or
    cross-user-reachable source (edge parents, client-supplied ids) and
    needs to scope it down before trusting or serializing anything about
    them -- see ``version_service.fork_lineage`` and
    ``services/project_service.py``.
    """
    if not file_ids:
        return set()
    result = await session.execute(
        select(File.id).where(File.id.in_(file_ids), File.user_id == user_id)
    )
    return set(result.scalars().all())
