"""FastAPI dependency wrapping ``get_user_id_from_request`` so route
signatures declare auth instead of every handler manually re-checking it.
"""

from fastapi import Request

from backend.app.api.utils import get_user_id_from_request
from backend.app.core.exceptions import UnauthorizedError


def require_user_id(request: Request) -> int:
    """``Depends(require_user_id)`` -- raises ``UnauthorizedError`` (401) if absent."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise UnauthorizedError("Not authenticated")
    return user_id


def optional_user_id(request: Request) -> int | None:
    """``Depends(optional_user_id)`` for endpoints with optional auth-scoping."""
    return get_user_id_from_request(request)
