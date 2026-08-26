"""Tests for backend/scripts/filter_db.py.

Stage 9 replaces ``get_client``'s sync ``OpenAI(...)`` client + hand-rolled
retry/empty-completion handling with
``external/openrouter_client.py::chat_completion`` -- these tests mock
``chat_completion`` at the seam (``backend.scripts.filter_db.chat_completion``)
and verify both the ``AIFilterError`` mapping (empty-completion vs. other
failures) and the ``ast.literal_eval``-based array parsing
(``wrap_in_python_array``) are unaffected by that plumbing swap.
"""

from unittest.mock import AsyncMock, MagicMock

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
        # timeout/max_retries are now consistent across all 4 scripts (see
        # openrouter_client.chat_completion's docstring): a 30s cap and 2
        # total attempts bound one batch's worst case to ~60s instead of
        # the old 300s x 3 = ~15 minutes.
        assert kwargs["timeout"] == 30.0
        # middle-out is off now: the script no longer requests it, so
        # overflow surfaces as a real error instead of a silent truncation.
        assert kwargs.get("use_middle_out", False) is False
        assert kwargs["max_retries"] == 2

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

        ids, system_prompt, user_prompt, coverage = await filter_posts_with_ai(
            "keep the good ones", "[t3_abc] hello\n---\n[t3_xyz] world", "sk-key"
        )

        assert ids == ["t3_abc", "t3_xyz"]
        assert "content analyst" in system_prompt
        assert "keep the good ones" in user_prompt
        assert coverage == {"batches_processed": 1, "batches_total": 1, "error": None}

    async def test_first_batch_failure_raises_immediately(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(side_effect=ExternalServiceError("boom", code=401)),
        )

        with pytest.raises(AIFilterError):
            await filter_posts_with_ai("criteria", "[t3_abc] hello", "sk-key")

    async def test_free_model_batch_cap_reports_partial_coverage(self, monkeypatch) -> None:
        # Force many small batches by capping the per-batch char budget, so
        # a free model hits MAX_BATCHES_FOR_FREE and the drop must be
        # visible in `coverage` instead of silently vanishing.
        monkeypatch.setattr(
            "backend.app.external.context_window.max_prompt_chars", lambda model, **kwargs: 40
        )
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value="[]"),
        )

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(10)])
        ids, _, _, coverage = await filter_posts_with_ai("criteria", content, "sk-key", model="")

        assert coverage["batches_total"] > 3
        assert coverage["batches_processed"] == 3

    async def test_paid_model_processes_all_batches(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.external.context_window.max_prompt_chars", lambda model, **kwargs: 40
        )
        monkeypatch.setattr("backend.scripts.filter_db.is_paid_model", lambda slug: True)
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value="[]"),
        )

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(10)])
        ids, _, _, coverage = await filter_posts_with_ai("criteria", content, "sk-key", model="paid/model")

        assert coverage["batches_processed"] == coverage["batches_total"]

    async def test_reports_progress_once_per_batch(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.external.context_window.max_prompt_chars", lambda model, **kwargs: 40
        )
        monkeypatch.setattr("backend.scripts.filter_db.is_paid_model", lambda slug: True)
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value="[]"),
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(5)])
        _, _, _, coverage = await filter_posts_with_ai("criteria", content, "sk-key", progress=progress)

        progress.add_total.assert_called_once_with(coverage["batches_total"])
        assert progress.advance.await_count == coverage["batches_total"]

    async def test_no_progress_arg_does_not_raise(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value="['t3_abc']"),
        )
        await filter_posts_with_ai("criteria", "[t3_abc] hello", "sk-key")

    async def test_mid_run_failure_returns_ids_from_earlier_batches_instead_of_raising(
        self, monkeypatch
    ) -> None:
        # Regression coverage: a later batch failing (e.g. the account ran
        # out of credits mid-run) must not discard IDs already extracted
        # from earlier, successful batches.
        monkeypatch.setattr(
            "backend.app.external.context_window.max_prompt_chars", lambda model, **kwargs: 40
        )
        monkeypatch.setattr("backend.scripts.filter_db.is_paid_model", lambda slug: True)
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(
                side_effect=[
                    "['t3_0']",
                    ExternalServiceError("Insufficient credits", code=402),
                    "['t3_2']",
                ]
            ),
        )

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(3)])
        ids, _, _, coverage = await filter_posts_with_ai("criteria", content, "sk-key", model="paid/model")

        assert ids == ["t3_0"]
        assert coverage["batches_processed"] == 1
        assert coverage["batches_total"] == 3
        assert "Insufficient credits" in coverage["error"]


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
