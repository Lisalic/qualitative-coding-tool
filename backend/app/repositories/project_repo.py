"""Repository for project-ownership lookups and project/file links.

Consolidates the ``if proj is None: 404 / if proj.user_id != user_id: 403``
block duplicated ~7 times across route files (e.g.
``routes/files.py::upload_zst``, ``routes/content.py::save_summary``,
``routes/projects.py::update_project`` -- grep for
``"Forbidden: project does not belong to user"`` to see the duplicated
pattern this replaces).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.models.workspace import Project, project_files_table


async def get_owned_project(session: AsyncSession, project_id: int, user_id: int) -> Project:
    """Fetch ``Project`` by id, raising ``NotFoundError`` if it doesn't
    exist and ``ForbiddenError`` if it exists but belongs to a different
    user.

    Unlike ``file_repo.get_owned_file``, these two outcomes ARE
    distinguishable here: ``project_id`` is always an integer primary key
    supplied directly by the caller, so "doesn't exist" and "exists,
    wrong owner" are two different query results rather than one
    ownership-scoped lookup that can only ever say "found" or "not
    found".
    """
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError(f"Project not found: {project_id}")
    if project.user_id != user_id:
        raise ForbiddenError("Forbidden: project does not belong to user")
    return project


async def async_link_file_to_project(session: AsyncSession, file_id: int, project_id: int) -> None:
    """Associate a file with a project via ``project_files`` (avoids ORM collection lazy IO in async)."""
    stmt = (
        pg_insert(project_files_table)
        .values(project_id=project_id, file_id=file_id)
        .on_conflict_do_nothing(
            index_elements=[
                project_files_table.c.project_id,
                project_files_table.c.file_id,
            ],
        )
    )
    await session.execute(stmt)
