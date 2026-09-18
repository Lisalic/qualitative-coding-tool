"""Shared context-window sizing and batching for LLM prompts.

Generalizes what ``backend/scripts/filter_db.py`` used to keep as private,
hand-maintained helpers (``MODEL_CONTEXT_LIMITS``/``_estimate_context_limit``/
``_batch_content``) so every LLM-backed pipeline script can chunk oversized
input the same way, sized against the model catalog's real ``context_length``
(``ai_models.context_length_for``) instead of a guessed substring-matched
table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, TypeVar

from backend.app.ai_models import context_length_for
from backend.app.core.exceptions import ContextBudgetError

if TYPE_CHECKING:
    from backend.app.jobs.progress import ProgressTracker

T = TypeVar("T")

CHARS_PER_TOKEN = 4
DEFAULT_SEPARATOR = "\n---\n"

# Separator for records that are themselves multi-line (e.g. an item
# assembled as several "LABEL: value" lines for codebook_apply /
# codebook_generator). "\n\n" is unsafe for this because Reddit
# selftext/body routinely contains blank lines, so joining and later
# splitting on "\n\n" tears a single item across a batch boundary --
# the fragment after the tear has no header line and gets dropped or
# misattributed. This sentinel cannot occur in source text.
ITEM_SEPARATOR = "\n<<<ITEM>>>\n"

# Fraction of the post-reserve budget a single prompt is allowed to fill.
# This does two jobs at once, deliberately kept in one knob:
#   1. Quality margin -- recall degrades as a prompt fills the window (the
#      "lost in the middle" effect), so we never target ~100% utilization.
#   2. Estimator slack -- real tokenization of Reddit/markdown text runs
#      nearer 3 chars/token than the 4 assumed by CHARS_PER_TOKEN, so a
#      budget sized at 4 chars/token under-counts tokens; halving it absorbs
#      that error.
# CHARS_PER_TOKEN stays at 4 rather than being lowered so the two forms of
# conservatism don't compound into a needlessly tiny budget.
INPUT_UTILIZATION = 0.5

# Output reserve for tasks whose output is bounded regardless of input size
# (a codebook, a summary, a comparison), as opposed to tasks whose output
# grows with input -- see ``proportional_output_reserve``.
BOUNDED_OUTPUT_TOKENS = 8_000


def get_context_length(model: str) -> int:
    """Real context length, in tokens, for ``model`` from the model catalog."""
    return context_length_for(model)


def estimate_tokens(text: str) -> int:
    """Rough chars/4 token estimate.

    Not a real tokenizer -- OpenRouter fans out to many model families
    (OpenAI, Anthropic, Google, Meta, ...), each with its own real
    tokenizer, so no single tokenizer would be accurate for all of them.
    This heuristic reserves generous headroom and fails safe by
    under-filling batches rather than overflowing a model's context.
    """
    return len(text or "") // CHARS_PER_TOKEN


def max_prompt_chars(
    model: str,
    *,
    reserved_chars: int,
    output_reserve_tokens: int,
    utilization: float = INPUT_UTILIZATION,
) -> int:
    """Usable character budget for the variable part of a prompt to ``model``.

    The window is split three ways: fixed prompt scaffolding
    (``reserved_chars`` -- the system prompt plus instructions repeated in
    every batch), a reserve for the model's own completion
    (``output_reserve_tokens``), and the remaining budget for variable
    content -- of which only ``utilization`` (default
    :data:`INPUT_UTILIZATION`) is actually spent, leaving a quality/estimation
    margin.

    Raises :class:`ContextBudgetError` when the fixed parts (scaffolding +
    output reserve) already exceed the window, so an impossible request
    fails loudly instead of returning a floor-clamped budget that is
    guaranteed to overflow anyway.
    """
    context_tokens = get_context_length(model)
    output_reserve_chars = output_reserve_tokens * CHARS_PER_TOKEN
    available = context_tokens * CHARS_PER_TOKEN - reserved_chars - output_reserve_chars
    if available <= 0:
        raise ContextBudgetError(
            f"The prompt scaffolding (~{reserved_chars // CHARS_PER_TOKEN:,} tokens) plus "
            f"reserved output (~{output_reserve_tokens:,} tokens) exceed {model}'s context "
            f"window ({context_tokens:,} tokens). Choose a larger-context model or send less."
        )
    return int(available * utilization)


def proportional_output_reserve(model: str, share: float) -> int:
    """Output reserve, in tokens, as ``share`` of ``model``'s window -- for
    tasks whose output grows with input (filter emits one ID per matching
    post, apply a coded block per post), unlike the fixed
    :data:`BOUNDED_OUTPUT_TOKENS` used for bounded-output tasks.
    """
    return int(get_context_length(model) * share)


def prompt_fits(
    model: str,
    *,
    prompt_chars: int,
    output_reserve_tokens: int,
    utilization: float = INPUT_UTILIZATION,
) -> bool:
    """Whether an already-assembled prompt of ``prompt_chars`` characters
    fits ``model``'s window once room is reserved for the completion, under
    the same ``utilization`` quality margin batching applies.

    Used by the whole-corpus compare paths -- which can't be batched, since
    a comparison is inherently over the entire input -- to choose between
    sending raw content, sending a compacted form, or failing with
    :class:`ContextBudgetError`.
    """
    context_tokens = get_context_length(model)
    output_reserve_chars = output_reserve_tokens * CHARS_PER_TOKEN
    available = context_tokens * CHARS_PER_TOKEN - output_reserve_chars
    if available <= 0:
        return False
    return prompt_chars <= int(available * utilization)


def batch_by_separator(content: str, max_chars: int, separator: str = DEFAULT_SEPARATOR) -> list[str]:
    """Split ``content`` into batches that fit within ``max_chars``,
    splitting only on ``separator`` boundaries so entries are never cut
    mid-way.
    """
    if len(content) <= max_chars:
        return [content]

    entries = content.split(separator)
    batches: list[str] = []
    current_batch: list[str] = []
    current_size = 0

    for entry in entries:
        entry_size = len(entry) + len(separator)
        if current_size + entry_size > max_chars and current_batch:
            batches.append(separator.join(current_batch))
            current_batch = [entry]
            current_size = entry_size
        else:
            current_batch.append(entry)
            current_size += entry_size

    if current_batch:
        batches.append(separator.join(current_batch))

    return batches


async def run_sequential_batches(
    batches: list[str],
    run_batch: Callable[[int, str], Awaitable[T]],
    *,
    progress: "ProgressTracker | None" = None,
) -> tuple[list[T], dict]:
    """Run ``run_batch(i, batch)`` once per batch, strictly in order --
    the shared error-recovery policy for every batched LLM script in this
    codebase (filter, apply, generate, summarize).

    Error policy: if the FIRST batch fails, the error propagates
    immediately -- with nothing yet collected, there is no partial result
    worth returning, and a first-call failure (bad key, no credits, an
    invalid model) would fail every subsequent batch too, so there is no
    point trying them. If a LATER batch fails, this stops there instead
    (same reasoning -- it's very likely the same problem) but returns
    whatever batches DID succeed rather than discarding them, so a caller
    can still hand back a partial, labeled result instead of nothing.

    Returns ``(results, coverage)``: ``results`` is the list of
    successful ``run_batch`` outputs, in call order; ``coverage`` is
    ``{"batches_processed": int, "batches_total": int, "error": str | None}``,
    where ``error`` is the stringified exception that stopped a partial
    run (``None`` on full success) -- see :func:`coverage_result_fields`
    for turning this into job-result keys.

    ``progress``, if given, has ``advance()`` awaited once per *attempted*
    batch (success or failure) so a progress bar keeps moving through a
    partial run instead of freezing at the point of failure.
    """
    results: list[T] = []
    error_message: str | None = None
    processed = 0
    for i, batch in enumerate(batches):
        try:
            result = await run_batch(i, batch)
            results.append(result)
            processed += 1
        except Exception as exc:
            if i == 0:
                raise
            error_message = str(exc)
            break
        finally:
            if progress is not None:
                await progress.advance()
    coverage = {
        "batches_processed": processed,
        "batches_total": len(batches),
        "error": error_message,
    }
    return results, coverage


def coverage_result_fields(coverage: dict) -> dict:
    """Extra keys to merge into a job's result dict from a ``coverage``
    dict (see :func:`run_sequential_batches`) -- ``{}`` for the common
    single/no-batch case where there's nothing to report, otherwise
    ``partial``/``batches_processed``/``batches_total`` (plus
    ``partial_error`` when a batch failure is what caused the partial
    result) so the frontend can surface a warning instead of silently
    showing an incomplete result as if it were complete.
    """
    if coverage["batches_total"] <= 1:
        return {}
    fields = {
        "partial": coverage["batches_processed"] < coverage["batches_total"],
        "batches_processed": coverage["batches_processed"],
        "batches_total": coverage["batches_total"],
    }
    if coverage.get("error"):
        fields["partial_error"] = coverage["error"]
    return fields
