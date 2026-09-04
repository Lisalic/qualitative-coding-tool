"""Service layer for row memos -- backs ``backend/app/api/memo_routes.py``.

Thin on purpose: the interesting decisions (one memo per row, blank body
means delete, memos follow their rows into derived artifacts) all live in
``repositories/memo_repo.py`` and ``storage_models.py::RowMemo``. What
this layer owns is the same thing every other service in this package
owns -- turning the opaque ``schemaname`` the frontend passes around into
an ownership-scoped ``file_id`` before any query runs
(``core/schema_guard.require_valid_schema`` for the cheap shape check,
then ``repositories/file_repo.resolve_file_id`` for the real check) -- so
that a memo can only ever be read from or written to a file the caller
owns.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.schema_guard import require_valid_schema
from backend.app.repositories import file_repo, memo_repo
from backend.app.storage_models import RowMemo


def _memo_to_dict(memo: RowMemo) -> dict[str, Any]:
    return {
        "row_type": memo.row_type,
        "row_id": memo.row_id,
        "body": memo.body,
        "updated_at": memo.updated_at.isoformat() if memo.updated_at else None,
    }


async def list_memos(session: AsyncSession, user_id: int, schema: str) -> dict[str, Any]:
    """Every memo on the file identified by ``schema``, owned by ``user_id``.

    One request per database rather than one per row -- see
    ``memo_repo.list_memos`` for why reading the whole set is cheap.
    """
    normalized = require_valid_schema(schema, field_name="schema")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)
    memos = await memo_repo.list_memos(session, file_id)
    return {"memos": [_memo_to_dict(m) for m in memos]}


async def upsert_memo(
    session: AsyncSession,
    user_id: int,
    *,
    schema: str,
    row_type: str,
    row_id: str,
    body: str,
) -> dict[str, Any]:
    """Save (or, on a blank ``body``, clear) the memo on one row.

    Returns ``{"memo": <memo> | None}`` -- a null memo is the successful
    "cleared" outcome, not an error, so the caller can render the empty
    state without a second request.
    """
    normalized = require_valid_schema(schema, field_name="schema")
    file_id = await file_repo.resolve_file_id(session, normalized, user_id)
    memo = await memo_repo.upsert_memo(
        session,
        file_id=file_id,
        row_type=row_type,
        row_id=row_id,
        body=body,
        author_user_id=user_id,
    )
    # Serialize BEFORE committing: the app's session expires instances on
    # commit, and re-reading an expired attribute afterwards would need a
    # lazy refresh -- which raises `MissingGreenlet` under the async
    # engine rather than quietly issuing a second SELECT.
    payload = _memo_to_dict(memo) if memo is not None else None
    await session.commit()
    return {"memo": payload}
