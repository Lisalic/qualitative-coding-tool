import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  acceptAll,
  acceptProposal,
  addProposals,
  counts,
  deserializeDraft,
  dismissAll,
  dismissProposal,
  draftStorageKey,
  emptyState,
  existingCodeRefs,
  isAiAccepted,
  seedDraftFromTree,
  serializeDraft,
  setDraft,
} from "../../lib/codebookEditorState";

function readDraft(sourceDatabase, targetCodebook) {
  if (!sourceDatabase) return emptyState();
  try {
    return deserializeDraft(
      window.localStorage.getItem(draftStorageKey(sourceDatabase, targetCodebook)),
    );
  } catch {
    // Private mode / disabled storage: work in memory instead of failing.
    return emptyState();
  }
}

function writeDraft(sourceDatabase, targetCodebook, state) {
  if (!sourceDatabase) return;
  try {
    window.localStorage.setItem(
      draftStorageKey(sourceDatabase, targetCodebook),
      serializeDraft(state),
    );
  } catch {
    // Quota or disabled storage -- the draft just isn't durable.
  }
}

/**
 * Stateful wrapper over `lib/codebookEditorState.js`, persisting the draft
 * to `localStorage` under the (source data, target codebook) pair.
 *
 * Persisted rather than held in memory for the same reason the filter
 * editor's draft is: writing a codebook is a long session spent reading
 * the corpus, and a multi-minute AI pass may run in the middle of it.
 * Losing that to a refresh would make the screen unusable, and the
 * alternative -- a server-side draft artifact -- is a table, routes and a
 * cleanup policy for state that only ever matters to one browser.
 *
 * **Writes happen in the mutators, not in an effect.** A persist effect on
 * `[state]` races its own hydration: the load effect's `setState` doesn't
 * reach the persist effect until the next render, so that effect fires
 * once with the stale EMPTY state and overwrites the very draft that was
 * just read back -- a refresh silently discards the user's work. Writing
 * where the change actually happens has no such ordering hazard, and
 * hydration never writes at all. (See `useFilterEditorState`, which
 * learned this the same way.)
 */
export function useCodebookEditorState(sourceDatabase, targetCodebook = "") {
  const [state, setState] = useState(() => readDraft(sourceDatabase, targetCodebook));
  const stateRef = useRef(state);
  stateRef.current = state;
  // `useState`'s initializer only runs on mount, so a later change of
  // source or target still needs an explicit re-hydration.
  const hydratedFor = useRef(draftStorageKey(sourceDatabase, targetCodebook));

  useEffect(() => {
    const key = draftStorageKey(sourceDatabase, targetCodebook);
    if (hydratedFor.current === key) return;
    hydratedFor.current = key;
    setState(readDraft(sourceDatabase, targetCodebook));
  }, [sourceDatabase, targetCodebook]);

  /** Apply a pure transform, then persist the result. */
  const commit = useCallback(
    (transform) => {
      const next = transform(stateRef.current);
      stateRef.current = next;
      setState(next);
      writeDraft(sourceDatabase, targetCodebook, next);
      return next;
    },
    [sourceDatabase, targetCodebook],
  );

  const clearDraft = useCallback(() => {
    const next = emptyState();
    stateRef.current = next;
    setState(next);
    if (!sourceDatabase) return;
    try {
      window.localStorage.removeItem(draftStorageKey(sourceDatabase, targetCodebook));
    } catch {
      // Nothing to clean up if storage is unavailable.
    }
  }, [sourceDatabase, targetCodebook]);

  const updateDraft = useCallback((tree) => commit((prev) => setDraft(prev, tree)), [commit]);

  /**
   * Load an existing codebook's codes as the starting draft (Refine mode).
   *
   * Deliberately NOT routed through `commit`: seeding is hydration, not an
   * edit, and persisting it would write a copy of the server's own state
   * over whatever unsaved draft the researcher already had for this
   * codebook. It writes only once the researcher actually changes
   * something.
   */
  const seedDraft = useCallback((tree) => {
    const next = seedDraftFromTree(stateRef.current, tree);
    stateRef.current = next;
    setState(next);
  }, []);

  /**
   * Fold a preview run's proposals into the review tray, returning what
   * actually arrived so the panel can report it -- the whole feedback
   * signal for a run that may have taken minutes.
   */
  const receiveProposals = useCallback(
    (proposals) => {
      let added = 0;
      let skipped = 0;
      commit((prev) => {
        const outcome = addProposals(prev, proposals);
        added = outcome.addedCount;
        skipped = outcome.skippedCount;
        return outcome.state;
      });
      return { added, skipped };
    },
    [commit],
  );

  const accept = useCallback((key) => commit((prev) => acceptProposal(prev, key)), [commit]);
  const acceptEvery = useCallback(() => commit((prev) => acceptAll(prev)), [commit]);
  const dismiss = useCallback((key) => commit((prev) => dismissProposal(prev, key)), [commit]);
  const dismissEvery = useCallback(() => commit((prev) => dismissAll(prev)), [commit]);

  return {
    draft: state.draft,
    proposals: state.proposals,
    counts: useMemo(() => counts(state), [state]),
    existingCodes: useMemo(() => existingCodeRefs(state), [state]),
    isAiAccepted: (codeUid) => isAiAccepted(state, codeUid),
    updateDraft,
    seedDraft,
    receiveProposals,
    accept,
    acceptEvery,
    dismiss,
    dismissEvery,
    clearDraft,
  };
}
