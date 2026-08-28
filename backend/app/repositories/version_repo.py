"""Repository for ``artifact_versions``, ``artifact_edges``, and
``codebook_codes``.

Dumb by design: no ownership checks, no sealing policy, no
``session.commit()`` calls -- that's all ``backend/app/services/
version_service.py``'s job. This module only knows how to read and write
rows; every function here takes exactly the ids/values it needs and does
the minimum SQL to satisfy the call.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.versioning_models import ArtifactVersion, ArtifactEdge, CodebookCode


# ---------------------------------------------------------------------------
# artifact_versions
# ---------------------------------------------------------------------------


async def create_version(
    session: AsyncSession,
    *,
    file_id: int,
    version_no: int,
    parent_version_id: int | None,
    author_user_id: int | None,
    origin: str,
    message: str | None = None,
    job_id: int | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    user_instructions: str | None = None,
    prompt_meta: dict | None = None,
    content: str | None = None,
    content_hash: str | None = None,
    sealed_at=None,
) -> ArtifactVersion:
    version = ArtifactVersion(
        file_id=file_id,
        version_no=version_no,
        parent_version_id=parent_version_id,
        author_user_id=author_user_id,
        origin=origin,
        message=message,
        job_id=job_id,
        model=model,
        system_prompt=system_prompt,
        user_instructions=user_instructions,
        prompt_meta=prompt_meta,
        content=content,
        content_hash=content_hash,
        sealed_at=sealed_at,
    )
    session.add(version)
    await session.flush()
    return version


async def head_version(session: AsyncSession, file_id: int) -> ArtifactVersion | None:
    """The highest-``version_no`` version for ``file_id``, sealed or not."""
    result = await session.execute(
        select(ArtifactVersion)
        .where(ArtifactVersion.file_id == file_id)
        .order_by(ArtifactVersion.version_no.desc())
        .limit(1)
    )
    return result.scalars().first()


async def get_version_by_no(session: AsyncSession, file_id: int, version_no: int) -> ArtifactVersion | None:
    result = await session.execute(
        select(ArtifactVersion).where(ArtifactVersion.file_id == file_id, ArtifactVersion.version_no == version_no)
    )
    return result.scalar_one_or_none()


async def get_version(session: AsyncSession, version_id: int) -> ArtifactVersion | None:
    result = await session.execute(select(ArtifactVersion).where(ArtifactVersion.id == version_id))
    return result.scalar_one_or_none()


async def latest_materialized_version(
    session: AsyncSession, file_id: int, *, at_or_before: int
) -> ArtifactVersion | None:
    """The highest-``version_no`` version for ``file_id`` with
    ``codes_materialized = True`` at or before ``at_or_before`` -- the
    anchor a non-materialized coding version's codes are read from (see
    ``versioning_models.ArtifactVersion``'s docstring). v1 is always
    materialized, so this only returns ``None`` if ``file_id`` has no
    versions at all.
    """
    result = await session.execute(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.file_id == file_id,
            ArtifactVersion.version_no <= at_or_before,
            ArtifactVersion.codes_materialized.is_(True),
        )
        .order_by(ArtifactVersion.version_no.desc())
        .limit(1)
    )
    return result.scalars().first()


async def list_versions(session: AsyncSession, file_id: int, *, limit: int = 100, offset: int = 0) -> list[ArtifactVersion]:
    result = await session.execute(
        select(ArtifactVersion)
        .where(ArtifactVersion.file_id == file_id)
        .order_by(ArtifactVersion.version_no.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def seal(session: AsyncSession, version: ArtifactVersion, *, at) -> None:
    version.sealed_at = at
    await session.flush()


async def delete_versions_for_file(session: AsyncSession, file_id: int) -> None:
    await session.execute(delete(ArtifactVersion).where(ArtifactVersion.file_id == file_id))


async def null_parent_version_pointers_into_file(session: AsyncSession, file_id: int) -> None:
    """Null out any OTHER file's ``ArtifactVersion.parent_version_id``
    that points at one of ``file_id``'s versions -- a fork's v1 points
    cross-file at its source's head (see ``ArtifactVersion``'s docstring),
    so deleting the source before clearing this would violate the FK.
    Must run before ``delete_versions_for_file`` on the same file.
    """
    await session.execute(
        ArtifactVersion.__table__.update()
        .where(
            ArtifactVersion.parent_version_id.in_(
                select(ArtifactVersion.id).where(ArtifactVersion.file_id == file_id)
            )
        )
        .values(parent_version_id=None)
    )


# ---------------------------------------------------------------------------
# codebook_codes
# ---------------------------------------------------------------------------


async def replace_codes(session: AsyncSession, version_id: int, codes: Sequence[dict]) -> None:
    """Delete-then-insert every ``codebook_codes`` row for ``version_id``.
    Only ever called on a version this same call is in the middle of
    creating (or a still-open draft), never on a sealed, already-read
    version -- so "replace" here is not a history-losing operation.
    """
    await session.execute(delete(CodebookCode).where(CodebookCode.version_id == version_id))
    for row in codes:
        session.add(CodebookCode(version_id=version_id, **row))
    await session.flush()


async def list_codes(session: AsyncSession, version_id: int) -> list[CodebookCode]:
    result = await session.execute(
        select(CodebookCode).where(CodebookCode.version_id == version_id).order_by(CodebookCode.position)
    )
    return list(result.scalars().all())


async def delete_codes(session: AsyncSession, version_id: int) -> None:
    """Delete every ``codebook_codes`` row for ``version_id`` without
    inserting replacements -- the demotion half of compaction (see
    ``version_service._demote_if_eligible``), as opposed to
    ``replace_codes``'s delete-then-insert.
    """
    await session.execute(delete(CodebookCode).where(CodebookCode.version_id == version_id))
    await session.flush()




# ---------------------------------------------------------------------------
# artifact_edges
# ---------------------------------------------------------------------------


async def add_edge(
    session: AsyncSession,
    *,
    child_file_id: int,
    parent_file_id: int,
    parent_version_id: int | None,
    relation: str,
    role: str,
    position: int = 0,
) -> ArtifactEdge:
    edge = ArtifactEdge(
        child_file_id=child_file_id,
        parent_file_id=parent_file_id,
        parent_version_id=parent_version_id,
        relation=relation,
        role=role,
        position=position,
    )
    session.add(edge)
    await session.flush()
    return edge


async def list_parent_edges(session: AsyncSession, child_file_id: int) -> list[ArtifactEdge]:
    result = await session.execute(
        select(ArtifactEdge).where(ArtifactEdge.child_file_id == child_file_id).order_by(ArtifactEdge.position)
    )
    return list(result.scalars().all())


async def list_parent_edges_for_files(session: AsyncSession, child_file_ids: Sequence[int]) -> list[ArtifactEdge]:
    if not child_file_ids:
        return []
    result = await session.execute(
        select(ArtifactEdge).where(ArtifactEdge.child_file_id.in_(child_file_ids)).order_by(ArtifactEdge.position)
    )
    return list(result.scalars().all())


async def list_child_edges(session: AsyncSession, parent_file_id: int) -> list[ArtifactEdge]:
    result = await session.execute(select(ArtifactEdge).where(ArtifactEdge.parent_file_id == parent_file_id))
    return list(result.scalars().all())


async def delete_edges_for_file(session: AsyncSession, file_id: int) -> None:
    await session.execute(
        delete(ArtifactEdge).where(
            (ArtifactEdge.child_file_id == file_id) | (ArtifactEdge.parent_file_id == file_id)
        )
    )
