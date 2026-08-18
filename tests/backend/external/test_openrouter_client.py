from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.external.errors import ExternalServiceError
from backend.app.external.openrouter_client import (
    chat_completion,
    get_openrouter_client,
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
