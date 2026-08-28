"""Tests for backend/scripts/codebook_generator.py.

Generate asks the model for JSON (``{"codes": [{family, name, definition,
...}]}``) via ``json_chat_completion`` -- the same 3-tier compliance
ladder as codebook_apply -- rather than free-form markdown. ``get_client``
stays on ``chat_completion`` for compare/summarize prose. These tests
mock ``json_chat_completion`` at the generate seam and ``chat_completion``
at ``get_client``.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.external.context_window import ITEM_SEPARATOR
from backend.scripts.codebook_generator import (
    CODEBOOK_JSON_SCHEMA,
    generate_codebook,
    generate_codebook_map_reduce,
    get_client,
    merge_codebook_json_drafts,
)


def _code(**overrides) -> dict:
    row = {
        "family": "A",
        "name": "One",
        "definition": "d",
        "inclusion": "i",
        "exclusion": "e",
        "keywords": "k",
        "example": "x",
    }
    row.update(overrides)
    return row


def _json_response(codes: list[dict]) -> str:
    return json.dumps({"codes": codes})


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
        assert kwargs["timeout"] == 30.0
        assert kwargs.get("use_middle_out", False) is False
        assert kwargs["max_retries"] == 2

    async def test_strips_markdown_fence_wrapper(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="```markdown\n# Heading\n\nSome **text**.\n```")
        monkeypatch.setattr("backend.scripts.codebook_generator.chat_completion", mock)

        result = await get_client("sys prompt", "user prompt", "sk-key", "model-x")

        assert result == "# Heading\n\nSome **text**."


class TestGenerateCodebook:
    async def test_builds_prompts_and_returns_triple(self, monkeypatch) -> None:
        raw = _json_response([_code()])
        mock = AsyncMock(return_value=raw)
        monkeypatch.setattr("backend.scripts.codebook_generator.json_chat_completion", mock)

        result, system_prompt, user_prompt = await generate_codebook(
            "post one\npost two", "sk-key", custom_prompt="focus on X", MODEL="model-y"
        )

        assert result == raw
        assert "post one" in user_prompt
        assert "focus on X" in user_prompt
        assert "return only the required JSON" in user_prompt
        assert "exactly this shape" in system_prompt
        assert '"codes"' in system_prompt
        assert "exclusion" in system_prompt
        assert mock.call_args.kwargs["model"] == "model-y"
        assert mock.call_args.kwargs["json_schema"] is CODEBOOK_JSON_SCHEMA
        assert mock.call_args.kwargs["timeout"] == 30.0
        assert mock.call_args.kwargs["max_retries"] == 2


class TestMergeCodebookJsonDrafts:
    def test_concatenates_codes_arrays(self) -> None:
        merged = json.loads(
            merge_codebook_json_drafts(
                [_json_response([_code(name="One")]), _json_response([_code(family="B", name="Two")])]
            )
        )
        assert [c["name"] for c in merged["codes"]] == ["One", "Two"]

    def test_skips_invalid_drafts(self) -> None:
        merged = json.loads(merge_codebook_json_drafts(["not json", _json_response([_code()])]))
        assert len(merged["codes"]) == 1


class TestGenerateCodebookMapReduce:
    async def test_single_batch_skips_reduce_call(self, monkeypatch) -> None:
        raw = _json_response([_code()])
        mock = AsyncMock(return_value=raw)
        monkeypatch.setattr("backend.scripts.codebook_generator.json_chat_completion", mock)

        result, system_prompt, user_prompt, coverage = await generate_codebook_map_reduce(
            "short data", "sk-key", custom_prompt="focus on X", MODEL="model-y"
        )

        assert mock.await_count == 1
        assert result == raw
        assert "qualitative researcher" in system_prompt
        assert "short data" in user_prompt
        assert coverage == {"batches_processed": 1, "batches_total": 1, "error": None}

    async def test_multiple_batches_triggers_one_reduce_call_with_all_drafts(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.context_window.max_prompt_chars",
            lambda model, **kwargs: 130,
        )
        responses = [
            _json_response([_code(name="One")]),
            _json_response([_code(family="B", name="Two")]),
            _json_response([_code(family="C", name="Three")]),
        ]
        mock = AsyncMock(side_effect=responses)
        monkeypatch.setattr("backend.scripts.codebook_generator.json_chat_completion", mock)

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        result, system_prompt, user_prompt, coverage = await generate_codebook_map_reduce(
            posts_content, "sk-key", custom_prompt="focus on X", MODEL="model-y"
        )

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
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.json_chat_completion",
            AsyncMock(return_value=_json_response([_code()])),
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
            _json_response([_code(name="One")]),
            _json_response([_code(family="B", name="Two")]),
            _json_response([_code(family="C", name="Three")]),
        ]
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.json_chat_completion", AsyncMock(side_effect=responses)
        )
        progress = MagicMock()
        progress.advance = AsyncMock()
        progress.add_total = AsyncMock()

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        await generate_codebook_map_reduce(posts_content, "sk-key", progress=progress)

        progress.add_total.assert_called_once_with(3)
        assert progress.advance.await_count == 3

    async def test_mid_map_failure_returns_merged_earlier_drafts(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.context_window.max_prompt_chars",
            lambda model, **kwargs: 130,
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.json_chat_completion",
            AsyncMock(
                side_effect=[
                    _json_response([_code(name="One")]),
                    ValueError("Insufficient credits: Your account or API key needs more credits."),
                ]
            ),
        )

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        result, _, _, coverage = await generate_codebook_map_reduce(posts_content, "sk-key")

        assert json.loads(result)["codes"][0]["name"] == "One"
        assert coverage["batches_processed"] == 1
        assert coverage["batches_total"] == 2
        assert "Insufficient credits" in coverage["error"]

    async def test_reduce_call_failure_returns_merged_drafts(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.context_window.max_prompt_chars",
            lambda model, **kwargs: 130,
        )
        monkeypatch.setattr(
            "backend.scripts.codebook_generator.json_chat_completion",
            AsyncMock(
                side_effect=[
                    _json_response([_code(name="One")]),
                    _json_response([_code(family="B", name="Two")]),
                    ValueError("Insufficient credits: Your account or API key needs more credits."),
                ]
            ),
        )

        posts_content = ITEM_SEPARATOR.join(["x" * 40, "y" * 40, "z" * 40])
        result, _, _, coverage = await generate_codebook_map_reduce(posts_content, "sk-key")

        names = [c["name"] for c in json.loads(result)["codes"]]
        assert names == ["One", "Two"]
        assert coverage["batches_processed"] == 2
        assert coverage["batches_total"] == 3
        assert "Insufficient credits" in coverage["error"]
