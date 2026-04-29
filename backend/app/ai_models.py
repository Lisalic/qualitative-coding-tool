"""OpenRouter model catalog loaded from backend constants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODELS_PATH = _REPO_ROOT / "backend" / "constants" / "openrouter_models.json"

with _MODELS_PATH.open(encoding="utf-8") as f:
    AI_MODELS: list[dict[str, Any]] = json.load(f)


def model_slug_at(index: int) -> str:
    """Return the OpenRouter slug at ``index``, clamped to the list bounds."""
    if not AI_MODELS:
        raise RuntimeError("AI_MODELS is empty; check backend/constants/openrouter_models.json")
    i = min(max(0, index), len(AI_MODELS) - 1)
    return AI_MODELS[i]["value"]
