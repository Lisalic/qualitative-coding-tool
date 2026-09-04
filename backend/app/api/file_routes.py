import json
import traceback

from fastapi import APIRouter, File as FastAPIFile, HTTPException, UploadFile, Form, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas import DeleteRowsRequest
from backend.app.core.auth_dependency import optional_user_id, require_user_id
from backend.app.core.exceptions import AppError
from backend.app.database import get_async_db
from backend.app.services import file_service

router = APIRouter()


@router.post("/upload-zst/")
async def upload_zst_file(
    file: UploadFile = FastAPIFile(...),
    subreddits: str = Form(None),
    data_type: str = Form(...),
    name: str = Form(None),
    description: str = Form(None),
    project_id: int = Form(None),
    user_id: int | None = Depends(optional_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    # Format validation stays here (pure request checks, no DB/IO), and
    # runs before auth -- matches the old handler's tested ordering
    # (a bad filename/subreddits/data_type 400s even with no auth header).
    if not file.filename.endswith('.zst'):
        raise HTTPException(status_code=400, detail="File must be a .zst file")

    subreddit_list = None
    if subreddits:
        try:
            subreddit_list = json.loads(subreddits)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid subreddits format")

    allowed = ("comments", "posts")
    if data_type not in allowed:
        raise HTTPException(status_code=400, detail="data_type must be 'posts' or 'comments'")
    import_data_type = "submissions" if data_type == "posts" else data_type

    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {exc}")

    # Manual auth check (not `Depends(require_user_id)`): the guard
    # clauses above must fire before auth, which only holds if auth is
    # checked in the function body, since FastAPI resolves all `Depends`
    # before the body runs at all.
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthenticated")

    try:
        file_rec, result = await file_service.upload_zst(
            db,
            user_id,
            file_content=content,
            filename=file.filename,
            data_type=import_data_type,
            subreddits=subreddit_list,
            name=name,
            description=description,
            project_id=project_id,
        )
    except (HTTPException, AppError):
        raise
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({
        "status": "completed",
        "file_name": file.filename,
        "authenticated": True,
        **result,
    })


@router.post("/merge-databases/")
async def merge_databases(
    request: Request,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            body = await request.json()
            databases = body.get("databases")
            name = body.get("name")
            description = body.get("description")
            project_id = body.get("project_id")
        else:
            form = await request.form()
            databases = form.get("databases")
            name = form.get("name")
            description = form.get("description")
            project_id = form.get("project_id")

        if isinstance(databases, str):
            db_list = json.loads(databases)
        elif isinstance(databases, list):
            db_list = databases
        else:
            raise HTTPException(status_code=400, detail="Invalid databases format")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid databases format") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {exc}") from exc

    try:
        _file_rec, result = await file_service.merge_databases(
            db,
            user_id,
            source_schemas=db_list,
            name=name,
            description=description,
            project_id=project_id,
        )
    except (HTTPException, AppError):
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(result)


@router.delete("/delete-database/{db_name}")
async def delete_database(
    db_name: str,
    user_id: int | None = Depends(optional_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    schema = db_name.strip()

    # Allow project-backed schemas (proj_), comparison schemas (cmp_), and summaries (sum_)
    if not (schema.startswith('proj_') or schema.startswith('cmp_') or schema.startswith('sum_')):
        raise HTTPException(status_code=400, detail="Invalid file schema identifier")

    # Manual auth check, after the prefix guard -- same ordering rationale
    # as upload_zst_file above (documented/tested: the guard fires first).
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        filename = await file_service.delete_database(db, user_id, schema)
    except (HTTPException, AppError):
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete file/schema: {exc}")

    return JSONResponse({"message": f"File '{filename}' deleted"})


@router.post("/delete-rows/")
async def delete_rows(
    payload: DeleteRowsRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Close (soft-delete) one or more rows from a file's submissions or
    comments table, minting a single version for the whole batch --
    replaces the old single-row ``/delete-row/`` (hard delete, no
    version, and a request-shape bug: the frontend posted ``schema`` but
    this route used to declare ``schemaname``, a mismatch the tests
    never caught -- see ``file_service.delete_rows``'s docstring).
    """
    schema = (payload.schema_name or "").strip()
    if schema.endswith('.db'):
        schema = schema[:-3]

    if not schema or not schema.startswith('proj_'):
        return JSONResponse({"error": "Invalid file schema"}, status_code=400)

    if payload.table not in ("submissions", "comments"):
        return JSONResponse({"error": "Invalid table"}, status_code=400)

    try:
        deleted = await file_service.delete_rows(
            db, user_id, schemaname=schema, table=payload.table, row_ids=payload.row_ids
        )
    except AppError:
        raise
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"deleted": deleted})


@router.post("/move-rows/")
async def move_rows(
    request: Request,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Move rows between file schemas."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    source = (body.get("source_schema") or "").strip()
    target = (body.get("target_schema") or "").strip()
    table = body.get("table")
    row_ids = body.get("row_ids") or []

    if source.endswith('.db'):
        source = source[:-3]
    if target.endswith('.db'):
        target = target[:-3]

    if not source or not source.startswith('proj_') or not target or not target.startswith('proj_'):
        return JSONResponse({"error": "Invalid file schema"}, status_code=400)
    if table not in ("submissions", "comments"):
        return JSONResponse({"error": "Invalid table"}, status_code=400)
    if not isinstance(row_ids, list) or len(row_ids) == 0:
        return JSONResponse({"error": "row_ids must be a non-empty list"}, status_code=400)

    try:
        moved = await file_service.move_rows(
            db,
            user_id,
            source_schema=source,
            target_schema=target,
            table=table,
            row_ids=row_ids,
        )
    except AppError:
        raise
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

    if moved == 0:
        return JSONResponse({"moved": 0, "message": "No matching rows found"})
    return JSONResponse({"moved": moved})
