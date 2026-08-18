"""Tests for backend/scripts/openrouter_http.py."""

import pytest

from backend.scripts.openrouter_http import (
    OPENROUTER_CLIENT_ERROR_CODES,
    OPENROUTER_HTTP_MESSAGES,
    openrouter_user_message,
)


def test_client_error_codes_matches_message_keys() -> None:
    """Regression guard: the comment says these are the codes passed
    through to the client (not remapped to 502) -- keep the two in sync.
    """
    assert set(OPENROUTER_HTTP_MESSAGES) == OPENROUTER_CLIENT_ERROR_CODES


def test_client_error_codes_is_immutable() -> None:
    assert isinstance(OPENROUTER_CLIENT_ERROR_CODES, frozenset)


@pytest.mark.parametrize("code", [400, 401, 402, 403, 404, 408, 429, 502, 503])
def test_every_known_code_has_a_message(code: int) -> None:
    msg = openrouter_user_message(code)
    assert msg == OPENROUTER_HTTP_MESSAGES[code]
    assert isinstance(msg, str) and msg


@pytest.mark.parametrize("code", [500, 0, -1, 999, 504])
def test_unknown_code_falls_back_to_generic_message(code: int) -> None:
    assert openrouter_user_message(code) == f"API error (code {code})"


def test_504_is_not_in_the_known_set() -> None:
    # 502/503 are present but 504 is not -- pin this so it isn't
    # "silently fixed" by someone assuming it's an oversight.
    assert 504 not in OPENROUTER_CLIENT_ERROR_CODES


def test_404_appends_stripped_model_slug() -> None:
    msg = openrouter_user_message(404, "  openai/gpt-4  ")
    assert msg.startswith(OPENROUTER_HTTP_MESSAGES[404])
    assert msg == f"{OPENROUTER_HTTP_MESSAGES[404]} Requested model: openai/gpt-4"


@pytest.mark.parametrize("slug", ["", "   ", None])
def test_404_with_blank_slug_has_no_suffix(slug) -> None:
    assert openrouter_user_message(404, slug) == OPENROUTER_HTTP_MESSAGES[404]


def test_404_default_slug_argument() -> None:
    assert openrouter_user_message(404) == OPENROUTER_HTTP_MESSAGES[404]


def test_non_404_code_ignores_slug() -> None:
    msg = openrouter_user_message(429, "some/model")
    assert msg == OPENROUTER_HTTP_MESSAGES[429]
    assert "some/model" not in msg


def test_string_code_never_matches_dict_lookup() -> None:
    assert openrouter_user_message("404", "x/y") == "API error (code 404)"


def test_float_404_hits_the_int_key_via_hash_equality() -> None:
    # 404.0 == 404 and hash(404.0) == hash(404), so dict.get(404.0) hits
    # the int key -- and `code == 404` is also True, so the slug suffix
    # is appended too.
    msg = openrouter_user_message(404.0, "x/y")  # type: ignore[arg-type]
    assert msg == f"{OPENROUTER_HTTP_MESSAGES[404]} Requested model: x/y"
