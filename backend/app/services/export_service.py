"""Export service for codebooks, coding entries, row memos, frequency
summaries, saved documents, and deterministic project bundles.

Produces deterministic, ordered output. Most people exporting from this
app are not technical, so **Word (``.docx``) and Excel (``.xlsx``) come
first and are the defaults** wherever they fit; the interchange formats
stay available, listed after, for researchers moving data into R, SPSS
or another QDA package:

* codebook -- ``docx`` (default: a readable codebook, families as
  headings, each code with its definition and rules -- see
  ``_codebook_docx``), ``xlsx`` (one row per code), ``qdc`` (REFI-QDA
  Codebook, the interchange standard NVivo/ATLAS.ti/MAXQDA implement --
  see ``core/qdc.py``) and ``csv``.
* coding -- ``xlsx`` (default: one workbook holding the coded quotes, the
  item-by-code matrix, the codebook and code counts as sheets, so nobody
  has to pick a layout), ``docx`` (a code report: every quote grouped
  under its code), ``csv`` and ``json``. Only ``csv``/``json`` take a
  ``layout`` -- see ``export_coding``. JSON stays the lossless archival
  form (offsets, nested code metadata, full source text).
* summary -- ``docx`` (default), ``xlsx`` and ``md``: a code-frequency
  table computed from a coding, a finished reading pasted into a write-up.
* memos -- ``docx`` (default), ``xlsx``, ``md`` and ``csv``: a memo is
  multi-paragraph prose, which a document holds best.
* document -- ``docx`` (default) and ``md``, for the artifacts whose
  content *is* a markdown blob (a saved ``summary``, a
  ``codebook_comparison``/``coding_comparison``): the ``md`` export is the
  stored blob as-is, the ``docx`` one renders it
  (``core/docx_render.py::markdown_to_docx``). Distinct from ``summary``
  above, which computes a frequency table *from a coding*.

Every format writes user text through the sanitizer matching its sink
(``core/export_text.py``): spreadsheet cells can't become formulas, XML
formats drop the control characters XML forbids, and generated markdown
headings/cells can't inject structure or HTML. Word/Excel headers are
plain language ("Code", "Coded by"); CSV/JSON keep their machine
headers.

The summary export groups by ``code_uid``, never by code name, so a
rename doesn't fragment history -- see
``repositories/export_repo.py::get_code_frequencies_by_uid``.

The project bundle (``export_project_bundle``) writes each project file
in the formats the caller picked for its type (``BUNDLE_FORMATS``) --
by default just that type's first (Word or Excel), so nothing is
duplicated unless asked for; picking several writes the same artifact
once per format. A file's row memos ride along as a sidecar the same way.

Privacy: ``include_source_text``/``include_author`` on ``export_coding``
and ``export_project_bundle`` both default to ``False`` -- an export is
opt-in to carrying the underlying quote's full source text or its
author, not opt-out, in every format.
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

from backend.app.core import docx_render
from backend.app.core.exceptions import NotFoundError, ValidationAppError
from backend.app.core.export_text import md_inline, neutralize_formula
from backend.app.core.qdc import serialize_codes_to_qdc
from backend.app.core.xlsx_render import SheetSpec, build_workbook
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


def _csv_cell(value: Any) -> str:
    """Exports carry Reddit text verbatim, so a post starting with
    ``=HYPERLINK(...)`` must reach a spreadsheet as text, not run."""
    if value is None:
        return ""
    if isinstance(value, str):
        return neutralize_formula(value)
    return str(value)


def _csv_serialize(rows: list[list[Any]], headers: list[str]) -> str:
    """CSV text for spreadsheets: a UTF-8 BOM so Excel doesn't read it as
    the local legacy encoding, and text cells neutralized against
    formula injection (numbers, e.g. a negative score, are left alone).
    """
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    return output.getvalue()


_MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    # REFI-QDA has no registered IANA type; a .qdc is an XML document.
    "qdc": "application/xml; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _md_table(rows: list[list[Any]], headers: list[str]) -> str:
    lines = [
        "| " + " | ".join(md_inline(h) for h in headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(md_inline(v) for v in row) + " |" for row in rows)
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


_ROW_TYPE_LABELS = {"submission": "Post", "comment": "Comment"}
_CODER_LABELS = {"human": "Human", "ai": "AI"}


def _row_type_label(row_type: str | None) -> str:
    return _ROW_TYPE_LABELS.get(row_type or "", (row_type or "").capitalize())


def _coder_label(coder: str | None, model: str | None) -> str:
    label = _CODER_LABELS.get(coder or "human", coder or "")
    return f"{label} ({model})" if model else label


def _version_label(resolved_version_no: int | None) -> str:
    return f"Version {resolved_version_no}" if resolved_version_no is not None else "No saved version"


def _display_name(file_record: Any) -> str:
    return file_record.filename or f"file_{file_record.id}"


def _family_groups(codes: list[CodebookCode]) -> list[tuple[str, list[CodebookCode]]]:
    """Codes grouped by ``family_uid`` in first-appearance order, each
    group labelled by its family name ("" for codes without one).

    Grouping by uid, not name, matches the qdc serializer: two families
    that happen to share a name stay two families.
    """
    groups: dict[str, list[CodebookCode]] = {}
    for c in codes:
        key = c.family_uid if c.family_uid and c.family_name else ""
        groups.setdefault(key, []).append(c)
    return [((group[0].family_name or "") if key else "", group) for key, group in groups.items()]


_CODEBOOK_XLSX_HEADERS = [
    "Family", "Code", "Definition", "Include when", "Exclude when", "Example", "Keywords", "Code ID",
]
_CODEBOOK_DOCX_FIELDS = (
    ("definition", "Definition"),
    ("inclusion", "Include when"),
    ("exclusion", "Exclude when"),
    ("example", "Example"),
    ("keywords", "Keywords"),
)


def _codebook_xlsx_rows(codes: list[CodebookCode]) -> list[list[Any]]:
    return [
        [
            c.family_name or "", c.name or "", c.definition or "", c.inclusion or "",
            c.exclusion or "", c.example or "", c.keywords or "", c.code_uid or "",
        ]
        for c in codes
    ]


_FREQUENCY_HEADERS = ["Code", "Family", "Times applied", "Items"]


def _frequency_rows(summary_data: list[dict[str, Any]]) -> list[list[Any]]:
    return [[s["name"], s["family_name"], s["frequency"], s["document_count"]] for s in summary_data]


def _frequency_xlsx_rows(summary_data: list[dict[str, Any]]) -> list[list[Any]]:
    return [row + [s["code_uid"]] for row, s in zip(_frequency_rows(summary_data), summary_data, strict=True)]


def _codebook_docx(title: str, version_label: str, codes: list[CodebookCode]) -> bytes:
    doc = docx_render.new_document(f"{title} — codebook", [version_label, f"{len(codes)} code(s)"])
    if not codes:
        docx_render.add_paragraph(doc, "This codebook has no codes yet.", italic=True)
    groups = _family_groups(codes)
    has_families = any(name for name, _ in groups)
    for family_name, group in groups:
        if family_name:
            docx_render.add_heading(doc, family_name, 1)
        elif has_families:
            docx_render.add_heading(doc, "Codes without a family", 1)
        for c in group:
            docx_render.add_heading(doc, c.name or "(unnamed code)", 2)
            for attr, label in _CODEBOOK_DOCX_FIELDS:
                value = (getattr(c, attr) or "").strip()
                if value:
                    docx_render.add_paragraph(doc, value, label=label)
    return docx_render.to_bytes(doc)


async def export_codebook(
    session: AsyncSession,
    ref: int | str,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "docx",
) -> tuple[str | bytes, str, str]:
    """Export codebook as (content, media_type, filename).

    ``docx`` (the default) is the codebook as a document someone reads
    and prints; ``xlsx`` one row per code for sorting/filtering; ``qdc``
    the REFI-QDA interchange standard -- the only format another QDA
    package imports as a codebook rather than as a table; ``csv`` one row
    per code for R.
    """
    _require_format(export_format, ("docx", "xlsx", "qdc", "csv"), "Codebook")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    if file_record.file_type != "codebook":
        raise ValidationAppError(f"File {file_id} is not a codebook (type={file_record.file_type})")

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="codebook")
    sorted_codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)

    base_name = _display_name(file_record).rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""
    filename = f"{base_name}{ver_suffix}_codebook.{export_format}"

    if export_format == "docx":
        content = _codebook_docx(_display_name(file_record), _version_label(resolved_version_no), sorted_codes)
        return content, _MEDIA_TYPES["docx"], filename

    if export_format == "xlsx":
        content = build_workbook(
            [SheetSpec("Codebook", _CODEBOOK_XLSX_HEADERS, _codebook_xlsx_rows(sorted_codes))],
            about=[
                ("File", _display_name(file_record)),
                ("Version", _version_label(resolved_version_no)),
                ("Codes", len(sorted_codes)),
            ],
        )
        return content, _MEDIA_TYPES["xlsx"], filename

    if export_format == "qdc":
        # `sorted_codes` is already in (position, code_uid) order, which
        # the serializer preserves -- families come out arranged the way
        # the researcher arranged them, not alphabetically.
        return serialize_codes_to_qdc(sorted_codes), _MEDIA_TYPES["qdc"], filename

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
    return _csv_serialize(rows, headers), _MEDIA_TYPES["csv"], filename


def _matrix_code_headers(codes: list[CodebookCode]) -> list[str]:
    """One matrix column header per code, by name -- suffixed with a
    short uid only where two codes share a name, so no column is
    ambiguous."""
    names = [c.name or c.code_uid for c in codes]
    return [
        f"{name} ({c.code_uid[:6]})" if names.count(name) > 1 else name
        for name, c in zip(names, codes, strict=True)
    ]


def _coding_xlsx(
    *,
    file_record: Any,
    resolved_version_no: int | None,
    codes: list[CodebookCode],
    entries: list[Any],
    all_rows: list[dict[str, Any]],
    row_lookup: dict[tuple[str, str], dict[str, Any]],
    summary_data: list[dict[str, Any]],
    include_source_text: bool,
    include_author: bool,
) -> bytes:
    code_meta = {c.code_uid: c for c in codes if c.code_uid}

    quote_headers = ["Item type", "Item ID", "Code", "Family", "Quote", "Notes", "Coded by", "Model"]
    if include_author:
        quote_headers.append("Author")
    if include_source_text:
        quote_headers.append("Source text")
    quote_headers += ["Code ID", "Entry ID", "Start offset", "End offset"]
    quote_rows = []
    for e in entries:
        c = code_meta.get(e.code_uid)
        row_info = row_lookup.get((e.row_type, str(e.post_id))) or {}
        coder = getattr(e, "coder", "human")
        r: list[Any] = [
            _row_type_label(e.row_type), str(e.post_id), (c.name if c else None) or e.code,
            c.family_name if c else "", e.quote or "", e.notes or "",
            _CODER_LABELS.get(coder, coder), getattr(e, "coder_model", None) or "",
        ]
        if include_author:
            r.append(row_info.get("author") or "")
        if include_source_text:
            r.append(row_info.get("source_text") or "")
        r += [e.code_uid or "", e.id, e.start_offset, e.end_offset]
        quote_rows.append(r)

    coded_uids = [c.code_uid for c in codes if c.code_uid]
    matrix_codes = [code_meta[uid] for uid in coded_uids]
    item_entries: dict[tuple[str, str], list[str]] = {}
    for e in entries:
        assigned = item_entries.setdefault((e.row_type or "", str(e.post_id or "")), [])
        if e.code_uid:
            assigned.append(e.code_uid)
    matrix_headers = ["Item type", "Item ID", "Coded", "Number of codes"]
    if include_author:
        matrix_headers.append("Author")
    if include_source_text:
        matrix_headers.append("Source text")
    matrix_headers += _matrix_code_headers(matrix_codes)
    matrix_rows = []
    for row in all_rows:
        assigned = item_entries.get((row["row_type"], row["post_id"]), [])
        r = [_row_type_label(row["row_type"]), row["post_id"], "Yes" if assigned else "No", len(assigned)]
        if include_author:
            r.append(row.get("author") or "")
        if include_source_text:
            r.append(row.get("source_text") or "")
        r += [assigned.count(uid) for uid in coded_uids]
        matrix_rows.append(r)

    return build_workbook(
        [
            SheetSpec("Coded quotes", quote_headers, quote_rows),
            SheetSpec("Matrix", matrix_headers, matrix_rows),
            SheetSpec("Codebook", _CODEBOOK_XLSX_HEADERS, _codebook_xlsx_rows(codes)),
            SheetSpec("Code counts", _FREQUENCY_HEADERS + ["Code ID"], _frequency_xlsx_rows(summary_data)),
        ],
        about=[
            ("File", _display_name(file_record)),
            ("Version", _version_label(resolved_version_no)),
            ("Coded quotes", len(entries)),
            ("Items", len(all_rows)),
            ("Includes author", "Yes" if include_author else "No"),
            ("Includes source text", "Yes" if include_source_text else "No"),
        ],
    )


def _coding_docx(
    *,
    file_record: Any,
    resolved_version_no: int | None,
    codes: list[CodebookCode],
    entries: list[Any],
    row_lookup: dict[tuple[str, str], dict[str, Any]],
    summary_data: list[dict[str, Any]],
    include_source_text: bool,
    include_author: bool,
) -> bytes:
    """A code report: code counts, then every quote under its code."""
    doc = docx_render.new_document(
        f"{_display_name(file_record)} — coded quotes",
        [_version_label(resolved_version_no), f"{len(entries)} coded quote(s)"],
    )
    docx_render.add_heading(doc, "Code counts", 1)
    if summary_data:
        docx_render.add_table(doc, _FREQUENCY_HEADERS, _frequency_rows(summary_data))
    else:
        docx_render.add_paragraph(doc, "No codes applied.", italic=True)

    by_uid: dict[str, list[Any]] = {}
    for e in entries:
        by_uid.setdefault(e.code_uid or "", []).append(e)

    def add_quotes(code_entries: list[Any]) -> None:
        if not code_entries:
            docx_render.add_paragraph(doc, "No quotes coded.", italic=True)
        for e in code_entries:
            docx_render.add_paragraph(doc, e.quote or "(no quote text)", style="Quote")
            reference = (
                f"{_row_type_label(e.row_type)} {e.post_id} · coded by "
                f"{_coder_label(getattr(e, 'coder', 'human'), getattr(e, 'coder_model', None))}"
            )
            docx_render.add_paragraph(doc, reference, italic=True)
            if e.notes:
                docx_render.add_paragraph(doc, e.notes, label="Note")
            row_info = row_lookup.get((e.row_type, str(e.post_id))) or {}
            if include_author:
                docx_render.add_paragraph(doc, row_info.get("author") or "(unknown)", label="Author")
            if include_source_text:
                docx_render.add_paragraph(doc, row_info.get("source_text") or "", label="Source text")

    groups = _family_groups(codes)
    has_families = any(name for name, _ in groups)
    for family_name, group in groups:
        if family_name:
            docx_render.add_heading(doc, family_name, 1)
        elif has_families:
            docx_render.add_heading(doc, "Codes without a family", 1)
        for c in group:
            docx_render.add_heading(doc, c.name or "(unnamed code)", 2)
            if c.definition:
                docx_render.add_paragraph(doc, c.definition, label="Definition")
            add_quotes(by_uid.get(c.code_uid or "", []))

    # An entry whose code_uid is no longer in the codebook still surfaces,
    # under the name it was coded with, rather than being dropped.
    known = {c.code_uid for c in codes}
    orphans = [uid for uid in by_uid if uid not in known]
    if orphans:
        docx_render.add_heading(doc, "Codes no longer in the codebook", 1)
        for uid in orphans:
            docx_render.add_heading(doc, by_uid[uid][0].code or uid or "(unnamed code)", 2)
            add_quotes(by_uid[uid])
    return docx_render.to_bytes(doc)


async def export_coding(
    session: AsyncSession,
    ref: int | str,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "xlsx",
    layout: str | None = None,
    include_source_text: bool = False,
    include_author: bool = False,
) -> tuple[str | bytes, str, str]:
    """Export coding data.

    ``xlsx`` (the default) is one workbook with every view as a sheet --
    coded quotes, the item-by-code matrix (uncoded items included), the
    codebook and code counts -- and ``docx`` a code report. Neither takes
    a ``layout``: passing one is an error rather than silently ignored.
    ``csv``/``json`` do, defaulting to ``long`` (one row per coded segment
    quote); ``wide`` is one row per dataset item -- including uncoded ones
    -- with a count column per code.
    """
    _require_format(export_format, ("xlsx", "docx", "csv", "json"), "Coding")
    if export_format in ("xlsx", "docx"):
        if layout is not None:
            raise ValidationAppError(
                f"layout applies only to csv/json coding exports; {export_format} includes every view"
            )
    else:
        layout = layout or "long"
        if layout not in ("long", "wide"):
            raise ValidationAppError(f"Unknown coding export layout: {layout!r}")

    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    if file_record.file_type != "coding":
        raise ValidationAppError(f"File {file_id} is not a coding artifact (type={file_record.file_type})")

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="coding")

    base_name = _display_name(file_record).rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""

    codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)
    code_meta = {c.code_uid: c for c in codes if c.code_uid}
    entries = await export_repo.get_coding_entries(session, file_id, version_no=version_no)

    row_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    if include_source_text or include_author or layout == "wide" or export_format == "xlsx":
        all_rows = await export_repo.get_all_rows_for_coding(session, file_id, version_no=version_no)
        row_lookup = {(r["row_type"], r["post_id"]): r for r in all_rows}
    else:
        all_rows = []

    if export_format in ("xlsx", "docx"):
        summary_data = await export_repo.get_code_frequencies_by_uid(
            session, file_id, codes=codes, version_no=version_no
        )
        if export_format == "xlsx":
            content = _coding_xlsx(
                file_record=file_record, resolved_version_no=resolved_version_no, codes=codes,
                entries=entries, all_rows=all_rows, row_lookup=row_lookup, summary_data=summary_data,
                include_source_text=include_source_text, include_author=include_author,
            )
            return content, _MEDIA_TYPES["xlsx"], f"{base_name}{ver_suffix}_coding.xlsx"
        content = _coding_docx(
            file_record=file_record, resolved_version_no=resolved_version_no, codes=codes,
            entries=entries, row_lookup=row_lookup, summary_data=summary_data,
            include_source_text=include_source_text, include_author=include_author,
        )
        return content, _MEDIA_TYPES["docx"], f"{base_name}{ver_suffix}_coded_quotes.docx"

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


def _memo_meta(m: Any) -> list[str]:
    meta = [f"memo {m.id}"]
    if m.author_user_id is not None:
        meta.append(f"author {m.author_user_id}")
    if m.created_at:
        meta.append(f"created {m.created_at.isoformat()}")
    if m.updated_at:
        meta.append(f"updated {m.updated_at.isoformat()}")
    return meta


async def export_memos(
    session: AsyncSession,
    ref: int | str,
    user_id: int,
    *,
    export_format: str = "docx",
) -> tuple[str | bytes, str, str]:
    """Export row memos as (content, media_type, filename).

    ``docx`` is the default: a memo body is multi-paragraph prose, which
    a document holds best. ``md`` keeps the same shape as plain text;
    ``xlsx``/``csv`` stay available for counting or joining memos against
    other exports.

    No ``version_no`` param: unlike codebook/coding/summary, row memos
    are deliberately not SCD-2 range-versioned (see the ``RowMemo``
    docstring) -- there is no historical "as of version N" snapshot to
    resolve, only the current live set, so there is nothing a version
    parameter could filter by.
    """
    _require_format(export_format, ("docx", "xlsx", "md", "csv"), "Memo")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    if file_record.file_type not in ("raw_data", "filtered_data", "coding"):
        raise ValidationAppError(
            f"File {file_id} does not carry memos (type={file_record.file_type})"
        )
    memos = await export_repo.get_row_memos(session, file_id)

    base_name = _display_name(file_record).rsplit(".", 1)[0]
    filename = f"{base_name}_memos.{export_format}"

    if export_format == "docx":
        doc = docx_render.new_document(f"{_display_name(file_record)} — memos", [f"{len(memos)} memo(s)"])
        if not memos:
            docx_render.add_paragraph(doc, "No memos.", italic=True)
        for m in memos:
            docx_render.add_heading(doc, f"{_row_type_label(m.row_type)} {m.row_id}", 2)
            docx_render.add_paragraph(doc, " - ".join(_memo_meta(m)), italic=True)
            # One Word paragraph per markdown paragraph; a single line
            # break inside one stays a line break.
            for block in re.split(r"\n\s*\n", (m.body or "").strip()):
                if block.strip():
                    docx_render.add_paragraph(doc, block.strip())
        return docx_render.to_bytes(doc), _MEDIA_TYPES["docx"], filename

    if export_format == "xlsx":
        content = build_workbook(
            [
                SheetSpec(
                    "Memos",
                    ["Item type", "Item ID", "Memo", "Author (user ID)", "Created", "Updated", "Memo ID"],
                    [
                        [
                            _row_type_label(m.row_type), m.row_id, m.body or "", m.author_user_id,
                            m.created_at.isoformat(sep=" ", timespec="minutes") if m.created_at else "",
                            m.updated_at.isoformat(sep=" ", timespec="minutes") if m.updated_at else "",
                            m.id,
                        ]
                        for m in memos
                    ],
                    column_widths={2: 80},
                )
            ],
            about=[("File", _display_name(file_record)), ("Memos", len(memos))],
        )
        return content, _MEDIA_TYPES["xlsx"], filename

    if export_format == "md":
        lines = [f"# {md_inline(_display_name(file_record))} -- memos", ""]
        if not memos:
            lines.append("_No memos._")
        for m in memos:
            lines.append(f"## {md_inline(m.row_type)} {md_inline(m.row_id)}")
            lines.append("")
            lines.append(f"*{' - '.join(_memo_meta(m))}*")
            lines.append("")
            # Body verbatim: its paragraph breaks are the point of
            # exporting memos as markdown at all.
            lines.append((m.body or "").strip())
            lines.append("")
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
    return _csv_serialize(rows, headers), _MEDIA_TYPES["csv"], filename


async def export_summary(
    session: AsyncSession,
    ref: int | str,
    user_id: int,
    *,
    version_no: int | None = None,
    export_format: str = "docx",
) -> tuple[str | bytes, str, str]:
    """Export a code frequency summary, grouped strictly by ``code_uid``.

    A frequency summary is a finished reading of a coding -- a handful of
    rows pasted into a write-up -- so ``docx`` is the default; ``xlsx``
    holds the counts as numbers, and ``md`` the same table as text.

    The frequency ordering (descending, then ``code_uid``) is the
    repository's -- see ``export_repo.get_code_frequencies_by_uid`` -- so
    a rename never reorders the table.
    """
    _require_format(export_format, ("docx", "xlsx", "md"), "Summary")
    file_record = await file_repo.get_owned_file(session, str(ref), user_id)
    file_id = file_record.id
    if file_record.file_type != "coding":
        raise ValidationAppError(f"File {file_id} is not a coding artifact")

    _, resolved_version_no = await _resolve_version(session, file_id, version_no, label="coding")
    codes = await _get_sorted_codebook_codes(session, file_id, version_no=version_no)
    summary_data = await export_repo.get_code_frequencies_by_uid(
        session, file_id, codes=codes, version_no=version_no
    )

    base_name = _display_name(file_record).rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""
    filename = f"{base_name}{ver_suffix}_summary.{export_format}"

    if export_format == "docx":
        doc = docx_render.new_document(
            f"{_display_name(file_record)} — code frequency", [_version_label(resolved_version_no)]
        )
        if summary_data:
            docx_render.add_table(doc, _FREQUENCY_HEADERS, _frequency_rows(summary_data))
        else:
            docx_render.add_paragraph(doc, "No codes applied.", italic=True)
        return docx_render.to_bytes(doc), _MEDIA_TYPES["docx"], filename

    if export_format == "xlsx":
        content = build_workbook(
            [SheetSpec("Code counts", _FREQUENCY_HEADERS + ["Code ID"], _frequency_xlsx_rows(summary_data))],
            about=[("File", _display_name(file_record)), ("Version", _version_label(resolved_version_no))],
        )
        return content, _MEDIA_TYPES["xlsx"], filename

    heading = f"# {md_inline(_display_name(file_record))} -- code frequency"
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
    export_format: str = "docx",
) -> tuple[str | bytes, str, str]:
    """Export a markdown-blob artifact (a saved summary or a comparison):
    ``docx`` (the default) renders the stored markdown as a Word
    document, ``md`` returns it unchanged.
    """
    _require_format(export_format, ("docx", "md"), "Document")
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

    base_name = _display_name(file_record).rsplit(".", 1)[0]
    ver_suffix = f"_v{resolved_version_no}" if resolved_version_no is not None else ""
    filename = f"{base_name}{ver_suffix}_{suffix}.{export_format}"
    if export_format == "md":
        return content, _MEDIA_TYPES["md"], filename

    doc = docx_render.new_document(
        _display_name(file_record), [f"{suffix.capitalize()} · {_version_label(resolved_version_no)}"]
    )
    docx_render.markdown_to_docx(doc, content)
    return docx_render.to_bytes(doc), _MEDIA_TYPES["docx"], filename


# Bundle format tokens per artifact type, each mapped to its bundle path
# suffix. The first token is the default -- Word or Excel, for a
# non-technical reader. Coding's csv/json tokens fold in the layout,
# since long and wide CSV are both ``.csv``.
BUNDLE_FORMATS: dict[str, dict[str, str]] = {
    "codebook": {
        "docx": "_codebook.docx",
        "xlsx": "_codebook.xlsx",
        "qdc": "_codebook.qdc",
        "csv": "_codebook.csv",
    },
    "coding": {
        "xlsx": "_coding.xlsx",
        "docx": "_coded_quotes.docx",
        "csv_long": "_segments_long.csv",
        "csv_wide": "_matrix_wide.csv",
        "json": "_segments_long.json",
    },
    "comparison": {"docx": "_comparison.docx", "md": "_comparison.md"},
    "summary": {"docx": "_summary.docx", "md": "_summary.md"},
    "memos": {"docx": "_memos.docx", "xlsx": "_memos.xlsx", "md": "_memos.md", "csv": "_memos.csv"},
}
_BUNDLE_CODING_EXPORTS: dict[str, tuple[str, str | None]] = {
    "xlsx": ("xlsx", None),
    "docx": ("docx", None),
    "csv_long": ("csv", "long"),
    "csv_wide": ("csv", "wide"),
    "json": ("json", "long"),
}
_BUNDLE_DOCUMENT_DIRS = {"comparison": "comparisons", "summary": "summaries"}


def _resolve_bundle_formats(kind: str, requested: list[str] | None) -> list[str]:
    """Validate and de-duplicate one type's requested bundle formats,
    in ``BUNDLE_FORMATS`` order; ``None``/empty means the default."""
    allowed = BUNDLE_FORMATS[kind]
    if not requested:
        return [next(iter(allowed))]
    unknown = sorted(set(requested) - allowed.keys())
    if unknown:
        raise ValidationAppError(f"Unsupported {kind} bundle format(s): {', '.join(unknown)}")
    return [token for token in allowed if token in requested]


def _as_bytes(content: str | bytes) -> bytes:
    return content.encode("utf-8") if isinstance(content, str) else content


async def export_project_bundle(
    session: AsyncSession,
    project_id: int,
    user_id: int,
    *,
    include_source_text: bool = False,
    include_author: bool = False,
    codebook_formats: list[str] | None = None,
    coding_formats: list[str] | None = None,
    comparison_formats: list[str] | None = None,
    summary_formats: list[str] | None = None,
    memo_formats: list[str] | None = None,
) -> tuple[bytes, str, str]:
    """Deterministic ZIP bundle of every artifact in a project: a
    manifest with a SHA-256 per file, the project's lineage graph, and
    one export per project file per requested format.

    The ``*_formats`` lists pick the formats (tokens from
    ``BUNDLE_FORMATS``) each artifact of that type is written in. Left
    unset, each artifact is written once in its type's first format --
    Word for codebooks, comparisons, saved summaries and memos, Excel for
    codings -- so content appears in two formats only when the caller
    asked for both. A file's row memos ride along as a sidecar, which for
    a ``raw_data``/``filtered_data`` file is its only export; memos are
    kept out of the artifact file rather than folded into it because they
    annotate rows, not codes, and merging them would change the
    artifact's schema.

    Byte-deterministic: entries are written in sorted-path order with a
    fixed ``date_time`` (2026-01-01 00:00:00), and the Word/Excel files
    inside are themselves frozen the same way (``xlsx_render.freeze_ooxml``),
    so identical content always produces identical bytes.
    """
    formats = {
        "codebook": _resolve_bundle_formats("codebook", codebook_formats),
        "coding": _resolve_bundle_formats("coding", coding_formats),
        "comparison": _resolve_bundle_formats("comparison", comparison_formats),
        "summary": _resolve_bundle_formats("summary", summary_formats),
        "memos": _resolve_bundle_formats("memos", memo_formats),
    }
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
            for token in formats["codebook"]:
                content, _, _ = await export_codebook(session, f.id, user_id, export_format=token)
                suffix = BUNDLE_FORMATS["codebook"][token]
                bundle_files[f"codebooks/{f.id}_{f_slug}{suffix}"] = _as_bytes(content)

        elif f.file_type == "coding":
            for token in formats["coding"]:
                export_format, layout = _BUNDLE_CODING_EXPORTS[token]
                content, _, _ = await export_coding(
                    session, f.id, user_id,
                    export_format=export_format, layout=layout,
                    include_source_text=include_source_text,
                    include_author=include_author,
                )
                suffix = BUNDLE_FORMATS["coding"][token]
                bundle_files[f"codings/{f.id}_{f_slug}{suffix}"] = _as_bytes(content)

        elif f.file_type in DOCUMENT_FILE_TYPES:
            kind = DOCUMENT_FILE_TYPES[f.file_type]
            for token in formats[kind]:
                try:
                    content, _, _ = await export_document(session, f.id, user_id, export_format=token)
                except NotFoundError:
                    break  # nothing stored yet -- nothing to carry
                suffix = BUNDLE_FORMATS[kind][token]
                bundle_files[f"{_BUNDLE_DOCUMENT_DIRS[kind]}/{f.id}_{f_slug}{suffix}"] = _as_bytes(content)

        memos = await export_repo.get_row_memos(session, f.id)
        if memos:
            for token in formats["memos"]:
                content, _, _ = await export_memos(session, f.id, user_id, export_format=token)
                suffix = BUNDLE_FORMATS["memos"][token]
                bundle_files[f"memos/{f.id}_{f_slug}{suffix}"] = _as_bytes(content)

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
        "schema_version": "3.0",
        "project_id": project.id,
        "project_name": project.projectname,
        "description": project.description,
        "privacy_flags": {
            "include_source_text": include_source_text,
            "include_author": include_author,
        },
        "formats": formats,
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
