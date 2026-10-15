"""Resolve the signed-in user from a request's session token."""

from typing import Any, Optional

from fastapi import Request

from backend.app.auth.tokens import decode_access_token


def get_token_payload_from_request(request: Request) -> Optional[dict[str, Any]]:
    """Extract and validate the JWT session payload from cookies or Authorization header.

    Returns the decoded claims dictionary or ``None`` if absent, malformed,
    expired, or scoped to a single-purpose flow (e.g. password reset).
    """
    token = None
    try:
        token = request.cookies.get("access_token")
    except Exception:  # noqa: BLE001 - a broken cookie accessor still permits bearer auth
        token = None

    if not token:
        auth = request.headers.get("Authorization") if hasattr(request, "headers") else None
        if auth and isinstance(auth, str) and auth.lower().startswith("bearer "):
            parts = auth.split(None, 1)
            token = parts[1] if len(parts) > 1 else None

    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except ValueError:
        return None

    # Purpose-scoped tokens (e.g. password reset) are never session tokens.
    if payload.get("purpose") is not None:
        return None

    return payload


def user_id_from_claims(payload: Optional[dict[str, Any]]) -> Optional[int]:
    """The user id a session token's ``sub`` claim names, or ``None`` when
    it is missing or not an integer. Says nothing about whether that user
    still exists -- see ``auth/dependencies.py::session_user_id``.
    """
    if not payload:
        return None
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
