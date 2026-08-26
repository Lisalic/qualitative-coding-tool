from backend.app.ai_models import model_slug_at
from backend.app.external import context_window
from backend.app.external.openrouter_client import chat_completion
from backend.app.external.response_parsers import strip_markdown_fences
from backend.app.jobs.progress import ProgressTracker

MODEL_1 = model_slug_at(0)
MODEL_2 = model_slug_at(1)
MODEL_3 = model_slug_at(2)
MODEL_4 = model_slug_at(3)
MODEL_5 = model_slug_at(4)
MODEL_6 = model_slug_at(5)
MODEL_7 = model_slug_at(6)
MAX_RETRIES = 2


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
    # Every caller (generate_codebook, compare_codebooks, compare_codings,
    # summarize_coding) treats this as free-form prose/markdown to render
    # or parse directly -- strip an occasional ``` fence wrapper here once,
    # rather than relying on each caller to remember to.
    return strip_markdown_fences(result)

_GENERATE_SYSTEM_PROMPT = """
    Act as a qualitative researcher analyzing the provided data. Your task is to develop or refine a concise and usable Codebook based on an open coding process applicable to general qualitative research topics.

    Focus on identifying meaningful themes, writing clear code definitions, specifying inclusion criteria, suggesting representative keywords, and providing example excerpts that illustrate each code. Organize the codes into 'full' code families. Instead of creating many small code families, group the codes into a few broad, overarching code families, each containing as many logically related codes as sensible.

    **STRICT OUTPUT INSTRUCTION:** Provide ONLY the codebook content below. Do not include any introductory or concluding conversational text.

    Format the output using the following structure for each code, including the leading "###"/"####" markers exactly as shown:

### Code Family: [Theme Name]
#### Code Name: [Name]
Definition: [Concise Definition]
Inclusion Criteria: [When to use this code]
Key Words: [Words or phrases frequently found in this code]
Example: [Quote from data]
    """

_CONSOLIDATE_SYSTEM_PROMPT = """You are an expert qualitative researcher. You are given SEVERAL DRAFT CODEBOOKS, each independently generated from a different subset of the same larger dataset. Your task is to merge them into ONE final, coherent codebook:
- Merge codes that describe the same underlying concept, even if named differently -- pick the clearer name (or a better one) and combine their definitions, inclusion criteria, and keywords.
- Keep codes that are genuinely distinct as separate codes.
- Re-group the merged codes into a few broad Code Families (don't just concatenate the input Code Families verbatim).
- Preserve at least one Example excerpt per merged code (pick the clearest one if duplicated across drafts).

**STRICT OUTPUT INSTRUCTION:** Output ONLY the final codebook, using the exact same format as the input drafts, including the leading "###"/"####" markers exactly as shown:

### Code Family: [Theme Name]
#### Code Name: [Name]
Definition: [Concise Definition]
Inclusion Criteria: [When to use this code]
Key Words: [Words or phrases frequently found in this code]
Example: [Quote from data]
"""


def _build_generate_user_prompt(posts_content: str, custom_prompt: str) -> str:
    return f"Here is the data for analysis: {posts_content} Additional Instructions: {custom_prompt}"


def _build_consolidation_user_prompt(drafts: list[str], custom_prompt: str) -> str:
    draft_blocks = "\n\n".join(f"--- DRAFT CODEBOOK {i + 1} ---\n{draft}" for i, draft in enumerate(drafts))
    return f"{draft_blocks}\n\nAdditional Instructions: {custom_prompt}"


async def generate_codebook(posts_content: str, api_key: str, custom_prompt: str = "", MODEL: str = MODEL_1) -> tuple[str, str, str]:
    system_prompt = _GENERATE_SYSTEM_PROMPT
    user_prompt = _build_generate_user_prompt(posts_content, custom_prompt)

    result = await get_client(system_prompt, user_prompt, api_key, MODEL)
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

    Returns ``(codebook_text, system_prompt, user_prompt, coverage)``.
    If a later map batch fails (e.g. the account runs out of credits
    mid-run), or the final reduce call itself fails, this returns the
    drafts that DID complete -- concatenated, un-consolidated -- instead
    of discarding them; ``coverage`` (see
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
        # verbatim rather than losing them to a failed reduce call too.
        fallback_text = "\n\n".join(drafts)
        fallback_prompt = _build_generate_user_prompt(posts_content, custom_prompt)
        return fallback_text, _GENERATE_SYSTEM_PROMPT, fallback_prompt, map_coverage

    reduce_user_prompt = _build_consolidation_user_prompt(drafts, custom_prompt)
    try:
        consolidated = await get_client(_CONSOLIDATE_SYSTEM_PROMPT, reduce_user_prompt, api_key, MODEL)
    except Exception as exc:
        if progress is not None:
            await progress.advance()
        fallback_text = "\n\n".join(drafts)
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
