"""Repository for ``artifact_content`` -- one TEXT blob per artifact.

Replaces the ~10 duplicated ``CREATE SCHEMA ...`` + ``content_store``
table blocks used by codebook / codebook_comparison / coding_comparison /
summary artifacts (see ``codebook_routes.py`` lines ~168-175 for what the
old write path looked like).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.storage_models import ArtifactContent


async def write_content(session: AsyncSession, file_id: int, content: str) -> None:
    """Upsert: insert a new row for ``file_id``, or overwrite ``.content``
    if one already exists.

    Implemented as select-then-insert/update via plain ORM operations
    rather than the ``pg_insert(...).on_conflict_do_update(...)`` idiom
    used elsewhere in this codebase (``database.py::async_link_file_to_project``)
    -- that construct is Postgres-only and would fail against the
    in-memory SQLite engine this repository's tests (and the rest of the
    test suite) run against, so it isn't used here despite being the
    general upsert idiom already in the codebase.
    """
    result = await session.execute(
        select(ArtifactContent).where(ArtifactContent.file_id == file_id)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        row.content = content
    else:
        session.add(ArtifactContent(file_id=file_id, content=content))


async def read_content(session: AsyncSession, file_id: int) -> str | None:
    """Return the stored content for ``file_id``, or ``None`` if no row
    exists.
    """
    result = await session.execute(
        select(ArtifactContent.content).where(ArtifactContent.file_id == file_id)
    )
    return result.scalar_one_or_none()
