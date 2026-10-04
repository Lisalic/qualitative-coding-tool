import json

from backend.app.core.evidence_match import normalize_label
from backend.app.external import context_window
from backend.app.external.openrouter_client import chat_completion, json_chat_completion
from backend.app.external.response_parsers import parse_json_object, strip_markdown_fences
from backend.app.jobs.progress import ProgressTracker

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
    # summarize_coding treats this as free-form prose -- strip an
    # occasional ``` fence wrapper here once.
    return strip_markdown_fences(result)


async def _json_client(
    system_prompt: str, user_prompt: str, api_key: str, MODEL: str, *, json_schema: dict
) -> str:
    # Same seam as codebook_apply.get_client: json_chat_completion + a
    # schema, so OpenRouter is asked for JSON three ways (strict schema,
    # json_object, prompt-only) rather than hoping a markdown prompt holds.
    # json_schema is required (not defaulted to CODEBOOK_JSON_SCHEMA) so a
    # caller can never silently ask for the generate/consolidate shape
    # while thinking it asked for the integrate shape (or vice versa) --
    # see INTEGRATE_JSON_SCHEMA below.
    if not api_key:
        raise ValueError("OpenRouter API key is required")
    return await json_chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=MODEL,
        json_schema=json_schema,
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

# Appended to _GENERATE_SYSTEM_PROMPT when the caller already has a draft
# codebook (the /codebook-editor "propose more codes" pass). The model is
# shown what exists and asked for what is missing, so a second pass over
# the same data adds to the researcher's draft instead of restating it.
_EXISTING_CODES_RULES = (
    "\n\nThe researcher has ALREADY written the codes listed under EXISTING CODES below.\n"
    "- Propose only codes that are NOT already covered by an existing code.\n"
    "- Never restate, rename, or lightly reword an existing code.\n"
    "- If a theme in the data is already fully covered, say nothing about it.\n"
    "- Reuse an existing family name when a new code belongs to that family.\n\n"
    "EXISTING CODES:\n"
)


def build_system_prompt(existing_codes: str = "") -> str:
    """The open-coding system prompt, optionally carrying the researcher's
    current draft so the model proposes *additional* codes rather than a
    fresh taxonomy. Empty ``existing_codes`` reproduces the original
    prompt byte for byte, so the one-shot generate path is unchanged.
    """
    existing_codes = (existing_codes or "").strip()
    if not existing_codes:
        return _GENERATE_SYSTEM_PROMPT
    return _GENERATE_SYSTEM_PROMPT + _EXISTING_CODES_RULES + existing_codes


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
    A draft that isn't a ``{"codes": [...]}`` object is skipped, and a
    code two drafts both proposed (same family and name, compared the way
    ``codebook_service`` enforces uniqueness) is kept once.
    """
    codes: list[object] = []
    seen: set[tuple[str, str]] = set()
    for draft in drafts:
        try:
            obj = parse_json_object(draft)
        except (TypeError, ValueError):
            continue
        items = obj.get("codes")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            key = (normalize_label(str(item.get("family") or "")), normalize_label(str(item.get("name") or "")))
            if key in seen:
                continue
            seen.add(key)
            codes.append(item)
    return json.dumps({"codes": codes})


async def generate_codebook(
    posts_content: str,
    api_key: str,
    custom_prompt: str = "",
    *,
    MODEL: str,
    existing_codes: str = "",
) -> tuple[str, str, str]:
    system_prompt = build_system_prompt(existing_codes)
    user_prompt = _build_generate_user_prompt(posts_content, custom_prompt)

    result = await _json_client(system_prompt, user_prompt, api_key, MODEL, json_schema=CODEBOOK_JSON_SCHEMA)
    return result, system_prompt, user_prompt


async def generate_codebook_map_reduce(
    posts_content: str,
    api_key: str,
    custom_prompt: str = "",
    *,
    MODEL: str,
    progress: ProgressTracker | None = None,
    existing_codes: str = "",
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
    system_prompt_for_batches = build_system_prompt(existing_codes)
    reserved_chars = len(system_prompt_for_batches) + len(_build_generate_user_prompt("", custom_prompt)) + 1000
    max_content_chars = context_window.max_prompt_chars(
        MODEL,
        reserved_chars=reserved_chars,
        # A codebook is a bounded taxonomy regardless of how much input it
        # was distilled from -- a fixed reserve, not a proportional one.
        output_reserve_tokens=context_window.BOUNDED_OUTPUT_TOKENS,
    )
    batches = context_window.batch_by_separator(posts_content, max_content_chars, separator=context_window.ITEM_SEPARATOR)

    if len(batches) == 1:
        result, system_prompt, user_prompt = await generate_codebook(
            posts_content, api_key, custom_prompt, MODEL=MODEL, existing_codes=existing_codes
        )
        return result, system_prompt, user_prompt, {"batches_processed": 1, "batches_total": 1, "error": None}

    # +1 for the reduce call below, so the bar reflects the full amount of
    # LLM work this map-reduce run does, not just the map half.
    if progress is not None:
        await progress.add_total(len(batches) + 1)

    async def _run_one_draft(i: int, batch: str) -> str:
        draft, _, _ = await generate_codebook(
            batch, api_key, custom_prompt, MODEL=MODEL, existing_codes=existing_codes
        )
        parsed = parse_json_object(draft)
        if not isinstance(parsed.get("codes"), list):
            raise ValueError(f"Batch {i+1}/{len(batches)}: the model's reply has no codes array")
        return draft

    drafts, map_coverage = await context_window.run_sequential_batches(batches, _run_one_draft, progress=progress)

    if map_coverage["error"] is not None:
        # The map step itself only partially completed -- there's nothing
        # coherent to consolidate, so return the drafts that DID succeed
        # merged rather than losing them to a failed reduce call too.
        fallback_text = merge_codebook_json_drafts(drafts)
        fallback_prompt = _build_generate_user_prompt(posts_content, custom_prompt)
        return fallback_text, system_prompt_for_batches, fallback_prompt, map_coverage

    reduce_user_prompt = _build_consolidation_user_prompt(drafts, custom_prompt)
    try:
        consolidated = await _json_client(
            _CONSOLIDATE_SYSTEM_PROMPT, reduce_user_prompt, api_key, MODEL, json_schema=CODEBOOK_JSON_SCHEMA
        )
    except Exception as exc:  # noqa: BLE001 - preserve map drafts if the reduce call fails
        if progress is not None:
            await progress.advance()
        fallback_text = merge_codebook_json_drafts(drafts)
        coverage = {
            "batches_processed": map_coverage["batches_processed"],
            "batches_total": map_coverage["batches_total"] + 1,
            "error": str(exc),
        }
        return fallback_text, system_prompt_for_batches, reduce_user_prompt, coverage

    if progress is not None:
        await progress.advance()
    coverage = {
        "batches_processed": map_coverage["batches_processed"] + 1,
        "batches_total": map_coverage["batches_total"] + 1,
        "error": None,
    }
    return consolidated, _CONSOLIDATE_SYSTEM_PROMPT, reduce_user_prompt, coverage


# ---------------------------------------------------------------------------
# integrate_codebooks: merge several whole, researcher-authored codebooks
# into one. Distinct from generate_codebook_map_reduce's consolidation step
# above -- that step merges DRAFTS of the same dataset (no cross-references
# needed); this merges independently-curated codebooks and must say, for
# each merged code, exactly which source code(s) it came from, so a human
# reviewer can trust (and correct) the merge rather than re-deriving it.
# ---------------------------------------------------------------------------

# Same flat shape as CODEBOOK_JSON_SCHEMA, plus per-code provenance: which
# source codebook(s) (1-based index into the CODEBOOK blocks shown in the
# prompt) and which source code within it. `codebook_generator.py`.
INTEGRATE_JSON_SCHEMA = {
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
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "codebook": {"type": "integer"},
                                "family": {"type": "string"},
                                "name": {"type": "string"},
                            },
                            "required": ["codebook", "family", "name"],
                            "additionalProperties": False,
                        },
                    },
                    "rationale": {"type": "string"},
                },
                "required": [
                    "family",
                    "name",
                    "definition",
                    "inclusion",
                    "exclusion",
                    "keywords",
                    "example",
                    "sources",
                    "rationale",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["codes"],
    "additionalProperties": False,
}

_INTEGRATE_JSON_SHAPE = (
    '{"codes": [{"family": "<theme name>", "name": "<code name>", '
    '"definition": "<concise definition>", "inclusion": "<when to use this code>", '
    '"exclusion": "<when NOT to use this code>", '
    '"keywords": "<words or phrases frequently found with this code>", '
    '"example": "<quote from the data>", '
    '"sources": [{"codebook": <1-based codebook number>, "family": "<its family name>", '
    '"name": "<its code name>"}], '
    '"rationale": "<one sentence -- required whenever a code has more than one source>"}]}'
)

_INTEGRATE_SYSTEM_PROMPT = (
    "You are an expert qualitative researcher. You are given SEVERAL CODEBOOKS, each written "
    "independently by a researcher (not drafts of one run -- each may use its own terminology "
    "and organization). Merge them into ONE final, coherent codebook:\n"
    "- Merge codes that describe the same underlying concept, even if named differently -- pick "
    "the clearer name (or a better one) and combine their definitions, inclusion criteria, "
    "exclusion criteria, and keywords.\n"
    "- Keep codes that are genuinely distinct as separate codes.\n"
    "- A code that appears in only one codebook is still a real code -- carry it through "
    "unchanged rather than dropping it.\n"
    "- Re-group the merged codes into a few broad families (don't just concatenate the input "
    "families verbatim).\n"
    "- Preserve at least one example excerpt per merged code (pick the clearest one if duplicated "
    "across sources).\n"
    "- For every code in your answer, list every source code it came from in \"sources\", using "
    "the 1-based CODEBOOK number shown in the input and that source code's own family/name. A "
    "code carried through from one codebook still needs exactly one entry in \"sources\".\n"
    "- Set \"rationale\" to one sentence explaining the merge whenever a code has more than one "
    "source; leave it an empty string for a single-source code.\n\n"
    "Return a single JSON object of exactly this shape (no markdown, no code fences, no explanation "
    "text -- the JSON object and nothing else):\n"
    f"{_INTEGRATE_JSON_SHAPE}"
)


def build_integrate_system_prompt(existing_codes: str = "") -> str:
    """The integrate-codebooks system prompt, optionally carrying the
    researcher's current draft (a second/re-run pass) so the model
    proposes only what's still missing -- same structure and same
    ``_EXISTING_CODES_RULES`` text as ``build_system_prompt``, whose
    wording ("propose only codes NOT already covered", "never restate or
    lightly reword") reads correctly for a merge too.
    """
    existing_codes = (existing_codes or "").strip()
    if not existing_codes:
        return _INTEGRATE_SYSTEM_PROMPT
    return _INTEGRATE_SYSTEM_PROMPT + _EXISTING_CODES_RULES + existing_codes


_INTEGRATE_COMPARISON_PREAMBLE = (
    "The researcher previously compared these codebooks. Use the comparison "
    "report(s) below as guidance on overlaps, conflicts and suggested merges, "
    "but treat the codebooks above as authoritative -- only propose codes "
    "grounded in them, and cite sources from them, never from the report."
)


def build_integrate_user_prompt(codebook_blocks: str, custom_prompt: str, comparison_blocks: str = "") -> str:
    """Public (unlike ``_build_generate_user_prompt``/
    ``_build_consolidation_user_prompt``) because
    ``codebook_service._run_integrate_codebook_job`` needs the exact
    rendered prompt ahead of the LLM call, to size it against the
    model's context window (``context_window.prompt_fits``) before
    spending a call on it.

    ``comparison_blocks`` (optional) is one or more rendered
    ``--- COMPARISON REPORT: name ---`` sections from Compare Codebook,
    placed after the codebooks and before the researcher's own
    suggestions so the merge can follow the comparison's recommendations.
    """
    parts = [codebook_blocks]
    comparison_blocks = (comparison_blocks or "").strip()
    if comparison_blocks:
        parts.append(f"{_INTEGRATE_COMPARISON_PREAMBLE}\n\n{comparison_blocks}")
    parts.append(f"Researcher's suggestions: {custom_prompt}")
    return "\n\n".join(parts)


async def integrate_codebooks(
    codebook_blocks: str,
    api_key: str,
    custom_prompt: str = "",
    *,
    MODEL: str,
    existing_codes: str = "",
    comparison_blocks: str = "",
) -> tuple[str, str, str]:
    """Merge whole codebooks (already rendered into ``codebook_blocks``,
    one ``--- CODEBOOK i: name ---`` section per source) into one, in a
    single call -- no map-reduce. Unlike ``generate_codebook_map_reduce``,
    a merge is inherently over ALL sources at once: batching would merge
    subsets and then merge the merges, changing the result and destroying
    the per-code ``sources`` provenance that is the point of this
    function. Callers are expected to guard the prompt against the
    model's context window themselves (``context_window.prompt_fits``)
    and surface a clear error rather than silently truncating input.

    Returns ``(result_json, system_prompt, user_prompt)``.
    """
    system_prompt = build_integrate_system_prompt(existing_codes)
    user_prompt = build_integrate_user_prompt(codebook_blocks, custom_prompt, comparison_blocks)
    result = await _json_client(system_prompt, user_prompt, api_key, MODEL, json_schema=INTEGRATE_JSON_SCHEMA)
    return result, system_prompt, user_prompt
