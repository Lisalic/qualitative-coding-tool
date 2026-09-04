import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  applyAiResult,
  counts,
  decidedIds,
  deserializeDraft,
  draftStorageKey,
  emptySelection,
  includedIds,
  isAiAdded,
  serializeDraft,
  stateOf,
  toggleAll,
  toggleExclude,
  toggleInclude,
} from "../../lib/filterEditorState";

function readDraft(sourceDatabase) {
  if (!sourceDatabase) return emptySelection();
  try {
    return deserializeDraft(window.localStorage.getItem(draftStorageKey(sourceDatabase)));
  } catch {
    // Private mode / disabled storage: work in memory instead of failing.
    return emptySelection();
  }
}

function writeDraft(sourceDatabase, selection) {
  if (!sourceDatabase) return;
  try {
    window.localStorage.setItem(draftStorageKey(sourceDatabase), serializeDraft(selection));
  } catch {
    // Quota or disabled storage -- the draft just isn't durable.
  }
}

/**
 * Stateful wrapper over `lib/filterEditorState.js`, persisting the draft
 * to `localStorage` under the source database.
 *
 * Persisted rather than held in memory because the editor is a long
 * session: the user pages through hundreds of rows and may run a
 * multi-minute AI pass in the middle of it. Losing all of that to a
 * refresh or a stray back-navigation would make the screen unusable, and
 * the alternative -- a server-side draft artifact -- is a table, routes
 * and a cleanup policy for state that only ever matters to one browser.
 *
 * Keyed per source database so drafts for different databases don't
 * collide, and cleared on a successful submit so the next filter of the
 * same source starts blank rather than inheriting the set that was just
 * turned into an artifact.
 *
 * **Writes happen in the mutators, not in an effect.** A persist effect
 * on `[selection]` races its own hydration: the load effect's
 * `setSelection` doesn't reach the persist effect until the next render,
 * so that effect fires once with the stale EMPTY selection and overwrites
 * the very draft that was just read back -- a refresh silently discards
 * the user's work. Writing where the change actually happens has no such
 * ordering hazard, and hydration never writes at all.
 */
export function useFilterEditorState(sourceDatabase) {
  const [selection, setSelection] = useState(() => readDraft(sourceDatabase));
  const selectionRef = useRef(selection);
  selectionRef.current = selection;
  // `useState`'s initializer only runs on mount, so a later change of
  // source database still needs an explicit re-hydration.
  const hydratedFor = useRef(sourceDatabase);

  useEffect(() => {
    if (hydratedFor.current === sourceDatabase) return;
    hydratedFor.current = sourceDatabase;
    setSelection(readDraft(sourceDatabase));
  }, [sourceDatabase]);

  /** Apply a pure transform, then persist the result. */
  const commit = useCallback(
    (transform) => {
      const next = transform(selectionRef.current);
      selectionRef.current = next;
      setSelection(next);
      writeDraft(sourceDatabase, next);
      return next;
    },
    [sourceDatabase],
  );

  const clearDraft = useCallback(() => {
    const next = emptySelection();
    selectionRef.current = next;
    setSelection(next);
    if (!sourceDatabase) return;
    try {
      window.localStorage.removeItem(draftStorageKey(sourceDatabase));
    } catch {
      // Nothing to clean up if storage is unavailable.
    }
  }, [sourceDatabase]);

  const include = useCallback(
    (rowType, id) => commit((prev) => toggleInclude(prev, rowType, id)),
    [commit],
  );
  const exclude = useCallback(
    (rowType, id) => commit((prev) => toggleExclude(prev, rowType, id)),
    [commit],
  );
  const includeAll = useCallback(
    (rowType, ids) => commit((prev) => toggleAll(prev, rowType, ids)),
    [commit],
  );

  /**
   * Fold an AI preview run's ids in, returning how many rows it actually
   * added so the panel can report "12 rows added by AI" -- the whole
   * feedback signal for a run that may have taken minutes.
   */
  const acceptAiSuggestions = useCallback(
    (result) => {
      let added = 0;
      commit((prev) => {
        const outcome = applyAiResult(prev, result);
        added = outcome.addedCount;
        return outcome.selection;
      });
      return added;
    },
    [commit],
  );

  return {
    selection,
    stateOf: (rowType, id) => stateOf(selection, rowType, id),
    isAiAdded: (rowType, id) => isAiAdded(selection, rowType, id),
    counts: useMemo(() => counts(selection), [selection]),
    decided: useMemo(() => decidedIds(selection), [selection]),
    included: useMemo(() => includedIds(selection), [selection]),
    include,
    exclude,
    includeAll,
    acceptAiSuggestions,
    clearDraft,
  };
}
