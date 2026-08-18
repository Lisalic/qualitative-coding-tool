"""Tests for backend/scripts/codebook_apply.py.

Stage 9 replaces ``get_client``'s sync ``OpenAI(...)`` client + retry loop
with ``external/openrouter_client.py::chat_completion`` -- these tests
mock ``chat_completion`` at the seam
(``backend.scripts.codebook_apply.chat_completion``) and verify the
POST_ID/CODE/EVIDENCE DSL parsing (``classify_posts`` ->
``normalize_coding_output``/``validate_coding_output``) is unaffected by
that plumbing swap.
"""

from unittest.mock import AsyncMock

import pytest

from backend.scripts.codebook_apply import classify_posts, get_client


class TestGetClient:
    async def test_no_api_key_raises(self) -> None:
        with pytest.raises(ValueError):
            await get_client("sys", "usr", "")

    async def test_returns_chat_completion_result_with_short_timeout(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="raw output")
        monkeypatch.setattr("backend.scripts.codebook_apply.chat_completion", mock)

        result = await get_client("sys prompt", "user prompt", "sk-key", "model-x")

        assert result == "raw output"
        kwargs = mock.call_args.kwargs
        assert kwargs["model"] == "model-x"
        # codebook_apply's timeout is deliberately shorter than the other
        # 3 scripts' 300s -- confirm the distinct value survived the move.
        assert kwargs["timeout"] == 30.0
        assert kwargs["use_middle_out"] is True
        assert kwargs["max_retries"] == 3


class TestClassifyPosts:
    async def test_canonical_output_survives_normalize_and_validate(self, monkeypatch) -> None:
        raw = (
            "POST_ID: p1\n"
            "CODE: Alpha\n"
            'EVIDENCE: "quote one"\n'
            "POST_ID: p2\n"
            "CODE: Beta\n"
            'EVIDENCE: "quote two"§"quote three"\n'
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.chat_completion", AsyncMock(return_value=raw)
        )

        result, system_prompt, user_prompt = await classify_posts(
            "CODEBOOK TEXT", "POSTS CONTENT", "be thorough", "sk-key"
        )

        assert "POST_ID: p1" in result
        assert "CODE: Alpha" in result
        assert 'EVIDENCE: "quote one"' in result
        assert "CODEBOOK TEXT" in user_prompt
        assert "POSTS CONTENT" in user_prompt
        assert "qualitative data coder" in system_prompt

    async def test_output_failing_validation_falls_back_to_raw_text(self, monkeypatch) -> None:
        # Not a valid POST_ID:/CODE:/EVIDENCE: block at all -- normalization
        # produces nothing usable, so classify_posts must fall back to the
        # raw (stripped) AI text rather than an empty string.
        raw = "  some unstructured free-form text with no post markers  "
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.chat_completion", AsyncMock(return_value=raw)
        )

        result, _, _ = await classify_posts("CB", "POSTS", "", "sk-key")

        assert result == raw.strip()

    async def test_uses_explicit_model_when_given(self, monkeypatch) -> None:
        mock = AsyncMock(return_value='POST_ID: p1\nCODE: A\nEVIDENCE: "x"\n')
        monkeypatch.setattr("backend.scripts.codebook_apply.chat_completion", mock)

        await classify_posts("CB", "POSTS", "", "sk-key", model="custom/model")

        assert mock.call_args.kwargs["model"] == "custom/model"
