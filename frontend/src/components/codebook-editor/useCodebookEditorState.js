import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  acceptAll,
  acceptProposal,
  addProposals,
  buildAssistRunsForSubmit,
  copySourceCode,
  counts,
  deserializeDraft,
  dismissAll,
  dismissProposal,
  emptyState,
  existingCodeRefs,
  isAiAccepted,
  seedDraftFromTree,
  serializeDraft,
  setDraft,
} from "../../lib/codebookEditorState";

function readDraft(storageKey) {
  if (!storageKey) return emptyState();
  try {
    return deserializeDraft(window.localStorage.getItem(storageKey));
  } catch {
    // Private mode / disabled storage: work in memory instead of failing.
    return emptyState();
  }
}

function writeDraft(storageKey, state) {
  if (!storageKey) return;
  try {
    window.localStorage.setItem(storageKey, serializeDraft(state));
  } catch {
    // Quota or disabled storage -- the draft just isn't durable.
  }
}

/**
 * Stateful wrapper over `lib/codebookEditorState.js`, persisting the draft
 * to `localStorage` under one caller-supplied `storageKey`.
 *
 * Parameterized on the key itself, not on `(sourceDatabase,
 * targetCodebook)`, because the integrate editor keys its draft on a
 * different, unordered thing -- a SET of source codebooks -- and the
 * hook's own job (read/write/clear/hydrate-on-change) doesn't care what
 * the key means, only that it changed.
 *
 * Persisted rather than held in memory: writing a codebook is a long
 * session, and a multi-minute AI pass may run in the middle of it, so
 * losing it to a refresh would make the screen unusable.
 *
 * **Writes happen in the mutators, not in an effect.** A persist effect
 * on `[state]` races its own hydration: the load effect's `setState`
 * doesn't reach the persist effect until the next render, so it fires
 * once with the stale EMPTY state and overwrites the draft just read
 * back -- a refresh silently discards the user's work. Writing where
 * the change actually happens has no such ordering hazard.
 */
export function useCodebookEditorState(storageKey) {
  const [state, setState] = useState(() => readDraft(storageKey));
  const stateRef = useRef(state);
  stateRef.current = state;
  // `useState`'s initializer only runs on mount, so a later change of key
  // still needs an explicit re-hydration.
  const hydratedFor = useRef(storageKey);

  useEffect(() => {
    if (hydratedFor.current === storageKey) return;
    hydratedFor.current = storageKey;
    setState(readDraft(storageKey));
  }, [storageKey]);

  /** Apply a pure transform, then persist the result. */
  const commit = useCallback(
    (transform) => {
      const next = transform(stateRef.current);
      stateRef.current = next;
      setState(next);
      writeDraft(storageKey, next);
      return next;
    },
    [storageKey],
  );

  const clearDraft = useCallback(() => {
    const next = emptyState();
    stateRef.current = next;
    setState(next);
    if (!storageKey) return;
    try {
      window.localStorage.removeItem(storageKey);
    } catch {
      // Nothing to clean up if storage is unavailable.
    }
  }, [storageKey]);

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
    (proposals, jobId) => {
      let added = 0;
      let skipped = 0;
      commit((prev) => {
        const outcome = addProposals(prev, proposals, jobId);
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
  /** The integrate editor's "rescue" path -- copy a source code the AI
   * tray never proposed a merge for straight into the draft. See
   * `lib/codebookEditorState.js::copySourceCode`. */
  const copyCode = useCallback((sourceCode) => commit((prev) => copySourceCode(prev, sourceCode)), [commit]);

  return {
    draft: state.draft,
    proposals: state.proposals,
    counts: useMemo(() => counts(state), [state]),
    existingCodes: useMemo(() => existingCodeRefs(state), [state]),
    isAiAccepted: (codeUid) => isAiAccepted(state, codeUid),
    assistRuns: useMemo(() => buildAssistRunsForSubmit(state), [state]),
    updateDraft,
    seedDraft,
    receiveProposals,
    accept,
    acceptEvery,
    dismiss,
    dismissEvery,
    copyCode,
    clearDraft,
  };
}
