import json
import time
import hmac
import hashlib
import base64
from typing import Dict, Any
try:
    from app.config import settings
except:
    try:
        from backend.app.config import settings
    except Exception as exc:
        print("Failed", exc)
        raise exc


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding and padding < 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode())


def create_access_token(payload: Dict[str, Any], expires_minutes: int = None) -> str:
    header = {"alg": settings.jwt_algorithm or "HS256", "typ": "JWT"}
    iat = int(time.time())
    if expires_minutes is None:
        exp = iat + (settings.jwt_access_token_expire_minutes * 60)
    else:
        exp = iat + (int(expires_minutes) * 60)

    body = payload.copy()
    body.update({"iat": iat, "exp": exp})

    header_b = _b64url_encode(json.dumps(header, separators=(',', ':')).encode())
    body_b = _b64url_encode(json.dumps(body, separators=(',', ':')).encode())
    signing_input = f"{header_b}.{body_b}".encode()

    secret = (settings.jwt_secret_key or settings.secret_key).encode()
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b = _b64url_encode(sig)

    return f"{header_b}.{body_b}.{sig_b}"


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        header_b, body_b, sig_b = token.split('.')
        signing_input = f"{header_b}.{body_b}".encode()
        secret = (settings.jwt_secret_key or settings.secret_key).encode()
        expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
        sig = _b64url_decode(sig_b)
        if not hmac.compare_digest(expected_sig, sig):
            raise ValueError("Invalid signature")

        body_json = _b64url_decode(body_b)
        payload = json.loads(body_json.decode())
        now = int(time.time())
        if payload.get("exp") and now > int(payload.get("exp")):
            raise ValueError("Token expired")
        return payload
    except Exception as exc:
        raise ValueError(str(exc))
