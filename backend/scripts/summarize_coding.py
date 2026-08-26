from backend.app.external import context_window
from backend.app.jobs.progress import ProgressTracker
from backend.scripts.codebook_generator import get_client, MODEL_3

_SYSTEM_PROMPT = (
    "You are an expert qualitative researcher specializing in thematic analysis and coding techniques. "
    "Your task is to analyze and summarize coded qualitative data using established qualitative research methods. "
    "Provide a comprehensive summary that includes:\n"
    "- Key themes and patterns identified in the coding\n"
    "- Frequency and distribution of codes\n"
    "- Relationships between codes and themes\n"
    "- Representative quotes or examples from the data\n"
    "- Overall insights and implications\n"
    "- Methodological observations about the coding approach\n"
    "Structure your response clearly with headings and be thorough but concise. "
    "Return the full summary as text (no extra JSON or metadata)."
)

_REDUCE_SYSTEM_PROMPT = (
    "You are an expert qualitative researcher. You are given SEVERAL PARTIAL SUMMARIES, each "
    "independently written from a different subset of the same larger coded dataset. Combine them "
    "into ONE comprehensive summary that:\n"
    "- Preserves every distinct theme and code mentioned across the partial summaries\n"
    "- Merges frequency/distribution notes into overall figures rather than repeating them per-subset\n"
    "- Keeps the most representative quotes/examples, without duplicating overlapping ones\n"
    "- Reads as a single, coherent analysis, not a list of the partial summaries\n"
    "Structure your response clearly with headings and be thorough but concise. "
    "Return the full summary as text (no extra JSON or metadata)."
)


def build_aggregated_coding_data(code_summaries: list[dict]) -> str:
    """Render ``coding_repo.code_summary_with_samples``'s output as the
    ``coding_data`` text ``summarize_coding`` expects -- exact counts per
    code plus a capped sample of evidence, instead of every raw coded row.
    """
    blocks = []
    for entry in code_summaries:
        quotes = "\n".join(f'- "{q}"' for q in entry.get("sample_evidence") or [])
        block = f"CODE: {entry['code']} (used {entry['count']} times)"
        if quotes:
            block += f"\nSample evidence:\n{quotes}"
        blocks.append(block)
    return "\n\n".join(blocks)


def _build_user_prompt(coding_data: str, extra_instructions: str) -> str:
    return (
        f"Coding Data to Summarize: {coding_data} Additional Instructions: {extra_instructions} "
        "Please provide a comprehensive summary of this coded qualitative data using qualitative "
        "research techniques."
    )


def _build_reduce_user_prompt(partial_summaries: list[str], extra_instructions: str) -> str:
    blocks = "\n\n".join(f"--- PARTIAL SUMMARY {i + 1} ---\n{s}" for i, s in enumerate(partial_summaries))
    return f"{blocks}\n\nAdditional Instructions: {extra_instructions}"


async def summarize_coding(
    coding_data: str,
    user_prompt: str = "",
    api_key: str = "",
    model: str = "",
    *,
    progress: ProgressTracker | None = None,
) -> tuple[str, dict]:
    """Summarize a coding output using qualitative coding techniques.

    ``coding_data`` is chunked to fit the chosen model's context window
    when it's too large for one call: each batch is summarized
    independently (map), then one reduce call combines the partial
    summaries into a single comprehensive one -- summarization, like
    codebook generation, synthesizes across the whole input, so partial
    summaries need reconciling rather than simple concatenation. The
    common case (content fits in one batch) skips the reduce call
    entirely. In practice this fallback rarely triggers: callers should
    prefer passing already-aggregated input (see
    ``build_aggregated_coding_data``), which is normally far smaller than
    any batching threshold.

    Returns ``(summary, coverage)``. If a later map batch fails (e.g. the
    account runs out of credits mid-run), or the final reduce call itself
    fails, this returns the partial summaries that DID complete --
    concatenated, un-combined -- instead of discarding them; ``coverage``
    (see ``context_window.run_sequential_batches``) records that so the
    caller can surface a partial-result warning. A first-batch failure
    still raises (nothing to salvage), same as before.
    """
    if not coding_data:
        raise ValueError("Coding data is required")

    if not api_key:
        raise ValueError("API key is required")

    chosen_model = model or MODEL_3
    trivial_coverage = {"batches_processed": 1, "batches_total": 1, "error": None}

    reserved_chars = len(_SYSTEM_PROMPT) + len(_build_user_prompt("", user_prompt)) + 1000
    max_content_chars = context_window.max_prompt_chars(
        chosen_model,
        reserved_chars=reserved_chars,
        # A summary is bounded regardless of how much coded data it
        # covers -- a fixed reserve, not a proportional one.
        output_reserve_tokens=context_window.BOUNDED_OUTPUT_TOKENS,
    )
    batches = context_window.batch_by_separator(coding_data, max_content_chars, separator="\n\n")

    if len(batches) == 1:
        try:
            summary = await get_client(_SYSTEM_PROMPT, _build_user_prompt(coding_data, user_prompt), api_key, chosen_model)
        except Exception as exc:
            raise ValueError(f"Failed to generate summary: {str(exc)}") from exc
        return summary, trivial_coverage

    # +1 for the reduce call below, so the bar reflects the full amount of
    # LLM work this map-reduce run does, not just the map half.
    if progress is not None:
        await progress.add_total(len(batches) + 1)

    async def _run_one_batch(i: int, batch: str) -> str:
        return await get_client(_SYSTEM_PROMPT, _build_user_prompt(batch, user_prompt), api_key, chosen_model)

    try:
        partial_summaries, map_coverage = await context_window.run_sequential_batches(
            batches, _run_one_batch, progress=progress
        )
    except Exception as exc:
        # The very first batch failed -- nothing succeeded yet, so there's
        # nothing to salvage.
        raise ValueError(f"Failed to generate summary: {str(exc)}") from exc

    if map_coverage["error"] is not None:
        # The map step itself only partially completed -- there's nothing
        # coherent to combine, so return the partial summaries that DID
        # succeed verbatim rather than losing them to a failed reduce too.
        return "\n\n".join(partial_summaries), map_coverage

    reduce_prompt = _build_reduce_user_prompt(partial_summaries, user_prompt)
    try:
        summary = await get_client(_REDUCE_SYSTEM_PROMPT, reduce_prompt, api_key, chosen_model)
    except Exception as exc:
        if progress is not None:
            await progress.advance()
        coverage = {
            "batches_processed": map_coverage["batches_processed"],
            "batches_total": map_coverage["batches_total"] + 1,
            "error": str(exc),
        }
        return "\n\n".join(partial_summaries), coverage

    if progress is not None:
        await progress.advance()
    coverage = {
        "batches_processed": map_coverage["batches_processed"] + 1,
        "batches_total": map_coverage["batches_total"] + 1,
        "error": None,
    }
    return summary, coverage