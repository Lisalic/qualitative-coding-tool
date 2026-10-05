/**
 * Helpers for export url construction and artifact format options.
 */

export function buildExportPath(fileId, targetType, format, versionNo = null, extraParams = null) {
  const params = new URLSearchParams();
  params.set("format", format);
  if (versionNo) {
    params.set("version_no", String(versionNo));
  }
  if (extraParams) {
    for (const [key, value] of Object.entries(extraParams)) {
      params.set(key, String(value));
    }
  }
  return `/api/export/${fileId}/${targetType}?${params.toString()}`;
}

/**
 * Plain-language format labels, shared by the export menu and the project
 * download dialog. Most users aren't technical, so a label names the
 * program a file opens in before its extension.
 */
const LABELS = {
  docx: "Word document (.docx)",
  xlsx: "Excel workbook (.xlsx)",
  qdc: "REFI-QDA codebook (.qdc)",
  csv: "CSV (.csv)",
  csvLong: "CSV – one row per quote",
  csvWide: "CSV – matrix",
  json: "JSON (.json)",
  md: "Markdown (.md)",
};

/**
 * What the project download dialog offers, per kind of artifact in the
 * bundle. `formats` are the backend's bundle tokens
 * (`export_service.BUNDLE_FORMATS`), Word/Excel first -- the first is
 * checked by default. `fileTypes` decides whether the kind appears at
 * all -- memos can sit on any raw/filtered/coding file, so they appear
 * whenever the project has one.
 */
export const PROJECT_BUNDLE_KINDS = [
  {
    key: "codebook",
    label: "Codebooks",
    fileTypes: ["codebook"],
    param: "codebook_formats",
    formats: [
      { value: "docx", label: LABELS.docx },
      { value: "xlsx", label: LABELS.xlsx },
      { value: "qdc", label: LABELS.qdc },
      { value: "csv", label: LABELS.csv },
    ],
  },
  {
    key: "coding",
    label: "Codings",
    fileTypes: ["coding"],
    param: "coding_formats",
    formats: [
      { value: "xlsx", label: LABELS.xlsx },
      { value: "docx", label: LABELS.docx },
      { value: "csv_long", label: LABELS.csvLong },
      { value: "csv_wide", label: LABELS.csvWide },
      { value: "json", label: LABELS.json },
    ],
  },
  {
    key: "comparison",
    label: "Comparisons",
    fileTypes: ["codebook_comparison", "coding_comparison"],
    param: "comparison_formats",
    formats: [
      { value: "docx", label: LABELS.docx },
      { value: "md", label: LABELS.md },
    ],
  },
  {
    key: "summary",
    label: "Summaries",
    fileTypes: ["summary"],
    param: "summary_formats",
    formats: [
      { value: "docx", label: LABELS.docx },
      { value: "md", label: LABELS.md },
    ],
  },
  {
    key: "memos",
    label: "Row memos (where written)",
    fileTypes: ["raw_data", "filtered_data", "coding"],
    param: "memo_formats",
    formats: [
      { value: "docx", label: LABELS.docx },
      { value: "xlsx", label: LABELS.xlsx },
      { value: "md", label: LABELS.md },
      { value: "csv", label: LABELS.csv },
    ],
  },
];

/**
 * `formats` maps a bundle query param (`codebook_formats`, ...) to the
 * tokens picked for it; each token is sent as its own repeated param.
 * `flags` carries the coding privacy opt-ins (`include_source_text`,
 * `include_author`), sent only when on.
 */
export function buildProjectBundlePath(projectId, { formats = {}, flags = {} } = {}) {
  const params = new URLSearchParams();
  for (const [param, values] of Object.entries(formats)) {
    for (const value of values) params.append(param, value);
  }
  for (const [param, on] of Object.entries(flags)) {
    if (on) params.set(param, "true");
  }
  const query = params.toString();
  return `/api/export/projects/${projectId}/bundle${query ? `?${query}` : ""}`;
}

// Path separators and control characters: a download name is
// user-chosen text, so it may name a file but never a path.
// eslint-disable-next-line no-control-regex
const UNSAFE_FILENAME_CHARS = /[\\/\u0000-\u001f\u007f]/g;

/**
 * The download name from a `Content-Disposition` header: the UTF-8
 * `filename*` when present (the real name, accents and all), else the
 * ASCII `filename`, else `fallback` -- with path separators and control
 * characters stripped, falling back if nothing is left.
 */
export function filenameFromDisposition(disposition, fallback) {
  if (!disposition) return fallback;
  let name = null;
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) {
    try {
      name = decodeURIComponent(encoded[1].trim());
    } catch {
      // Malformed escape: fall through to the plain name.
    }
  }
  if (name === null) {
    const plain = disposition.match(/filename="([^"]+)"/i) || disposition.match(/filename=([^;]+)/i);
    name = plain ? plain[1].trim() : null;
  }
  const safe = (name || "").replace(UNSAFE_FILENAME_CHARS, "_").replace(/^[.\s]+/, "").trim();
  return safe || fallback;
}

/** Mirrors the backend's `_slugify` (export_service.py) for the client-side filename fallback. */
export function slugify(value, fallback) {
  if (!value) return fallback;
  const slug = value
    .replace(/[^\p{L}\p{N}_\s-]/gu, "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, "_");
  return slug || fallback;
}

/**
 * The export formats offered per artifact type, Word/Excel first -- the
 * first is what a non-technical user should reach for, and the backend's
 * default. The interchange formats (.qdc, .csv, .json, .md) follow for
 * researchers moving data into R, SPSS or another QDA package; see
 * `backend/app/services/export_service.py`'s module docstring. The
 * backend's `format` query patterns enforce the same lists, so adding a
 * format here without adding it there 422s.
 *
 * Coding's Word/Excel exports carry every view (the Excel workbook holds
 * quotes, matrix, codebook and counts as sheets), so only its CSV/JSON
 * options send a `layout` -- the backend rejects one on xlsx/docx.
 */
export function getExportOptions(artifactType) {
  if (artifactType === "codebook") {
    return [
      { label: LABELS.docx, target: "codebook", format: "docx" },
      { label: LABELS.xlsx, target: "codebook", format: "xlsx" },
      { label: LABELS.qdc, target: "codebook", format: "qdc" },
      { label: LABELS.csv, target: "codebook", format: "csv" },
    ];
  }
  if (artifactType === "coding") {
    return [
      { label: LABELS.xlsx, target: "coding", format: "xlsx" },
      { label: LABELS.docx, target: "coding", format: "docx" },
      { label: LABELS.csvLong, target: "coding", format: "csv", extraParams: { layout: "long" } },
      { label: LABELS.csvWide, target: "coding", format: "csv", extraParams: { layout: "wide" } },
      { label: LABELS.json, target: "coding", format: "json", extraParams: { layout: "long" } },
    ];
  }
  // `summary` is a code-frequency table computed from a coding
  // (`export_service.export_summary`); `document` is a saved summary or
  // comparison, whose stored markdown Word renders
  // (`export_service.export_document`).
  if (artifactType === "summary") {
    return [
      { label: LABELS.docx, target: "summary", format: "docx" },
      { label: LABELS.xlsx, target: "summary", format: "xlsx" },
      { label: LABELS.md, target: "summary", format: "md" },
    ];
  }
  if (artifactType === "document") {
    return [
      { label: LABELS.docx, target: "document", format: "docx" },
      { label: LABELS.md, target: "document", format: "md" },
    ];
  }
  if (artifactType === "memos") {
    return [
      { label: LABELS.docx, target: "memos", format: "docx" },
      { label: LABELS.xlsx, target: "memos", format: "xlsx" },
      { label: LABELS.md, target: "memos", format: "md" },
      { label: LABELS.csv, target: "memos", format: "csv" },
    ];
  }
  return [
    { label: LABELS.csv, target: artifactType, format: "csv" },
    { label: LABELS.json, target: artifactType, format: "json" },
  ];
}
