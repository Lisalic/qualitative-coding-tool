import os
import sqlite3
import hashlib
import binascii
from fastapi import Request

try:
    from backend.app.auth import decode_access_token
except Exception:
    from app.auth import decode_access_token


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
