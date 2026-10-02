import binascii
import hashlib
import hmac
import os
from typing import Any, Optional

from fastapi import Request

try:
    from backend.app.auth import decode_access_token
except ImportError:
    from app.auth import decode_access_token



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
    still exists -- see ``core/auth_dependency.py::session_user_id``.
    """
    if not payload:
        return None
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        return None


def _hash_password(password: str) -> str:
    """Hash the password using PBKDF2-HMAC-SHA256. Returns salt$iterations$hashhex"""
    salt = os.urandom(16)
    iterations = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{binascii.hexlify(salt).decode()}${iterations}${binascii.hexlify(dk).decode()}"


def _verify_password(stored: str, provided: str) -> bool:
    """Verify a stored password of format salt$iterations$hashhex against a provided password."""
    try:
        salt_hex, iterations_s, hash_hex = stored.split("$")
        salt = binascii.unhexlify(salt_hex)
        iterations = int(iterations_s)
        dk = binascii.unhexlify(hash_hex)
        test_dk = hashlib.pbkdf2_hmac("sha256", provided.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(test_dk, dk)
    except (ValueError, TypeError, AttributeError, binascii.Error):
        return False
