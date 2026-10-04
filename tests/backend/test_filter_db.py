"""Tests for backend/scripts/filter_db.py.

Covers the two-way AI triage contract (``{"include": [...], "exclude": [...]}``,
parsed by ``parse_decision_object``) that replaced the old "array of ids to
keep" contract, plus the ``get_client`` retry/error-mapping plumbing these
tests already exercised (mocking ``chat_completion`` at the seam
``backend.scripts.filter_db.chat_completion``).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.external.errors import ExternalServiceError
from backend.scripts.filter_db import (
    AIFilterError,
    get_client,
    parse_decision_object,
    triage_posts_with_ai,
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
        # timeout/max_retries are consistent across all 4 scripts (see
        # openrouter_client.chat_completion's docstring): a 30s cap and 2
        # total attempts bound one batch's worst case to ~60s instead of
        # the old 300s x 3 = ~15 minutes.
        assert kwargs["timeout"] == 30.0
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


class TestTriagePostsWithAi:
    async def test_parses_include_and_exclude_from_decision_object(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": ["t3_abc"], "exclude": ["t3_xyz"]}'),
        )

        include_ids, exclude_ids, system_prompt, user_prompt, coverage = await triage_posts_with_ai(
            "keep the good ones", "drop the spam", "", "[t3_abc] hello\n---\n[t3_xyz] world", "sk-key"
        )

        assert include_ids == ["t3_abc"]
        assert exclude_ids == ["t3_xyz"]
        assert "content analyst" in system_prompt
        assert "keep the good ones" in user_prompt
        assert "drop the spam" in user_prompt
        assert coverage == {"batches_processed": 1, "batches_total": 1, "error": None}

    async def test_examples_block_rendered_in_prompt_and_criteria_omitted(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": [], "exclude": []}'),
        )

        _, _, _, user_prompt, _ = await triage_posts_with_ai(
            "", "", "INCLUDED:\n[t3_1] good one", "[t3_abc] hello", "sk-key"
        )

        assert "PRIOR DECISIONS" in user_prompt
        assert "[t3_1] good one" in user_prompt
        assert "INCLUDE criteria" not in user_prompt
        assert "EXCLUDE criteria" not in user_prompt

    async def test_ids_not_in_batch_are_dropped(self, monkeypatch) -> None:
        # A hallucinated id (not present in the batch's [ID] markers) must
        # never be applied to a row -- there is no such row on the editor
        # side to mark.
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": ["t3_abc", "made_up_id"], "exclude": []}'),
        )

        include_ids, exclude_ids, _, _, _ = await triage_posts_with_ai(
            "criteria", "", "", "[t3_abc] hello", "sk-key"
        )

        assert include_ids == ["t3_abc"]
        assert exclude_ids == []

    async def test_id_in_both_lists_counts_as_include_only(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": ["t3_abc"], "exclude": ["t3_abc"]}'),
        )

        include_ids, exclude_ids, _, _, _ = await triage_posts_with_ai(
            "criteria", "criteria2", "", "[t3_abc] hello", "sk-key"
        )

        assert include_ids == ["t3_abc"]
        assert exclude_ids == []

    async def test_first_batch_failure_raises_immediately(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(side_effect=ExternalServiceError("boom", code=401)),
        )

        with pytest.raises(AIFilterError):
            await triage_posts_with_ai("criteria", "", "", "[t3_abc] hello", "sk-key")

    async def test_free_model_batch_cap_reports_partial_coverage(self, monkeypatch) -> None:
        # Force many small batches by capping the per-batch char budget, so
        # a free model hits MAX_BATCHES_FOR_FREE and the drop must be
        # visible in `coverage` instead of silently vanishing.
        monkeypatch.setattr(
            "backend.app.external.context_window.max_prompt_chars", lambda model, **kwargs: 40
        )
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": [], "exclude": []}'),
        )

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(10)])
        _, _, _, _, coverage = await triage_posts_with_ai("criteria", "", "", content, "sk-key", model="")

        assert coverage["batches_total"] > 3
        assert coverage["batches_processed"] == 3

    async def test_paid_model_processes_all_batches(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.external.context_window.max_prompt_chars", lambda model, **kwargs: 40
        )
        monkeypatch.setattr("backend.scripts.filter_db.is_paid_model", lambda slug: True)
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": [], "exclude": []}'),
        )

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(10)])
        _, _, _, _, coverage = await triage_posts_with_ai(
            "criteria", "", "", content, "sk-key", model="paid/model"
        )

        assert coverage["batches_processed"] == coverage["batches_total"]

    async def test_reports_progress_once_per_batch(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.external.context_window.max_prompt_chars", lambda model, **kwargs: 40
        )
        monkeypatch.setattr("backend.scripts.filter_db.is_paid_model", lambda slug: True)
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": [], "exclude": []}'),
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(5)])
        _, _, _, _, coverage = await triage_posts_with_ai(
            "criteria", "", "", content, "sk-key", progress=progress
        )

        progress.add_total.assert_called_once_with(coverage["batches_total"])
        assert progress.advance.await_count == coverage["batches_total"]

    async def test_no_progress_arg_does_not_raise(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.filter_db.chat_completion",
            AsyncMock(return_value='{"include": ["t3_abc"], "exclude": []}'),
        )
        await triage_posts_with_ai("criteria", "", "", "[t3_abc] hello", "sk-key")

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
                    '{"include": ["t3_0"], "exclude": []}',
                    ExternalServiceError("Insufficient credits", code=402),
                    '{"include": ["t3_2"], "exclude": []}',
                ]
            ),
        )

        content = "\n---\n".join([f"[t3_{i}] " + ("x" * 30) for i in range(3)])
        include_ids, _, _, _, coverage = await triage_posts_with_ai(
            "criteria", "", "", content, "sk-key", model="paid/model"
        )

        assert include_ids == ["t3_0"]
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

    def test_accepts_an_already_parsed_list(self) -> None:
        assert wrap_in_python_array(["a", "b"]) == ["a", "b"]


class TestParseDecisionObject:
    def test_truncated_object_never_promotes_excluded_ids(self) -> None:
        """A reply cut off mid-way doesn't parse; the fallback used to
        scrape every quoted id, so excluded posts came back as includes.
        """
        include_ids, _ = parse_decision_object('{"include": ["a", "b"], "exclude": ["c", "d')
        assert include_ids == ["a", "b"]

    def test_json_object(self) -> None:
        include_ids, exclude_ids = parse_decision_object('{"include": ["a"], "exclude": ["b"]}')
        assert include_ids == ["a"]
        assert exclude_ids == ["b"]

    def test_fenced_json(self) -> None:
        include_ids, exclude_ids = parse_decision_object(
            '```json\n{"include": ["a", "b"], "exclude": []}\n```'
        )
        assert include_ids == ["a", "b"]
        assert exclude_ids == []

    def test_python_literal_object(self) -> None:
        include_ids, exclude_ids = parse_decision_object("{'include': ['a'], 'exclude': ['b']}")
        assert include_ids == ["a"]
        assert exclude_ids == ["b"]

    def test_bare_list_treated_as_include_only(self) -> None:
        include_ids, exclude_ids = parse_decision_object("['a', 'b']")
        assert include_ids == ["a", "b"]
        assert exclude_ids == []

    def test_missing_keys_default_to_empty(self) -> None:
        include_ids, exclude_ids = parse_decision_object('{"include": ["a"]}')
        assert include_ids == ["a"]
        assert exclude_ids == []

    def test_garbage_falls_back_to_regex_include_only(self) -> None:
        include_ids, exclude_ids = parse_decision_object('not json but "a" is quoted')
        assert include_ids == ["a"]
        assert exclude_ids == []
