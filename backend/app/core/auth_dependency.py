"""FastAPI dependencies that turn a request's session token into a user id.

A token is accepted only while its user still exists and its ``pwh`` claim
matches that user's current password fingerprint, so resetting a password
signs out every session issued before it. This costs one primary-key lookup
per authenticated request, on the request's own session.
"""

import hmac
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.utils import get_token_payload_from_request, user_id_from_claims
from backend.app.auth import password_fingerprint
from backend.app.core.exceptions import UnauthorizedError
from backend.app.database import User, get_async_db


async def session_user_id(request: Request, db: AsyncSession) -> Optional[int]:
    """The id of the user this request's session token belongs to, or
    ``None`` when there is no valid, current session.

    Database errors propagate: a session must never be accepted because its
    revocation check couldn't run.
    """
    payload = get_token_payload_from_request(request)
    user_id = user_id_from_claims(payload)
    if user_id is None:
        return None

    stored_hash = (await db.execute(select(User.password).where(User.id == user_id))).scalar_one_or_none()
    if stored_hash is None:
        return None
    if not hmac.compare_digest(str(payload.get("pwh") or ""), password_fingerprint(stored_hash)):
        return None
    return user_id


async def require_user_id(request: Request, db: AsyncSession = Depends(get_async_db)) -> int:
    """``Depends(require_user_id)`` -- raises ``UnauthorizedError`` (401)
    unless the request carries a valid, current session.
    """
    user_id = await session_user_id(request, db)
    if user_id is None:
        raise UnauthorizedError("Not authenticated")
    return user_id


async def optional_user_id(request: Request, db: AsyncSession = Depends(get_async_db)) -> Optional[int]:
    """``Depends(optional_user_id)`` for endpoints with optional auth-scoping."""
    return await session_user_id(request, db)
