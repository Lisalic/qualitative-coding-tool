"""Model pricing and pre-run batch estimation engine (QC-005).

Provides deterministic cost calculation from catalog pricing tables,
robust fallbacks for unknown models, and pre-run cost/time estimation.
Unknown provider usage or pricing is always represented as ``None`` --
never coerced to 0, which would silently misreport an unknown cost as a
known free one.
"""

from __future__ import annotations

from typing import Any
from backend.app.ai_models import _MODEL_META_BY_SLUG, is_paid_model


def get_model_pricing(model_slug: str) -> dict[str, Any]:
    """Retrieve pricing metadata for a model slug.

    A ``:free`` suffix is treated as a known free model even if absent
    from the catalog. Otherwise, a slug missing from the catalog reports
    ``known=False`` with ``None`` pricing rather than guessing $0.
    """
    clean_slug = (model_slug or "").strip()
    if clean_slug.endswith(":free"):
        return {
            "model": clean_slug,
            "known": True,
            "paid": False,
            "input_usd_per_million": 0.0,
            "output_usd_per_million": 0.0,
        }

    if clean_slug not in _MODEL_META_BY_SLUG:
        return {
            "model": clean_slug,
            "known": False,
            "paid": None,
            "input_usd_per_million": None,
            "output_usd_per_million": None,
        }

    meta = _MODEL_META_BY_SLUG[clean_slug]
    is_paid = is_paid_model(clean_slug)
    pricing = meta.get("pricing") or {}

    input_val = pricing.get("inputUsdPerMillion")
    output_val = pricing.get("outputUsdPerMillion")
    input_price = float(input_val) if input_val is not None else (0.0 if not is_paid else None)
    output_price = float(output_val) if output_val is not None else (0.0 if not is_paid else None)

    return {
        "model": clean_slug,
        "known": True,
        "paid": is_paid,
        "input_usd_per_million": input_price,
        "output_usd_per_million": output_price,
    }


def calculate_cost(
    model_slug: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    """Calculate deterministic dollar cost based on catalog pricing.

    Returns ``None`` -- never 0.0 -- whenever the pricing metadata or the
    token counts themselves are unknown. A genuinely free model still
    returns 0.0.
    """
    if prompt_tokens is None or completion_tokens is None:
        return None

    pricing = get_model_pricing(model_slug)
    if not pricing["known"]:
        return None
    if pricing["paid"] is False:
        return 0.0
    if pricing["input_usd_per_million"] is None or pricing["output_usd_per_million"] is None:
        return None

    input_cost = (max(0, prompt_tokens) / 1_000_000.0) * pricing["input_usd_per_million"]
    output_cost = (max(0, completion_tokens) / 1_000_000.0) * pricing["output_usd_per_million"]

    return round(input_cost + output_cost, 6)


def estimate_batch_cost(
    model_slug: str,
    item_count: int = 1,
    *,
    avg_prompt_tokens_per_item: int = 600,
    avg_completion_tokens_per_item: int = 200,
) -> dict[str, Any]:
    """Produce conservative upfront cost and duration estimates for a batch run."""
    safe_count = max(1, item_count)
    pricing = get_model_pricing(model_slug)

    total_prompt_tokens = safe_count * avg_prompt_tokens_per_item
    total_completion_tokens = safe_count * avg_completion_tokens_per_item

    cost = calculate_cost(model_slug, total_prompt_tokens, total_completion_tokens)

    # Conservative duration estimate: ~2.5s per batch/item for paid models,
    # ~1.5s per item for free ones.
    is_paid = pricing["paid"]
    duration_per_item = 2.5 if is_paid else 1.5
    estimated_duration_s = round(safe_count * duration_per_item, 1)

    return {
        "model": pricing["model"],
        "known": pricing["known"],
        "is_paid": is_paid,
        "item_count": safe_count,
        "estimated_prompt_tokens": total_prompt_tokens,
        "estimated_completion_tokens": total_completion_tokens,
        "estimated_cost_usd": cost,
        "estimated_duration_s": estimated_duration_s,
    }
