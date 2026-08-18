from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import Prompt, User, get_async_db
from backend.app.services import prompt_service

router = APIRouter()


def _prompt_to_dict(p: Prompt) -> dict:
    return {
        "id": int(p.id),
        "user_id": str(p.user_id) if p.user_id is not None else None,
        "promptname": p.promptname,
        "prompt": p.prompt,
        "type": p.type,
    }


async def _parse_body(request: Request) -> dict:
    """Parse a JSON or form request body into a plain dict.

    Kept as a manual ``HTTPException`` (not a ``core.exceptions.AppError``)
    so the response body stays ``{"detail": "..."}`` -- matching the
    pre-existing contract the frontend/tests rely on for malformed-payload
    errors, distinct from the ``{"error": "..."}`` shape service-raised
    errors produce.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    try:
        if "application/json" in content_type:
            return await request.json()
        form = await request.form()
        return {k: form.get(k) for k in form.keys()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid request payload: {str(exc)}")


@router.get("/prompts/")
async def list_prompts(
    prompt_type: str | None = None,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """List the authenticated user's prompts, optionally filtered by type."""
    rows = await prompt_service.list_prompts(db, user_id, prompt_type)
    return JSONResponse({"prompts": [_prompt_to_dict(r) for r in rows]})


@router.post("/prompts/")
async def create_prompt(
    request: Request,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Create a new prompt owned by the authenticated user."""
    data = await _parse_body(request)

    promptname = data.get("promptname")
    prompt_val = data.get("prompt")
    ptype = data.get("type")

    if not promptname or not prompt_val or not ptype:
        raise HTTPException(status_code=400, detail="Missing required fields: promptname, prompt, type")

    # Defensive check preserved from the pre-refactor handler: a
    # well-signed token can still reference a user row that no longer
    # exists. Kept as a manual HTTPException (not routed through
    # prompt_service/AppError) so the response body stays
    # {"detail": "User not found"} rather than {"error": "..."}.
    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=401, detail="User not found")

    new_prompt = await prompt_service.create_prompt(db, user_id, promptname, prompt_val, ptype)
    return JSONResponse(_prompt_to_dict(new_prompt))


@router.post("/prompts/{prompt_id}/update")
async def update_prompt(
    prompt_id: int,
    request: Request,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Update a prompt owned by the authenticated user."""
    data = await _parse_body(request)

    updated = await prompt_service.update_prompt(
        db,
        user_id,
        prompt_id,
        promptname=data.get("promptname"),
        prompt=data.get("prompt"),
        type=data.get("type"),
    )
    return JSONResponse(_prompt_to_dict(updated))


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Delete a prompt owned by the authenticated user."""
    await prompt_service.delete_prompt(db, user_id, prompt_id)
    return JSONResponse({"deleted": True, "id": prompt_id})
