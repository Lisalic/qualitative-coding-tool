"""OpenRouter model catalog shared with the frontend via ``shared/openrouter_models.json``."""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODELS_PATH = _REPO_ROOT / "shared" / "openrouter_models.json"

with _MODELS_PATH.open(encoding="utf-8") as f:
    AI_MODELS: list[dict[str, str]] = json.load(f)


def model_slug_at(index: int) -> str:
    """Return the OpenRouter slug at ``index``, clamped to the list bounds."""
    if not AI_MODELS:
        raise RuntimeError("AI_MODELS is empty; check shared/openrouter_models.json")
    i = min(max(0, index), len(AI_MODELS) - 1)
    return AI_MODELS[i]["value"]
