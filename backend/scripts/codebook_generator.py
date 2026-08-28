import json

from backend.app.ai_models import model_slug_at
from backend.app.external import context_window
from backend.app.external.openrouter_client import chat_completion, json_chat_completion
from backend.app.external.response_parsers import parse_json_object, strip_markdown_fences
from backend.app.jobs.progress import ProgressTracker

MODEL_1 = model_slug_at(0)
MODEL_2 = model_slug_at(1)
MODEL_3 = model_slug_at(2)
MODEL_4 = model_slug_at(3)
MODEL_5 = model_slug_at(4)
MODEL_6 = model_slug_at(5)
MODEL_7 = model_slug_at(6)
MAX_RETRIES = 2

# Flat -- one object per code, family name repeated -- rather than nested
# by family: fewer nesting levels is easier for weaker models, same lesson
# as codebook_apply.CODING_JSON_SCHEMA.
CODEBOOK_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "codes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "family": {"type": "string"},
                    "name": {"type": "string"},
                    "definition": {"type": "string"},
                    "inclusion": {"type": "string"},
                    "exclusion": {"type": "string"},
                    "keywords": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": [
                    "family",
                    "name",
                    "definition",
                    "inclusion",
                    "exclusion",
                    "keywords",
                    "example",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["codes"],
    "additionalProperties": False,
}


async def get_client(system_prompt: str, user_prompt: str, api_key: str, MODEL: str) -> str:
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    result = await chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=MODEL,
        timeout=30.0,
        max_retries=MAX_RETRIES,
    )
    # compare_codebooks / compare_codings / summarize_coding treat this as
    # free-form prose -- strip an occasional ``` fence wrapper here once.
    return strip_markdown_fences(result)


async def _json_client(system_prompt: str, user_prompt: str, api_key: str, MODEL: str) -> str:
    # Same seam as codebook_apply.get_client: json_chat_completion + a
    # schema, so OpenRouter is asked for JSON three ways (strict schema,
    # json_object, prompt-only) rather than hoping a markdown prompt holds.
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    return await json_chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=MODEL,
        json_schema=CODEBOOK_JSON_SCHEMA,
        timeout=30.0,
        max_retries=MAX_RETRIES,
    )

# Same trick as codebook_apply.classify_posts: the JSON object is written
# into the prompt as a literal example (the "DSL") *and* passed as a
# json_schema to json_chat_completion. The inline shape is what weaker
# models copy when constrained decoding isn't available.
_GENERATE_JSON_SHAPE = (
    '{"codes": [{"family": "<theme name>", "name": "<code name>", '
    '"definition": "<concise definition>", "inclusion": "<when to use this code>", '
    '"exclusion": "<when NOT to use this code>", '
    '"keywords": "<words or phrases frequently found with this code>", '
    '"example": "<quote from the data>"}]}'
)

_GENERATE_SYSTEM_PROMPT = (
    "You are a qualitative researcher analyzing the provided data.\n"
    "Develop a concise codebook via open coding. Identify meaningful themes, write "
    "clear code definitions, specify inclusion and exclusion criteria, suggest "
    "representative keywords, and provide example excerpts. Group codes into a few "
    "broad families rather than many small ones.\n\n"
    "Return a single JSON object of exactly this shape (no markdown, no code fences, no explanation "
    "text -- the JSON object and nothing else):\n"
    f"{_GENERATE_JSON_SHAPE}\n\n"
    "Rules:\n"
    "- family is the code family / theme name.\n"
    "- name is the code name.\n"
    "- definition is a concise definition of the code.\n"
    "- inclusion is when to use this code.\n"
    "- exclusion is when NOT to use this code.\n"
    "- keywords are words or phrases frequently found with this code.\n"
    "- example is a quote from the data.\n"
    "- Output one object per code."
)

_CONSOLIDATE_SYSTEM_PROMPT = (
    "You are an expert qualitative researcher. You are given SEVERAL DRAFT CODEBOOKS as JSON, "
    "each independently generated from a different subset of the same larger dataset. Merge them "
    "into ONE final, coherent codebook:\n"
    "- Merge codes that describe the same underlying concept, even if named differently -- pick "
    "the clearer name (or a better one) and combine their definitions, inclusion criteria, "
    "exclusion criteria, and keywords.\n"
    "- Keep codes that are genuinely distinct as separate codes.\n"
    "- Re-group the merged codes into a few broad families (don't just concatenate the input "
    "families verbatim).\n"
    "- Preserve at least one example excerpt per merged code (pick the clearest one if duplicated "
    "across drafts).\n\n"
    "Return a single JSON object of exactly this shape (no markdown, no code fences, no explanation "
    "text -- the JSON object and nothing else):\n"
    f"{_GENERATE_JSON_SHAPE}"
)


def _build_generate_user_prompt(posts_content: str, custom_prompt: str) -> str:
    return (
        "Analyze DATA and return only the required JSON."
        f"\n\nDATA:\n{posts_content}\n\nAdditional instructions: {custom_prompt}"
    )


def _build_consolidation_user_prompt(drafts: list[str], custom_prompt: str) -> str:
    draft_blocks = "\n\n".join(f"--- DRAFT CODEBOOK {i + 1} ---\n{draft}" for i, draft in enumerate(drafts))
    return f"{draft_blocks}\n\nAdditional Instructions: {custom_prompt}"


def merge_codebook_json_drafts(drafts: list[str]) -> str:
    """Concatenate the ``codes`` arrays from each draft JSON object.

    Partial map-reduce failure used to ``"\\n\\n".join`` markdown drafts;
    joining JSON objects is invalid, so this is the equivalent fallback.
    A draft that isn't a ``{"codes": [...]}`` object is skipped.
    """
    codes: list[object] = []
    for draft in drafts:
        try:
            obj = parse_json_object(draft)
        except (TypeError, ValueError):
            continue
        items = obj.get("codes")
        if isinstance(items, list):
            codes.extend(item for item in items if isinstance(item, dict))
    return json.dumps({"codes": codes})


async def generate_codebook(posts_content: str, api_key: str, custom_prompt: str = "", MODEL: str = MODEL_1) -> tuple[str, str, str]:
    system_prompt = _GENERATE_SYSTEM_PROMPT
    user_prompt = _build_generate_user_prompt(posts_content, custom_prompt)

    result = await _json_client(system_prompt, user_prompt, api_key, MODEL)
    return result, system_prompt, user_prompt


async def generate_codebook_map_reduce(
    posts_content: str,
    api_key: str,
    custom_prompt: str = "",
    MODEL: str = MODEL_1,
    *,
    progress: ProgressTracker | None = None,
) -> tuple[str, str, str, dict]:
    """Generate a codebook from ``posts_content``, batching + reconciling
    across multiple LLM calls when it's too large for one.

    Unlike filter/apply's independent per-item classification, codebook
    generation *synthesizes* a taxonomy over the whole dataset -- two
    batches could independently invent overlapping/duplicate codes, so
    per-batch outputs can't just be concatenated. When more than one batch
    is needed, this runs a map step (today's single-batch
    ``generate_codebook`` prompt, once per batch) followed by one
    reduce/consolidation call that merges the drafts into one coherent
    codebook. The common case (content fits in one batch) skips the
    reduce call entirely, preserving today's exact one-call cost and
    behavior.

    Returns ``(codebook_json, system_prompt, user_prompt, coverage)``.
    If a later map batch fails (e.g. the account runs out of credits
    mid-run), or the final reduce call itself fails, this returns the
    drafts that DID complete -- ``codes`` arrays merged, un-consolidated
    -- instead of discarding them; ``coverage`` (see
    ``context_window.run_sequential_batches``) records that so the caller
    can surface a partial-result warning.
    """
    reserved_chars = len(_GENERATE_SYSTEM_PROMPT) + len(_build_generate_user_prompt("", custom_prompt)) + 1000
    max_content_chars = context_window.max_prompt_chars(
        MODEL,
        reserved_chars=reserved_chars,
        # A codebook is a bounded taxonomy regardless of how much input it
        # was distilled from -- a fixed reserve, not a proportional one.
        output_reserve_tokens=context_window.BOUNDED_OUTPUT_TOKENS,
    )
    batches = context_window.batch_by_separator(posts_content, max_content_chars, separator=context_window.ITEM_SEPARATOR)

    if len(batches) == 1:
        result, system_prompt, user_prompt = await generate_codebook(posts_content, api_key, custom_prompt, MODEL=MODEL)
        return result, system_prompt, user_prompt, {"batches_processed": 1, "batches_total": 1, "error": None}

    # +1 for the reduce call below, so the bar reflects the full amount of
    # LLM work this map-reduce run does, not just the map half.
    if progress is not None:
        await progress.add_total(len(batches) + 1)

    async def _run_one_draft(i: int, batch: str) -> str:
        draft, _, _ = await generate_codebook(batch, api_key, custom_prompt, MODEL=MODEL)
        return draft

    drafts, map_coverage = await context_window.run_sequential_batches(batches, _run_one_draft, progress=progress)

    if map_coverage["error"] is not None:
        # The map step itself only partially completed -- there's nothing
        # coherent to consolidate, so return the drafts that DID succeed
        # merged rather than losing them to a failed reduce call too.
        fallback_text = merge_codebook_json_drafts(drafts)
        fallback_prompt = _build_generate_user_prompt(posts_content, custom_prompt)
        return fallback_text, _GENERATE_SYSTEM_PROMPT, fallback_prompt, map_coverage

    reduce_user_prompt = _build_consolidation_user_prompt(drafts, custom_prompt)
    try:
        consolidated = await _json_client(_CONSOLIDATE_SYSTEM_PROMPT, reduce_user_prompt, api_key, MODEL)
    except Exception as exc:
        if progress is not None:
            await progress.advance()
        fallback_text = merge_codebook_json_drafts(drafts)
        coverage = {
            "batches_processed": map_coverage["batches_processed"],
            "batches_total": map_coverage["batches_total"] + 1,
            "error": str(exc),
        }
        return fallback_text, _GENERATE_SYSTEM_PROMPT, reduce_user_prompt, coverage

    if progress is not None:
        await progress.advance()
    coverage = {
        "batches_processed": map_coverage["batches_processed"] + 1,
        "batches_total": map_coverage["batches_total"] + 1,
        "error": None,
    }
    return consolidated, _CONSOLIDATE_SYSTEM_PROMPT, reduce_user_prompt, coverage
