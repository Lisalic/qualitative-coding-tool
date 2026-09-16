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

export function getExportOptions(artifactType) {
  if (artifactType === "codebook") {
    return [{ label: "Codebook (.csv)", target: "codebook", format: "csv" }];
  }
  if (artifactType === "coding") {
    return [
      { label: "Coding Segments, long (.csv)", target: "coding", format: "csv", extraParams: { layout: "long" } },
    ];
  }
  if (artifactType === "summary") {
    return [
      { label: "Summary (.csv)", target: "summary", format: "csv" },
      { label: "Summary (.json)", target: "summary", format: "json" },
    ];
  }
  if (artifactType === "memos") {
    return [
      { label: "Memos (.csv)", target: "memos", format: "csv" },
      { label: "Memos (.json)", target: "memos", format: "json" },
    ];
  }
  return [
    { label: "CSV (.csv)", target: artifactType, format: "csv" },
    { label: "JSON (.json)", target: artifactType, format: "json" },
  ];
}
