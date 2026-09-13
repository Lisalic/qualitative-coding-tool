/**
 * Helpers for export url construction and artifact format options.
 */

export function buildExportPath(fileId, targetType, format, versionNo = null) {
  const params = new URLSearchParams();
  params.set("format", format);
  if (versionNo) {
    params.set("version_no", String(versionNo));
  }
  return `/api/export/${fileId}/${targetType}?${params.toString()}`;
}

export function getExportOptions(artifactType) {
  if (artifactType === "codebook") {
    return [
      { label: "Codebook (.csv)", target: "codebook", format: "csv" },
      { label: "Codebook (.json)", target: "codebook", format: "json" },
    ];
  }
  if (artifactType === "coding") {
    return [
      { label: "Coding Entries (.csv)", target: "coding", format: "csv" },
      { label: "Coding Entries (.json)", target: "coding", format: "json" },
      { label: "Row Memos (.csv)", target: "memos", format: "csv" },
      { label: "Row Memos (.json)", target: "memos", format: "json" },
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
