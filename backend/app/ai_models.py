"""OpenRouter model catalog loaded from backend constants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODELS_PATH = _REPO_ROOT / "backend" / "constants" / "openrouter_models.json"

with _MODELS_PATH.open(encoding="utf-8") as f:
    AI_MODELS: list[dict[str, Any]] = json.load(f)

_MODEL_META_BY_SLUG: dict[str, dict[str, Any]] = {
    str(m.get("value")): m for m in AI_MODELS if m.get("value")
}


def set_catalog(models: list[dict[str, Any]]) -> None:
    """Replace the in-memory catalog (called after a successful OpenRouter refresh).

    Every AI-backed request now carries its own caller-chosen ``model``
    slug end to end -- there are no more module-level "default model"
    constants resolved once from ``model_slug_at`` at import time (a
    scheme retired because a model retired from OpenRouter's live catalog
    would leave such a constant silently pointing at a dead slug until
    the next process restart). ``is_paid_model``, ``context_length_for``,
    and a fresh ``/api/models`` read all see the live catalog immediately,
    since they look it up at call time.
    """
    global AI_MODELS, _MODEL_META_BY_SLUG
    if not models:
        raise ValueError("Refusing to set an empty model catalog")
    AI_MODELS = models
    _MODEL_META_BY_SLUG = {str(m.get("value")): m for m in models if m.get("value")}


async def refresh_from_openrouter() -> None:
    """Fetch the live OpenRouter catalog and replace the in-memory one."""
    from backend.app.external.openrouter_catalog import fetch_openrouter_catalog

    models = await fetch_openrouter_catalog()
    set_catalog(models)


def model_slug_at(index: int) -> str:
    """Return the OpenRouter slug at ``index``, clamped to the list bounds."""
    if not AI_MODELS:
        raise RuntimeError("AI_MODELS is empty; check backend/constants/openrouter_models.json")
    i = min(max(0, index), len(AI_MODELS) - 1)
    return AI_MODELS[i]["value"]


def is_paid_model(slug: str) -> bool:
    """Return True when the model is marked paid in the catalog."""
    metadata = _MODEL_META_BY_SLUG.get((slug or "").strip())
    if not metadata:
        return False
    return bool(metadata.get("paid") is True)


def context_length_for(slug: str, *, default: int = 32_000) -> int:
    """Real context length (tokens) for ``slug`` from the model catalog,
    falling back to ``default`` when the slug is unknown or the catalog
    entry has no usable ``context_length``.
    """
    metadata = _MODEL_META_BY_SLUG.get((slug or "").strip())
    if not metadata:
        return default
    length = metadata.get("context_length")
    if not isinstance(length, int) or length <= 0:
        return default
    return length
