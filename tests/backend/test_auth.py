"""Tests for backend/app/auth.py -- the hand-rolled HMAC-SHA256 JWT.

Covers: base64url padding math (_b64url_encode/_decode), the
create_access_token/decode_access_token round trip, signature
verification, expiry handling, and every documented failure mode.
"""

import base64
import binascii
import json

import pytest

from backend.app import auth as auth_module
from backend.app.auth import (
    _b64url_decode,
    _b64url_encode,
    create_access_token,
    decode_access_token,
)
from backend.app.config import settings


# ---------------------------------------------------------------------------
# _b64url_encode / _b64url_decode
# ---------------------------------------------------------------------------


class TestB64UrlEncode:
    @pytest.mark.parametrize(
        "data,expected",
        [
            (b"", ""),
            (b"A", "QQ"),  # 1 byte -> 2 chars, no padding to strip
            (b"AB", "QUI"),  # 2 bytes -> 3 chars
            (b"ABC", "QUJD"),  # 3 bytes -> 4 chars, no padding present
        ],
    )
    def test_padding_lengths(self, data: bytes, expected: str) -> None:
        assert _b64url_encode(data) == expected

    def test_never_contains_plus_or_slash(self) -> None:
        # bytes 0xFB-0xFF are exactly where standard base64 would emit
        # '+' or '/'; the urlsafe alphabet must substitute '-'/'_'.
        data = bytes(range(256))
        out = _b64url_encode(data)
        assert "+" not in out
        assert "/" not in out
        assert "=" not in out

    def test_requires_bytes(self) -> None:
        with pytest.raises(TypeError):
            _b64url_encode("not bytes")  # type: ignore[arg-type]

    @pytest.mark.parametrize("data", [b"", b"x", b"xy", b"xyz", b"round-trip-me!!"])
    def test_round_trip(self, data: bytes) -> None:
        assert _b64url_decode(_b64url_encode(data)) == data


class TestB64UrlDecode:
    def test_len_mod_4_eq_0_no_padding_added(self) -> None:
        # "QUJD" already has len % 4 == 0; must decode without modification.
        assert _b64url_decode("QUJD") == b"ABC"

    def test_len_mod_4_eq_2_adds_double_equals(self) -> None:
        assert _b64url_decode("QQ") == b"A"

    def test_len_mod_4_eq_3_adds_single_equals(self) -> None:
        assert _b64url_decode("QUI") == b"AB"

    def test_len_mod_4_eq_1_is_unrecoverable(self) -> None:
        with pytest.raises(binascii.Error):
            _b64url_decode("A")

    def test_empty_string(self) -> None:
        assert _b64url_decode("") == b""

    def test_already_padded_input_passes_through(self) -> None:
        assert _b64url_decode("QQ==") == b"A"

    def test_non_alphabet_chars_are_silently_discarded(self) -> None:
        # base64.urlsafe_b64decode uses validate=False: non-alphabet bytes
        # are dropped rather than rejected.
        assert _b64url_decode("é") == b""

    def test_non_alphabet_chars_can_still_break_padding(self) -> None:
        # "QQ!!" has len 4 (no padding added), but after '!!' is discarded
        # only 2 valid chars remain -> incorrect padding.
        with pytest.raises(binascii.Error):
            _b64url_decode("QQ!!")

    def test_requires_str(self) -> None:
        with pytest.raises(AttributeError):
            _b64url_decode(b"QQ==")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_returns_three_dot_separated_segments(self, frozen_time: float) -> None:
        token = create_access_token({"sub": "1"})
        parts = token.split(".")
        assert len(parts) == 3
        assert "=" not in token

    def test_header_alg_defaults_to_hs256(self, frozen_time: float) -> None:
        token = create_access_token({"sub": "1"})
        header_b = token.split(".")[0]
        header = json.loads(_b64url_decode(header_b))
        assert header == {"alg": "HS256", "typ": "JWT"}

    def test_header_alg_is_decorative_only(self, monkeypatch, frozen_time: float) -> None:
        # Claiming RS256 in the header must not change how the token is
        # signed -- the implementation hardcodes HMAC-SHA256 regardless.
        monkeypatch.setattr(settings, "jwt_algorithm", "RS256")
        token = create_access_token({"sub": "1"})
        header = json.loads(_b64url_decode(token.split(".")[0]))
        assert header["alg"] == "RS256"
        # Still decodes fine because decode_access_token never reads `alg`.
        payload = decode_access_token(token)
        assert payload["sub"] == "1"

    def test_default_expiry_uses_settings_minutes(self, frozen_time: float) -> None:
        token = create_access_token({"sub": "1"})
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        assert payload["iat"] == int(frozen_time)
        assert payload["exp"] == int(frozen_time) + settings.jwt_access_token_expire_minutes * 60

    def test_explicit_expires_minutes_overrides_default(self, frozen_time: float) -> None:
        token = create_access_token({"sub": "1"}, expires_minutes=5)
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        assert payload["exp"] == int(frozen_time) + 5 * 60

    def test_expires_minutes_zero_means_exp_equals_iat(self, frozen_time: float) -> None:
        token = create_access_token({"sub": "1"}, expires_minutes=0)
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        assert payload["exp"] == payload["iat"]

    def test_expires_minutes_accepts_numeric_string(self, frozen_time: float) -> None:
        token = create_access_token({"sub": "1"}, expires_minutes="5")  # type: ignore[arg-type]
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        assert payload["exp"] == int(frozen_time) + 5 * 60

    def test_caller_supplied_iat_exp_are_overwritten(self, frozen_time: float) -> None:
        original = {"sub": "1", "iat": 111, "exp": 222}
        token = create_access_token(dict(original))
        payload = json.loads(_b64url_decode(token.split(".")[1]))
        assert payload["iat"] == int(frozen_time)
        assert payload["exp"] != 222
        # Original dict passed in must not be mutated.
        assert original == {"sub": "1", "iat": 111, "exp": 222}

    def test_non_serializable_payload_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            create_access_token({"sub": {1, 2, 3}})  # a set is not JSON-serializable

    def test_secret_key_change_changes_signature(self, monkeypatch, frozen_time: float) -> None:
        monkeypatch.setattr(settings, "jwt_secret_key", "secret-a")
        token_a = create_access_token({"sub": "1"})
        monkeypatch.setattr(settings, "jwt_secret_key", "secret-b")
        token_b = create_access_token({"sub": "1"})
        assert token_a.split(".")[2] != token_b.split(".")[2]


# ---------------------------------------------------------------------------
# decode_access_token
# ---------------------------------------------------------------------------


class TestDecodeAccessToken:
    def test_round_trip(self) -> None:
        token = create_access_token({"sub": "1", "email": "a@b.com"})
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["email"] == "a@b.com"
        assert "iat" in payload and "exp" in payload

    @pytest.mark.parametrize("token", ["a.b", "a.b.c.d", ""])
    def test_wrong_segment_count_raises_value_error(self, token: str) -> None:
        with pytest.raises(ValueError):
            decode_access_token(token)

    def test_tampered_payload_is_rejected_before_json_parsing(self) -> None:
        token = create_access_token({"sub": "1"})
        header_b, body_b, sig_b = token.split(".")
        # Flip the body but keep the (now-mismatched) signature.
        tampered_body = body_b[:-1] + ("A" if body_b[-1] != "A" else "B")
        tampered = f"{header_b}.{tampered_body}.{sig_b}"
        with pytest.raises(ValueError, match="Invalid signature"):
            decode_access_token(tampered)

    def test_tampered_signature_is_rejected(self) -> None:
        token = create_access_token({"sub": "1"})
        header_b, body_b, sig_b = token.split(".")
        # Flip a character away from the tail: the final base64 char of a
        # segment can carry redundant padding bits that don't affect the
        # decoded bytes, so tamper near the front instead.
        tampered_sig = ("A" if sig_b[0] != "A" else "B") + sig_b[1:]
        tampered = f"{header_b}.{body_b}.{tampered_sig}"
        with pytest.raises(ValueError, match="Invalid signature"):
            decode_access_token(tampered)

    def test_empty_signature_segment_is_rejected(self) -> None:
        token = create_access_token({"sub": "1"})
        header_b, body_b, _ = token.split(".")
        with pytest.raises(ValueError, match="Invalid signature"):
            decode_access_token(f"{header_b}.{body_b}.")

    def test_wrong_secret_rejects_valid_structure(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "jwt_secret_key", "secret-a")
        token = create_access_token({"sub": "1"})
        monkeypatch.setattr(settings, "jwt_secret_key", "secret-b")
        with pytest.raises(ValueError, match="Invalid signature"):
            decode_access_token(token)

    def test_alg_none_style_forgery_is_rejected(self) -> None:
        # Craft a token claiming alg "none" with an empty signature --
        # decode_access_token must ignore the header and still verify HMAC.
        header = _b64url_encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        body = _b64url_encode(json.dumps({"sub": "1"}).encode())
        forged = f"{header}.{body}."
        with pytest.raises(ValueError, match="Invalid signature"):
            decode_access_token(forged)

    # -- expiry boundary --------------------------------------------------

    def test_exp_equal_to_now_is_not_expired(self, monkeypatch) -> None:
        fixed = 1_700_000_000
        monkeypatch.setattr(auth_module.time, "time", lambda: float(fixed))
        token = create_access_token({"sub": "1"}, expires_minutes=0)  # exp == iat == fixed
        payload = decode_access_token(token)  # `now == exp` at decode time too
        assert payload["exp"] == fixed

    def test_exp_plus_one_is_expired(self, monkeypatch) -> None:
        fixed = 1_700_000_000
        monkeypatch.setattr(auth_module.time, "time", lambda: float(fixed))
        token = create_access_token({"sub": "1"}, expires_minutes=0)
        monkeypatch.setattr(auth_module.time, "time", lambda: float(fixed + 1))
        with pytest.raises(ValueError, match="Token expired"):
            decode_access_token(token)

    def test_exp_zero_is_treated_as_expired(self, frozen_time: float) -> None:
        """Confirmed bug: `payload.get("exp")` is falsy for the literal
        value 0, so a token with `exp: 0` was treated as never-expiring
        instead of already-expired-at-the-epoch. Fixed by checking
        `is not None` instead of truthiness.
        """
        import hashlib
        import hmac

        header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64url_encode(json.dumps({"sub": "1", "iat": 0, "exp": 0}).encode())
        secret = (settings.jwt_secret_key or settings.secret_key).encode()
        sig = _b64url_encode(hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest())
        token = f"{header}.{body}.{sig}"
        with pytest.raises(ValueError, match="Token expired"):
            decode_access_token(token)

    def test_missing_exp_never_expires(self, frozen_time: float) -> None:
        header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64url_encode(json.dumps({"sub": "1"}).encode())
        import hashlib
        import hmac

        secret = (settings.jwt_secret_key or settings.secret_key).encode()
        sig = _b64url_encode(hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest())
        token = f"{header}.{body}.{sig}"
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert "exp" not in payload

    def test_non_json_body_raises_value_error(self) -> None:
        import hashlib
        import hmac

        header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64url_encode(b"not json")
        secret = (settings.jwt_secret_key or settings.secret_key).encode()
        sig = _b64url_encode(hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest())
        with pytest.raises(ValueError):
            decode_access_token(f"{header}.{body}.{sig}")

    def test_non_object_json_body_raises_value_error(self) -> None:
        import hashlib
        import hmac

        header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64url_encode(b"[1, 2, 3]")
        secret = (settings.jwt_secret_key or settings.secret_key).encode()
        sig = _b64url_encode(hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest())
        with pytest.raises(ValueError):
            decode_access_token(f"{header}.{body}.{sig}")

    def test_none_token_raises_value_error_not_attribute_error(self) -> None:
        with pytest.raises(ValueError):
            decode_access_token(None)  # type: ignore[arg-type]
