import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, requestJson } from "../../api";
import { keyFor } from "../../lib/filterEditorState";
import { isProjectSchema } from "../../lib/schemaGuards";

/**
 * Every memo on one database, fetched once and indexed by `"<type>:<id>"`.
 *
 * One request per database rather than one per visible row: only rows a
 * researcher actually wrote about have a memo at all, so the whole set is
 * small even for a database with 100k submissions (see
 * `backend/app/repositories/memo_repo.py::list_memos`). That is what lets
 * the table render a memo indicator on every row without an N+1.
 *
 * Shared by the data viewer and the filter editor -- both show the same
 * rows and both open the same `EntryModal`, so a memo written in one is
 * immediately visible in the other.
 */
export function useRowMemos(database) {
  const [memos, setMemos] = useState(() => new Map());
  const [error, setError] = useState("");
  // Only the newest load may fill the index: switching database while the
  // previous one's memos are still loading used to show them under the new
  // database (and star/memo writes then targeted the wrong rows).
  const latestLoad = useRef(0);
  const databaseRef = useRef(database);
  databaseRef.current = database;

  const load = useCallback(async () => {
    const requestId = ++latestLoad.current;
    if (!database || !isProjectSchema(database)) {
      setMemos(new Map());
      return;
    }
    try {
      const response = await apiFetch(
        `/api/memos/?schema=${encodeURIComponent(String(database))}`,
      );
      if (!response.ok) throw new Error("Failed to load memos");
      const data = await response.json();
      if (requestId !== latestLoad.current) return;
      const next = new Map();
      for (const memo of data.memos || []) {
        next.set(keyFor(memo.row_type, memo.row_id), memo);
      }
      setMemos(next);
      setError("");
    } catch (err) {
      if (requestId !== latestLoad.current) return;
      // A memo is an annotation on top of the data -- failing to load one
      // must never blank out the rows themselves.
      setError(err?.message || "Failed to load memos");
      setMemos(new Map());
    }
  }, [database]);

  useEffect(() => {
    load();
  }, [load]);

  const getMemo = useCallback(
    (rowType, id) => memos.get(keyFor(rowType, id)) || null,
    [memos],
  );

  /**
   * Save (or, with a blank body, clear) one row's memo.
   *
   * Updates the local index from the server's response rather than
   * re-fetching the whole set, and returns `{ ok, error }` so the caller
   * can show a failure inline instead of silently dropping the edit.
   */
  const saveMemo = useCallback(
    async (rowType, rowId, body) => {
      if (!database) return { ok: false, error: "No database selected" };
      const { ok, data, error: err } = await requestJson("/api/memos/", {
        method: "PUT",
        body: { schema: String(database), row_type: rowType, row_id: rowId, body },
      });
      if (!ok) return { ok: false, error: err || "Failed to save memo" };
      // The database changed while the save was in flight: the memo was
      // saved, but it belongs to the previous index, not the current one.
      if (database !== databaseRef.current) return { ok: true };

      setMemos((prev) => {
        const next = new Map(prev);
        const key = keyFor(rowType, rowId);
        if (data?.memo) next.set(key, data.memo);
        else next.delete(key);
        return next;
      });
      return { ok: true };
    },
    [database],
  );

  return { memos, getMemo, saveMemo, reloadMemos: load, memoError: error };
}
