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

export function buildProjectBundlePath(projectId) {
  return `/api/export/projects/${projectId}/bundle`;
}

/** Mirrors the backend's `_slugify` (export_service.py) for the client-side filename fallback. */
export function slugify(value, fallback) {
  if (!value) return fallback;
  const slug = value
    .replace(/[^\w\s-]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, "_");
  return slug || fallback;
}

/**
 * The export formats offered per artifact type, best first -- two for
 * most artifacts, three for `coding`, one for `summary`/`document`.
 *
 * Deliberately not a uniform CSV/JSON pair -- each artifact gets the
 * format that best preserves it plus the one that best travels; see
 * `backend/app/services/export_service.py`'s module docstring. The
 * backend's `format` query patterns enforce the same pairs, so adding a
 * format here without adding it there 422s.
 *
 * Labels are the bare extension: the dropdown is already headed "Export
 * Format" under an "Export" button sitting on the artifact, so repeating
 * the artifact's name in every row said nothing the user couldn't see.
 * The one exception is a short parenthetical when two options share an
 * extension (coding's long vs. matrix CSV).
 */
export function getExportOptions(artifactType) {
  // .qdc is the REFI-QDA Codebook standard -- the only one of these
  // formats another QDA package (NVivo, ATLAS.ti, MAXQDA) imports as a
  // codebook rather than as an undifferentiated table, so it leads.
  if (artifactType === "codebook") {
    return [
      { label: ".qdc", target: "codebook", format: "qdc" },
      { label: ".csv", target: "codebook", format: "csv" },
    ];
  }
  // Coding also offers the wide matrix -- one row per item (uncoded rows
  // included), one 0/1 column per code -- the shape SPSS/R/Excel analyses
  // want. Long is one row per coded segment.
  if (artifactType === "coding") {
    return [
      { label: ".csv", target: "coding", format: "csv", extraParams: { layout: "long" } },
      { label: ".csv (matrix)", target: "coding", format: "csv", extraParams: { layout: "wide" } },
      { label: ".json", target: "coding", format: "json", extraParams: { layout: "long" } },
    ];
  }
  // Single-option exports download directly from the trigger:
  // `summary` is a code-frequency table computed from a coding (a finished
  // reading, not source data -- see `export_service.export_summary`), and
  // `document` is a saved summary or comparison, exported as its stored
  // markdown (`export_service.export_document`).
  if (artifactType === "summary") {
    return [{ label: ".md", target: "summary", format: "md" }];
  }
  if (artifactType === "document") {
    return [{ label: ".md", target: "document", format: "md" }];
  }
  if (artifactType === "memos") {
    return [
      { label: ".md", target: "memos", format: "md" },
      { label: ".csv", target: "memos", format: "csv" },
    ];
  }
  return [
    { label: ".csv", target: artifactType, format: "csv" },
    { label: ".json", target: artifactType, format: "json" },
  ];
}
