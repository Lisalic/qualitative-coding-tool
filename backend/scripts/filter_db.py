import ast
import re
import datetime

from backend.app.ai_models import is_paid_model
from backend.app.external import context_window
from backend.app.external.errors import ExternalServiceError
from backend.app.external.openrouter_client import chat_completion
from backend.app.external.response_parsers import strip_markdown_fences
from backend.app.jobs.progress import ProgressTracker
from backend.scripts.openrouter_http import openrouter_user_message

FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
MAX_RETRIES = 2

MAX_BATCHES_FOR_FREE = 3


class AIFilterError(Exception):
    """Raised when AI filtering fails with a known error code."""
    def __init__(self, message: str, code: int = 0):
        self.code = code
        super().__init__(message)


def _log_ai(stage: str, message: str, data: dict = None):
    """Human-readable logging for AI operations."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    prefix = f"[{timestamp}] AI_FILTER | {stage}"
    if data:
        details = " | ".join(f"{k}={v}" for k, v in data.items())
        print(f"{prefix} | {message} | {details}")
    else:
        print(f"{prefix} | {message}")


def _preview_response(response: str, max_len: int = 500) -> str:
    """Create a readable preview of AI response."""
    response = response.strip()
    if len(response) <= max_len:
        return response
    half = max_len // 2 - 10
    return f"{response[:half]}\n... [{len(response) - max_len} chars omitted] ...\n{response[-half:]}"


async def get_client(system_prompt: str, user_prompt: str, api_key: str, model: str = FREE_MODEL) -> str:
    if not api_key:
        raise AIFilterError("OpenRouter API key is required", code=401)

    total_chars = len(system_prompt) + len(user_prompt)

    _log_ai("REQUEST", f"API call to {model}", {
        "prompt_chars": f"{total_chars:,}"
    })

    def _on_retry(attempt: int, exc: Exception, wait_seconds: float) -> None:
        if isinstance(exc, ExternalServiceError) and "empty completion" in str(exc).lower():
            _log_ai(
                "RETRY",
                f"Empty completion, attempt {attempt}/{MAX_RETRIES}",
                {"wait": f"{wait_seconds}s", "model": model},
            )
        else:
            _log_ai(
                "RETRY",
                f"Attempt {attempt}/{MAX_RETRIES} failed: {type(exc).__name__}",
                {"wait": f"{wait_seconds}s"},
            )

    try:
        return await chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            api_key=api_key,
            model=model,
            timeout=30.0,
            max_retries=MAX_RETRIES,
            on_retry=_on_retry,
        )
    except ExternalServiceError as e:
        if e.code == 0 and "empty completion" in str(e).lower():
            msg = (
                "The model returned no usable output (empty reply). "
                "This often happens when a free model is overloaded or briefly unavailable—try another model or retry."
            )
            _log_ai("ERROR", msg, {"model": model})
            raise AIFilterError(msg, code=502) from None
        code = e.code
        msg = openrouter_user_message(code, model) if code else str(e)
        extra = {"model": model, "http_code": code} if code else None
        _log_ai("ERROR", f"All {MAX_RETRIES} attempts failed: {msg}", extra)
        raise AIFilterError(msg, code=code) from e


async def _run_batched_filter(
    content_type: str,
    filter_prompt: str,
    content: str,
    api_key: str,
    model: str,
    system_prompt: str,
    progress: ProgressTracker | None = None,
) -> tuple[list, str, dict]:
    """
    Shared batched filtering logic for both posts and comments.

    Batch execution and error policy (batch 1 failure raises immediately,
    a later batch failure stops and keeps what succeeded) both come from
    ``context_window.run_sequential_batches``.

    Returns:
        tuple: (list of IDs, last_user_prompt, coverage)
        ``coverage`` is
        ``{"batches_processed": int, "batches_total": int, "error": str | None}``
        -- when free-model batch capping (below) or a batch failure means
        not all of ``content`` was actually sent to the model, callers can
        surface that instead of silently returning an incomplete result.

    ``progress`` (optional) gets its total incremented by this call's batch
    count and advanced once per attempted batch, so a caller running both
    posts and comments through this function can share one
    ``ProgressTracker`` for a single combined progress figure.
    """
    chosen_model = model or FREE_MODEL
    paid_model = is_paid_model(chosen_model)
    max_content_chars = context_window.max_prompt_chars(
        chosen_model,
        reserved_chars=len(system_prompt) + len(filter_prompt) + 1000,
        # Output is one ID per matching post -- scales with the batch, so
        # reserve a proportional slice of the window for it.
        output_reserve_tokens=context_window.proportional_output_reserve(chosen_model, 0.15),
    )

    _log_ai(f"FILTER_{content_type.upper()}", f"Starting with {chosen_model}", {
        "content_chars": f"{len(content):,}",
        "max_per_batch": f"{max_content_chars:,}"
    })

    batches = context_window.batch_by_separator(content, max_content_chars)
    total_batches = len(batches)

    if not paid_model and total_batches > MAX_BATCHES_FOR_FREE:
        if MAX_BATCHES_FOR_FREE <= 1:
            _log_ai("BATCHING", f"Content requires {total_batches} batches, limiting to 1 (first batch only)")
            batches = [batches[0]]
        else:
            _log_ai("BATCHING", f"Content requires {total_batches} batches, limiting to {MAX_BATCHES_FOR_FREE} (sampling evenly)")
            indices = [int(i * (total_batches - 1) / (MAX_BATCHES_FOR_FREE - 1)) for i in range(MAX_BATCHES_FOR_FREE)]
            batches = [batches[i] for i in indices]
    else:
        _log_ai("BATCHING", f"Split into {total_batches} batch(es)")

    if paid_model:
        _log_ai("BATCH_POLICY", "Paid model: no max-batch cap applied")
    else:
        _log_ai("BATCH_POLICY", f"Free model: max {MAX_BATCHES_FOR_FREE} batches")

    if progress is not None:
        await progress.add_total(len(batches))

    label = "Posts" if content_type == "posts" else "Comments"
    user_prompts = [
        (f"Filter criteria: {filter_prompt}\n\n{label} to analyze:\n{batch}" if filter_prompt
         else f"Return ALL {content_type.lower()} IDs:\n{batch}")
        for batch in batches
    ]

    async def _run_one_batch(i: int, batch: str) -> list:
        _log_ai("BATCH", f"Processing batch {i+1}/{len(batches)}", {"chars": f"{len(batch):,}"})
        response = await get_client(system_prompt, user_prompts[i], api_key, chosen_model)

        _log_ai("RESPONSE", f"Batch {i+1} response ({len(response)} chars):")
        print(f"    {_preview_response(response, 300)}")

        batch_ids = wrap_in_python_array(response)
        _log_ai("BATCH_RESULT", f"Batch {i+1}: extracted {len(batch_ids)} IDs")
        return batch_ids

    batch_id_lists, run_coverage = await context_window.run_sequential_batches(batches, _run_one_batch, progress=progress)
    all_ids = [id_ for batch_ids in batch_id_lists for id_ in batch_ids]
    unique_ids = list(dict.fromkeys(all_ids))
    last_user_prompt = user_prompts[-1] if user_prompts else ""

    # `total_batches` (pre-free-model-cap) is the true denominator for
    # "how much of the content got covered" -- distinct from
    # `run_coverage`'s own `batches_total`, which is only the (possibly
    # capped) subset actually attempted.
    coverage = {
        "batches_processed": run_coverage["batches_processed"],
        "batches_total": total_batches,
        "error": run_coverage["error"],
    }

    if coverage["batches_processed"] < coverage["batches_total"]:
        _log_ai("COVERAGE", f"Only {coverage['batches_processed']}/{coverage['batches_total']} batches processed -- result is partial", coverage)
    _log_ai("COMPLETE", f"Total unique IDs: {len(unique_ids)}")

    return unique_ids, last_user_prompt, coverage


async def filter_posts_with_ai(
    filter_prompt: str, posts_content: str, api_key: str, model: str = "", *, progress: ProgressTracker | None = None
) -> tuple[list, str, str, dict]:
    """
    Use AI to filter posts. Raises AIFilterError on first-batch failure.

    Returns ``(ids, system_prompt, last_user_prompt, coverage)`` -- see
    ``_run_batched_filter`` for ``coverage``'s shape.
    """
    system_prompt = """You are an expert content analyst. Your task is to filter posts and return ONLY a Python array of post IDs.

INSTRUCTIONS:
1. Analyze each post in the provided content. Posts are separated by "---".
2. Each post starts with [ID] followed by the content.
3. Return ONLY IDs of posts that match the filtering criteria.
4. RETURN ONLY a valid Python array of STRING IDs exactly as they appear in [ID] markers, e.g. ['abc123', 'xyz789']
5. If no posts match, return: []

CRITICAL: Return ONLY the raw Python array. No markdown, no backticks, no explanation."""

    ids, last_user_prompt, coverage = await _run_batched_filter(
        "posts", filter_prompt, posts_content, api_key, model, system_prompt, progress=progress
    )
    return ids, system_prompt, last_user_prompt, coverage


async def filter_comments_with_ai(
    filter_prompt: str, comments_content: str, api_key: str, model: str = "", *, progress: ProgressTracker | None = None
) -> tuple[list, str, str, dict]:
    """
    Use AI to filter comments. Raises AIFilterError on first-batch failure.

    Returns ``(ids, system_prompt, last_user_prompt, coverage)`` -- see
    ``_run_batched_filter`` for ``coverage``'s shape.
    """
    system_prompt = """You are an expert content analyst. Your task is to filter comments and return ONLY a Python array of comment IDs.

INSTRUCTIONS:
1. Analyze each comment in the provided content. Comments are separated by "---".
2. Each comment starts with [ID] followed by the content.
3. Return ONLY IDs of comments that match the filtering criteria.
4. RETURN ONLY a valid Python array of STRING IDs exactly as they appear in [ID] markers, e.g. ['abc123', 'xyz789']
5. If no comments match, return: []

CRITICAL: Return ONLY the raw Python array. No markdown, no backticks, no explanation."""

    ids, last_user_prompt, coverage = await _run_batched_filter(
        "comments", filter_prompt, comments_content, api_key, model, system_prompt, progress=progress
    )
    return ids, system_prompt, last_user_prompt, coverage



def wrap_in_python_array(content: str) -> list:
    """
    Parse AI response into a list of ID strings.
    Handles various formats the AI might return.
    """
    # Remove common markdown artifacts (identical logic to
    # external/response_parsers.py::strip_markdown_fences, so reuse it
    # directly instead of keeping a second copy).
    content = strip_markdown_fences(content)

    # Try to parse as Python literal
    try:
        obj = ast.literal_eval(content)
        if isinstance(obj, list):
            result = [str(x) for x in obj if x is not None]
            _log_ai("PARSE", f"Parsed {len(result)} IDs via ast.literal_eval")
            return result
    except Exception as e:
        _log_ai("PARSE_WARN", f"ast.literal_eval failed: {e}, falling back to regex")

    # Fallback: extract quoted strings
    matches = re.findall(r"['\"]([^'\"]+)['\"]", content)
    if not matches:
        _log_ai("PARSE_WARN", "No quoted strings found in response")
        return []

    # Filter to ID-like tokens only
    filtered = [m for m in matches if re.match(r"^[A-Za-z0-9_:-]+$", m)]
    _log_ai("PARSE", f"Extracted {len(filtered)} IDs via regex fallback (from {len(matches)} quoted strings)")
    return filtered