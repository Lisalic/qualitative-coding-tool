from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas import MemoUpsertRequest
from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.services import memo_service

router = APIRouter()


@router.get("/memos/")
async def list_memos(
    schema: str = Query(..., description="File schema name"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Every memo on a file owned by the authenticated user.

    Deliberately unpaginated: only rows someone actually wrote about have
    a memo, so the whole set is small enough to fetch once per database
    and index client-side -- see ``repositories/memo_repo.list_memos``.
    """
    return JSONResponse(await memo_service.list_memos(db, user_id, schema))


@router.put("/memos/")
async def upsert_memo(
    payload: MemoUpsertRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Create, replace, or clear the memo on one row.

    ``PUT`` rather than ``POST`` because there is exactly one memo per
    ``(file, row_type, row_id)`` and this call is idempotent; a blank
    ``body`` clears it and returns ``{"memo": null}``.
    """
    result = await memo_service.upsert_memo(
        db,
        user_id,
        schema=payload.schema_,
        row_type=payload.row_type,
        row_id=payload.row_id,
        body=payload.body,
    )
    return JSONResponse(result)
