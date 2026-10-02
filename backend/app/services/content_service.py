"""Service layer for saved summaries -- backs
backend/app/api/content_routes.py.

Content lives in a version's ``artifact_versions.content`` blob now
(``version_service.commit_blob_version``), not in the old one-row-per-file
``artifact_content`` table.

``schemaname`` is still generated with the old ``sum_`` prefix
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
from backend.app.database import File, async_link_file_to_project
from backend.app.repositories import project_repo
from backend.app.services import version_service
from backend.app.versioning_models import ORIGIN_EDITED


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
    commit its content as a blob version, and link to a project (owned by
    ``user_id``) if ``project_id`` is given. Raises
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

    await version_service.commit_blob_version(
        session, file_id=file_rec.id, author_user_id=user_id, origin=ORIGIN_EDITED, content=content,
    )

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
        # Lowest-id match, not scalar_one_or_none -- see
        # `repositories/file_repo.py::_lookup_file` for why a
        # non-unique `filename` must not raise here.
        file_rec = None
        for condition in (File.schemaname == summary_id, File.filename == summary_id):
            result = await session.execute(base.where(condition).order_by(File.id).limit(1))
            file_rec = result.scalars().first()
            if file_rec is not None:
                break
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
