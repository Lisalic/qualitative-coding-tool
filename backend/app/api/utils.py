import os
import hashlib
import binascii
from fastapi import Request

try:
    from backend.app.auth import decode_access_token
except Exception:
    from app.auth import decode_access_token

# Re-exported for existing importers; the implementation now lives in
# backend.app.core.schema_guard. Remove this shim once nothing imports
# is_proj_schema/normalize_schema from here (planned for the refactor's
# cleanup stage).
try:
    from backend.app.core.schema_guard import is_proj_schema, normalize_schema  # noqa: F401
except Exception:
    from app.core.schema_guard import is_proj_schema, normalize_schema  # noqa: F401


def get_user_id_from_request(request: Request):
    """Get user ID from request token. Returns int or None."""
    token = None
    try:
        token = request.cookies.get("access_token")
    except Exception:
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
    except Exception:
        return None

    sub = payload.get("sub")
    if sub is not None:
        try:
            return int(sub)
        except (ValueError, TypeError):
            return None
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
        return binascii.hexlify(test_dk) == binascii.hexlify(dk)
    except Exception:
        return False
