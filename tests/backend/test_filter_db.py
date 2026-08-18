"""Tests for backend/scripts/filter_db.py.

Stage 9 replaces ``get_client``'s sync ``OpenAI(...)`` client + hand-rolled
retry/empty-completion handling with
``external/openrouter_client.py::chat_completion`` -- these tests mock
``chat_completion`` at the seam (``backend.scripts.filter_db.chat_completion``)
and verify both the ``AIFilterError`` mapping (empty-completion vs. other
failures) and the ``ast.literal_eval``-based array parsing
(``wrap_in_python_array``) are unaffected by that plumbing swap.
"""

from unittest.mock import AsyncMock

import pytest

from backend.app.external.errors import ExternalServiceError
from backend.scripts.filter_db import (
    AIFilterError,
    filter_posts_with_ai,
    get_client,
    wrap_in_python_array,
)


class TestGetClient:
    async def test_no_api_key_raises_401(self) -> None:
        with pytest.raises(AIFilterError) as exc_info:
            await get_client("sys", "usr", "")
        assert exc_info.value.code == 401

    async def test_returns_chat_completion_result(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="raw response")
        monkeypatch.setattr("backend.scripts.filter_db.chat_completion", mock)

        result = await get_client("sys prompt", "user prompt", "sk-key", "model-x")

        assert result == "raw response"
        kwargs = mock.call_args.kwargs
        assert kwargs["timeout"] == 300.0
        assert kwargs["use_middle_out"] is True
        assert kwargs["max_retries"] == 3

    async def test_empty_completion_error_maps_to_friendly_502(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(side_effect=ExternalServiceError("OpenRouter returned an empty completion")),
        )

        with pytest.raises(AIFilterError) as exc_info:
            await get_client("sys", "usr", "sk-key", "model-x")

        assert exc_info.value.code == 502
        assert "no usable output" in str(exc_info.value)

    async def test_other_external_error_maps_via_openrouter_user_message(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(side_effect=ExternalServiceError("boom", code=429)),
        )

        with pytest.raises(AIFilterError) as exc_info:
            await get_client("sys", "usr", "sk-key", "model-x")

        assert exc_info.value.code == 429
        assert "Rate limited" in str(exc_info.value)


class TestFilterPostsWithAi:
    async def test_parses_ids_from_python_array_response(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value="['t3_abc', 't3_xyz']"),
        )

        ids, system_prompt, user_prompt = await filter_posts_with_ai(
            "keep the good ones", "[t3_abc] hello\n---\n[t3_xyz] world", "sk-key"
        )

        assert ids == ["t3_abc", "t3_xyz"]
        assert "content analyst" in system_prompt
        assert "keep the good ones" in user_prompt

    async def test_first_batch_failure_raises_immediately(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(side_effect=ExternalServiceError("boom", code=401)),
        )

        with pytest.raises(AIFilterError):
            await filter_posts_with_ai("criteria", "[t3_abc] hello", "sk-key")


class TestWrapInPythonArray:
    def test_parses_literal_array(self) -> None:
        assert wrap_in_python_array("['a', 'b']") == ["a", "b"]

    def test_strips_markdown_fence_before_parsing(self) -> None:
        assert wrap_in_python_array("```python\n['a', 'b']\n```") == ["a", "b"]

    def test_empty_array(self) -> None:
        assert wrap_in_python_array("[]") == []

    def test_falls_back_to_regex_on_invalid_literal(self) -> None:
        assert wrap_in_python_array('not a list but "a" and "b" are quoted') == ["a", "b"]

    def test_no_quoted_strings_returns_empty(self) -> None:
        assert wrap_in_python_array("nothing useful here") == []
