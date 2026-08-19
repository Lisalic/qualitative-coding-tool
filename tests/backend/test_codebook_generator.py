"""Tests for backend/scripts/codebook_generator.py.

Stage 9 replaces the sync ``OpenAI(...)`` client + hand-rolled retry loop
with a call into ``external/openrouter_client.py::chat_completion`` --
these tests mock ``chat_completion`` at the seam
(``backend.scripts.codebook_generator.chat_completion``) instead of the
OpenAI SDK.
"""

from unittest.mock import AsyncMock

import pytest

from backend.scripts.codebook_generator import generate_codebook, get_client


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

    async def test_strips_markdown_fence_wrapper(self, monkeypatch) -> None:
        # generate_codebook/compare_codebooks/compare_codings/summarize_coding
        # all go through this one seam -- an LLM that ignores "return plain
        # text" and wraps its whole answer in a ```markdown fence should
        # come out clean here rather than rendering as a raw, unwrapped code
        # block in every viewer that displays this text.
        mock = AsyncMock(return_value="```markdown\n# Heading\n\nSome **text**.\n```")
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        result = await get_client("sys prompt", "user prompt", "sk-key", "model-x")

        assert result == "# Heading\n\nSome **text**."


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
