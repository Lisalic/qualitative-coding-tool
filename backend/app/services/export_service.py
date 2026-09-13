"""Export service for codebooks, coding entries, row memos, and frequency summaries.

Produces deterministic, ordered, valid UTF-8 CSV (RFC 4180) and JSON.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.repositories import file_repo, memo_repo, coding_repo, version_repo
from backend.app.services import version_service


def _json_serial(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _csv_serialize(rows: list[list[Any]], headers: list[str]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if v is None else str(v) for v in row])
    return output.getvalue()


async def export_codebook(
    session: AsyncSession,
    file_id: int,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "csv",
) -> tuple[str, str, str]:
    """Export codebook as (content, media_type, filename)."""
    file_record = await file_repo.get_owned_file(session, str(file_id), user_id)
    if file_record.file_type != "codebook":
        raise ValidationAppError(f"File {file_id} is not a codebook (type={file_record.file_type})")

    resolved_version = (
        await version_repo.get_version_by_no(session, file_id, version_no)
        if version_no is not None
        else await version_repo.head_version(session, file_id)
    )
    resolved_version_no = resolved_version.version_no if resolved_version else version_no

    codes = await version_service.read_codes(session, file_id, version_no=version_no)
    # Sort deterministically by position then code_uid
    sorted_codes = sorted(codes, key=lambda c: (c.position if c.position is not None else 999999, c.code_uid or ""))

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    if export_format == "json":
        data = {
            "file_id": file_id,
            "name": file_record.filename,
            "version_no": resolved_version_no,
            "codes": [
                {
                    "code_uid": c.code_uid,
                    "name": c.name,
                    "family_uid": c.family_uid,
                    "family_name": c.family_name,
                    "definition": c.definition,
                    "inclusion": c.inclusion,
                    "exclusion": c.exclusion,
                    "example": c.example,
                    "keywords": c.keywords,
                    "position": c.position,
                }
                for c in sorted_codes
            ],
        }
        filename = f"{base_name}{ver_suffix}_codebook.json"
        return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

    # CSV export
    headers = [
        "code_uid",
        "name",
        "family_uid",
        "family_name",
        "definition",
        "inclusion",
        "exclusion",
        "example",
        "keywords",
        "position",
    ]
    rows = [
        [
            c.code_uid or "",
            c.name or "",
            c.family_uid or "",
            c.family_name or "",
            c.definition or "",
            c.inclusion or "",
            c.exclusion or "",
            c.example or "",
            c.keywords or "",
            c.position if c.position is not None else "",
        ]
        for c in sorted_codes
    ]
    filename = f"{base_name}{ver_suffix}_codebook.csv"
    return _csv_serialize(rows, headers), "text/csv; charset=utf-8", filename


async def export_coding(
    session: AsyncSession,
    file_id: int,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "csv",
) -> tuple[str, str, str]:
    """Export coding entries as (content, media_type, filename)."""
    file_record = await file_repo.get_owned_file(session, str(file_id), user_id)
    if file_record.file_type != "coding":
        raise ValidationAppError(f"File {file_id} is not a coding artifact (type={file_record.file_type})")

    resolved_version = (
        await version_repo.get_version_by_no(session, file_id, version_no)
        if version_no is not None
        else await version_repo.head_version(session, file_id)
    )
    resolved_version_no = resolved_version.version_no if resolved_version else version_no

    if version_no is not None:
        entries = await coding_repo.entries_as_of(session, file_id, version_no)
    else:
        entries = await coding_repo.get_coding_entries(session, file_id)

    sorted_entries = sorted(
        entries,
        key=lambda e: (e.row_type or "", str(e.post_id or ""), e.start_offset or 0, e.end_offset or 0, e.code_uid or "", e.id or 0),
    )

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    if export_format == "json":
        data = {
            "file_id": file_id,
            "name": file_record.filename,
            "version_no": resolved_version_no,
            "entries": [
                {
                    "entry_id": e.id,
                    "row_type": e.row_type,
                    "post_id": e.post_id,
                    "code_uid": e.code_uid,
                    "code": e.code,
                    "quote": e.quote,
                    "start_offset": e.start_offset,
                    "end_offset": e.end_offset,
                    "notes": e.notes,
                    "coder": getattr(e, "coder", "human"),
                    "coder_model": getattr(e, "coder_model", None),
                    "valid_from": e.valid_from,
                    "valid_to": e.valid_to,
                }
                for e in sorted_entries
            ],
        }
        filename = f"{base_name}{ver_suffix}_coding.json"
        return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

    headers = [
        "entry_id",
        "row_type",
        "post_id",
        "code_uid",
        "code",
        "quote",
        "start_offset",
        "end_offset",
        "notes",
        "coder",
        "coder_model",
        "valid_from",
        "valid_to",
    ]
    rows = [
        [
            e.id,
            e.row_type,
            e.post_id,
            e.code_uid,
            e.code,
            e.quote or "",
            e.start_offset if e.start_offset is not None else "",
            e.end_offset if e.end_offset is not None else "",
            e.notes or "",
            getattr(e, "coder", "human"),
            getattr(e, "coder_model", None) or "",
            e.valid_from,
            e.valid_to if e.valid_to is not None else "",
        ]
        for e in sorted_entries
    ]
    filename = f"{base_name}{ver_suffix}_coding.csv"
    return _csv_serialize(rows, headers), "text/csv; charset=utf-8", filename


async def export_memos(
    session: AsyncSession,
    file_id: int,
    user_id: int,
    *,
    export_format: str = "csv",
) -> tuple[str, str, str]:
    """Export row memos as (content, media_type, filename)."""
    file_record = await file_repo.get_owned_file(session, str(file_id), user_id)
    memos = await memo_repo.list_memos(session, file_id)
    sorted_memos = sorted(memos, key=lambda m: (m.row_type or "", str(m.row_id or ""), m.id or 0))

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]

    if export_format == "json":
        data = {
            "file_id": file_id,
            "name": file_record.filename,
            "memos": [
                {
                    "memo_id": m.id,
                    "row_type": m.row_type,
                    "row_id": m.row_id,
                    "body": m.body,
                    "author_user_id": m.author_user_id,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
                for m in sorted_memos
            ],
        }
        filename = f"{base_name}_memos.json"
        return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

    headers = [
        "memo_id",
        "row_type",
        "row_id",
        "body",
        "author_user_id",
        "created_at",
        "updated_at",
    ]
    rows = [
        [
            m.id,
            m.row_type,
            m.row_id,
            m.body or "",
            m.author_user_id if m.author_user_id is not None else "",
            m.created_at.isoformat() if m.created_at else "",
            m.updated_at.isoformat() if m.updated_at else "",
        ]
        for m in sorted_memos
    ]
    filename = f"{base_name}_memos.csv"
    return _csv_serialize(rows, headers), "text/csv; charset=utf-8", filename


async def export_summary(
    session: AsyncSession,
    file_id: int,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "csv",
) -> tuple[str, str, str]:
    """Export code frequency summary as (content, media_type, filename)."""
    file_record = await file_repo.get_owned_file(session, str(file_id), user_id)
    if file_record.file_type != "coding":
        raise ValidationAppError(f"File {file_id} is not a coding artifact")

    resolved_version = (
        await version_repo.get_version_by_no(session, file_id, version_no)
        if version_no is not None
        else await version_repo.head_version(session, file_id)
    )
    resolved_version_no = resolved_version.version_no if resolved_version else version_no

    if version_no is not None:
        entries = await coding_repo.entries_as_of(session, file_id, version_no)
        counts: dict[str, int] = {}
        for e in entries:
            if e.code:
                counts[e.code] = counts.get(e.code, 0) + 1
        freq_list = list(counts.items())
    else:
        freq_list = await coding_repo.code_frequency(session, file_id)

    # Deterministic: sorted descending by frequency, then ascending by code name
    sorted_freq = sorted(freq_list, key=lambda f: (-f[1], f[0]))

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    if export_format == "json":
        data = {
            "file_id": file_id,
            "name": file_record.filename,
            "version_no": resolved_version_no,
            "summary": [
                {"code": code, "frequency": count}
                for code, count in sorted_freq
            ],
        }
        filename = f"{base_name}{ver_suffix}_summary.json"
        return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

    headers = ["code", "frequency"]
    rows = [[code, count] for code, count in sorted_freq]
    filename = f"{base_name}{ver_suffix}_summary.csv"
    return _csv_serialize(rows, headers), "text/csv; charset=utf-8", filename
