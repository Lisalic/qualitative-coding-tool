"""Service layer for project/file listing and CRUD -- backs
backend/app/api/project_routes.py.

Async, ORM-only. ``list_files_for_user`` and ``list_projects_with_files``
replace the two N+1-shaped handlers in the old router (``my_projects`` did
one ``FileTable`` query + one lineage query *per file*; ``list_projects``
did one lineage query per file per project) with a constant number of
queries regardless of file count, via
``repositories/file_repo.py::list_files_with_tables`` plus
``repositories/version_repo.py::list_parent_edges_for_files`` and a single
bulk ownership-scoped lookup for any referenced parent files not already
in that result set.

Both listings now emit the SAME ``parent_files`` entry shape
(``{id, name, schema_name, type}``) -- the old code had two different
shapes for the same concept (``list_files_for_user`` included
``schema_name``, ``list_projects_with_files`` didn't), documented as
deliberate at the time but really just drift.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.exceptions import ValidationAppError
from backend.app.database import File, Project
from backend.app.repositories import file_repo, project_repo, version_repo


async def _build_parent_files_map(session: AsyncSession, files: list[File], user_id: int) -> dict[int, list[dict]]:
    """``child_file_id -> [{id, name, schema_name, type}, ...]`` for every
    parent edge among ``files``, scoped to parents ``user_id`` actually
    owns -- at most two extra queries (edges, then any parent ``File``
    rows not already in ``files``) regardless of file/edge count.

    Ownership-scoping this lookup (via ``file_repo.filter_owned_ids``)
    closes a pre-existing gap: the old ``_resolve_parent_files`` did an
    unscoped ``File.id.in_(missing_ids)`` lookup, so a parent belonging
    to another user could be resolved and serialized here.
    """
    file_ids = [f.id for f in files]
    edges = await version_repo.list_parent_edges_for_files(session, file_ids)
    if not edges:
        return {}

    parent_ids = {e.parent_file_id for e in edges}
    owned_parent_ids = await file_repo.filter_owned_ids(session, parent_ids, user_id)

    by_id: dict[int, File] = {f.id: f for f in files if f.id in owned_parent_ids}
    missing_ids = owned_parent_ids - set(by_id.keys())
    if missing_ids:
        result = await session.execute(select(File).where(File.id.in_(missing_ids)))
        for parent in result.scalars().all():
            by_id[parent.id] = parent

    parents_by_child: dict[int, list[dict]] = {}
    for edge in edges:
        if edge.parent_file_id not in owned_parent_ids:
            continue
        parent = by_id.get(edge.parent_file_id)
        if parent is None:
            continue
        parents_by_child.setdefault(edge.child_file_id, []).append(
            {
                "id": str(parent.id),
                "name": parent.filename,
                "schema_name": parent.schemaname,
                "type": parent.file_type,
            }
        )
    return parents_by_child


def _file_type_filter(file_type: str) -> tuple[str, ...]:
    """Exact match on ``file_type``. Comparisons (``codebook_comparison``/
    ``coding_comparison``) are their own type and are only ever surfaced by
    requesting that type directly -- they no longer fold into a plain
    ``codebook``/``coding`` listing, so the generic codebook/coding pickers
    and viewers stay comparison-free; their dedicated comparison viewers
    request the comparison type explicitly instead.
    """
    return (file_type,)


async def list_files_for_user(
    session: AsyncSession, user_id: int, file_type: str = "raw_data"
) -> list[dict]:
    """Replaces ``my_projects``. Returns dicts shaped exactly like the old
    handler's per-file entries.
    """
    types = _file_type_filter(file_type)
    all_files = await file_repo.list_files_with_tables(session, user_id)
    matched = [f for f in all_files if f.file_type in types]
    parents_by_child = await _build_parent_files_map(session, all_files, user_id)

    result = []
    for p in matched:
        tables = [{"table_name": t.tablename, "row_count": t.row_count} for t in p.tables]
        result.append(
            {
                "id": str(p.id),
                "display_name": p.filename,
                "description": p.description,
                "schema_name": p.schemaname,
                "file_type": p.file_type,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "tables": tables,
                "parent_files": parents_by_child.get(p.id, []),
            }
        )
    return result


async def create_project(
    session: AsyncSession, user_id: int, name: str, description: str | None
) -> Project:
    """Create and persist a new project owned by ``user_id``. Raises
    ``ValidationAppError`` (400) for a blank/whitespace-only name, matching
    the old handler's behavior.
    """
    if not name or not name.strip():
        raise ValidationAppError("Project name is required")

    proj = Project(user_id=user_id, projectname=name.strip(), description=(description or None))
    session.add(proj)
    await session.commit()
    await session.refresh(proj)
    return proj


async def update_project(
    session: AsyncSession, user_id: int, project_id: int, name: str, description: str | None
) -> Project:
    """Update a project's name/description. Raises ``NotFoundError``/
    ``ForbiddenError`` (via ``project_repo.get_owned_project``) before
    ``ValidationAppError`` for a blank name -- same check order as the old
    handler.
    """
    proj = await project_repo.get_owned_project(session, project_id, user_id)

    if not name or not name.strip():
        raise ValidationAppError("Project name is required")

    proj.projectname = name.strip()
    proj.description = description or None
    await session.commit()
    await session.refresh(proj)
    return proj


async def list_projects_with_files(session: AsyncSession, user_id: int) -> list[dict]:
    """Replaces ``list_projects``. Returns dicts shaped exactly like the
    old handler's per-project entries, except each file's ``parent_files``
    entries now carry the SAME ``{id, name, schema_name, type}`` shape
    ``list_files_for_user`` uses (see this module's docstring).

    Loads every one of the user's files (with tables eagerly loaded)
    first via ``file_repo.list_files_with_tables`` so those fully-
    populated ``File`` instances are already in the session's identity
    map; the subsequent ``Project`` query with
    ``selectinload(Project.files)`` then reuses those same instances
    instead of re-querying their relationships -- keeping the total query
    count constant regardless of file/project count.
    """
    all_files = await file_repo.list_files_with_tables(session, user_id)
    parents_by_child = await _build_parent_files_map(session, all_files, user_id)

    result_p = await session.execute(
        select(Project).where(Project.user_id == user_id).options(selectinload(Project.files))
    )
    projects = result_p.scalars().unique().all()

    result = []
    for proj in projects:
        files = []
        for f in proj.files:
            files.append(
                {
                    "id": str(f.id),
                    "display_name": f.filename,
                    "schema_name": f.schemaname,
                    "file_type": f.file_type,
                    "description": f.description,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                    "parent_files": parents_by_child.get(f.id, []),
                }
            )
        result.append(
            {
                "id": str(proj.id),
                "projectname": proj.projectname,
                "description": proj.description,
                "created_at": proj.created_at.isoformat() if proj.created_at else None,
                "files": files,
            }
        )
    return result


async def rename_file(
    session: AsyncSession,
    user_id: int,
    schema_name: str,
    display_name: str,
    description: str | None,
) -> File:
    """Rename a file's display name. Uses ``file_repo.get_owned_file``,
    which raises ``NotFoundError`` for both "doesn't exist" and "exists,
    not yours" -- matching the old handler's single 404 for both cases.
    """
    file_rec = await file_repo.get_owned_file(session, schema_name.strip(), user_id)

    file_rec.filename = display_name
    if description is not None:
        file_rec.description = description
    await session.commit()
    await session.refresh(file_rec)
    return file_rec
