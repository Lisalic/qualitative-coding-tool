"""Single seam for all OpenRouter (LLM) calls.

Replaces 4 independent sync ``OpenAI(...)`` + hand-rolled ``time.sleep``
retry-loop implementations (one per script in ``backend/scripts/``) with
one async client + one shared retry helper. Response *parsing* stays in
each script -- a codebook string, a POST_ID/CODE/EVIDENCE DSL, and a JSON
object are different output contracts and forcing one shape here would be
speculative.
"""

import asyncio
import time
from typing import Any, Awaitable, Callable, TypeVar

from openai import AsyncOpenAI

from backend.app.external.errors import ExternalServiceError, extract_http_error_code, is_retryable_error
from backend.app.jobs.progress import get_current_accounting_tracker

OPENROUTER_URL = "https://openrouter.ai/api/v1"

T = TypeVar("T")


def get_openrouter_client(api_key: str) -> AsyncOpenAI:
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    return AsyncOpenAI(api_key=api_key, base_url=OPENROUTER_URL)


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    initial_delay_s: float = 2.0,
    is_retryable: Callable[[Exception], bool] | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Call ``fn()``, retrying with exponential backoff on failure."""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fn()
        except Exception as e:  # noqa: BLE001 - re-raised below, this just gates retry
            last_error = e
            if is_retryable is not None and not is_retryable(e):
                raise
            if attempt == max_retries:
                raise
            wait_time = initial_delay_s * (2 ** (attempt - 1))
            if on_retry is not None:
                on_retry(attempt, e, wait_time)
            await asyncio.sleep(wait_time)

    assert last_error is not None  # pragma: no cover - loop always returns or raises
    raise last_error


async def chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
    temperature: float = 0.05,
    timeout: float = 30.0,
    response_format: dict[str, str] | None = None,
    use_middle_out: bool = False,
    max_retries: int = 2,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> str:
    """One OpenRouter chat completion call, with retry/backoff and accounting."""
    client = get_openrouter_client(api_key)

    async def _call() -> str:
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            timeout=timeout,
        )
        if use_middle_out:
            kwargs["extra_body"] = {"transforms": ["middle-out"]}
        if response_format is not None:
            kwargs["response_format"] = response_format

        start_time = time.perf_counter()
        response = await client.chat.completions.create(**kwargs)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Record accounting if tracker is active
        tracker = get_current_accounting_tracker()
        if tracker is not None:
            usage = getattr(response, "usage", None)
            p_tokens = getattr(usage, "prompt_tokens", 0) or 0
            c_tokens = getattr(usage, "completion_tokens", 0) or 0
            tracker.record_call(
                model=model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                duration_ms=duration_ms,
            )
            try:
                await tracker.flush()
            except Exception:
                pass

        content = response.choices[0].message.content
        if not content:
            raise ExternalServiceError("OpenRouter returned an empty completion")
        return content

    try:
        return await retry_async(
            _call, max_retries=max_retries, is_retryable=is_retryable_error, on_retry=on_retry
        )
    except ExternalServiceError:
        raise
    except Exception as e:
        raise ExternalServiceError(str(e), code=extract_http_error_code(e)) from e


async def json_chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
    json_schema: dict[str, Any] | None = None,
    temperature: float = 0.05,
    timeout: float = 30.0,
    max_retries: int = 2,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> str:
    """``chat_completion`` with a 3-tier compliance ladder for a JSON-shaped response."""
    response_formats: list[dict[str, Any] | None] = []
    if json_schema is not None:
        response_formats.append({
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": json_schema},
        })
    response_formats.append({"type": "json_object"})
    response_formats.append(None)

    last_error: Exception | None = None
    for response_format in response_formats:
        try:
            return await chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key=api_key,
                model=model,
                temperature=temperature,
                timeout=timeout,
                response_format=response_format,
                max_retries=max_retries,
                on_retry=on_retry,
            )
        except Exception as e:  # noqa: BLE001 - fall through to the next tier
            last_error = e

    assert last_error is not None
    raise last_error
