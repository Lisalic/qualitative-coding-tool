import ast
import datetime
import json
import re

from backend.app.ai_models import is_paid_model
from backend.app.external import context_window
from backend.app.external.errors import ExternalServiceError
from backend.app.external.openrouter_client import chat_completion
from backend.app.external.response_parsers import strip_markdown_fences
from backend.app.jobs.progress import ProgressTracker
from backend.scripts.openrouter_http import openrouter_user_message

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


async def get_client(system_prompt: str, user_prompt: str, api_key: str, model: str = "") -> str:
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


def _build_triage_system_prompt(label: str) -> str:
    """System prompt for the shared include/exclude triage pass.

    One prompt for both posts and comments (parameterized by ``label``)
    replacing the two near-duplicate literals this module used to carry.
    Unlike the old "return the ids to keep" contract, the model now labels
    each item in EITHER direction and is told to leave an item out of both
    arrays when it's not confident -- that third, unlabeled state is what
    keeps a row "undecided" in the editor rather than forcing every row
    into a binary call.
    """
    lower = label.lower()
    return f"""You are an expert content analyst. Your task is to triage {lower} against the given criteria and sort each into "include" or "exclude".

INSTRUCTIONS:
1. Analyze each item in the provided content. Items are separated by "---".
2. Each item starts with [ID] followed by the content.
3. Classify each item as INCLUDE (matches the include criteria, or resembles the researcher's own INCLUDED examples) or EXCLUDE (matches the exclude criteria, or resembles the researcher's own EXCLUDED examples).
4. If an item is genuinely ambiguous or you lack a criterion to judge it by, leave it out of BOTH lists rather than guessing.
5. RETURN ONLY a valid JSON object with STRING IDs exactly as they appear in [ID] markers, shaped like:
   {{"include": ["abc123", "xyz789"], "exclude": ["def456"]}}
6. If nothing matches either direction, return: {{"include": [], "exclude": []}}

CRITICAL: Return ONLY the raw JSON object. No markdown, no backticks, no explanation."""


def _build_user_prompt(
    label: str, include_prompt: str, exclude_prompt: str, examples_block: str, batch: str
) -> str:
    """Per-batch user prompt: whichever of criteria / prior-decision
    examples were supplied, followed by the batch itself. Replaces the
    single-criteria f-string this module used to build inline.
    """
    sections = []
    if include_prompt:
        sections.append(f"INCLUDE criteria: {include_prompt}")
    if exclude_prompt:
        sections.append(f"EXCLUDE criteria: {exclude_prompt}")
    if examples_block:
        sections.append(f"PRIOR DECISIONS BY THE RESEARCHER -- match this judgement:\n{examples_block}")
    if not sections:
        sections.append(f"Classify every {label.lower()} using your own best judgement.")
    sections.append(f"{label} to analyze:\n{batch}")
    return "\n\n".join(sections)


def _ids_in_batch(batch: str) -> set:
    """The set of ``[ID]`` markers actually present in a batch, so an id
    the model hallucinates (not in the content it was sent) never gets
    applied to a row -- there is no such row key on the editor side, and
    it would otherwise ride along into the submit payload unexplained.
    """
    return set(re.findall(r"\[([^\[\]\n]+)\]", batch))


async def _run_batched_filter(
    content_type: str,
    include_prompt: str,
    exclude_prompt: str,
    examples_block: str,
    content: str,
    api_key: str,
    model: str,
    system_prompt: str,
    progress: ProgressTracker | None = None,
) -> tuple[list, list, str, dict]:
    """
    Shared batched triage logic for both posts and comments.

    Batch execution and error policy (batch 1 failure raises immediately,
    a later batch failure stops and keeps what succeeded) both come from
    ``context_window.run_sequential_batches``.

    Returns:
        tuple: (include_ids, exclude_ids, last_user_prompt, coverage)
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
    chosen_model = model
    paid_model = is_paid_model(chosen_model)
    scaffolding_chars = (
        len(system_prompt) + len(include_prompt) + len(exclude_prompt) + len(examples_block) + 1000
    )
    max_content_chars = context_window.max_prompt_chars(
        chosen_model,
        reserved_chars=scaffolding_chars,
        # Output is one ID per matching item, in either list -- scales
        # with the batch, so reserve a proportional slice of the window.
        output_reserve_tokens=context_window.proportional_output_reserve(chosen_model, 0.15),
    )

    _log_ai(f"FILTER_{content_type.upper()}", f"Starting with {chosen_model}", {
        "content_chars": f"{len(content):,}"
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
        _build_user_prompt(label, include_prompt, exclude_prompt, examples_block, batch) for batch in batches
    ]

    async def _run_one_batch(i: int, batch: str) -> tuple[list, list]:
        _log_ai("BATCH", f"Processing batch {i+1}/{len(batches)}", {"chars": f"{len(batch):,}"})
        response = await get_client(system_prompt, user_prompts[i], api_key, chosen_model)

        _log_ai("RESPONSE", f"Batch {i+1} response ({len(response)} chars):")
        print(f"    {_preview_response(response, 300)}")

        include_ids, exclude_ids = parse_decision_object(response)
        valid_ids = _ids_in_batch(batch)
        include_ids = [i for i in include_ids if i in valid_ids]
        exclude_ids = [i for i in exclude_ids if i in valid_ids and i not in include_ids]
        _log_ai("BATCH_RESULT", f"Batch {i+1}: {len(include_ids)} include, {len(exclude_ids)} exclude")
        return include_ids, exclude_ids

    batch_results, run_coverage = await context_window.run_sequential_batches(batches, _run_one_batch, progress=progress)
    all_include = [id_ for inc, _exc in batch_results for id_ in inc]
    all_exclude = [id_ for _inc, exc in batch_results for id_ in exc]
    unique_include = list(dict.fromkeys(all_include))
    unique_exclude = list(dict.fromkeys(all_exclude))
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
    _log_ai("COMPLETE", f"Total: {len(unique_include)} include, {len(unique_exclude)} exclude")

    return unique_include, unique_exclude, last_user_prompt, coverage


async def triage_posts_with_ai(
    include_prompt: str,
    exclude_prompt: str,
    examples_block: str,
    posts_content: str,
    api_key: str,
    model: str = "",
    *,
    progress: ProgressTracker | None = None,
) -> tuple[list, list, str, str, dict]:
    """
    Use AI to triage posts into include/exclude. Raises AIFilterError on
    first-batch failure.

    Returns ``(include_ids, exclude_ids, system_prompt, last_user_prompt, coverage)``
    -- see ``_run_batched_filter`` for ``coverage``'s shape.
    """
    system_prompt = _build_triage_system_prompt("Posts")

    include_ids, exclude_ids, last_user_prompt, coverage = await _run_batched_filter(
        "posts", include_prompt, exclude_prompt, examples_block, posts_content, api_key, model, system_prompt,
        progress=progress,
    )
    return include_ids, exclude_ids, system_prompt, last_user_prompt, coverage


async def triage_comments_with_ai(
    include_prompt: str,
    exclude_prompt: str,
    examples_block: str,
    comments_content: str,
    api_key: str,
    model: str = "",
    *,
    progress: ProgressTracker | None = None,
) -> tuple[list, list, str, str, dict]:
    """
    Use AI to triage comments into include/exclude. Raises AIFilterError on
    first-batch failure.

    Returns ``(include_ids, exclude_ids, system_prompt, last_user_prompt, coverage)``
    -- see ``_run_batched_filter`` for ``coverage``'s shape.
    """
    system_prompt = _build_triage_system_prompt("Comments")

    include_ids, exclude_ids, last_user_prompt, coverage = await _run_batched_filter(
        "comments", include_prompt, exclude_prompt, examples_block, comments_content, api_key, model, system_prompt,
        progress=progress,
    )
    return include_ids, exclude_ids, system_prompt, last_user_prompt, coverage


def wrap_in_python_array(content) -> list:
    """
    Coerce a parsed value (or, if given a raw string, an AI response) into
    a list of ID strings. Handles various formats the AI might return.

    Kept for its regex fallback: ``parse_decision_object`` calls this on
    the whole response when JSON parsing fails, in case the model reverted
    to the old "just an array" habit.
    """
    if isinstance(content, list):
        return [str(x) for x in content if x is not None]

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


def parse_decision_object(content: str) -> tuple[list, list]:
    """Parse an AI triage response into ``(include_ids, exclude_ids)``.

    Expects ``{"include": [...], "exclude": [...]}`` (the current system
    prompt's contract). Falls back to reading a bare JSON/Python array as
    an include-only list -- some models still answer with just an array
    despite instructions, and that answer is still useful.
    """
    stripped = strip_markdown_fences(content)

    try:
        obj = json.loads(stripped)
    except Exception:
        try:
            obj = ast.literal_eval(stripped)
        except Exception:
            obj = None

    if isinstance(obj, dict):
        include_ids = wrap_in_python_array(obj.get("include") or [])
        exclude_ids = wrap_in_python_array(obj.get("exclude") or [])
        _log_ai("PARSE", f"Parsed decision object: {len(include_ids)} include, {len(exclude_ids)} exclude")
        return include_ids, exclude_ids

    if isinstance(obj, list):
        _log_ai("PARSE_WARN", "Response was a bare array, not a decision object -- treating as include-only")
        return wrap_in_python_array(obj), []

    _log_ai("PARSE_WARN", "Response was neither a JSON object nor an array, falling back to regex array extraction")
    return wrap_in_python_array(stripped), []
