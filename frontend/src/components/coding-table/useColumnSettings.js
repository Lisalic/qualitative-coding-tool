import { useCallback, useMemo, useState } from "react";
import {
  clampColumnWidth,
  COLUMN_WIDTHS_DEFAULT,
  COLUMN_WIDTHS_MAX,
  COLUMN_WIDTHS_MIN,
  DEFAULT_COLUMN_VISIBILITY,
  TABLE_COLUMNS,
  TABLE_COLUMN_STORAGE_KEY,
  TABLE_COLUMN_WIDTH_STORAGE_KEY,
} from "./constants";

function normalizeColumnWidths(raw) {
  const next = { ...COLUMN_WIDTHS_DEFAULT };
  if (!raw || typeof raw !== "object") return next;
  const allowed = new Set(TABLE_COLUMNS.map((c) => c.id));
  for (const [key, value] of Object.entries(raw)) {
    if (!allowed.has(key)) continue;
    next[key] = clampColumnWidth(key, value);
  }
  return next;
}

function readStoredColumnWidths() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(TABLE_COLUMN_WIDTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return normalizeColumnWidths(parsed);
  } catch {
    return null;
  }
}

function readStoredColumnVisibility() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(TABLE_COLUMN_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const allowed = new Set(TABLE_COLUMNS.map((c) => c.id));
    const next = { ...DEFAULT_COLUMN_VISIBILITY };
    for (const [key, val] of Object.entries(parsed)) {
      if (allowed.has(key) && typeof val === "boolean") next[key] = val;
    }
    return next;
  } catch {
    return null;
  }
}

function normalizeColumnVisibility(raw) {
  const merged = {
    ...DEFAULT_COLUMN_VISIBILITY,
    ...(raw && typeof raw === "object" ? raw : {}),
  };
  const visibleCount = TABLE_COLUMNS.filter((c) => merged[c.id]).length;
  if (visibleCount === 0) return { ...DEFAULT_COLUMN_VISIBILITY };
  return merged;
}

export default function useColumnSettings() {
  const [columnVisibility, setColumnVisibility] = useState(() =>
    normalizeColumnVisibility(readStoredColumnVisibility() || {}),
  );
  const [columnWidths, setColumnWidths] = useState(() =>
    normalizeColumnWidths(readStoredColumnWidths()),
  );

  const visibleColumns = useMemo(
    () => TABLE_COLUMNS.filter((c) => columnVisibility[c.id]),
    [columnVisibility],
  );
  const visibleColumnCount = visibleColumns.length;

  const setColumnVisibilityAndPersist = useCallback((updater) => {
    setColumnVisibility((prev) => {
      const next =
        typeof updater === "function" ? updater(prev) : { ...prev, ...updater };
      const count = TABLE_COLUMNS.filter((c) => next[c.id]).length;
      if (count === 0) return prev;
      try {
        localStorage.setItem(TABLE_COLUMN_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore quota / private mode
      }
      return next;
    });
  }, []);

  const toggleColumnVisibility = useCallback(
    (columnId) => {
      setColumnVisibilityAndPersist((prev) => ({
        ...prev,
        [columnId]: !prev[columnId],
      }));
    },
    [setColumnVisibilityAndPersist],
  );

  const setColumnWidthsAndPersist = useCallback((updater) => {
    setColumnWidths((prev) => {
      const nextCandidate =
        typeof updater === "function" ? updater(prev) : { ...prev, ...updater };
      const next = normalizeColumnWidths(nextCandidate);
      try {
        localStorage.setItem(TABLE_COLUMN_WIDTH_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore quota / private mode
      }
      return next;
    });
  }, []);

  const getColumnCellStyle = useCallback(
    (columnId) => {
      const width = clampColumnWidth(columnId, columnWidths[columnId]);
      return {
        width: `${width}px`,
        minWidth: `${COLUMN_WIDTHS_MIN[columnId]}px`,
        maxWidth: `${COLUMN_WIDTHS_MAX[columnId]}px`,
        verticalAlign: "top",
        overflow: "hidden",
      };
    },
    [columnWidths],
  );

  return {
    columnVisibility,
    columnWidths,
    setColumnWidths,
    setColumnWidthsAndPersist,
    visibleColumns,
    visibleColumnCount,
    toggleColumnVisibility,
    getColumnCellStyle,
  };
}
