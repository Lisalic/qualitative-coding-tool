"""Repository for ``artifact_assists``.

Dumb by design, same convention as ``version_repo.py``: no job
validation, no ownership checks -- that is
``services/assist_service.py``'s job. This module only knows how to
insert and read rows.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.versioning_models import ArtifactAssist, ArtifactVersion


async def insert_assist(
    session: AsyncSession,
    *,
    file_id: int,
    version_id: int,
    stage: str,
    job_id: int | None,
    model: str | None,
    system_prompt: str | None,
    user_instructions: str | None,
    prompt_meta: dict | None,
    proposed_count: int,
    accepted_count: int,
    dismissed_count: int,
    accepted_refs: list | None,
) -> ArtifactAssist:
    assist = ArtifactAssist(
        file_id=file_id,
        version_id=version_id,
        stage=stage,
        job_id=job_id,
        model=model,
        system_prompt=system_prompt,
        user_instructions=user_instructions,
        prompt_meta=prompt_meta,
        proposed_count=proposed_count,
        accepted_count=accepted_count,
        dismissed_count=dismissed_count,
        accepted_refs=accepted_refs,
    )
    session.add(assist)
    await session.flush()
    return assist


async def list_for_file(
    session: AsyncSession, file_id: int, *, version_no: int | None = None
) -> list[tuple[ArtifactAssist, int]]:
    """Every assist run recorded against ``file_id``, oldest first, paired
    with the ``version_no`` it was recorded against. ``version_no``
    narrows to assists recorded on that one version.
    """
    query = (
        select(ArtifactAssist, ArtifactVersion.version_no)
        .join(ArtifactVersion, ArtifactAssist.version_id == ArtifactVersion.id)
        .where(ArtifactAssist.file_id == file_id)
    )
    if version_no is not None:
        query = query.where(ArtifactVersion.version_no == version_no)
    query = query.order_by(ArtifactAssist.created_at, ArtifactAssist.id)
    result = await session.execute(query)
    return [(row[0], row[1]) for row in result.all()]
