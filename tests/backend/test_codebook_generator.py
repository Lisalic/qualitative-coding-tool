"""Tests for backend/scripts/codebook_generator.py.

Stage 9 replaces the sync ``OpenAI(...)`` client + hand-rolled retry loop
with a call into ``external/openrouter_client.py::chat_completion`` --
these tests mock ``chat_completion`` at the seam
(``backend.scripts.codebook_generator.chat_completion``) instead of the
OpenAI SDK, and verify the response-parsing logic (percentage extraction
in ``compare_agreement``) is untouched by that plumbing swap.
"""

from unittest.mock import AsyncMock

import pytest

from backend.scripts.codebook_generator import (
    compare_agreement,
    generate_codebook,
    get_client,
)


class TestGetClient:
    async def test_no_api_key_raises(self) -> None:
        with pytest.raises(ValueError):
            await get_client("sys", "usr", "", "model-x")

    async def test_returns_chat_completion_result(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="raw llm text")
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        result = await get_client("sys prompt", "user prompt", "sk-key", "model-x")

        assert result == "raw llm text"
        mock.assert_awaited_once()
        kwargs = mock.call_args.kwargs
        assert kwargs["system_prompt"] == "sys prompt"
        assert kwargs["user_prompt"] == "user prompt"
        assert kwargs["api_key"] == "sk-key"
        assert kwargs["model"] == "model-x"
        assert kwargs["timeout"] == 300.0
        assert kwargs["use_middle_out"] is True
        assert kwargs["max_retries"] == 3


class TestGenerateCodebook:
    async def test_builds_prompts_and_returns_triple(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="Code Family: A\nCode Name: B")
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        result, system_prompt, user_prompt = await generate_codebook(
            "post one\npost two", "sk-key", custom_prompt="focus on X", MODEL="model-y"
        )

        assert result == "Code Family: A\nCode Name: B"
        assert "post one" in user_prompt
        assert "focus on X" in user_prompt
        assert "qualitative researcher" in system_prompt
        assert mock.call_args.kwargs["model"] == "model-y"


class TestCompareAgreement:
    async def test_extracts_integer_percentage(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(return_value="85%"),
        )
        result = await compare_agreement("cb a", "cb b", "sk-key")
        assert result == "85%"

    async def test_extracts_percentage_from_surrounding_text(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(return_value="The agreement is about 72.5 percent overall."),
        )
        result = await compare_agreement("cb a", "cb b", "sk-key")
        assert result == "72.5%"

    async def test_clamps_value_over_100(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(return_value="150"),
        )
        result = await compare_agreement("cb a", "cb b", "sk-key")
        assert result == "100%"

    async def test_no_number_falls_back_to_stripped_response(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(return_value="  no digits here  "),
        )
        result = await compare_agreement("cb a", "cb b", "sk-key")
        assert result == "no digits here"

    async def test_empty_response_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(return_value=""),
        )
        with pytest.raises(ValueError, match="Empty response"):
            await compare_agreement("cb a", "cb b", "sk-key")
