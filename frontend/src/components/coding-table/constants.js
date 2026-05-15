export const TABLE_COLUMN_STORAGE_KEY = "viewCoding.tableColumnVisibility.v2";
export const TABLE_COLUMN_WIDTH_STORAGE_KEY = "viewCoding.tableColumnWidths.v1";

export const TABLE_COLUMNS = [
  { id: "postId", label: "Post ID" },
  { id: "title", label: "Title" },
  { id: "content", label: "Content" },
  { id: "codesApplied", label: "Codes Applied" },
];

export const COLUMN_WIDTHS_DEFAULT = {
  postId: 220,
  title: 220,
  content: 520,
  codesApplied: 240,
};

export const COLUMN_WIDTHS_MIN = {
  postId: 100,
  title: 100,
  content: 100,
  codesApplied: 100,
};

export const COLUMN_WIDTHS_MAX = {
  postId: 420,
  title: 520,
  content: 760,
  codesApplied: 420,
};

export const DEFAULT_COLUMN_VISIBILITY = {
  postId: false,
  title: true,
  content: true,
  codesApplied: true,
};

export function clampColumnWidth(columnId, width) {
  const min = COLUMN_WIDTHS_MIN[columnId] ?? 120;
  const max = COLUMN_WIDTHS_MAX[columnId] ?? 1200;
  const numeric = Number(width);
  if (!Number.isFinite(numeric)) return COLUMN_WIDTHS_DEFAULT[columnId] ?? min;
  return Math.min(max, Math.max(min, numeric));
}
