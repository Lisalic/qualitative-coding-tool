"""Model pricing and pre-run batch estimation engine (QC-005).

Provides deterministic cost calculation from catalog pricing tables,
robust fallbacks for unknown models, and pre-run cost/time estimation.
"""

from __future__ import annotations

from typing import Any
from backend.app.ai_models import _MODEL_META_BY_SLUG, is_paid_model


def get_model_pricing(model_slug: str) -> dict[str, Any]:
    """Retrieve pricing metadata for a model slug."""
    clean_slug = (model_slug or "").strip()
    meta = _MODEL_META_BY_SLUG.get(clean_slug, {})
    is_paid = is_paid_model(clean_slug)
    pricing = meta.get("pricing") or {}

    input_price = float(pricing.get("inputUsdPerMillion", 0.0))
    output_price = float(pricing.get("outputUsdPerMillion", 0.0))

    return {
        "model": clean_slug,
        "paid": is_paid,
        "input_usd_per_million": input_price,
        "output_usd_per_million": output_price,
    }


def calculate_cost(
    model_slug: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Calculate deterministic dollar cost based on catalog pricing.

    Free models or models with 0 pricing always return 0.0.
    """
    pricing = get_model_pricing(model_slug)
    if not pricing["paid"]:
        return 0.0

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

    # Conservative duration estimate: ~1.5s per batch/item for fast/flash models,
    # ~3.0s per item for larger models
    is_paid = pricing["paid"]
    duration_per_item = 2.5 if is_paid else 1.5
    estimated_duration_s = round(safe_count * duration_per_item, 1)

    return {
        "model": pricing["model"],
        "is_paid": is_paid,
        "item_count": safe_count,
        "estimated_prompt_tokens": total_prompt_tokens,
        "estimated_completion_tokens": total_completion_tokens,
        "estimated_cost_usd": cost,
        "estimated_duration_s": estimated_duration_s,
    }
