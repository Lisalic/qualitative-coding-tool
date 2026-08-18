"""Service layer for project/file listing and CRUD -- backs
backend/app/api/project_routes.py.

Async, ORM-only. ``list_files_for_user`` and ``list_projects_with_files``
replace the two N+1-shaped handlers in the old router (``my_projects`` did
one ``FileTable`` query + one ``FileDependency`` query *per file*;
``list_projects`` did one dependency query per file per project) with a
constant number of queries regardless of file count, via
``repositories/file_repo.py::list_files_with_tables_and_deps`` plus a
single bulk lookup for any referenced parent files not already in that
result set.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.exceptions import ValidationAppError
from backend.app.database import File, Project
from backend.app.repositories import file_repo, project_repo


async def _resolve_parent_files(session: AsyncSession, files: list[File]) -> dict[int, File]:
    """Build an ``id -> File`` map covering every file in ``files`` plus
    every ``parent_file_id`` referenced by their ``child_dependencies`` --
    at most one extra query beyond ``files`` itself (only issued when a
    referenced parent isn't already among ``files``), so this stays
    constant regardless of file/dependency count.
    """
    by_id: dict[int, File] = {f.id: f for f in files}
    missing_ids = {
        dep.parent_file_id
        for f in files
        for dep in f.child_dependencies
        if dep.parent_file_id not in by_id
    }
    if missing_ids:
        result = await session.execute(select(File).where(File.id.in_(missing_ids)))
        for parent in result.scalars().all():
            by_id[parent.id] = parent
    return by_id


def _file_type_filter(file_type: str) -> tuple[str, ...]:
    """Matches the old ``my_projects`` handler's mapping: requesting
    'codebook' or 'coding' also includes the corresponding saved
    comparison files; anything else is an exact match.
    """
    if file_type == "codebook":
        return ("codebook", "codebook_comparison")
    if file_type == "coding":
        return ("coding", "coding_comparison")
    return (file_type,)


async def list_files_for_user(
    session: AsyncSession, user_id: int, file_type: str = "raw_data"
) -> list[dict]:
    """Replaces ``my_projects``. Returns dicts shaped exactly like the old
    handler's per-file entries.
    """
    types = _file_type_filter(file_type)
    all_files = await file_repo.list_files_with_tables_and_deps(session, user_id)
    matched = [f for f in all_files if f.file_type in types]
    parent_lookup = await _resolve_parent_files(session, all_files)

    result = []
    for p in matched:
        tables = [{"table_name": t.tablename, "row_count": t.row_count} for t in p.tables]
        parent_files = []
        for dep in p.child_dependencies:
            parent = parent_lookup.get(dep.parent_file_id)
            if parent:
                parent_files.append(
                    {
                        "id": str(parent.id),
                        "name": parent.filename,
                        "schema_name": parent.schemaname,
                        "type": parent.file_type,
                    }
                )
        result.append(
            {
                "id": str(p.id),
                "display_name": p.filename,
                "description": p.description,
                "schema_name": p.schemaname,
                "file_type": p.file_type,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "tables": tables,
                "parent_files": parent_files,
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
    old handler's per-project entries (note: each file's ``parent_files``
    entries here carry ``id``/``name``/``type`` only -- no ``schema_name``
    -- distinct from ``list_files_for_user``'s shape above).

    Loads every one of the user's files (with tables/dependencies eagerly
    loaded) first via ``file_repo.list_files_with_tables_and_deps`` so
    those fully-populated ``File`` instances are already in the session's
    identity map; the subsequent ``Project`` query with
    ``selectinload(Project.files)`` then reuses those same instances
    instead of re-querying their relationships -- keeping the total query
    count constant regardless of file/project count.
    """
    all_files = await file_repo.list_files_with_tables_and_deps(session, user_id)
    parent_lookup = await _resolve_parent_files(session, all_files)

    result_p = await session.execute(
        select(Project).where(Project.user_id == user_id).options(selectinload(Project.files))
    )
    projects = result_p.scalars().unique().all()

    result = []
    for proj in projects:
        files = []
        for f in proj.files:
            parent_files = []
            for dep in f.child_dependencies:
                parent = parent_lookup.get(dep.parent_file_id)
                if parent:
                    parent_files.append(
                        {"id": str(parent.id), "name": parent.filename, "type": parent.file_type}
                    )
            files.append(
                {
                    "id": str(f.id),
                    "display_name": f.filename,
                    "schema_name": f.schemaname,
                    "file_type": f.file_type,
                    "description": f.description,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                    "parent_files": parent_files,
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
