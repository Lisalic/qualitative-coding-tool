import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  applyAiResult,
  buildAssistRunsForSubmit,
  counts,
  decidedIds,
  deserializeDraft,
  draftStorageKey,
  emptySelection,
  excludedIds,
  includedIds,
  isAiDecided,
  serializeDraft,
  stateOf,
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
 * to `localStorage` under the source database (same persist-in-mutators
 * rationale as `useCodebookEditorState`, which this predates).
 *
 * Keyed per source database so drafts for different databases don't
 * collide, and cleared on a successful submit so the next filter of the
 * same source starts blank rather than inheriting the set that was just
 * turned into an artifact.
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

  const snapshot = useCallback(() => selectionRef.current, []);
  const clearDraftIfUnchanged = useCallback((savedSelection) => {
    if (selectionRef.current !== savedSelection) return false;
    clearDraft();
    return true;
  }, [clearDraft]);

  const include = useCallback(
    (rowType, id) => commit((prev) => toggleInclude(prev, rowType, id)),
    [commit],
  );
  const exclude = useCallback(
    (rowType, id) => commit((prev) => toggleExclude(prev, rowType, id)),
    [commit],
  );
  /**
   * Fold an AI preview run's ids in (both directions), returning how many
   * rows it actually included/excluded so the panel can report
   * "3 included, 2 excluded" -- the whole feedback signal for a run that
   * may have taken minutes.
   */
  const acceptAiSuggestions = useCallback(
    (result) => {
      let includedCount = 0;
      let excludedCount = 0;
      commit((prev) => {
        const outcome = applyAiResult(prev, result);
        includedCount = outcome.includedCount;
        excludedCount = outcome.excludedCount;
        return outcome.selection;
      });
      return { includedCount, excludedCount };
    },
    [commit],
  );

  return {
    selection,
    stateOf: (rowType, id) => stateOf(selection, rowType, id),
    isAiDecided: (rowType, id) => isAiDecided(selection, rowType, id),
    counts: useMemo(() => counts(selection), [selection]),
    decided: useMemo(() => decidedIds(selection), [selection]),
    included: useMemo(() => includedIds(selection), [selection]),
    excluded: useMemo(() => excludedIds(selection), [selection]),
    assistRuns: useMemo(() => buildAssistRunsForSubmit(selection), [selection]),
    include,
    exclude,
    snapshot,
    clearDraftIfUnchanged,
    acceptAiSuggestions,
    clearDraft,
  };
}
