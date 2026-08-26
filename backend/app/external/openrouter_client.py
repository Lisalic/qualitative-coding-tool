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

from backend.app.external.errors import ExternalServiceError, extract_http_error_code, is_retryable_error

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
    timeout: float = 30.0,
    response_format: dict[str, str] | None = None,
    use_middle_out: bool = False,
    max_retries: int = 2,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> str:
    """One OpenRouter chat completion call, with retry/backoff.

    ``timeout``/``max_retries`` default to a 30s cap and 2 total attempts --
    every call site in this codebase now passes these same values explicitly
    (kept consistent on purpose: the worst case for one batch is bounded to
    roughly ``timeout * max_retries`` plus a few seconds of backoff, instead
    of the 300s/3-attempt combination this used to default to, which let a
    single stuck batch take up to ~15 minutes before failing). A free-tier
    call that hasn't responded within 30s is very unlikely to be about to
    succeed, so a shorter timeout fails fast rather than hanging.

    Retries skip permanent, request-is-broken errors (see
    :data:`backend.app.external.errors.NON_RETRYABLE_HTTP_CODES`) --
    a bad key or an empty account will never succeed by resending the exact
    same request, so those fail on the first attempt instead of burning
    through backoff and more attempts for nothing.

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
            # Off by default: middle-out silently deletes the middle of an
            # oversized prompt, so overflow would vanish without a signal.
            # Every pipeline now sizes its prompts up front (see
            # external/context_window.py), so a size miss should surface as
            # a real error, not a quietly truncated answer.
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
    """``chat_completion`` with a 3-tier compliance ladder for a
    JSON-shaped response, tried in order within one logical call:

    1. ``response_format={"type": "json_schema", "json_schema": {...,
       "strict": True}}`` (only if ``json_schema`` is given) -- constrained
       decoding, the strongest guarantee OpenRouter/the underlying model
       can offer.
    2. ``response_format={"type": "json_object"}`` -- plain JSON mode,
       supported by far more models than strict schema decoding.
    3. no ``response_format`` at all -- some providers reject the
       ``response_format`` parameter outright rather than degrading
       gracefully; a prompt-only call still usually gets valid JSON back
       from a model that was asked clearly for it.

    Mirrors the existing 2-tier fallback in
    ``backend/scripts/tag_expansion.py::_fetch_expansion_json``, promoted
    to a shared seam (rather than a second private copy) now that a
    second caller (``backend/scripts/codebook_apply.py::classify_posts``)
    needs the same ladder plus the strict-schema tier that caller can
    additionally take advantage of.

    Each tier is one attempt (no internal backoff -- a caller wanting
    backoff across the whole ladder wraps this in its own retry loop, the
    same relationship ``chat_completion``'s ``max_retries`` already has to
    an outer caller). Returns the first tier's raw response text; the
    caller is still responsible for parsing it as JSON -- this function
    only maximizes the odds that parsing succeeds, it does not parse.
    Raises the last tier's exception if every tier fails.
    """
    response_formats: list[dict[str, Any] | None] = []
    if json_schema is not None:
        response_formats.append(
            {
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True, "schema": json_schema},
            }
        )
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

    assert last_error is not None  # pragma: no cover - loop always returns or leaves last_error set
    raise last_error
