import os
import re
import sqlite3
import hashlib
import binascii
from fastapi import Request

try:
    from backend.app.auth import decode_access_token
except Exception:
    from app.auth import decode_access_token

# Re-export script-level symbols that legacy route code imports via
# ``from .utils import ...``. Keeping them here (instead of moving the
# imports into every route) means tests can monkeypatch
# ``backend.app.api.utils.classify_posts`` / etc. without patching the
# script modules directly.
from backend.app.database import engine  # noqa: F401
from backend.scripts.codebook_apply import classify_posts  # noqa: F401
from backend.scripts.codebook_generator import (  # noqa: F401
    MODEL_1,
    MODEL_3,
    get_client as codebook_get_client,
)


_PROJ_SCHEMA_RE = re.compile(r"^proj_[A-Za-z0-9_]+$")


def normalize_schema(raw: str | None) -> str:
    """Strip whitespace and a trailing ``.db`` from a schema name.

    Returns an empty string for ``None`` so callers can use the usual
    ``if not schema`` check before the structural ``proj_`` test.
    """
    if raw is None:
        return ""
    value = raw.strip()
    if value.endswith(".db"):
        value = value[:-3]
    return value


def is_proj_schema(name: str) -> bool:
    """True when ``name`` matches the ``proj_<hex>`` schema convention."""
    return bool(_PROJ_SCHEMA_RE.match(name or ""))


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
            token = auth.split(None, 1)[1]

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
        except ValueError:
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


def get_database_metadata(db_path):
    """Get metadata for a database file."""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM submissions")
        submission_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM comments")
        comment_count = cursor.fetchone()[0]

        conn.close()

        creation_time = os.path.getctime(str(db_path))

        return {
            "total_submissions": submission_count,
            "total_comments": comment_count,
            "date_created": creation_time if creation_time > 0 else None
        }
    except Exception as e:
        print(f"Error getting metadata for {db_path}: {e}")
        return {
            "total_submissions": 0,
            "total_comments": 0,
            "date_created": None
        }
