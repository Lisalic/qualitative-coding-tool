"""Single seam for all OpenRouter (LLM) calls.

Replaces 4 independent sync ``OpenAI(...)`` + hand-rolled ``time.sleep``
retry-loop implementations (one per script in ``backend/scripts/``) with
one async client + one shared retry helper. Response *parsing* stays in
each script -- a codebook string, a POST_ID/CODE/EVIDENCE DSL, and a JSON
object are different output contracts and forcing one shape here would be
speculative.

Landed in Stage 0, unused until Stage 9 rewires the scripts to call
``chat_completion`` instead of building their own client.
"""

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

from openai import AsyncOpenAI

from backend.app.external.errors import ExternalServiceError, extract_http_error_code

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
    """Call ``fn()``, retrying with exponential backoff on failure.

    ``is_retryable(exc)`` (default: always retryable) lets a caller bail
    out immediately on a non-retryable error instead of burning through
    every attempt. ``on_retry(attempt, exc, wait_seconds)`` is an optional
    logging/observability hook, called before each backoff sleep.
    """
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
    timeout: float = 300.0,
    response_format: dict[str, str] | None = None,
    use_middle_out: bool = True,
    max_retries: int = 3,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> str:
    """One OpenRouter chat completion call, with retry/backoff.

    Raises :class:`ExternalServiceError` (with a best-effort ``.code``
    HTTP status) if every attempt fails, or if every attempt returns an
    empty completion.
    """
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

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise ExternalServiceError("OpenRouter returned an empty completion")
        return content

    try:
        return await retry_async(
            _call, max_retries=max_retries, on_retry=on_retry
        )
    except ExternalServiceError:
        raise
    except Exception as e:
        raise ExternalServiceError(str(e), code=extract_http_error_code(e)) from e
