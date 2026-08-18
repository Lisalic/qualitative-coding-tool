"""Tests for backend/app/api/utils.py.

Covers: normalize_schema, is_proj_schema, get_user_id_from_request,
_hash_password, _verify_password.

Two of these tests (test_bearer_with_no_token_* and
test_sub_as_list_returns_none_not_typeerror) assert the FIXED behavior for
confirmed bugs -- see Part 3 of the plan. Before the fix they fail with
IndexError / TypeError instead of returning None.
"""

import re

import pytest

from backend.app.api.utils import (
    _hash_password,
    _verify_password,
    get_user_id_from_request,
)
from backend.app.core.schema_guard import is_proj_schema, normalize_schema


# ---------------------------------------------------------------------------
# normalize_schema
# ---------------------------------------------------------------------------


class TestNormalizeSchema:
    def test_none_returns_empty_string(self) -> None:
        assert normalize_schema(None) == ""

    @pytest.mark.parametrize("raw", ["", "   ", "\t\n", "\xa0"])
    def test_blank_variants_return_empty_string(self, raw: str) -> None:
        assert normalize_schema(raw) == ""

    def test_strips_trailing_db_suffix(self) -> None:
        assert normalize_schema("proj_a.db") == "proj_a"

    def test_strips_surrounding_whitespace_then_suffix(self) -> None:
        assert normalize_schema("  proj_a.db  ") == "proj_a"

    def test_strip_happens_before_suffix_check_leaving_residue(self) -> None:
        # `.strip()` runs first, so an internal space right before `.db`
        # is NOT re-stripped after truncation -- a real gotcha.
        assert normalize_schema("proj_a .db") == "proj_a "

    def test_only_one_trailing_db_suffix_is_removed(self) -> None:
        assert normalize_schema("proj_a.db.db") == "proj_a.db"

    def test_case_sensitive_suffix(self) -> None:
        assert normalize_schema("proj_a.DB") == "proj_a.DB"

    def test_dot_db_alone_becomes_empty(self) -> None:
        assert normalize_schema(".db") == ""

    def test_does_not_validate_structure(self) -> None:
        assert normalize_schema("'; DROP TABLE x--") == "'; DROP TABLE x--"


# ---------------------------------------------------------------------------
# is_proj_schema
# ---------------------------------------------------------------------------


class TestIsProjSchema:
    @pytest.mark.parametrize(
        "name",
        ["proj_a", "proj_A9", "proj__", "proj_0", "proj_" + "a" * 500],
    )
    def test_valid_names(self, name: str) -> None:
        assert is_proj_schema(name) is True

    @pytest.mark.parametrize("name", [None, ""])
    def test_none_and_empty_are_false(self, name) -> None:
        assert is_proj_schema(name) is False

    def test_bare_prefix_with_no_suffix_is_false(self) -> None:
        # The `+` quantifier requires at least one trailing char.
        assert is_proj_schema("proj_") is False

    def test_trailing_newline_hole(self) -> None:
        # Classic Python-regex `$`-matches-before-trailing-newline gap.
        assert is_proj_schema("proj_a\n") is True
        assert is_proj_schema("proj_a\nx") is False

    def test_case_sensitive_prefix(self) -> None:
        assert is_proj_schema("PROJ_a") is False
        assert is_proj_schema("Proj_a") is False

    def test_leading_whitespace_rejected(self) -> None:
        assert is_proj_schema(" proj_a") is False

    @pytest.mark.parametrize("name", ["proj_a-b", "proj_a.db", "proj_a b"])
    def test_disallowed_characters_rejected(self, name: str) -> None:
        assert is_proj_schema(name) is False

    def test_ascii_only_character_class(self) -> None:
        assert is_proj_schema("proj_é") is False


# ---------------------------------------------------------------------------
# get_user_id_from_request
# ---------------------------------------------------------------------------


class TestGetUserIdFromRequest:
    def test_valid_cookie_token(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub="42")})
        assert get_user_id_from_request(req) == 42

    def test_valid_bearer_header_token(self, fake_request, make_token) -> None:
        req = fake_request(headers={"Authorization": f"Bearer {make_token(sub='7')}"})
        assert get_user_id_from_request(req) == 7

    def test_bearer_scheme_is_case_insensitive(self, fake_request, make_token) -> None:
        tok = make_token(sub="7")
        req = fake_request(headers={"Authorization": f"bearer {tok}"})
        assert get_user_id_from_request(req) == 7
        req2 = fake_request(headers={"Authorization": f"BeArEr {tok}"})
        assert get_user_id_from_request(req2) == 7

    def test_cookie_wins_over_header(self, fake_request, make_token) -> None:
        req = fake_request(
            cookies={"access_token": make_token(sub="1")},
            headers={"Authorization": f"Bearer {make_token(sub='2')}"},
        )
        assert get_user_id_from_request(req) == 1

    def test_invalid_cookie_short_circuits_valid_header(self, fake_request, make_token) -> None:
        # A present-but-garbage cookie must NOT fall through to a valid
        # header: `if not token` only re-checks the header when the cookie
        # itself was falsy, not when it merely failed to decode.
        req = fake_request(
            cookies={"access_token": "garbage-not-a-jwt"},
            headers={"Authorization": f"Bearer {make_token(sub='2')}"},
        )
        assert get_user_id_from_request(req) is None

    def test_empty_string_cookie_falls_through_to_header(self, fake_request, make_token) -> None:
        req = fake_request(
            cookies={"access_token": ""},
            headers={"Authorization": f"Bearer {make_token(sub='2')}"},
        )
        assert get_user_id_from_request(req) == 2

    @pytest.mark.parametrize("scheme", ["Token abc", "Basic abc"])
    def test_non_bearer_scheme_returns_none(self, fake_request, scheme: str) -> None:
        req = fake_request(headers={"Authorization": scheme})
        assert get_user_id_from_request(req) is None

    def test_no_cookie_no_header_returns_none(self, fake_request) -> None:
        assert get_user_id_from_request(fake_request()) is None

    def test_object_without_headers_attr(self, fake_request) -> None:
        class Bare:
            cookies: dict = {}

        assert get_user_id_from_request(Bare()) is None

    def test_cookies_property_raising_falls_through_to_header(self, make_token) -> None:
        class RaisingCookies:
            @property
            def cookies(self):
                raise RuntimeError("boom")

            headers = {"Authorization": f"Bearer {make_token(sub='9')}"}

        assert get_user_id_from_request(RaisingCookies()) == 9

    def test_expired_cookie_token_returns_none(self, fake_request) -> None:
        from backend.app.auth import create_access_token

        expired = create_access_token({"sub": "1"}, expires_minutes=-10)
        req = fake_request(cookies={"access_token": expired})
        assert get_user_id_from_request(req) is None

    # -- sub coercion -------------------------------------------------

    def test_sub_missing_returns_none(self, fake_request, make_token) -> None:
        # make_token always sets sub, so build a payload without it directly.
        from backend.app.auth import create_access_token

        token = create_access_token({"email": "a@b.com"})
        req = fake_request(cookies={"access_token": token})
        assert get_user_id_from_request(req) is None

    def test_sub_none_returns_none(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub=None)})
        assert get_user_id_from_request(req) is None

    def test_sub_numeric_string_with_whitespace(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub="  42  ")})
        assert get_user_id_from_request(req) == 42

    def test_sub_int(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub=42)})
        assert get_user_id_from_request(req) == 42

    def test_sub_non_numeric_string_returns_none(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub="abc")})
        assert get_user_id_from_request(req) is None

    def test_sub_float_is_truncated(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub=4.9)})
        assert get_user_id_from_request(req) == 4

    def test_sub_bool_false_is_valid_zero(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub=False)})
        assert get_user_id_from_request(req) == 0

    # -- confirmed-bug fixes: must not surface as 500-worthy exceptions --

    def test_bearer_with_only_scheme_and_space_returns_none(self, fake_request) -> None:
        """Confirmed bug: 'Bearer ' (trailing space, no token) used to raise
        an uncaught IndexError from `auth.split(None, 1)[1]`. Fixed to
        return None so the caller can respond 401 instead of crashing 500.
        """
        req = fake_request(headers={"Authorization": "Bearer "})
        assert get_user_id_from_request(req) is None

    def test_bearer_with_only_whitespace_remainder_returns_none(self, fake_request) -> None:
        req = fake_request(headers={"Authorization": "bearer   "})
        assert get_user_id_from_request(req) is None

    def test_sub_as_list_returns_none_not_typeerror(self, fake_request, make_token) -> None:
        """Confirmed bug: a non-scalar `sub` (e.g. a list) used to raise an
        uncaught TypeError from `int(sub)`, since only ValueError was
        caught. Fixed to also catch TypeError and return None.
        """
        req = fake_request(cookies={"access_token": make_token(sub=["1"])})
        assert get_user_id_from_request(req) is None

    def test_sub_as_dict_returns_none_not_typeerror(self, fake_request, make_token) -> None:
        req = fake_request(cookies={"access_token": make_token(sub={"a": 1})})
        assert get_user_id_from_request(req) is None


# ---------------------------------------------------------------------------
# _hash_password / _verify_password
# ---------------------------------------------------------------------------


_HASH_FORMAT = re.compile(r"^[0-9a-f]{32}\$100000\$[0-9a-f]{64}$")


class TestPasswordHashing:
    def test_hash_format(self) -> None:
        assert _HASH_FORMAT.match(_hash_password("hello"))

    def test_same_password_hashes_differently_each_time(self) -> None:
        assert _hash_password("hello") != _hash_password("hello")

    @pytest.mark.parametrize(
        "password",
        ["", "x", "correct horse battery staple", "pässwörd", "emoji🎉", "a\x00b", "  padded  "],
    )
    def test_round_trip(self, password: str) -> None:
        stored = _hash_password(password)
        assert _verify_password(stored, password) is True

    def test_wrong_password_fails(self) -> None:
        stored = _hash_password("correct")
        assert _verify_password(stored, "incorrect") is False

    def test_case_sensitive(self) -> None:
        stored = _hash_password("Password")
        assert _verify_password(stored, "password") is False

    def test_uppercase_hex_in_stored_value_still_verifies(self) -> None:
        # Both sides are re-hexlified before comparison, so a stored value
        # using uppercase hex must still verify correctly.
        stored = _hash_password("hello")
        salt_hex, iters, hash_hex = stored.split("$")
        upper_stored = f"{salt_hex.upper()}${iters}${hash_hex.upper()}"
        assert _verify_password(upper_stored, "hello") is True

    @pytest.mark.parametrize(
        "stored",
        [
            "",
            "onlyonepart",
            "a$b",
            "a$b$c$d",
            None,
            "zz$100000$aa",  # non-hex salt
            "aa$abc$aa",  # non-numeric iterations
            "aa$0$aa",  # iterations must be > 0
            "aa$-1$aa",
        ],
    )
    def test_malformed_stored_value_fails_closed(self, stored) -> None:
        assert _verify_password(stored, "anything") is False

    def test_iteration_mismatch_fails(self) -> None:
        stored = _hash_password("hello")
        salt_hex, _, hash_hex = stored.split("$")
        tampered = f"{salt_hex}$99999$hash_hex"
        assert _verify_password(tampered, "hello") is False

    def test_salt_mismatch_fails(self) -> None:
        stored = _hash_password("hello")
        salt_hex, iters, hash_hex = stored.split("$")
        flipped = ("00" if salt_hex[:2] != "00" else "11") + salt_hex[2:]
        tampered = f"{flipped}${iters}${hash_hex}"
        assert _verify_password(tampered, "hello") is False

    def test_provided_none_fails_closed(self) -> None:
        stored = _hash_password("hello")
        assert _verify_password(stored, None) is False  # type: ignore[arg-type]
