"""API routes for exporting codebooks, codings, code-frequency
summaries, memos, saved summaries/comparisons (``document``), and
deterministic project bundles.

Word (``docx``) or Excel (``xlsx``) is every endpoint's default -- most
users aren't technical -- with the interchange formats still offered
after them: codebook ``docx|xlsx|qdc|csv``, coding ``xlsx|docx|csv|json``,
memos ``docx|xlsx|md|csv``, summary ``docx|xlsx|md``, document
``docx|md``. See ``services/export_service.py``'s module docstring for
why; the ``format`` patterns below are the enforcement point, so an
unsupported format 422s rather than silently falling through.
"""

import re
import unicodedata
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth_dependency import require_user_id
from backend.app.database import get_async_db
from backend.app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


def _attachment(filename: str) -> dict[str, str]:
    """``Content-Disposition`` for a download named ``filename``.

    Headers are Latin-1 on the wire, so a raw name with a curly
    apostrophe, CJK or an emoji used to 500 the export. The real name
    goes in the RFC 6266 ``filename*`` (UTF-8, percent-encoded), which
    browsers prefer; ``filename`` carries an ASCII stand-in for any
    client that doesn't read it.
    """
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r'[^\w.\- ]', "_", ascii_name).strip() or "export"
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"}


@router.get("/{ref}/codebook")
async def export_codebook(
    ref: str,
    format: str = Query("docx", pattern="^(docx|xlsx|qdc|csv)$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_codebook(
        db, ref, user_id, version_no=version_no, export_format=format
    )
    headers = _attachment(filename)
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/coding")
async def export_coding(
    ref: str,
    format: str = Query("xlsx", pattern="^(xlsx|docx|csv|json)$"),
    layout: Literal["long", "wide"] | None = Query(
        None, description="csv/json only (default long); xlsx and docx include every view"
    ),
    version_no: int | None = Query(None, ge=1),
    include_source_text: bool = Query(False, description="Include each quote's full source text (off by default)"),
    include_author: bool = Query(False, description="Include each row's author (off by default)"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_coding(
        db,
        ref,
        user_id,
        version_no=version_no,
        export_format=format,
        layout=layout,
        include_source_text=include_source_text,
        include_author=include_author,
    )
    headers = _attachment(filename)
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/memos")
async def export_memos(
    ref: str,
    format: str = Query("docx", pattern="^(docx|xlsx|md|csv)$"),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_memos(
        db, ref, user_id, export_format=format
    )
    headers = _attachment(filename)
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/summary")
async def export_summary(
    ref: str,
    format: str = Query("docx", pattern="^(docx|xlsx|md)$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_summary(
        db, ref, user_id, version_no=version_no, export_format=format
    )
    headers = _attachment(filename)
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/{ref}/document")
async def export_document(
    ref: str,
    format: str = Query("docx", pattern="^(docx|md)$"),
    version_no: int | None = Query(None, ge=1),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    """A saved summary or comparison, as Word or its stored markdown."""
    content, media_type, filename = await export_service.export_document(
        db, ref, user_id, version_no=version_no, export_format=format
    )
    headers = _attachment(filename)
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/projects/{project_id}/bundle")
async def export_project_bundle(
    project_id: int,
    include_source_text: bool = Query(False, description="Include each quote's full source text (off by default)"),
    include_author: bool = Query(False, description="Include each row's author (off by default)"),
    codebook_formats: list[Literal["docx", "xlsx", "qdc", "csv"]] = Query(
        ["docx"], description="Formats each codebook is written in (repeat the param for several)"
    ),
    coding_formats: list[Literal["xlsx", "docx", "csv_long", "csv_wide", "json"]] = Query(
        ["xlsx"], description="Formats each coding is written in (repeat the param for several)"
    ),
    comparison_formats: list[Literal["docx", "md"]] = Query(
        ["docx"], description="Formats each comparison is written in (repeat the param for several)"
    ),
    summary_formats: list[Literal["docx", "md"]] = Query(
        ["docx"], description="Formats each saved summary is written in (repeat the param for several)"
    ),
    memo_formats: list[Literal["docx", "xlsx", "md", "csv"]] = Query(
        ["docx"], description="Formats each file's row memos are written in (repeat the param for several)"
    ),
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    content, media_type, filename = await export_service.export_project_bundle(
        db,
        project_id,
        user_id,
        include_source_text=include_source_text,
        include_author=include_author,
        codebook_formats=list(codebook_formats),
        coding_formats=list(coding_formats),
        comparison_formats=list(comparison_formats),
        summary_formats=list(summary_formats),
        memo_formats=list(memo_formats),
    )
    headers = _attachment(filename)
    return Response(content=content, media_type=media_type, headers=headers)
