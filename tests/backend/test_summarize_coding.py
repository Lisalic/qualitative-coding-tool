"""Tests for backend/scripts/summarize_coding.py.

``summarize_coding`` goes through ``codebook_generator.get_client`` (the
same seam ``generate_codebook``/``compare_codebooks``/``compare_codings``
use) rather than importing ``chat_completion`` itself, so these tests mock
it at ``backend.scripts.codebook_generator.chat_completion``, where
``get_client`` actually calls it.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.scripts.summarize_coding import (
    build_aggregated_coding_data,
    summarize_coding,
)


class TestBuildAggregatedCodingData:
    def test_renders_code_count_and_evidence(self) -> None:
        code_summaries = [
            {"code": "CODE_A", "count": 3, "sample_evidence": ["quote one", "quote two"]},
        ]
        text = build_aggregated_coding_data(code_summaries)
        assert "CODE: CODE_A (used 3 times)" in text
        assert '- "quote one"' in text
        assert '- "quote two"' in text

    def test_code_with_no_evidence_omits_evidence_block(self) -> None:
        code_summaries = [{"code": "CODE_A", "count": 1, "sample_evidence": []}]
        text = build_aggregated_coding_data(code_summaries)
        assert text == "CODE: CODE_A (used 1 times)"

    def test_multiple_codes_joined_with_blank_line(self) -> None:
        code_summaries = [
            {"code": "CODE_A", "count": 1, "sample_evidence": []},
            {"code": "CODE_B", "count": 2, "sample_evidence": []},
        ]
        text = build_aggregated_coding_data(code_summaries)
        assert "CODE_A" in text.split("\n\n")[0]
        assert "CODE_B" in text.split("\n\n")[1]

    def test_empty_list_returns_empty_string(self) -> None:
        assert build_aggregated_coding_data([]) == ""


class TestSummarizeCoding:
    async def test_missing_coding_data_raises(self) -> None:
        with pytest.raises(ValueError, match="Coding data is required"):
            await summarize_coding("", api_key="sk-key")

    async def test_missing_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="API key is required"):
            await summarize_coding("some data", api_key="")

    async def test_single_batch_returns_llm_response_directly(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="the summary")
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        result, coverage = await summarize_coding("CODE: A (used 1 times)", api_key="sk-key")

        assert result == "the summary"
        assert mock.await_count == 1
        assert coverage == {"batches_processed": 1, "batches_total": 1, "error": None}

    async def test_llm_failure_wrapped_in_value_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(side_effect=RuntimeError("boom")),
        )

        with pytest.raises(ValueError, match="Failed to generate summary"):
            await summarize_coding("some data", api_key="sk-key")

    async def test_large_input_batches_and_reduces(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.context_window.max_prompt_chars",
            lambda model, **kwargs: 50,
        )
        responses = [
            "partial summary one",
            "partial summary two",
            "final combined summary",
        ]
        mock = AsyncMock(side_effect=responses)
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        coding_data = "\n\n".join(["x" * 40, "y" * 40])
        result, coverage = await summarize_coding(coding_data, api_key="sk-key")

        assert mock.await_count == 3
        assert result == "final combined summary"
        assert coverage == {"batches_processed": 3, "batches_total": 3, "error": None}
        reduce_call_user_prompt = mock.call_args_list[-1].kwargs["user_prompt"]
        assert "PARTIAL SUMMARY 1" in reduce_call_user_prompt
        assert "partial summary one" in reduce_call_user_prompt
        assert "partial summary two" in reduce_call_user_prompt

    async def test_single_batch_does_not_register_progress(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(return_value="the summary"),
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        await summarize_coding("CODE: A (used 1 times)", api_key="sk-key", progress=progress)

        progress.add_total.assert_not_called()
        progress.advance.assert_not_awaited()

    async def test_large_input_reports_progress_for_map_and_reduce(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.context_window.max_prompt_chars",
            lambda model, **kwargs: 50,
        )
        responses = ["partial summary one", "partial summary two", "final combined summary"]
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion", AsyncMock(side_effect=responses)
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        coding_data = "\n\n".join(["x" * 40, "y" * 40])
        await summarize_coding(coding_data, api_key="sk-key", progress=progress)

        # 2 map batches + 1 reduce call = 3 total units of progress.
        progress.add_total.assert_called_once_with(3)
        assert progress.advance.await_count == 3

    async def test_mid_map_failure_returns_earlier_partial_summaries_instead_of_raising(
        self, monkeypatch
    ) -> None:
        # Regression coverage: a later map batch failing (e.g. the account
        # ran out of credits) must not discard partial summaries already
        # written -- there's nothing coherent to combine, so return them
        # verbatim.
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.context_window.max_prompt_chars",
            lambda model, **kwargs: 50,
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(
                side_effect=[
                    "partial summary one",
                    ValueError("Insufficient credits: Your account or API key needs more credits."),
                ]
            ),
        )

        coding_data = "\n\n".join(["x" * 40, "y" * 40])
        result, coverage = await summarize_coding(coding_data, api_key="sk-key")

        assert result == "partial summary one"
        assert coverage["batches_processed"] == 1
        assert coverage["batches_total"] == 2
        assert "Insufficient credits" in coverage["error"]

    async def test_reduce_call_failure_returns_partial_summaries_instead_of_raising(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "backend.scripts.summarize_coding.context_window.max_prompt_chars",
            lambda model, **kwargs: 50,
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.chat_completion",
            AsyncMock(
                side_effect=[
                    "partial summary one",
                    "partial summary two",
                    ValueError("Insufficient credits: Your account or API key needs more credits."),
                ]
            ),
        )

        coding_data = "\n\n".join(["x" * 40, "y" * 40])
        result, coverage = await summarize_coding(coding_data, api_key="sk-key")

        assert "partial summary one" in result
        assert "partial summary two" in result
        assert coverage["batches_processed"] == 2
        assert coverage["batches_total"] == 3
        assert "Insufficient credits" in coverage["error"]
