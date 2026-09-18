"""Tests for backend/app/external/context_window.py.

The shared batching/context-limit primitive that generalizes what used to
be private helpers in ``backend/scripts/filter_db.py``
(``MODEL_CONTEXT_LIMITS``/``_estimate_context_limit``/``_batch_content``).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.core.exceptions import ContextBudgetError
from backend.app.external import context_window


class TestGetContextLength:
    def test_known_slug_from_real_catalog(self) -> None:
        from backend.app import ai_models

        slug = next(m["value"] for m in ai_models.AI_MODELS if m.get("context_length"))
        expected = ai_models._MODEL_META_BY_SLUG[slug]["context_length"]
        assert context_window.get_context_length(slug) == expected

    def test_unknown_slug_falls_back_to_default(self) -> None:
        assert context_window.get_context_length("not/a/real-model") == 32_000


class TestEstimateTokens:
    def test_chars_over_four(self) -> None:
        assert context_window.estimate_tokens("a" * 400) == 100

    def test_empty_string(self) -> None:
        assert context_window.estimate_tokens("") == 0

    def test_none_treated_as_empty(self) -> None:
        assert context_window.estimate_tokens(None) == 0


class TestMaxPromptChars:
    def test_splits_window_into_scaffold_output_and_utilized_input(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_000)
        # window = 10,000 tok * 4 = 40,000 chars; - 500 scaffold - 0 output
        # = 39,500; * 0.5 utilization = 19,750.
        assert (
            context_window.max_prompt_chars("any-model", reserved_chars=500, output_reserve_tokens=0)
            == 19_750
        )

    def test_subtracts_output_reserve_before_applying_utilization(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_000)
        # 40,000 - 500 scaffold - (1,000 tok * 4) output = 35,500; * 0.5 = 17,750.
        assert (
            context_window.max_prompt_chars("any-model", reserved_chars=500, output_reserve_tokens=1_000)
            == 17_750
        )

    def test_utilization_override_is_applied(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_000)
        # 40,000 - 0 - 0 = 40,000; * 0.25 = 10,000.
        assert (
            context_window.max_prompt_chars(
                "any-model", reserved_chars=0, output_reserve_tokens=0, utilization=0.25
            )
            == 10_000
        )

    def test_raises_context_budget_error_when_fixed_parts_exceed_window(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 100)
        # 400 chars of window, but scaffolding alone asks for 1,000,000.
        with pytest.raises(ContextBudgetError):
            context_window.max_prompt_chars(
                "tiny-model", reserved_chars=1_000_000, output_reserve_tokens=0
            )


class TestProportionalOutputReserve:
    def test_returns_share_of_window_in_tokens(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_000)
        assert context_window.proportional_output_reserve("any-model", 0.15) == 1_500

    def test_truncates_to_int(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_001)
        # 10,001 * 0.15 = 1,500.15 -> 1,500
        assert context_window.proportional_output_reserve("any-model", 0.15) == 1_500


class TestPromptFits:
    def test_true_at_utilized_budget_boundary(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_000)
        # budget = (40,000 - 0) * 0.5 = 20,000
        assert context_window.prompt_fits("m", prompt_chars=20_000, output_reserve_tokens=0) is True

    def test_false_just_over_utilized_budget(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_000)
        assert context_window.prompt_fits("m", prompt_chars=20_001, output_reserve_tokens=0) is False

    def test_output_reserve_shrinks_the_budget(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 10_000)
        # (40,000 - 1,000 tok * 4) * 0.5 = 18,000
        assert context_window.prompt_fits("m", prompt_chars=18_000, output_reserve_tokens=1_000) is True
        assert context_window.prompt_fits("m", prompt_chars=18_001, output_reserve_tokens=1_000) is False

    def test_false_when_output_reserve_alone_exceeds_window(self, monkeypatch) -> None:
        monkeypatch.setattr(context_window, "get_context_length", lambda model: 100)
        assert context_window.prompt_fits("m", prompt_chars=1, output_reserve_tokens=1_000_000) is False


class TestBatchBySeparator:
    def test_content_under_limit_returns_single_batch(self) -> None:
        assert context_window.batch_by_separator("short content", 1000) == ["short content"]

    def test_splits_on_separator_boundaries(self) -> None:
        content = "\n---\n".join(["a" * 40, "b" * 40, "c" * 40])
        batches = context_window.batch_by_separator(content, max_chars=50)
        assert len(batches) == 3
        assert batches[0] == "a" * 40

    def test_packs_multiple_entries_per_batch_when_they_fit(self) -> None:
        content = "\n---\n".join(["a" * 10, "b" * 10, "c" * 10])
        batches = context_window.batch_by_separator(content, max_chars=100)
        assert len(batches) == 1

    def test_empty_content_returns_single_empty_batch(self) -> None:
        assert context_window.batch_by_separator("", 100) == [""]

    def test_custom_separator(self) -> None:
        content = "\n\n".join(["x" * 40, "y" * 40])
        batches = context_window.batch_by_separator(content, max_chars=50, separator="\n\n")
        assert len(batches) == 2


class TestRunSequentialBatches:
    async def test_all_succeed(self) -> None:
        async def run_batch(i, batch):
            return f"result-{batch}"

        results, coverage = await context_window.run_sequential_batches(["a", "b", "c"], run_batch)

        assert results == ["result-a", "result-b", "result-c"]
        assert coverage == {"batches_processed": 3, "batches_total": 3, "error": None}

    async def test_first_batch_failure_raises_immediately(self) -> None:
        async def run_batch(i, batch):
            raise ValueError("insufficient credits")

        with pytest.raises(ValueError, match="insufficient credits"):
            await context_window.run_sequential_batches(["a", "b"], run_batch)

    async def test_later_batch_failure_returns_partial_results_instead_of_raising(self) -> None:
        async def run_batch(i, batch):
            if i == 2:
                raise ValueError("insufficient credits")
            return f"result-{i}"

        results, coverage = await context_window.run_sequential_batches(["a", "b", "c", "d"], run_batch)

        assert results == ["result-0", "result-1"]
        assert coverage == {"batches_processed": 2, "batches_total": 4, "error": "insufficient credits"}

    async def test_stops_at_first_failure_and_never_attempts_later_batches(self) -> None:
        attempted = []

        async def run_batch(i, batch):
            attempted.append(i)
            if i == 1:
                raise ValueError("boom")
            return i

        await context_window.run_sequential_batches(["a", "b", "c"], run_batch)

        assert attempted == [0, 1]

    async def test_progress_advances_once_per_attempted_batch_including_the_failed_one(self) -> None:
        progress = MagicMock()
        progress.advance = AsyncMock()

        async def run_batch(i, batch):
            if i == 1:
                raise ValueError("boom")
            return i

        await context_window.run_sequential_batches(["a", "b", "c"], run_batch, progress=progress)

        # Batch 0 (success) and batch 1 (failure, then stop) are attempted;
        # batch 2 never runs, so advance() is called exactly twice.
        assert progress.advance.await_count == 2

    async def test_empty_batches_returns_empty_results(self) -> None:
        async def run_batch(i, batch):
            raise AssertionError("should never be called")

        results, coverage = await context_window.run_sequential_batches([], run_batch)

        assert results == []
        assert coverage == {"batches_processed": 0, "batches_total": 0, "error": None}


class TestCoverageResultFields:
    def test_single_batch_returns_empty_dict(self) -> None:
        coverage = {"batches_processed": 1, "batches_total": 1, "error": None}
        assert context_window.coverage_result_fields(coverage) == {}

    def test_zero_batches_returns_empty_dict(self) -> None:
        coverage = {"batches_processed": 0, "batches_total": 0, "error": None}
        assert context_window.coverage_result_fields(coverage) == {}

    def test_full_multi_batch_success_reports_partial_false_with_no_error(self) -> None:
        coverage = {"batches_processed": 5, "batches_total": 5, "error": None}
        assert context_window.coverage_result_fields(coverage) == {
            "partial": False,
            "batches_processed": 5,
            "batches_total": 5,
        }

    def test_partial_multi_batch_includes_error_message(self) -> None:
        coverage = {"batches_processed": 3, "batches_total": 7, "error": "insufficient credits"}
        assert context_window.coverage_result_fields(coverage) == {
            "partial": True,
            "batches_processed": 3,
            "batches_total": 7,
            "partial_error": "insufficient credits",
        }
