"""Read-only endpoint exposing the OpenRouter model catalog.

The catalog itself lives in ``backend/app/ai_models.py`` and is refreshed
daily from OpenRouter (see the background task started in ``main.py``); this
route just reads whatever is currently cached.
"""

from fastapi import APIRouter, Depends

from backend.app import ai_models
from backend.app.api.schemas import AiModelOut
from backend.app.core.auth_dependency import require_user_id

router = APIRouter()


@router.get("/models", response_model=list[AiModelOut])
async def list_ai_models(user_id: int = Depends(require_user_id)) -> list[dict]:
    return ai_models.AI_MODELS
