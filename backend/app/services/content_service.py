"""Service layer for saved comparisons/summaries -- backs
backend/app/api/content_routes.py.

First real caller of ``repositories/artifact_content_repo.py`` and
``repositories/project_repo.py::get_owned_project``. Replaces the old
per-artifact ``CREATE SCHEMA "cmp_*"``/``"sum_*"`` + ``content_store``
table pattern with a single row in the fixed ``artifact_content`` table
keyed by ``file_id`` -- no DDL, no dynamic schema names, at all in this
path anymore.

``schemaname`` is still generated with the old ``cmp_``/``sum_`` prefix
purely as a backward-compatible opaque identifier string -- the frontend
still expects a ``schema_name``-shaped value back and uses it to look
files up later (see ``repositories/file_repo.py``'s schemaname lookup
pass) -- it no longer names a real Postgres schema.
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError
from backend.app.database import File, FileDependency, async_link_file_to_project
from backend.app.repositories import artifact_content_repo, project_repo


async def _link_parents(session: AsyncSession, child_file_id: int, parent_file_ids: list[int]) -> None:
    for pid in parent_file_ids:
        session.add(FileDependency(child_file_id=child_file_id, parent_file_id=int(pid)))
    await session.flush()


async def save_comparison(
    session: AsyncSession,
    user_id: int,
    *,
    content: str,
    title: str,
    description: str | None,
    file_type: str | None,
    project_id: int | None,
    parent_file_ids: list[int] | None,
) -> File:
    """Create a `File` row for a saved comparison, write its content into
    ``artifact_content``, link any parent artifacts via ``FileDependency``,
    and link to a project (owned by ``user_id``) if ``project_id`` is
    given. Raises ``NotFoundError``/``ForbiddenError`` (via
    ``project_repo.get_owned_project``) if ``project_id`` doesn't resolve
    to a project owned by ``user_id``.
    """
    base_name = title if title and title.strip() else "comparison"
    schema_name = f"cmp_{secrets.token_hex(6)}"

    file_rec = File(
        user_id=user_id,
        filename=base_name,
        schemaname=schema_name,
        file_type=(file_type or "comparison"),
        description=(description or None),
    )
    session.add(file_rec)
    await session.flush()

    await artifact_content_repo.write_content(session, file_rec.id, content)

    if parent_file_ids:
        await _link_parents(session, file_rec.id, [int(pid) for pid in parent_file_ids])

    if project_id is not None:
        project = await project_repo.get_owned_project(session, project_id, user_id)
        await async_link_file_to_project(session, file_rec.id, project.id)
        await session.flush()

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


async def save_summary(
    session: AsyncSession,
    user_id: int,
    *,
    content: str,
    name: str,
    description: str | None,
    project_id: int | None,
) -> File:
    """Create a `File` row (``file_type='summary'``) for a saved summary,
    write its content into ``artifact_content``, and link to a project
    (owned by ``user_id``) if ``project_id`` is given. Raises
    ``NotFoundError``/``ForbiddenError`` (via
    ``project_repo.get_owned_project``) if ``project_id`` doesn't resolve
    to a project owned by ``user_id``.
    """
    schema_name = f"sum_{secrets.token_hex(6)}"
    final_description = (description or "").strip() if description is not None else None
    if final_description == "":
        final_description = None

    file_rec = File(
        user_id=user_id,
        filename=name,
        schemaname=schema_name,
        file_type="summary",
        description=final_description,
    )
    session.add(file_rec)
    await session.flush()

    await artifact_content_repo.write_content(session, file_rec.id, content)

    if project_id is not None:
        project = await project_repo.get_owned_project(session, project_id, user_id)
        await async_link_file_to_project(session, file_rec.id, project.id)
        await session.flush()

    await session.commit()
    await session.refresh(file_rec)
    return file_rec


async def get_summary(session: AsyncSession, user_id: int, summary_id: str | None) -> File:
    """Resolve a ``File`` row with ``file_type='summary'`` owned by
    ``user_id``, matching by schemaname, then filename, then (if
    ``summary_id`` parses as ``int``) id -- or, if ``summary_id`` is
    ``None``, the most recently created summary owned by ``user_id``.

    Doesn't reuse ``repositories/file_repo.py``'s 3-way lookup helpers:
    those don't have a "most recent if no ref given" fallback, which this
    endpoint's existing behavior depends on. Raises ``NotFoundError`` if
    nothing matches -- this is also the fix for the pre-existing missing
    auth-scoping gap (the old handler matched across all users' files).
    """
    base = select(File).where(File.file_type == "summary", File.user_id == user_id)

    if summary_id:
        result = await session.execute(base.where(File.schemaname == summary_id))
        file_rec = result.scalar_one_or_none()
        if file_rec is None:
            result = await session.execute(base.where(File.filename == summary_id))
            file_rec = result.scalar_one_or_none()
        if file_rec is None:
            try:
                fid = int(summary_id)
            except ValueError:
                fid = None
            if fid is not None:
                result = await session.execute(base.where(File.id == fid))
                file_rec = result.scalar_one_or_none()
    else:
        # Tie-break on id (not just created_at): SQLite's `created_at`
        # resolution can tie two rows inserted in the same test/request,
        # and even on Postgres two rows created in the same statement
        # batch could share a timestamp -- id.desc() keeps "most recent"
        # well-defined either way.
        result = await session.execute(
            base.order_by(File.created_at.desc(), File.id.desc()).limit(1)
        )
        file_rec = result.scalars().first()

    if file_rec is None:
        raise NotFoundError(f"No summary file found: {summary_id!r}")
    return file_rec
