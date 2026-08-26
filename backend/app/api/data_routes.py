from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.api.schemas import FilterDataRequest, PostContentsRequest, as_form
from backend.app.database import get_async_db
from backend.app.services import data_service

router = APIRouter()


@router.get("/word-count-ranges/")
async def word_count_ranges(
    schema: str = Query(...),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Word count ranges (0-1000 in steps of 10) for a file's submissions
    and comments, binned via SQL against the fixed storage tables.
    """
    ranges = await data_service.get_word_count_ranges(db, user_id, schema)
    return JSONResponse(ranges)


@router.get("/file-entries/")
async def project_entries(
    schema: str = Query(..., description="File schema name"),
    limit: int = 10,
    offset: int = 0,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Paginated submissions/comments rows for a file, owned by the
    authenticated user.
    """
    entries = await data_service.get_file_entries(db, user_id, schema, limit, offset)
    return JSONResponse(entries)


@router.get("/comments/{submission_id}")
async def get_comments_for_submission(
    submission_id: str,
    database: str = Query("original"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """All comments for a given submission id, from a file owned by the
    authenticated user.
    """
    comments = await data_service.get_comments_for_submission(db, user_id, submission_id, database)
    return JSONResponse(comments)


@router.post("/post-contents/")
async def get_post_contents(
    payload: PostContentsRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Title/content for a set of post and/or comment ids, from a file
    owned by the authenticated user. Structural fix for the old
    SQL-injection-adjacent gap: the schema name is resolved to an
    ownership-checked ``file_id`` via ``file_repo`` before any query runs
    -- see ``backend/app/services/data_service.py::get_post_contents``.
    """
    contents = await data_service.get_post_contents(db, user_id, payload.schema_, payload.post_ids)
    return JSONResponse(contents)


@router.post("/filter-data/")
async def filter_data(
    payload: FilterDataRequest = Depends(as_form(FilterDataRequest)),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Kick off a background job that filters posts/comments (optionally
    via tag pre-filtering and/or an AI call) and materializes the result
    as a new ``filtered_data`` file, and return immediately with a job id
    to poll instead of blocking the request -- see backend/app/jobs/.
    """
    job = await data_service.start_filter_data_job(
        db,
        user_id,
        database=payload.database,
        name=payload.name,
        api_key=payload.api_key,
        model=payload.model,
        prompt=payload.prompt,
        min_words=payload.min_words,
        sample_percentage=payload.sample_percentage,
        filter_tags=payload.filter_tags,
        description=payload.description,
        project_id=payload.project_id,
        content_scope=payload.content_scope,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)
