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
    base = select(File).where(File.user_id == user_id)
    if file_types:
        base = base.where(File.file_type.in_(file_types))

    result = await session.execute(base.where(File.schemaname == ref))
    file_rec = result.scalar_one_or_none()
    if file_rec is not None:
        return file_rec

    result = await session.execute(base.where(File.filename == ref))
    file_rec = result.scalar_one_or_none()
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


async def list_files_with_tables_and_deps(session: AsyncSession, user_id: int) -> list[File]:
    """All of ``user_id``'s files, with ``.tables``, ``.child_dependencies``,
    and ``.parent_dependencies`` eagerly loaded via ``selectinload`` -- a
    small constant number of queries regardless of file count (fixes the
    N+1 in Stage 2's ``my_projects``/``list_projects``; not wired into any
    route yet).
    """
    result = await session.execute(
        select(File)
        .where(File.user_id == user_id)
        .options(
            selectinload(File.tables),
            selectinload(File.child_dependencies),
            selectinload(File.parent_dependencies),
        )
    )
    return list(result.scalars().all())
