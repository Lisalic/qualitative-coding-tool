import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api";
import { PROJ_SCHEMA_RE } from "../../lib/schemaGuards";

/** Stable identity for a submission/comment row across the whole app. */
export function rowKey(row) {
  return `${row.rowType}:${row.id}`;
}

/**
 * Paged submissions+comments for one source database, shared by the
 * filter and codebook editors -- `FilterEditor.jsx` and
 * `CodebookEditor.jsx` used to each carry an identical ~60-line copy of
 * this (fetch, the `proj_` schema guard, the submissions+comments merge,
 * `totalRows`/`hasNextPage`, and the default-`activeKey` effect).
 *
 * Load failures land in their own `loadError`, separate from whatever a
 * caller's own submit path reports -- paging or switching databases used
 * to call `setError("")` on the ONE shared slot both used, silently
 * wiping a submit error the user hadn't read yet.
 *
 * The active-row default is written with a functional `setActiveKey`
 * update rather than reading `activeKey` from the closure, so the effect
 * needs no `eslint-disable react-hooks/exhaustive-deps` to stay correct.
 */
export function useEditorRows(database) {
  const [entries, setEntries] = useState(null);
  const [page, setPage] = useState(0);
  const [limit, setLimitState] = useState(25);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [activeKey, setActiveKey] = useState(null);

  useEffect(() => {
    setPage(0);
    setActiveKey(null);
  }, [database]);

  const setLimit = useCallback((next) => {
    setLimitState(next);
    setPage(0);
  }, []);

  const fetchEntries = useCallback(async () => {
    if (!database || !PROJ_SCHEMA_RE.test(String(database))) {
      setEntries(null);
      return;
    }
    setLoading(true);
    setLoadError("");
    try {
      const response = await apiFetch(
        `/api/file-entries/?limit=${limit}&offset=${page * limit}&schema=${encodeURIComponent(
          String(database),
        )}`,
      );
      if (!response.ok) throw new Error("Failed to load rows");
      setEntries(await response.json());
    } catch (err) {
      setLoadError(err?.message || "Failed to load rows");
      setEntries(null);
    } finally {
      setLoading(false);
    }
  }, [database, limit, page]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const rows = useMemo(() => {
    const submissions = (entries?.submissions || []).map((row) => ({ ...row, rowType: "submission" }));
    const comments = (entries?.comments || []).map((row) => ({ ...row, rowType: "comment" }));
    return [...submissions, ...comments];
  }, [entries]);

  const totalRows = (entries?.total_submissions || 0) + (entries?.total_comments || 0);
  const hasNextPage =
    (entries?.total_submissions || 0) > (page + 1) * limit ||
    (entries?.total_comments || 0) > (page + 1) * limit;

  // Default to the first row on the page once it loads, so the reader
  // pane is never empty when there's something to read.
  useEffect(() => {
    if (rows.length === 0) {
      setActiveKey(null);
      return;
    }
    setActiveKey((prev) => (prev && rows.some((r) => rowKey(r) === prev) ? prev : rowKey(rows[0])));
  }, [rows]);

  const activeRow = useMemo(() => rows.find((r) => rowKey(r) === activeKey) || null, [rows, activeKey]);

  return {
    rows,
    totalRows,
    hasNextPage,
    loading,
    loadError,
    page,
    setPage,
    limit,
    setLimit,
    activeKey,
    setActiveKey,
    activeRow,
  };
}
