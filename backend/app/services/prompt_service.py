"""Service layer for prompt CRUD -- backs backend/app/api/prompt_routes.py.

Async, ORM-only (no raw SQL), and the sole owner of not-found/ownership
semantics for prompts so the route handlers stay thin request/response
shims. Callers are expected to have already resolved the authenticated
user id (e.g. via ``core/auth_dependency.py::require_user_id``).
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ForbiddenError, NotFoundError
from backend.app.database import Prompt

_UPDATABLE_FIELDS = ("promptname", "prompt", "type")


async def list_prompts(
    session: AsyncSession, user_id: int, prompt_type: str | None = None
) -> list[Prompt]:
    """Return all prompts owned by ``user_id``, optionally filtered by ``type``."""
    stmt = select(Prompt).where(Prompt.user_id == user_id)
    if prompt_type:
        stmt = stmt.where(Prompt.type == prompt_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_prompt(
    session: AsyncSession,
    user_id: int,
    promptname: str,
    prompt: str,
    type: str | None = None,
) -> Prompt:
    """Create and persist a new prompt owned by ``user_id``."""
    new_prompt = Prompt(user_id=user_id, promptname=promptname, prompt=prompt, type=type)
    session.add(new_prompt)
    await session.commit()
    await session.refresh(new_prompt)
    return new_prompt


async def _get_owned_prompt(session: AsyncSession, user_id: int, prompt_id: int) -> Prompt:
    """Fetch a prompt by id, distinguishing "doesn't exist" from "exists,
    but belongs to someone else" -- ``NotFoundError`` (404) for the former,
    ``ForbiddenError`` (403) for the latter.
    """
    result = await session.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt_row = result.scalar_one_or_none()
    if prompt_row is None:
        raise NotFoundError("Prompt not found")
    if int(prompt_row.user_id) != int(user_id):
        raise ForbiddenError("Forbidden")
    return prompt_row


async def update_prompt(
    session: AsyncSession, user_id: int, prompt_id: int, **fields: Any
) -> Prompt:
    """Update the given fields on a prompt owned by ``user_id``.

    Raises ``NotFoundError`` if no prompt with ``prompt_id`` exists at all,
    ``ForbiddenError`` if it exists but is owned by a different user. Only
    keys in ``promptname``/``prompt``/``type`` with a non-``None`` value are
    applied, matching the original route's "only touch supplied fields"
    behavior.
    """
    prompt_row = await _get_owned_prompt(session, user_id, prompt_id)
    for field in _UPDATABLE_FIELDS:
        value = fields.get(field)
        if value is not None:
            setattr(prompt_row, field, value)
    await session.commit()
    await session.refresh(prompt_row)
    return prompt_row


async def delete_prompt(session: AsyncSession, user_id: int, prompt_id: int) -> None:
    """Delete a prompt owned by ``user_id``.

    Raises ``NotFoundError``/``ForbiddenError`` with the same semantics as
    ``update_prompt``.
    """
    prompt_row = await _get_owned_prompt(session, user_id, prompt_id)
    await session.delete(prompt_row)
    await session.commit()
