"""Tests for backend/scripts/codebook_generator.py.

Stage 9 replaces the sync ``OpenAI(...)`` client + hand-rolled retry loop
with a call into ``external/openrouter_client.py::chat_completion`` --
these tests mock ``chat_completion`` at the seam
(``backend.scripts.codebook_generator.chat_completion``) instead of the
OpenAI SDK.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.external.context_window import ITEM_SEPARATOR
from backend.scripts.codebook_generator import (
    generate_codebook,
    generate_codebook_map_reduce,
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
        # timeout/max_retries are now consistent across all 4 scripts (see
        # openrouter_client.chat_completion's docstring): a 30s cap and 2
        # total attempts bound one batch's worst case to ~60s instead of
        # the old 300s x 3 = ~15 minutes.
        assert kwargs["timeout"] == 30.0
        # middle-out is off now: the script no longer requests it, so
        # overflow surfaces as a real error instead of a silent truncation.
        assert kwargs.get("use_middle_out", False) is False
        assert kwargs["max_retries"] == 2

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


class TestGenerateCodebookMapReduce:
    async def test_single_batch_skips_reduce_call(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="Code Family: A\nCode Name: B")
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        result, system_prompt, user_prompt, coverage = await generate_codebook_map_reduce(
            "short data", "sk-key", custom_prompt="focus on X", MODEL="model-y"
        )

        assert mock.await_count == 1
        assert result == "Code Family: A\nCode Name: B"
        assert "qualitative researcher" in system_prompt
        assert "short data" in user_prompt
        assert coverage == {"batches_processed": 1, "batches_total": 1, "error": None}

    async def test_multiple_batches_triggers_one_reduce_call_with_all_drafts(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.context_window.max_prompt_chars",
            lambda model, **kwargs: 130,
        )
        responses = [
            "### Code Family: A\n#### Code Name: One",
            "### Code Family: B\n#### Code Name: Two",
            "### Code Family: C\n#### Code Name: Three (consolidated)",
        ]
        mock = AsyncMock(side_effect=responses)
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        result, system_prompt, user_prompt, coverage = await generate_codebook_map_reduce(
            posts_content, "sk-key", custom_prompt="focus on X", MODEL="model-y"
        )

        # 2 map calls (one per draft batch) + 1 reduce call.
        assert mock.await_count == 3
        assert result == responses[-1]
        assert "DRAFT CODEBOOKS" in system_prompt
        assert "DRAFT CODEBOOK 1" in user_prompt
        assert "DRAFT CODEBOOK 2" in user_prompt
        assert responses[0] in user_prompt
        assert responses[1] in user_prompt
        assert "focus on X" in user_prompt
        assert coverage == {"batches_processed": 3, "batches_total": 3, "error": None}

    async def test_single_batch_does_not_register_progress(self, monkeypatch) -> None:
        # No real batching happened -- nothing meaningful to report, and
        # the frontend hides the bar for total<=1 anyway.
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(return_value="Code Family: A"),
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        await generate_codebook_map_reduce("short data", "sk-key", progress=progress)

        progress.add_total.assert_not_called()
        progress.advance.assert_not_awaited()

    async def test_multiple_batches_reports_progress_for_map_and_reduce(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.context_window.max_prompt_chars",
            lambda model, **kwargs: 130,
        )
        responses = [
            "### Code Family: A\n#### Code Name: One",
            "### Code Family: B\n#### Code Name: Two",
            "### Code Family: C\n#### Code Name: Three (consolidated)",
        ]
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion", AsyncMock(side_effect=responses)
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        await generate_codebook_map_reduce(posts_content, "sk-key", progress=progress)

        # 2 map batches + 1 reduce call = 3 total units of progress.
        progress.add_total.assert_called_once_with(3)
        assert progress.advance.await_count == 3

    async def test_mid_map_failure_returns_earlier_drafts_instead_of_raising(self, monkeypatch) -> None:
        # Regression coverage: a later map batch failing (e.g. the account
        # ran out of credits) must not discard drafts already generated --
        # there's nothing coherent to reduce, so return them verbatim.
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.context_window.max_prompt_chars",
            lambda model, **kwargs: 130,
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(
                side_effect=[
                    "### Code Family: A\n#### Code Name: One",
                    ValueError("Insufficient credits: Your account or API key needs more credits."),
                ]
            ),
        )

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        result, _, _, coverage = await generate_codebook_map_reduce(posts_content, "sk-key")

        assert result == "### Code Family: A\n#### Code Name: One"
        assert coverage["batches_processed"] == 1
        assert coverage["batches_total"] == 2
        assert "Insufficient credits" in coverage["error"]

    async def test_reduce_call_failure_returns_drafts_instead_of_raising(self, monkeypatch) -> None:
        # Every map batch succeeded, but the final consolidation call
        # itself fails -- still return the (un-consolidated) drafts
        # rather than nothing.
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.context_window.max_prompt_chars",
            lambda model, **kwargs: 130,
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(
                side_effect=[
                    "### Code Family: A\n#### Code Name: One",
                    "### Code Family: B\n#### Code Name: Two",
                    ValueError("Insufficient credits: Your account or API key needs more credits."),
                ]
            ),
        )

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        result, _, _, coverage = await generate_codebook_map_reduce(posts_content, "sk-key")

        assert "Code Name: One" in result
        assert "Code Name: Two" in result
        assert coverage["batches_processed"] == 2
        assert coverage["batches_total"] == 3
        assert "Insufficient credits" in coverage["error"]
