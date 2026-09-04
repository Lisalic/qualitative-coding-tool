from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.api.schemas import (
    DuplicateDataRequest,
    FilterDataRequest,
    FilterPreviewRequest,
    ManualFilterRequest,
    PostContentsRequest,
    as_form,
)
from backend.app.database import get_async_db
from backend.app.repositories import version_repo
from backend.app.services import data_service

router = APIRouter()


async def _file_info(db: AsyncSession, file_rec) -> dict:
    head = await version_repo.head_version(db, file_rec.id)
    return {
        "id": str(file_rec.id),
        "schema_name": file_rec.schemaname,
        "filename": file_rec.filename,
        "description": file_rec.description,
        "file_type": file_rec.file_type,
        "systemprompt": head.system_prompt if head else None,
        "instructions": head.user_instructions if head else None,
        "prompt_meta": head.prompt_meta if head else None,
    }


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
    version_no: int | None = Query(None, description="Read the file AS OF this version instead of live"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Paginated submissions/comments rows for a file, owned by the
    authenticated user. ``version_no`` reads the file as it was at that
    point in its history (time travel over the SCD-2 ranges on
    ``submissions``/``comments``); omitted, it reads the currently live
    rows.
    """
    entries = await data_service.get_file_entries(db, user_id, schema, limit, offset, version_no)
    return JSONResponse(entries)


@router.post("/data/{ref}/duplicate")
async def duplicate_data(
    ref: str,
    payload: DuplicateDataRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Fork a whole ``raw_data``/``filtered_data`` artifact (its own
    rows, its lineage) into a brand-new file -- from head by default, or
    from ``from_version_no`` if given (see
    ``data_service.duplicate_data``'s docstring). The restore path for
    data files, matching ``POST /api/coding/{ref}/duplicate`` /
    ``POST /api/codebook/{ref}/duplicate``.
    """
    file_rec = await data_service.duplicate_data(
        db, user_id, ref, display_name=payload.display_name, from_version_no=payload.from_version_no
    )
    return JSONResponse({"message": "Duplicated", "file": await _file_info(db, file_rec)})


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


@router.post("/filter-preview/")
async def filter_preview(
    payload: FilterPreviewRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Kick off a background job that runs the AI filter and returns the
    row ids it would keep, **without creating anything**.

    The assistive half of the filter editor. Unlike ``/filter-data/``,
    which is the whole operation, this is a suggestion the user can
    accept, reject or add to before submitting; the rows they have
    already ruled on are passed in so a repeated run proposes new
    candidates instead of re-litigating settled ones. A JSON body rather
    than ``as_form`` because it carries those id lists.
    """
    job = await data_service.start_filter_preview_job(
        db,
        user_id,
        database=payload.database,
        api_key=payload.api_key,
        model=payload.model,
        prompt=payload.prompt,
        min_words=payload.min_words,
        sample_percentage=payload.sample_percentage,
        filter_tags=payload.filter_tags,
        content_scope=payload.content_scope,
        decided_post_ids=payload.decided_post_ids,
        decided_comment_ids=payload.decided_comment_ids,
    )
    return JSONResponse({"job_id": job.id, "status": job.status}, status_code=202)


@router.post("/filtered-data/manual")
async def create_manual_filtered_data(
    payload: ManualFilterRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
) -> JSONResponse:
    """Create a ``filtered_data`` artifact from a hand-picked set of rows.

    The submit half of the filter editor. Synchronous, not a job: no LLM
    call is involved, only the same set-based row copy the AI path ends
    with -- see ``data_service.create_manual_filtered_data``.
    """
    file_rec, counts = await data_service.create_manual_filtered_data(
        db,
        user_id,
        database=payload.database,
        name=payload.name,
        description=payload.description,
        project_id=payload.project_id,
        post_ids=payload.post_ids,
        comment_ids=payload.comment_ids,
    )
    return JSONResponse(
        {
            "message": "Filtered database created",
            "file": await _file_info(db, file_rec),
            "counts": counts,
        }
    )
