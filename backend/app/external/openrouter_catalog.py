"""Fetches and normalizes OpenRouter's public model catalog.

``GET {OPENROUTER_URL}/models`` is a public, unauthenticated OpenRouter
endpoint (distinct from the chat-completions API in ``openrouter_client.py``,
which requires a per-request user API key), so this uses a plain ``httpx``
GET rather than the ``AsyncOpenAI`` client.
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.app.external.openrouter_client import OPENROUTER_URL, retry_async

MODELS_URL = f"{OPENROUTER_URL}/models"


def _is_text_model(architecture: dict[str, Any]) -> bool:
    """Keep only models that accept and return text (this app only does chat completions)."""
    input_modalities = architecture.get("input_modalities") or []
    output_modalities = architecture.get("output_modalities") or []
    if not input_modalities or not output_modalities:
        return True
    return "text" in input_modalities and "text" in output_modalities


def _map_model(raw: dict[str, Any]) -> dict[str, Any] | None:
    slug = raw.get("id")
    if not slug:
        return None
    if not _is_text_model(raw.get("architecture") or {}):
        return None

    pricing = raw.get("pricing") or {}
    try:
        prompt_price = float(pricing.get("prompt") or 0)
        completion_price = float(pricing.get("completion") or 0)
    except (TypeError, ValueError):
        prompt_price = completion_price = 0.0

    paid = prompt_price > 0 or completion_price > 0
    model: dict[str, Any] = {
        "value": slug,
        "label": raw.get("name") or slug,
        "paid": paid,
    }
    context_length = raw.get("context_length")
    if isinstance(context_length, int) and context_length > 0:
        model["context_length"] = context_length
    if paid:
        model["pricing"] = {
            "inputUsdPerMillion": round(prompt_price * 1_000_000, 6),
            "outputUsdPerMillion": round(completion_price * 1_000_000, 6),
        }
    return model


async def fetch_openrouter_catalog(timeout: float = 30.0) -> list[dict[str, Any]]:
    """Fetch and normalize the live OpenRouter model catalog.

    Raises on network failure (after retries) or if OpenRouter returns no
    usable text models -- callers should keep the previous catalog on error.
    """

    async def _call() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(MODELS_URL)
            response.raise_for_status()
            body = response.json()
            return body.get("data") or []

    raw_models = await retry_async(_call, max_retries=3, initial_delay_s=2.0)
    models = [m for m in (_map_model(raw) for raw in raw_models) if m is not None]
    if not models:
        raise ValueError("OpenRouter returned no usable text models")
    return models
