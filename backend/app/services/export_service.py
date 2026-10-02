"""Export service for codebooks, coding entries, row memos, frequency
summaries, and deterministic project bundles.

Produces deterministic, ordered, valid UTF-8 output. Each artifact kind
offers exactly two formats -- the one that best preserves it and the one
that best travels -- rather than a uniform CSV/JSON pair:

* codebook -- ``qdc`` (REFI-QDA Codebook, the interchange standard
  NVivo/ATLAS.ti/MAXQDA implement -- see ``core/qdc.py``) and ``csv``
  (one row per code, carrying ``code_uid``/``family_uid``, for Excel/R).
  ``qdc`` is the default and what the project bundle archives: a codebook
  is the artifact researchers most often need to carry into another QDA
  package, and it is the only one of these exports a standard exists for.
* coding -- ``csv`` and ``json``. Segments carry offsets, nested code
  metadata and optionally full source text with arbitrary newlines, so
  JSON stays the lossless archival form here.
* summary -- ``md`` only. A frequency table is a finished reading of
  a coding, not source data something re-parses; anyone wanting the
  numbers exports the coding and counts.
* memos -- ``md`` first and ``csv`` second: a memo is multi-paragraph
  prose, which a single CSV cell is the wrong shape for.
* document -- ``md`` only, for the artifacts whose content *is* a
  markdown blob (a saved ``summary``, a ``codebook_comparison``/
  ``coding_comparison``): exported as-is, since there are no rows to
  reshape. Distinct from ``summary`` above, which computes a frequency
  table *from a coding*.

Coding exports come in two layouts: ``long`` (one row per coded segment)
and ``wide`` (one row per dataset item, including uncoded ones, with a
column per code) -- see ``export_coding``. The summary export groups by
``code_uid``, never by code name, so a rename doesn't fragment history --
see ``export_summary``/``repositories/export_repo.py::get_code_frequencies_by_uid``.

The project bundle (``export_project_bundle``) writes exactly one file
per project file, always in that artifact's best format, so nothing is
duplicated across formats; a file's row memos ride along as a single
``.md`` sidecar. A ``codebook_comparison``/``coding_comparison`` is
carried as its raw markdown blob -- unlike codebook/coding, a comparison
has no structured rows to serialize, so its content is exported as-is
rather than reshaped.

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
from backend.app.core.qdc import serialize_codes_to_qdc
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


_MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    # REFI-QDA has no registered IANA type; a .qdc is an XML document.
    "qdc": "application/xml; charset=utf-8",
}


def _md_cell(val: Any) -> str:
    """One markdown table cell: pipes escaped and newlines flattened, so a
    multi-line definition can't break the row it sits in.
    """
    if val is None:
        return ""
    return str(val).replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").strip()


def _md_table(rows: list[list[Any]], headers: list[str]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(_md_cell(v) for v in row) + " |" for row in rows)
    return "\n".join(lines)


def _require_format(export_format: str, allowed: tuple[str, ...], artifact: str) -> None:
    """Reject a format this artifact doesn't offer.

    Each export below picks its format with an ``if``/fallthrough, so
    without this an unrecognised value silently returns the *last*
    branch's format -- asking a codebook for ``md`` used to hand back CSV
    under a ``.csv`` filename rather than failing. The route patterns
    already reject bad input at the API edge; this covers internal
    callers, which is where a stale format string actually survives.
    """
    if export_format not in allowed:
        raise ValidationAppError(
            f"{artifact} exports are {' or '.join(allowed)} only (got {export_format!r})"
        )


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
    ref: int | str,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "qdc",
) -> tuple[str, str, str]:
    """Export codebook as (content, media_type, filename).

    ``qdc`` (the default) is the REFI-QDA Codebook interchange standard,
    and what the project bundle archives -- it is the only one of these
    formats another QDA package can import as a codebook rather than as
    an undifferentiated table. ``csv`` is one row per code for a
    spreadsheet or R.
    """
    _require_format(export_format, ("qdc", "csv"), "Codebook")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    if file_record.file_type != "codebook":
        raise ValidationAppError(f"File {file_id} is not a codebook (type={file_record.file_type})")

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="codebook")
    sorted_codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    if export_format == "qdc":
        # `sorted_codes` is already in (position, code_uid) order, which
        # the serializer preserves -- families come out arranged the way
        # the researcher arranged them, not alphabetically.
        content = serialize_codes_to_qdc(sorted_codes)
        filename = f"{base_name}{ver_suffix}_codebook.qdc"
        return content, _MEDIA_TYPES["qdc"], filename

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
    return _csv_serialize(rows, headers), _MEDIA_TYPES["csv"], filename


async def export_coding(
    session: AsyncSession,
    ref: int | str,
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
    _require_format(export_format, ("csv", "json"), "Coding")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
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
            return json.dumps(data, indent=2, default=_json_serial), _MEDIA_TYPES["json"], filename

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
        return _csv_serialize(rows, headers), _MEDIA_TYPES["csv"], filename

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
        return json.dumps(data, indent=2, default=_json_serial), _MEDIA_TYPES["json"], filename

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
    return _csv_serialize(rows, headers), _MEDIA_TYPES["csv"], filename


async def export_memos(
    session: AsyncSession,
    ref: int | str,
    user_id: int,
    *,
    export_format: str = "md",
) -> tuple[str, str, str]:
    """Export row memos as (content, media_type, filename).

    ``md`` is the default and the form the project bundle archives: a
    memo body is multi-paragraph prose, which a single CSV cell is the
    wrong shape for -- it reads as one unwrapped line in a spreadsheet
    and its blank lines fight the parser. ``csv`` stays available for
    counting or joining memos against other exports.

    No ``version_no`` param: unlike codebook/coding/summary, row memos
    are deliberately not SCD-2 range-versioned (see the ``RowMemo``
    docstring) -- there is no historical "as of version N" snapshot to
    resolve, only the current live set, so there is nothing a version
    parameter could filter by.
    """
    _require_format(export_format, ("md", "csv"), "Memo")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    if file_record.file_type not in ("raw_data", "filtered_data", "coding"):
        raise ValidationAppError(
            f"File {file_id} does not carry memos (type={file_record.file_type})"
        )
    memos = await export_repo.get_row_memos(session, file_id)

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]

    if export_format == "md":
        lines = [f"# {file_record.filename or f'file_{file_id}'} -- memos", ""]
        if not memos:
            lines.append("_No memos._")
        for m in memos:
            lines.append(f"## {m.row_type} {m.row_id}")
            lines.append("")
            meta = [f"memo {m.id}"]
            if m.author_user_id is not None:
                meta.append(f"author {m.author_user_id}")
            if m.created_at:
                meta.append(f"created {m.created_at.isoformat()}")
            if m.updated_at:
                meta.append(f"updated {m.updated_at.isoformat()}")
            lines.append(f"*{' - '.join(meta)}*")
            lines.append("")
            # Body verbatim: its paragraph breaks are the point of
            # exporting memos as markdown at all.
            lines.append((m.body or "").strip())
            lines.append("")
        filename = f"{base_name}_memos.md"
        return "\n".join(lines).rstrip() + "\n", _MEDIA_TYPES["md"], filename

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
    return _csv_serialize(rows, headers), _MEDIA_TYPES["csv"], filename


async def export_summary(
    session: AsyncSession,
    ref: int | str,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "md",
) -> tuple[str, str, str]:
    """Export code frequency summary as markdown, grouped strictly by
    ``code_uid``.

    Markdown is the only format offered here, unlike every other export.
    A frequency summary is a finished read-only reading of a coding --
    a handful of rows you paste into a write-up -- not source data
    something downstream re-parses; anyone wanting the underlying numbers
    exports the coding itself and counts. ``export_format`` is kept in
    the signature so the route's ``format`` query parameter stays
    uniform, but ``md`` is the only accepted value.

    The frequency ordering (descending, then ``code_uid``) is the
    repository's -- see ``export_repo.get_code_frequencies_by_uid`` -- so
    a rename never reorders the table.
    """
    _require_format(export_format, ("md",), "Summary")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    if file_record.file_type != "coding":
        raise ValidationAppError(f"File {file_id} is not a coding artifact")

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="coding")
    codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)
    summary_data = await export_repo.get_code_frequencies_by_uid(
        session, file_id, codes=codes, version_no=version_no
    )

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    heading = f"# {file_record.filename or f'file_{file_id}'} -- code frequency"
    if resolved_version_no is not None:
        heading += f" (v{resolved_version_no})"
    if summary_data:
        table = _md_table(
            [
                [s["name"], s["family_name"], s["frequency"], s["document_count"], s["code_uid"]]
                for s in summary_data
            ],
            ["Code", "Family", "Frequency", "Documents", "Code UID"],
        )
    else:
        table = "_No codes applied._"
    filename = f"{base_name}{ver_suffix}_summary.md"
    return f"{heading}\n\n{table}\n", _MEDIA_TYPES["md"], filename


DOCUMENT_FILE_TYPES = {
    "summary": "summary",
    "codebook_comparison": "comparison",
    "coding_comparison": "comparison",
}


async def export_document(
    session: AsyncSession,
    ref: int | str,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "md",
) -> tuple[str, str, str]:
    """Export a markdown-blob artifact (a saved summary or a comparison)
    as its stored markdown, unchanged.
    """
    _require_format(export_format, ("md",), "Document")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    suffix = DOCUMENT_FILE_TYPES.get(file_record.file_type)
    if suffix is None:
        raise ValidationAppError(
            f"File {file_id} is not a summary or comparison (type={file_record.file_type})"
        )

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label=suffix)
    content = await version_service.read_blob(session, file_id, version_no=version_no)
    if content is None:
        raise NotFoundError(f"No content stored for file {file_id}")

    base_name = (file_record.filename or f"file_{file_id}").rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""
    return content, _MEDIA_TYPES["md"], f"{base_name}{ver_suffix}_{suffix}.md"


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
    exactly one export per project file.

    One file in, one file out. Each artifact is written only in the
    format that best preserves it -- codebook ``.qdc`` (REFI-QDA, the
    codebook interchange standard), coding ``.csv`` (segments, long),
    comparison/summary ``.md`` (its raw blob) -- never the same content twice in
    two formats. A file's row memos ride along as a single
    ``.md`` sidecar, which for a ``raw_data``/``filtered_data`` file is
    its only export; memos are kept out of the artifact file rather than
    folded into it because they annotate rows, not codes, and merging
    them would change the artifact's schema.

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
            cb_qdc, _, _ = await export_codebook(session, f.id, user_id, export_format="qdc")
            bundle_files[f"codebooks/{f.id}_{f_slug}_codebook.qdc"] = cb_qdc.encode("utf-8")

        elif f.file_type == "coding":
            content, _, _ = await export_coding(
                session, f.id, user_id,
                export_format="csv", layout="long",
                include_source_text=include_source_text,
                include_author=include_author,
            )
            bundle_files[f"codings/{f.id}_{f_slug}_segments_long.csv"] = content.encode("utf-8")

        elif f.file_type in ("codebook_comparison", "coding_comparison"):
            content = await version_service.read_blob(session, f.id)
            if content is not None:
                bundle_files[f"comparisons/{f.id}_{f_slug}_comparison.md"] = content.encode("utf-8")

        elif f.file_type == "summary":
            content = await version_service.read_blob(session, f.id)
            if content is not None:
                bundle_files[f"summaries/{f.id}_{f_slug}_summary.md"] = content.encode("utf-8")

        memos = await export_repo.get_row_memos(session, f.id)
        if memos:
            m_md, _, _ = await export_memos(session, f.id, user_id, export_format="md")
            bundle_files[f"memos/{f.id}_{f_slug}_memos.md"] = m_md.encode("utf-8")

    manifest_entries = []
    for path in sorted(bundle_files.keys()):
        content = bundle_files[path]
        ext = path.rsplit(".", 1)[-1]
        manifest_entries.append(
            {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
                "media_type": _MEDIA_TYPES.get(ext, _MEDIA_TYPES["csv"]).split(";")[0],
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
