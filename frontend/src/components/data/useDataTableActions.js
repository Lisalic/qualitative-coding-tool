import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../api";
import DialogService from "../feedback/DialogService";
import ToastService from "../feedback/ToastService";

export function useDataTableActions({
  currentDatabase,
  fetchEntries,
  loading,
  setLoading,
  setError,
}) {
  const [selectedRows, setSelectedRows] = useState(new Set());
  const [projects, setProjects] = useState([]);
  const [targetDb, setTargetDb] = useState("");

  useEffect(() => {
    setSelectedRows(new Set());
  }, [currentDatabase]);

  // The move-target list is the same on every database, so it's loaded once
  // per mount (not once per database switch), and never written after
  // unmount.
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const response = await apiFetch("/api/my-files/?file_type=raw_data");
        if (!response.ok || !mounted) return;
        const data = await response.json();
        if (!mounted) return;
        setProjects(data.projects || []);
      } catch {
        // ignore
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!currentDatabase) return;
    setTargetDb((prev) => {
      if (prev && prev !== currentDatabase) return prev;
      const other = projects.find((p) => p.schema_name !== currentDatabase);
      return other ? other.schema_name : "";
    });
  }, [currentDatabase, projects]);

  const keyFor = useCallback((type, id) => `${type}:${id}`, []);

  const isSelected = useCallback(
    (type, id) => selectedRows.has(keyFor(type, id)),
    [selectedRows, keyFor],
  );

  const toggleSelection = useCallback(
    (type, id, event) => {
      if (event?.stopPropagation) event.stopPropagation();
      setSelectedRows((prev) => {
        const next = new Set(prev);
        const key = keyFor(type, id);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      });
    },
    [keyFor],
  );

  const toggleSelectAll = useCallback(
    (type, list) => {
      const keys = (list || []).map((item) => keyFor(type, item.id));
      setSelectedRows((prev) => {
        const next = new Set(prev);
        const allSelected = keys.length > 0 && keys.every((key) => next.has(key));
        if (allSelected) {
          keys.forEach((key) => next.delete(key));
        } else {
          keys.forEach((key) => next.add(key));
        }
        return next;
      });
    },
    [keyFor],
  );

  const deleteSelected = useCallback(async () => {
    if (!currentDatabase || selectedRows.size === 0) return;
    const confirmed = await DialogService.confirm(
      `Delete ${selectedRows.size} selected entries? Earlier versions keep them.`,
      { title: "Delete entries", confirmLabel: "Delete", danger: true },
    );
    if (!confirmed) return;

    // Grouped into at most one request per table, so the backend mints
    // one version for the whole batch rather than one per row (see
    // file_service.delete_rows's docstring).
    const groups = { submission: [], comment: [] };
    for (const key of Array.from(selectedRows)) {
      const [type, ...rest] = String(key).split(":");
      const rowId = rest.join(":");
      if (type === "submission") groups.submission.push(rowId);
      else groups.comment.push(rowId);
    }

    // One request per table: if the second fails, the first group is
    // already gone server-side, so the table is refetched and those rows
    // dropped from the selection either way -- a retry must not resend ids
    // that were already closed.
    const done = new Set();
    try {
      setLoading(true);
      setError("");

      for (const [typeKey, rowIds] of Object.entries(groups)) {
        if (!rowIds.length) continue;
        const table = typeKey === "submission" ? "submissions" : "comments";

        const response = await apiFetch("/api/delete-rows/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            schema_name: currentDatabase,
            table,
            row_ids: rowIds,
          }),
        });

        if (!response.ok) {
          const text = await response.text();
          throw new Error(`Delete failed: ${response.status} ${text}`);
        }

        const data = await response.json();
        if (data.error) throw new Error(data.error);
        rowIds.forEach((rowId) => done.add(keyFor(typeKey, rowId)));
      }
    } catch (error) {
      setError(`Error deleting selected: ${error.message}`);
    } finally {
      setSelectedRows((prev) => new Set(Array.from(prev).filter((key) => !done.has(key))));
      await fetchEntries();
      setLoading(false);
    }
  }, [currentDatabase, fetchEntries, keyFor, selectedRows, setError, setLoading]);

  const moveSelected = useCallback(async () => {
    if (!currentDatabase || !targetDb || selectedRows.size === 0) return;
    if (targetDb === currentDatabase) {
      ToastService.show("Select a different target database", "info");
      return;
    }

    const confirmed = await DialogService.confirm(
      `Move ${selectedRows.size} selected entries to ${targetDb}?`,
      { title: "Move entries", confirmLabel: "Move" },
    );
    if (!confirmed) return;

    const groups = { submission: [], comment: [] };
    for (const key of Array.from(selectedRows)) {
      const [type, ...rest] = key.split(":");
      const rowId = rest.join(":");
      if (type === "submission") groups.submission.push(rowId);
      else groups.comment.push(rowId);
    }

    // Same partial-failure handling as deleteSelected above.
    const done = new Set();
    try {
      setLoading(true);
      setError("");
      for (const [typeKey, rowIds] of Object.entries(groups)) {
        if (!rowIds.length) continue;
        const table = typeKey === "submission" ? "submissions" : "comments";
        const response = await apiFetch("/api/move-rows/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_schema: currentDatabase,
            target_schema: targetDb,
            table,
            row_ids: rowIds,
          }),
        });

        if (!response.ok) {
          const text = await response.text();
          throw new Error(`Move failed: ${response.status} ${text}`);
        }
        rowIds.forEach((rowId) => done.add(keyFor(typeKey, rowId)));
      }
    } catch (error) {
      setError(`Error moving selected: ${error.message}`);
    } finally {
      setSelectedRows((prev) => new Set(Array.from(prev).filter((key) => !done.has(key))));
      await fetchEntries();
      setLoading(false);
    }
  }, [
    currentDatabase,
    fetchEntries,
    keyFor,
    selectedRows,
    setError,
    setLoading,
    targetDb,
  ]);

  return {
    selectedRows,
    setSelectedRows,
    projects,
    targetDb,
    setTargetDb,
    loading,
    keyFor,
    isSelected,
    toggleSelection,
    toggleSelectAll,
    deleteSelected,
    moveSelected,
  };
}
