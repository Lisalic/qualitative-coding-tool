"""Tests for QC-005: model pricing, accounting tracking, missing metadata fallbacks, and batch estimation."""

from backend.app.external.pricing import calculate_cost, estimate_batch_cost, get_model_pricing
from backend.app.jobs.progress import JobAccountingTracker


def test_free_model_pricing_always_zero():
    # Nex AGI free model
    cost = calculate_cost("nex-agi/nex-n2.5-mini:free", prompt_tokens=10000, completion_tokens=5000)
    assert cost == 0.0

    meta = get_model_pricing("nex-agi/nex-n2.5-mini:free")
    assert meta["paid"] is False


def test_paid_model_pricing_deterministic_calculation():
    # Claude Opus 5: input $5/M, output $25/M
    # 100,000 prompt tokens -> 0.1 * 5 = $0.50
    # 20,000 completion tokens -> 0.02 * 25 = $0.50
    # Total = $1.00
    cost = calculate_cost("anthropic/claude-opus-5", prompt_tokens=100_000, completion_tokens=20_000)
    assert cost == 1.0


def test_missing_or_unknown_model_pricing_fallback():
    # Unknown model pricing is None -- never guessed as a known $0.0.
    cost = calculate_cost("unknown-provider/nonexistent-model", prompt_tokens=5000, completion_tokens=1000)
    assert cost is None

    meta = get_model_pricing("unknown-provider/nonexistent-model")
    assert meta["known"] is False
    assert meta["paid"] is None


def test_unknown_token_counts_never_coerced_to_zero():
    # A provider that didn't report usage yields an unknown (None) cost,
    # not a misleadingly precise $0.00.
    assert calculate_cost("anthropic/claude-opus-5", prompt_tokens=None, completion_tokens=2000) is None
    assert calculate_cost("anthropic/claude-opus-5", prompt_tokens=1000, completion_tokens=None) is None


def test_estimate_batch_cost_conservative():
    est_free = estimate_batch_cost("nex-agi/nex-n2.5-mini:free", item_count=10)
    assert est_free["item_count"] == 10
    assert est_free["estimated_cost_usd"] == 0.0
    assert est_free["is_paid"] is False
    assert est_free["estimated_duration_s"] > 0

    est_paid = estimate_batch_cost("anthropic/claude-opus-5", item_count=5)
    assert est_paid["item_count"] == 5
    assert est_paid["estimated_cost_usd"] > 0.0
    assert est_paid["is_paid"] is True


def test_job_accounting_tracker_accumulation_and_fallback():
    tracker = JobAccountingTracker(job_id=42, model="anthropic/claude-opus-5")

    # Record first call with valid tokens
    tracker.record_call(
        model="anthropic/claude-opus-5",
        prompt_tokens=10_000,
        completion_tokens=2_000,
        duration_ms=1200,
    )
    assert tracker.call_count == 1
    assert tracker.prompt_tokens == 10_000
    assert tracker.completion_tokens == 2_000
    assert tracker.total_tokens == 12_000
    assert tracker.duration_ms == 1200
    assert tracker.estimated_cost_usd > 0.0

    # Record second call with missing/None tokens (must fall back cleanly)
    tracker.record_call(
        model="anthropic/claude-opus-5",
        prompt_tokens=0,
        completion_tokens=0,
        duration_ms=800,
    )
    assert tracker.call_count == 2
    assert tracker.total_tokens == 12_000
    assert tracker.duration_ms == 2000

    d = tracker.to_dict()
    assert d["job_id"] == 42
    assert d["call_count"] == 2
