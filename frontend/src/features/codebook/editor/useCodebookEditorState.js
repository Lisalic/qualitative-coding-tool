import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  acceptAll,
  acceptProposal,
  addProposals,
  buildAssistRunsForSubmit,
  clearAssistRuns,
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
} from "./codebookEditorState";

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

// Every keystroke in a code's name or definition commits a new state;
// serializing and writing the whole draft synchronously on each one made
// large codebooks lag. Writes are coalesced and flushed shortly after the
// last change (and on unmount/key change/page hide, so nothing is lost).
const WRITE_DEBOUNCE_MS = 250;

/**
 * Stateful wrapper over `features/codebook/editor/codebookEditorState.js`, persisting the draft
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

  // Pending (debounced) write: which key it belongs to and the timer.
  const pendingWrite = useRef({ key: null, timer: null });

  const flushWrite = useCallback(() => {
    const pending = pendingWrite.current;
    if (pending.timer == null) return;
    clearTimeout(pending.timer);
    pending.timer = null;
    const key = pending.key;
    pending.key = null;
    if (key) writeDraft(key, stateRef.current);
  }, []);

  const scheduleWrite = useCallback(
    (key) => {
      if (!key) return;
      const pending = pendingWrite.current;
      // A different key's write is still pending: land it first so its
      // draft isn't lost to the new key's timer.
      if (pending.key && pending.key !== key) flushWrite();
      if (pending.timer != null) clearTimeout(pending.timer);
      pending.key = key;
      pending.timer = setTimeout(flushWrite, WRITE_DEBOUNCE_MS);
    },
    [flushWrite],
  );

  useEffect(() => {
    const onPageHide = () => flushWrite();
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      flushWrite();
    };
  }, [flushWrite]);

  useEffect(() => {
    if (hydratedFor.current === storageKey) return;
    // Land the previous key's pending draft before reading the new one.
    flushWrite();
    hydratedFor.current = storageKey;
    setState(readDraft(storageKey));
  }, [flushWrite, storageKey]);

  /** Apply a pure transform, then persist the result. */
  const commit = useCallback(
    (transform) => {
      const next = transform(stateRef.current);
      stateRef.current = next;
      setState(next);
      scheduleWrite(storageKey);
      return next;
    },
    [scheduleWrite, storageKey],
  );

  const clearDraft = useCallback(() => {
    const next = emptyState();
    stateRef.current = next;
    setState(next);
    // A write still queued for this draft must not resurrect it.
    const pending = pendingWrite.current;
    if (pending.timer != null) clearTimeout(pending.timer);
    pending.timer = null;
    pending.key = null;
    if (!storageKey) return;
    try {
      window.localStorage.removeItem(storageKey);
    } catch {
      // Nothing to clean up if storage is unavailable.
    }
  }, [storageKey]);

  const snapshot = useCallback(() => stateRef.current, []);
  const clearDraftIfUnchanged = useCallback((savedState) => {
    if (stateRef.current !== savedState) return false;
    clearDraft();
    return true;
  }, [clearDraft]);

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
   * `features/codebook/editor/codebookEditorState.js::copySourceCode`. */
  const copyCode = useCallback((sourceCode) => commit((prev) => copySourceCode(prev, sourceCode)), [commit]);
  /** After a save has recorded this session's assist runs -- see
   * `features/codebook/editor/codebookEditorState.js::clearAssistRuns`. */
  const markAssistRunsRecorded = useCallback(() => commit((prev) => clearAssistRuns(prev)), [commit]);

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
    markAssistRunsRecorded,
    clearDraft,
    snapshot,
    clearDraftIfUnchanged,
  };
}
