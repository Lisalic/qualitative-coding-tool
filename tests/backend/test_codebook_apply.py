"""Tests for backend/scripts/codebook_apply.py.

``classify_posts`` asks the model for JSON (``{"codings": [{"item_id",
"code", "quotes"}]}``) via ``external/openrouter_client.py::
json_chat_completion`` (the 3-tier compliance ladder) rather than the old
POST_ID/CODE/EVIDENCE text DSL -- these tests mock ``json_chat_completion``
at the seam (``backend.scripts.codebook_apply.json_chat_completion``) and
verify the JSON parse (``parse_coding_response``) and per-batch merging.
Anti-hallucination validation (does the item/code/quote actually exist)
is a separate concern tested in ``tests/backend/services/test_coding_service.py``
-- ``classify_posts`` only parses structurally, it doesn't verify truth.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.external.context_window import ITEM_SEPARATOR
from backend.scripts.codebook_apply import classify_posts, get_client, parse_coding_response


def _json_response(codings: list[dict]) -> str:
    import json

    return json.dumps({"codings": codings})


class TestGetClient:
    async def test_no_api_key_raises(self) -> None:
        with pytest.raises(ValueError):
            await get_client("sys", "usr", "")

    async def test_returns_json_chat_completion_result_with_short_timeout(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="raw output")
        monkeypatch.setattr("backend.scripts.codebook_apply.json_chat_completion", mock)

        result = await get_client("sys prompt", "user prompt", "sk-key", "model-x")

        assert result == "raw output"
        kwargs = mock.call_args.kwargs
        assert kwargs["model"] == "model-x"
        # timeout/max_retries are consistent across every script that uses
        # the shared seam (see openrouter_client.chat_completion's
        # docstring): a 30s cap and 2 total attempts.
        assert kwargs["timeout"] == 30.0
        assert kwargs["max_retries"] == 2
        # The strict-schema tier of the compliance ladder is requested.
        assert kwargs["json_schema"] is not None


class TestParseCodingResponse:
    def test_parses_a_valid_payload(self) -> None:
        raw = _json_response([{"item_id": "p1", "code": "Alpha", "quotes": ["quote one"]}])
        entries = parse_coding_response(raw)
        assert entries == [{"item_id": "p1", "code": "Alpha", "quotes": ["quote one"]}]

    def test_strips_markdown_fences(self) -> None:
        raw = "```json\n" + _json_response([{"item_id": "p1", "code": "A", "quotes": ["x"]}]) + "\n```"
        entries = parse_coding_response(raw)
        assert entries == [{"item_id": "p1", "code": "A", "quotes": ["x"]}]

    def test_not_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            parse_coding_response("not json at all")

    def test_missing_codings_key_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            parse_coding_response('{"not_codings": []}')

    def test_drops_a_malformed_individual_entry_but_keeps_the_rest(self) -> None:
        import json

        raw = json.dumps({"codings": [{"item_id": "p1", "code": "A", "quotes": ["x"]}, {"missing": "fields"}]})
        entries = parse_coding_response(raw)
        assert entries == [{"item_id": "p1", "code": "A", "quotes": ["x"]}]

    def test_missing_quotes_defaults_to_empty_list(self) -> None:
        raw = '{"codings": [{"item_id": "p1", "code": "A"}]}'
        entries = parse_coding_response(raw)
        assert entries == [{"item_id": "p1", "code": "A", "quotes": []}]


class TestClassifyPosts:
    async def test_parses_and_returns_structured_entries(self, monkeypatch) -> None:
        raw = _json_response(
            [
                {"item_id": "p1", "code": "Alpha", "quotes": ["quote one"]},
                {"item_id": "p2", "code": "Beta", "quotes": ["quote two", "quote three"]},
            ]
        )
        monkeypatch.setattr("backend.scripts.codebook_apply.json_chat_completion", AsyncMock(return_value=raw))

        entries, system_prompt, user_prompt, coverage = await classify_posts(
            "CODEBOOK TEXT", "POSTS CONTENT", "be thorough", "sk-key"
        )

        assert entries == [
            {"item_id": "p1", "code": "Alpha", "quotes": ["quote one"]},
            {"item_id": "p2", "code": "Beta", "quotes": ["quote two", "quote three"]},
        ]
        assert "CODEBOOK TEXT" in user_prompt
        assert "POSTS CONTENT" in user_prompt
        assert "qualitative data coder" in system_prompt
        assert coverage == {"batches_processed": 1, "batches_total": 1, "error": None}

    async def test_output_that_cannot_be_parsed_yields_no_entries_for_that_batch(self, monkeypatch) -> None:
        raw = "  some unstructured free-form text, not JSON at all  "
        monkeypatch.setattr("backend.scripts.codebook_apply.json_chat_completion", AsyncMock(return_value=raw))

        entries, _, _, coverage = await classify_posts("CB", "POSTS", "", "sk-key")

        assert entries == []
        # The batch call itself still succeeded (no exception) -- only the
        # JSON parse of its content failed -- so coverage reports full
        # success, just with zero usable entries.
        assert coverage == {"batches_processed": 1, "batches_total": 1, "error": None}

    async def test_uses_explicit_model_when_given(self, monkeypatch) -> None:
        mock = AsyncMock(return_value=_json_response([{"item_id": "p1", "code": "A", "quotes": ["x"]}]))
        monkeypatch.setattr("backend.scripts.codebook_apply.json_chat_completion", mock)

        await classify_posts("CB", "POSTS", "", "sk-key", model="custom/model")

        assert mock.call_args.kwargs["model"] == "custom/model"

    async def test_large_posts_content_is_batched_and_entries_concatenated(self, monkeypatch) -> None:
        # Force a tiny per-batch budget so posts_content (joined the same
        # way coding_service._assemble_posts_content joins entries) splits
        # into multiple batches -- each batch's response should be parsed
        # independently and the results concatenated, since post IDs are
        # disjoint across batches by construction.
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.context_window.max_prompt_chars",
            lambda model, **kwargs: 40,
        )
        responses = [
            _json_response([{"item_id": "p1", "code": "A", "quotes": ["x"]}]),
            _json_response([{"item_id": "p2", "code": "B", "quotes": ["y"]}]),
            _json_response([{"item_id": "p3", "code": "C", "quotes": ["z"]}]),
        ]
        mock = AsyncMock(side_effect=responses)
        monkeypatch.setattr("backend.scripts.codebook_apply.json_chat_completion", mock)

        posts_content = ITEM_SEPARATOR.join([f"POST_ID: p{i}  " + ("x" * 30) for i in range(1, 4)])
        entries, _, last_user_prompt, coverage = await classify_posts("CB", posts_content, "", "sk-key")

        assert mock.await_count >= 3
        assert {e["item_id"] for e in entries} == {"p1", "p2", "p3"}
        # last_user_prompt reflects the final batch sent, matching the
        # `last_user_prompt` precedent in filter_db._run_batched_filter.
        assert "CODEBOOK" in last_user_prompt
        assert coverage == {"batches_processed": 3, "batches_total": 3, "error": None}

    async def test_a_multi_paragraph_item_is_never_split_mid_batch(self, monkeypatch) -> None:
        # Regression test: batching used to join/split on "\n\n", but
        # Reddit selftext/body routinely contains blank lines -- so a
        # single multi-paragraph item could be torn across a batch
        # boundary. ITEM_SEPARATOR is a sentinel that can't occur in
        # source text, so even under a tiny budget a single item stays
        # whole in one batch rather than being split.
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.context_window.max_prompt_chars",
            lambda model, **kwargs: 10,
        )
        mock = AsyncMock(return_value=_json_response([{"item_id": "p1", "code": "A", "quotes": ["para one"]}]))
        monkeypatch.setattr("backend.scripts.codebook_apply.json_chat_completion", mock)

        multi_paragraph_item = "POST_ID: p1\nTYPE: post\nCONTENT: para one\n\npara two\n\npara three"
        entries, _, last_user_prompt, _ = await classify_posts("CB", multi_paragraph_item, "", "sk-key")

        # Never split: exactly one call, and the whole item (both blank
        # lines intact) reached the model in a single batch.
        assert mock.await_count == 1
        assert "para one\n\npara two\n\npara three" in last_user_prompt
        assert entries == [{"item_id": "p1", "code": "A", "quotes": ["para one"]}]

    async def test_reports_progress_once_per_batch(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.context_window.max_prompt_chars",
            lambda model, **kwargs: 40,
        )
        responses = [
            _json_response([{"item_id": "p1", "code": "A", "quotes": ["x"]}]),
            _json_response([{"item_id": "p2", "code": "B", "quotes": ["y"]}]),
            _json_response([{"item_id": "p3", "code": "C", "quotes": ["z"]}]),
        ]
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.json_chat_completion", AsyncMock(side_effect=responses)
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        posts_content = ITEM_SEPARATOR.join([f"POST_ID: p{i}  " + ("x" * 30) for i in range(1, 4)])
        await classify_posts("CB", posts_content, "", "sk-key", progress=progress)

        progress.add_total.assert_called_once_with(3)
        assert progress.advance.await_count == 3

    async def test_single_batch_still_reports_progress(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.json_chat_completion",
            AsyncMock(return_value=_json_response([{"item_id": "p1", "code": "A", "quotes": ["x"]}])),
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        await classify_posts("CB", "POSTS", "", "sk-key", progress=progress)

        progress.add_total.assert_called_once_with(1)
        assert progress.advance.await_count == 1

    async def test_no_progress_arg_does_not_raise(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.json_chat_completion",
            AsyncMock(return_value=_json_response([{"item_id": "p1", "code": "A", "quotes": ["x"]}])),
        )
        await classify_posts("CB", "POSTS", "", "sk-key")

    async def test_mid_run_failure_returns_earlier_batches_instead_of_raising(self, monkeypatch) -> None:
        # Regression coverage: classify_posts used to have no per-batch
        # error handling at all -- ANY batch raising (e.g. the account ran
        # out of credits) discarded every batch already classified. It
        # must now return the batches that DID succeed instead.
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.context_window.max_prompt_chars",
            lambda model, **kwargs: 40,
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_apply.json_chat_completion",
            AsyncMock(
                side_effect=[
                    _json_response([{"item_id": "p1", "code": "A", "quotes": ["x"]}]),
                    ValueError("Insufficient credits: Your account or API key needs more credits."),
                    _json_response([{"item_id": "p3", "code": "C", "quotes": ["z"]}]),
                ]
            ),
        )

        posts_content = ITEM_SEPARATOR.join([f"POST_ID: p{i}  " + ("x" * 30) for i in range(1, 4)])
        entries, _, _, coverage = await classify_posts("CB", posts_content, "", "sk-key")

        assert {e["item_id"] for e in entries} == {"p1"}
        assert coverage["batches_processed"] == 1
        assert coverage["batches_total"] == 3
        assert "Insufficient credits" in coverage["error"]
