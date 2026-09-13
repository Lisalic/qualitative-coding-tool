"""Export service for codebooks, coding entries, row memos, frequency
summaries, and deterministic project bundles.

Produces deterministic, ordered, valid UTF-8 CSV (RFC 4180) and JSON.
Coding exports come in two layouts: ``long`` (one row per coded segment)
and ``wide`` (one row per dataset item, including uncoded ones, with a
column per code) -- see ``export_coding``. The summary export groups by
``code_uid``, never by code name, so a rename doesn't fragment history --
see ``export_summary``/``repositories/export_repo.py::get_code_frequencies_by_uid``.
The project bundle (``export_project_bundle``) also carries any
``codebook_comparison``/``coding_comparison`` artifact in the project as
its raw markdown blob under ``comparisons/`` -- unlike codebook/coding, a
comparison has no structured rows to serialize into CSV, so its content
is exported as-is rather than reshaped.

Privacy: ``include_source_text``/``include_author`` on ``export_coding``
and ``export_project_bundle`` both default to ``False`` -- an export is
opt-in to carrying the underlying quote's full source text or its
author, not opt-out.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.repositories import export_repo, file_repo, project_repo, version_repo
from backend.app.services import version_service
from backend.app.versioning_models import CodebookCode


async def _get_sorted_codebook_codes(
    session: AsyncSession, file_id: int, *, version_no: int | None = None
) -> list[CodebookCode]:
    """Codebook codes for a file as of ``version_no`` or head, sorted
    deterministically: (position, code_uid).

    Lives here, not in ``export_repo.py``: resolving a version's codes is
    ``version_service.read_codes``'s job (it may need to apply a stored
    delta against the nearest materialized ancestor -- see that
    function's docstring), and repositories don't import the service
    layer.
    """
    codes = await version_service.read_codes(session, file_id, version_no=version_no)
    return sorted(
        codes,
        key=lambda c: (
            c.position if c.position is not None else 999999,
            c.code_uid or "",
        ),
    )


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


def _slugify(val: str | None, default: str = "export") -> str:
    if not val:
        return default
    slug = re.sub(r"[^\w\s-]", "", val).strip().lower()
    return re.sub(r"[-\s]+", "_", slug) or default


async def _resolve_version(
    session: AsyncSession, file_id: int, version_no: int | None, *, label: str
) -> tuple[Any, int | None]:
    """Resolve ``version_no`` (or head) to its ``ArtifactVersion`` row.

    Raises ``NotFoundError`` when a version was explicitly requested and
    doesn't exist -- an export used to silently fall through to an empty
    result for a bad ``version_no`` instead of a 404, which read as a
    valid-but-empty export rather than an error.
    """
    if version_no is not None:
        version = await version_repo.get_version_by_no(session, file_id, version_no)
        if version is None:
            raise NotFoundError(f"Version {version_no} not found for {label} file {file_id}")
        return version, version.version_no

    version = await version_repo.head_version(session, file_id)
    return version, (version.version_no if version else None)


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

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="codebook")
    sorted_codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)

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

    headers = [
        "code_uid", "name", "family_uid", "family_name", "definition",
        "inclusion", "exclusion", "example", "keywords", "position",
    ]
    rows = [
        [
            c.code_uid or "", c.name or "", c.family_uid or "", c.family_name or "",
            c.definition or "", c.inclusion or "", c.exclusion or "", c.example or "",
            c.keywords or "", c.position if c.position is not None else "",
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
    layout: str = "long",
    include_source_text: bool = False,
    include_author: bool = False,
) -> tuple[str, str, str]:
    """Export coding data as ``long`` (one row per coded segment quote) or
    ``wide`` (one row per dataset item -- including uncoded ones -- with a
    0/1 or count column per code).
    """
    file_record = await file_repo.get_owned_file(session, str(file_id), user_id)
    if file_record.file_type != "coding":
        raise ValidationAppError(f"File {file_id} is not a coding artifact (type={file_record.file_type})")

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="coding")

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)
    code_meta = {c.code_uid: c for c in codes if c.code_uid}
    entries = await export_repo.get_coding_entries(session, file_id, version_no=version_no)

    row_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    if include_source_text or include_author or layout == "wide":
        all_rows = await export_repo.get_all_rows_for_coding(session, file_id, version_no=version_no)
        row_lookup = {(r["row_type"], r["post_id"]): r for r in all_rows}
    else:
        all_rows = []

    if layout == "long":
        if export_format == "json":
            json_entries = []
            for e in entries:
                c = code_meta.get(e.code_uid)
                row_info = row_lookup.get((e.row_type, str(e.post_id)))
                item = {
                    "file_id": file_id,
                    "version_no": resolved_version_no,
                    "entry_id": e.id,
                    "row_type": e.row_type,
                    "post_id": e.post_id,
                    "code_uid": e.code_uid,
                    "code": e.code,
                    "family_uid": c.family_uid if c else "",
                    "family_name": c.family_name if c else "",
                    "quote": e.quote,
                    "start_offset": e.start_offset,
                    "end_offset": e.end_offset,
                    "notes": e.notes,
                    "coder": getattr(e, "coder", "human"),
                    "coder_model": getattr(e, "coder_model", None),
                }
                if include_author:
                    item["author"] = row_info.get("author") if row_info else None
                if include_source_text:
                    item["source_text"] = row_info.get("source_text") if row_info else None
                json_entries.append(item)

            data = {
                "file_id": file_id,
                "name": file_record.filename,
                "version_no": resolved_version_no,
                "layout": "long",
                "include_source_text": include_source_text,
                "include_author": include_author,
                "entries": json_entries,
            }
            filename = f"{base_name}{ver_suffix}_segments_long.json"
            return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

        headers = [
            "file_id", "version_no", "entry_id", "row_type", "post_id", "code_uid",
            "code", "family_uid", "family_name", "quote", "start_offset", "end_offset",
            "notes", "coder", "coder_model",
        ]
        if include_author:
            headers.append("author")
        if include_source_text:
            headers.append("source_text")

        rows = []
        for e in entries:
            c = code_meta.get(e.code_uid)
            row_info = row_lookup.get((e.row_type, str(e.post_id)))
            r = [
                file_id, resolved_version_no if resolved_version_no is not None else "",
                e.id, e.row_type, e.post_id, e.code_uid, e.code,
                c.family_uid if c and c.family_uid else "", c.family_name if c and c.family_name else "",
                e.quote or "", e.start_offset if e.start_offset is not None else "",
                e.end_offset if e.end_offset is not None else "", e.notes or "",
                getattr(e, "coder", "human"), getattr(e, "coder_model", None) or "",
            ]
            if include_author:
                r.append((row_info.get("author") if row_info else "") or "")
            if include_source_text:
                r.append((row_info.get("source_text") if row_info else "") or "")
            rows.append(r)

        filename = f"{base_name}{ver_suffix}_segments_long.csv"
        return _csv_serialize(rows, headers), "text/csv; charset=utf-8", filename

    if layout != "wide":
        raise ValidationAppError(f"Unknown coding export layout: {layout!r}")

    # wide: one row per item (including uncoded ones), a column per code.
    item_entries: dict[tuple[str, str], list[str]] = {}
    for e in entries:
        key = (e.row_type or "", str(e.post_id or ""))
        item_entries.setdefault(key, [])
        if e.code_uid:
            item_entries[key].append(e.code_uid)

    sorted_code_uids = [c.code_uid for c in codes if c.code_uid]

    if export_format == "json":
        json_rows = []
        for row in all_rows:
            key = (row["row_type"], row["post_id"])
            assigned = item_entries.get(key, [])
            item_dict: dict[str, Any] = {
                "row_type": row["row_type"],
                "post_id": row["post_id"],
                "is_coded": 1 if assigned else 0,
                "total_codes": len(assigned),
            }
            if include_author:
                item_dict["author"] = row.get("author")
            if include_source_text:
                item_dict["source_text"] = row.get("source_text")
            item_dict["codes"] = {uid: assigned.count(uid) for uid in sorted_code_uids}
            json_rows.append(item_dict)

        data = {
            "file_id": file_id,
            "name": file_record.filename,
            "version_no": resolved_version_no,
            "layout": "wide",
            "include_source_text": include_source_text,
            "include_author": include_author,
            "codebook": [
                {"code_uid": c.code_uid, "name": c.name, "family_uid": c.family_uid, "family_name": c.family_name}
                for c in codes
            ],
            "rows": json_rows,
        }
        filename = f"{base_name}{ver_suffix}_matrix_wide.json"
        return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

    headers = ["row_type", "post_id", "is_coded", "total_codes"]
    if include_author:
        headers.append("author")
    if include_source_text:
        headers.append("source_text")
    headers.extend([f"code_{uid}" for uid in sorted_code_uids])

    rows = []
    for row in all_rows:
        key = (row["row_type"], row["post_id"])
        assigned = item_entries.get(key, [])
        r = [row["row_type"], row["post_id"], 1 if assigned else 0, len(assigned)]
        if include_author:
            r.append(row.get("author") or "")
        if include_source_text:
            r.append(row.get("source_text") or "")
        r.extend(assigned.count(uid) for uid in sorted_code_uids)
        rows.append(r)

    filename = f"{base_name}{ver_suffix}_matrix_wide.csv"
    return _csv_serialize(rows, headers), "text/csv; charset=utf-8", filename


async def export_memos(
    session: AsyncSession,
    file_id: int,
    user_id: int,
    *,
    export_format: str = "csv",
) -> tuple[str, str, str]:
    """Export row memos as (content, media_type, filename).

    No ``version_no`` param: unlike codebook/coding/summary, row memos
    are deliberately not SCD-2 range-versioned (see the ``RowMemo``
    docstring) -- there is no historical "as of version N" snapshot to
    resolve, only the current live set, so there is nothing a version
    parameter could filter by.
    """
    file_record = await file_repo.get_owned_file(session, str(file_id), user_id)
    if file_record.file_type not in ("raw_data", "filtered_data", "coding"):
        raise ValidationAppError(
            f"File {file_id} does not carry memos (type={file_record.file_type})"
        )
    memos = await export_repo.get_row_memos(session, file_id)

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
                for m in memos
            ],
        }
        filename = f"{base_name}_memos.json"
        return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

    headers = ["memo_id", "row_type", "row_id", "body", "author_user_id", "created_at", "updated_at"]
    rows = [
        [
            m.id, m.row_type, m.row_id, m.body or "",
            m.author_user_id if m.author_user_id is not None else "",
            m.created_at.isoformat() if m.created_at else "",
            m.updated_at.isoformat() if m.updated_at else "",
        ]
        for m in memos
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
    """Export code frequency summary, grouped strictly by ``code_uid``."""
    file_record = await file_repo.get_owned_file(session, str(file_id), user_id)
    if file_record.file_type != "coding":
        raise ValidationAppError(f"File {file_id} is not a coding artifact")

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="coding")
    codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)
    summary_data = await export_repo.get_code_frequencies_by_uid(
        session, file_id, codes=codes, version_no=version_no
    )

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    if export_format == "json":
        data = {
            "file_id": file_id,
            "name": file_record.filename,
            "version_no": resolved_version_no,
            "summary": summary_data,
        }
        filename = f"{base_name}{ver_suffix}_summary.json"
        return json.dumps(data, indent=2, default=_json_serial), "application/json; charset=utf-8", filename

    headers = ["code_uid", "name", "family_uid", "family_name", "frequency", "document_count"]
    rows = [
        [s["code_uid"], s["name"], s["family_uid"], s["family_name"], s["frequency"], s["document_count"]]
        for s in summary_data
    ]
    filename = f"{base_name}{ver_suffix}_summary.csv"
    return _csv_serialize(rows, headers), "text/csv; charset=utf-8", filename


async def export_project_bundle(
    session: AsyncSession,
    project_id: int,
    user_id: int,
    *,
    include_source_text: bool = False,
    include_author: bool = False,
) -> tuple[bytes, str, str]:
    """Deterministic ZIP bundle of every artifact in a project: a
    manifest with a SHA-256 per file, the project's lineage graph, and
    every codebook/coding (long + wide + summary)/memos/comparison export.

    Byte-deterministic: entries are written in sorted-path order with a
    fixed ``date_time`` (2026-01-01 00:00:00), so identical content always
    produces identical bytes -- no timestamp or filesystem-order noise.
    """
    project = await project_repo.get_owned_project(session, project_id, user_id)
    files = await export_repo.get_project_files(session, project_id)

    bundle_files: dict[str, bytes] = {}

    lineage_graph = await export_repo.get_project_lineage_graph(session, files)
    bundle_files["lineage/project_lineage.json"] = json.dumps(
        lineage_graph, indent=2, default=_json_serial
    ).encode("utf-8")

    for f in files:
        f_slug = _slugify(f.filename, default=f"file_{f.id}")

        if f.file_type == "codebook":
            cb_csv, _, _ = await export_codebook(session, f.id, user_id, export_format="csv")
            cb_json, _, _ = await export_codebook(session, f.id, user_id, export_format="json")
            bundle_files[f"codebooks/{f.id}_{f_slug}_codebook.csv"] = cb_csv.encode("utf-8")
            bundle_files[f"codebooks/{f.id}_{f_slug}_codebook.json"] = cb_json.encode("utf-8")

        elif f.file_type == "coding":
            for layout in ("long", "wide"):
                for fmt in ("csv", "json"):
                    content, _, _ = await export_coding(
                        session, f.id, user_id,
                        export_format=fmt, layout=layout,
                        include_source_text=include_source_text,
                        include_author=include_author,
                    )
                    suffix = "segments_long" if layout == "long" else "matrix_wide"
                    bundle_files[f"codings/{f.id}_{f_slug}_{suffix}.{fmt}"] = content.encode("utf-8")

            sum_csv, _, _ = await export_summary(session, f.id, user_id, export_format="csv")
            sum_json, _, _ = await export_summary(session, f.id, user_id, export_format="json")
            bundle_files[f"codings/{f.id}_{f_slug}_summary.csv"] = sum_csv.encode("utf-8")
            bundle_files[f"codings/{f.id}_{f_slug}_summary.json"] = sum_json.encode("utf-8")

        elif f.file_type in ("codebook_comparison", "coding_comparison"):
            content = await version_service.read_blob(session, f.id)
            if content is not None:
                bundle_files[f"comparisons/{f.id}_{f_slug}_comparison.md"] = content.encode("utf-8")

        memos = await export_repo.get_row_memos(session, f.id)
        if memos:
            m_csv, _, _ = await export_memos(session, f.id, user_id, export_format="csv")
            m_json, _, _ = await export_memos(session, f.id, user_id, export_format="json")
            bundle_files[f"memos/{f.id}_{f_slug}_memos.csv"] = m_csv.encode("utf-8")
            bundle_files[f"memos/{f.id}_{f_slug}_memos.json"] = m_json.encode("utf-8")

    _MEDIA_TYPES_BY_EXT = {"json": "application/json", "csv": "text/csv", "md": "text/markdown"}

    manifest_entries = []
    for path in sorted(bundle_files.keys()):
        content = bundle_files[path]
        ext = path.rsplit(".", 1)[-1]
        manifest_entries.append(
            {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
                "media_type": _MEDIA_TYPES_BY_EXT.get(ext, "text/csv"),
            }
        )

    manifest = {
        "schema_version": "2.0",
        "project_id": project.id,
        "project_name": project.projectname,
        "description": project.description,
        "privacy_flags": {
            "include_source_text": include_source_text,
            "include_author": include_author,
        },
        "files_count": len(manifest_entries),
        "files": manifest_entries,
    }
    bundle_files["manifest.json"] = json.dumps(manifest, indent=2, default=_json_serial).encode("utf-8")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_files.keys()):
            zinfo = zipfile.ZipInfo(filename=path, date_time=(2026, 1, 1, 0, 0, 0))
            zinfo.external_attr = 0o644 << 16
            zf.writestr(zinfo, bundle_files[path])

    proj_slug = _slugify(project.projectname, default=f"project_{project.id}")
    filename = f"{proj_slug}_project_bundle.zip"
    return zip_buffer.getvalue(), "application/zip", filename
