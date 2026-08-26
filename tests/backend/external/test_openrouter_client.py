from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.external.errors import ExternalServiceError
from backend.app.external.openrouter_client import (
    chat_completion,
    get_openrouter_client,
    json_chat_completion,
    retry_async,
)


class TestGetOpenrouterClient:
    def test_no_api_key_raises(self) -> None:
        with pytest.raises(ValueError):
            get_openrouter_client("")

    def test_returns_async_openai_pointed_at_openrouter(self) -> None:
        client = get_openrouter_client("sk-test")
        assert str(client.base_url).rstrip("/") == "https://openrouter.ai/api/v1"


class TestRetryAsync:
    async def test_succeeds_first_try_no_sleep(self, monkeypatch) -> None:
        sleeps: list[float] = []
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.asyncio.sleep",
            AsyncMock(side_effect=lambda s: sleeps.append(s)),
        )
        fn = AsyncMock(return_value="ok")
        result = await retry_async(fn)
        assert result == "ok"
        assert fn.await_count == 1
        assert sleeps == []

    async def test_retries_with_exponential_backoff_then_succeeds(self, monkeypatch) -> None:
        sleeps: list[float] = []
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.asyncio.sleep",
            AsyncMock(side_effect=lambda s: sleeps.append(s)),
        )
        fn = AsyncMock(side_effect=[ValueError("1"), ValueError("2"), "ok"])
        result = await retry_async(fn, max_retries=3, initial_delay_s=2.0)
        assert result == "ok"
        assert fn.await_count == 3
        assert sleeps == [2.0, 4.0]

    async def test_exhausts_retries_raises_last_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.asyncio.sleep", AsyncMock()
        )
        fn = AsyncMock(side_effect=[ValueError("1"), ValueError("2"), ValueError("final")])
        with pytest.raises(ValueError, match="final"):
            await retry_async(fn, max_retries=3, initial_delay_s=0.01)
        assert fn.await_count == 3

    async def test_non_retryable_error_short_circuits(self, monkeypatch) -> None:
        sleep_mock = AsyncMock()
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.asyncio.sleep", sleep_mock
        )
        fn = AsyncMock(side_effect=ValueError("fatal"))
        with pytest.raises(ValueError, match="fatal"):
            await retry_async(fn, max_retries=5, is_retryable=lambda e: False)
        assert fn.await_count == 1
        sleep_mock.assert_not_called()

    async def test_on_retry_callback_invoked(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.asyncio.sleep", AsyncMock()
        )
        calls = []
        fn = AsyncMock(side_effect=[ValueError("x"), "ok"])
        await retry_async(
            fn,
            max_retries=2,
            initial_delay_s=1.0,
            on_retry=lambda attempt, exc, wait: calls.append((attempt, str(exc), wait)),
        )
        assert calls == [(1, "x", 1.0)]

    async def test_max_retries_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            await retry_async(AsyncMock(), max_retries=0)


def _fake_client(content: str | None = "hello", *, side_effect=None) -> MagicMock:
    client = MagicMock()
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=content))]
    if side_effect is not None:
        client.chat.completions.create = AsyncMock(side_effect=side_effect)
    else:
        client.chat.completions.create = AsyncMock(return_value=completion)
    return client


class TestChatCompletion:
    async def test_returns_content_on_success(self, monkeypatch) -> None:
        client = _fake_client("the response")
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        result = await chat_completion(
            system_prompt="sys", user_prompt="usr", api_key="sk-x", model="m"
        )
        assert result == "the response"
        client.chat.completions.create.assert_awaited_once()

    async def test_use_middle_out_sets_extra_body(self, monkeypatch) -> None:
        client = _fake_client("x")
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        await chat_completion(
            system_prompt="s", user_prompt="u", api_key="k", model="m", use_middle_out=True
        )
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["extra_body"] == {"transforms": ["middle-out"]}

    async def test_middle_out_disabled_omits_extra_body(self, monkeypatch) -> None:
        client = _fake_client("x")
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        await chat_completion(
            system_prompt="s", user_prompt="u", api_key="k", model="m", use_middle_out=False
        )
        kwargs = client.chat.completions.create.call_args.kwargs
        assert "extra_body" not in kwargs

    async def test_response_format_passed_through(self, monkeypatch) -> None:
        client = _fake_client("x")
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        fmt = {"type": "json_object"}
        await chat_completion(
            system_prompt="s", user_prompt="u", api_key="k", model="m", response_format=fmt
        )
        assert client.chat.completions.create.call_args.kwargs["response_format"] == fmt

    async def test_empty_completion_retried_then_raises_external_service_error(
        self, monkeypatch
    ) -> None:
        client = _fake_client(content=None)
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.asyncio.sleep", AsyncMock()
        )
        with pytest.raises(ExternalServiceError):
            await chat_completion(
                system_prompt="s",
                user_prompt="u",
                api_key="k",
                model="m",
                max_retries=2,
            )
        assert client.chat.completions.create.await_count == 2

    async def test_sdk_exception_wrapped_with_extracted_code(self, monkeypatch) -> None:
        client = _fake_client(side_effect=Exception("Error code: 429 - rate limited"))
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.asyncio.sleep", AsyncMock()
        )
        with pytest.raises(ExternalServiceError) as exc_info:
            await chat_completion(
                system_prompt="s", user_prompt="u", api_key="k", model="m", max_retries=1
            )
        assert exc_info.value.code == 429

    async def test_no_api_key_raises_before_any_call(self) -> None:
        with pytest.raises(ValueError):
            await chat_completion(
                system_prompt="s", user_prompt="u", api_key="", model="m"
            )

    async def test_permanent_error_skips_remaining_retries(self, monkeypatch) -> None:
        # A 402 (insufficient credits) will never succeed by resending the
        # same request -- it must fail on the first attempt, not burn
        # through every retry first.
        client = _fake_client(side_effect=Exception("Error code: 402 - insufficient credits"))
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        sleep_mock = AsyncMock()
        monkeypatch.setattr("backend.app.external.openrouter_client.asyncio.sleep", sleep_mock)

        with pytest.raises(ExternalServiceError) as exc_info:
            await chat_completion(
                system_prompt="s", user_prompt="u", api_key="k", model="m", max_retries=3
            )

        assert exc_info.value.code == 402
        assert client.chat.completions.create.await_count == 1
        sleep_mock.assert_not_called()

    async def test_default_timeout_and_max_retries_are_consistent_and_tight(self, monkeypatch) -> None:
        # See the docstring on chat_completion: 30s / 2 attempts bounds a
        # single batch's worst case to roughly a minute instead of the old
        # 300s x 3 = ~15 minutes.
        client = _fake_client("x")
        monkeypatch.setattr(
            "backend.app.external.openrouter_client.get_openrouter_client",
            lambda api_key: client,
        )
        await chat_completion(system_prompt="s", user_prompt="u", api_key="k", model="m")

        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["timeout"] == 30.0


class TestJsonChatCompletion:
    """The 3-tier compliance ladder: strict json_schema (if given) ->
    json_object -> no response_format, tried within one call, mirroring
    the existing 2-tier precedent in
    ``backend/scripts/tag_expansion.py::_fetch_expansion_json``.
    """

    async def test_first_tier_succeeds_uses_strict_json_schema(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="the response")
        monkeypatch.setattr("backend.app.external.openrouter_client.chat_completion", mock)

        result = await json_chat_completion(
            system_prompt="s", user_prompt="u", api_key="k", model="m", json_schema={"type": "object"}
        )

        assert result == "the response"
        mock.assert_awaited_once()
        response_format = mock.call_args.kwargs["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        assert response_format["json_schema"]["schema"] == {"type": "object"}

    async def test_no_json_schema_given_starts_at_json_object_tier(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="ok")
        monkeypatch.setattr("backend.app.external.openrouter_client.chat_completion", mock)

        await json_chat_completion(system_prompt="s", user_prompt="u", api_key="k", model="m")

        assert mock.call_args.kwargs["response_format"] == {"type": "json_object"}
        assert mock.await_count == 1

    async def test_falls_back_to_json_object_when_schema_tier_fails(self, monkeypatch) -> None:
        mock = AsyncMock(side_effect=[Exception("schema rejected"), "ok"])
        monkeypatch.setattr("backend.app.external.openrouter_client.chat_completion", mock)

        result = await json_chat_completion(
            system_prompt="s", user_prompt="u", api_key="k", model="m", json_schema={"type": "object"}
        )

        assert result == "ok"
        assert mock.await_count == 2
        assert mock.call_args_list[1].kwargs["response_format"] == {"type": "json_object"}

    async def test_falls_back_to_no_response_format_when_both_earlier_tiers_fail(self, monkeypatch) -> None:
        mock = AsyncMock(side_effect=[Exception("schema rejected"), Exception("json mode rejected"), "ok"])
        monkeypatch.setattr("backend.app.external.openrouter_client.chat_completion", mock)

        result = await json_chat_completion(
            system_prompt="s", user_prompt="u", api_key="k", model="m", json_schema={"type": "object"}
        )

        assert result == "ok"
        assert mock.await_count == 3
        assert mock.call_args_list[2].kwargs["response_format"] is None

    async def test_all_tiers_failing_raises_the_last_error(self, monkeypatch) -> None:
        mock = AsyncMock(side_effect=[Exception("a"), Exception("b"), Exception("final")])
        monkeypatch.setattr("backend.app.external.openrouter_client.chat_completion", mock)

        with pytest.raises(Exception, match="final"):
            await json_chat_completion(
                system_prompt="s", user_prompt="u", api_key="k", model="m", json_schema={"type": "object"}
            )
        assert mock.await_count == 3

    async def test_forwards_model_timeout_and_max_retries(self, monkeypatch) -> None:
        mock = AsyncMock(return_value="ok")
        monkeypatch.setattr("backend.app.external.openrouter_client.chat_completion", mock)

        await json_chat_completion(
            system_prompt="s", user_prompt="u", api_key="k", model="model-x", timeout=15.0, max_retries=1
        )

        kwargs = mock.call_args.kwargs
        assert kwargs["model"] == "model-x"
        assert kwargs["timeout"] == 15.0
        assert kwargs["max_retries"] == 1
