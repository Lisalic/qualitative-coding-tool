from pydantic import ValidationError

from backend.app.ai_models import model_slug_at
from backend.app.api.schemas import AICodingPayload
from backend.app.external import context_window
from backend.app.external.openrouter_client import json_chat_completion
from backend.app.external.response_parsers import parse_json_object
from backend.app.jobs.progress import ProgressTracker

FREE_MODEL = model_slug_at(0)
MAX_RETRIES = 2

# JSON Schema for the strict-decoding tier of the compliance ladder (see
# ``openrouter_client.json_chat_completion``). Flat -- one object per
# (item, code) pair, item_id repeated across objects for the same item --
# rather than nested by item: fewer nesting levels is measurably easier
# for weaker models to produce correctly and trivial to validate
# per-entry, and it matches ``AICodingPayload``/``AICodingEntry`` exactly.
CODING_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "codings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "code": {"type": "string"},
                    "quotes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["item_id", "code", "quotes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["codings"],
    "additionalProperties": False,
}


async def get_client(system_prompt: str, user_prompt: str, api_key: str, model: str = FREE_MODEL) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")

    def _on_retry(attempt: int, exc: Exception, wait_seconds: float) -> None:
        print(f"\nAPI call failed (attempt {attempt}/{MAX_RETRIES}): {type(exc).__name__}")
        print(f"Retrying in {wait_seconds}s...")

    result = await json_chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=model,
        json_schema=CODING_JSON_SCHEMA,
        timeout=30.0,
        max_retries=MAX_RETRIES,
        on_retry=_on_retry,
    )
    print("API call successful.")
    return result


def parse_coding_response(raw_text: str) -> list[dict]:
    """Parse one batch's raw model output into a list of ``{item_id, code,
    quotes}`` dicts.

    Uses ``response_parsers.parse_json_object`` (strips markdown fences,
    requires a JSON object) then validates the ``{"codings": [...]}``
    shape with :class:`AICodingPayload` -- a malformed *individual* entry
    (missing field, wrong type) is dropped rather than failing the whole
    batch, since one bad entry from a weak model shouldn't discard every
    other entry it got right. Raises ``ValueError`` only when the response
    isn't valid JSON at all, or isn't a ``{"codings": [...]}`` object --
    the caller (``classify_posts``) treats that as this batch producing no
    entries.
    """
    obj = parse_json_object(raw_text, error_cls=ValueError)
    codings_raw = obj.get("codings")
    if not isinstance(codings_raw, list):
        raise ValueError("Response JSON must have a 'codings' array")

    entries: list[dict] = []
    for raw_entry in codings_raw:
        try:
            validated = AICodingPayload.model_validate({"codings": [raw_entry]}).codings[0]
        except ValidationError:
            continue
        entries.append({"item_id": validated.item_id, "code": validated.code, "quotes": validated.quotes})
    return entries


def _build_classify_user_prompt(codebook: str, posts_batch: str, methodology: str) -> str:
    return (
        "Apply CODEBOOK to ITEMS CONTENT and return only the required JSON. "
        "Use as many relevant codes per item as evidence supports, and as many quotes "
        "per code as the item's CONTENT actually supports."
        f"\n\nCODEBOOK:\n{codebook}\n\nITEMS CONTENT:\n{posts_batch}\n\nMETHODOLOGY:\n{methodology}"
    )


async def classify_posts(
    codebook: str,
    posts_content: str,
    methodology: str,
    api_key: str,
    model: str = "",
    *,
    progress: ProgressTracker | None = None,
) -> tuple[list[dict], str, str, dict]:
    """Classify every item (post or comment) in ``posts_content`` against
    ``codebook``.

    ``posts_content`` (assembled by
    ``coding_service._assemble_posts_content`` as one or more
    ``POST_ID:``/``TYPE:``/``CONTENT:`` records per item, joined with
    ``context_window.ITEM_SEPARATOR``) is chunked to fit the chosen
    model's context window when it's too large for one call --
    classification is independent per item (a fixed codebook applied to
    each item in isolation), so item ids are disjoint across batches by
    construction and the per-batch parsed entries are simply concatenated,
    no cross-batch reconciliation needed (same shape as
    ``filter_db._run_batched_filter``).

    A comment's record carries an ``IN_REPLY_TO:`` line with its parent
    post's title/text for context -- the model must never quote that line,
    only the comment's own ``CONTENT:``.

    Returns ``(coding_entries, system_prompt, last_user_prompt, coverage)``
    -- ``coding_entries`` is a flat list of ``{item_id, code, quotes}``
    dicts merged across every batch (structurally parsed, but *not yet*
    checked against real data -- that anti-hallucination pass happens in
    ``coding_service`` via ``core/evidence_match.py``). ``coverage`` (see
    ``context_window.run_sequential_batches``) reports whether every
    batch's classification call succeeded; if a later batch fails (e.g.
    the account runs out of credits mid-run), entries from batches that
    already succeeded are still returned rather than discarded.
    """

    print("Starting codebook application process...")

    system_prompt = (
        "You are a qualitative data coder.\n"
        "Apply CODEBOOK to ITEMS CONTENT using METHODOLOGY.\n"
        "Each item in ITEMS CONTENT is separated by a line reading exactly \"<<<ITEM>>>\" and has a POST_ID, "
        "a TYPE (post or comment), and a CONTENT field; a comment item may also have an IN_REPLY_TO field "
        "giving its parent post's title/text as context only.\n\n"
        "Return a single JSON object of exactly this shape (no markdown, no code fences, no explanation "
        "text -- the JSON object and nothing else):\n"
        '{"codings": [{"item_id": "<exact_post_id_from_input>", '
        '"code": "<exact_code_name_from_codebook>", '
        '"quotes": ["<exact_substring_from_that_items_CONTENT>", "..."]}]}\n\n'
        "Rules:\n"
        "- item_id must be copied verbatim from that item's own POST_ID line, including any prefix such as "
        "t3_ or t1_.\n"
        "- code must be an exact code name from CODEBOOK, without its code family name.\n"
        "- Output one object per (item, code) pair -- if the same code applies to an item for more than one "
        "reason, list every supporting quote in that one object's quotes array rather than repeating the "
        "object.\n"
        "- Every quote must be an exact, contiguous substring of that item's own CONTENT field -- never from "
        "TITLE or IN_REPLY_TO, and never paraphrased, summarized, truncated with \"...\", or reformatted. "
        "Copy the characters exactly as they appear, including original punctuation and capitalization.\n"
        "- Consider every item in ITEMS CONTENT and attempt to code each one; omit an item from the output "
        "entirely only if truly no code in CODEBOOK applies to it, not merely because it is ambiguous or "
        "brief.\n"
        "- Do not invent an item_id, a code, or a quote that doesn't genuinely appear in the input."
    )

    chosen_model = model or FREE_MODEL

    # Reserve room for everything the prompt repeats in every batch (the
    # codebook and methodology can themselves be large) so only the
    # remaining budget is spent on posts_content.
    reserved_chars = len(system_prompt) + len(_build_classify_user_prompt(codebook, "", methodology)) + 1000
    max_content_chars = context_window.max_prompt_chars(
        chosen_model,
        reserved_chars=reserved_chars,
        # Output is a JSON object with one entry per (item, code) pair,
        # each quoting the source text back -- the heaviest output-per-
        # input of any pipeline, so reserve a larger share.
        output_reserve_tokens=context_window.proportional_output_reserve(chosen_model, 0.35),
    )
    batches = context_window.batch_by_separator(posts_content, max_content_chars, separator=context_window.ITEM_SEPARATOR)

    print(f"Prompts prepared. Sending request to AI model across {len(batches)} batch(es)...")

    if progress is not None:
        await progress.add_total(len(batches))

    user_prompts = [_build_classify_user_prompt(codebook, batch, methodology) for batch in batches]

    async def _run_one_batch(i: int, batch: str) -> list[dict]:
        raw_result = await get_client(system_prompt, user_prompts[i], api_key, chosen_model)
        try:
            return parse_coding_response(raw_result)
        except ValueError as exc:
            print(f"Batch {i+1}/{len(batches)} output could not be parsed as JSON: {exc}")
            return []

    batch_results, coverage = await context_window.run_sequential_batches(batches, _run_one_batch, progress=progress)
    coding_entries = [entry for batch_entries in batch_results for entry in (batch_entries or [])]
    last_user_prompt = user_prompts[-1] if user_prompts else ""

    print("Response received from AI model. Codebook application completed.")
    return coding_entries, system_prompt, last_user_prompt, coverage
