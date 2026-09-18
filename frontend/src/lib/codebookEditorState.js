/**
 * The codebook editor's draft + proposal state, as pure functions.
 *
 * Two separate things live here, and keeping them separate is the point:
 *
 *   draft     -- the researcher's codebook, a family->codes tree exactly
 *                as `CodeLegend` renders and edits it (see
 *                `lib/codingUtils.js`), so the editor reuses the one code
 *                editor this app has rather than growing a second.
 *   proposals -- codes the AI suggested, held in a review tray and
 *                belonging to nobody until accepted.
 *
 * The filter editor merges an AI result straight into the selection
 * (`filterEditorState.applyAiResult`) because a suggestion there is one
 * bit: include this row. A code is not one bit -- it carries a
 * definition, inclusion and exclusion criteria, keywords and an example,
 * and adopting one is a claim about how the whole corpus will be read. So
 * proposals never touch the draft on their own; `acceptProposal` is the
 * only door between the two. What the two editors DO share is the rule
 * that matters: the assistant may add, never overwrite.
 *
 * Kept here rather than inside the React hook because `frontend/src/lib/**`
 * is the layer the Vitest suite covers (see CLAUDE.md);
 * `useCodebookEditorState` is a thin stateful wrapper over these.
 *
 * `assistRuns`/`acceptedKeyToUid` are the C2 AI-assist provenance channel
 * (closes GAP-4): `addProposals` records which keys a run genuinely added
 * to the tray, `acceptProposal` remembers which `code_uid` an accepted
 * key became, and `buildAssistRunsForSubmit` reduces both into
 * `{job_id, proposed_count, accepted_count, dismissed_count,
 * accepted_refs}` at submit time -- a key never accepted (still in the
 * tray, or explicitly dismissed) counts as dismissed. The server
 * re-derives model/prompts from the job itself
 * (`services/assist_service.py`) rather than trusting this.
 *
 * `copySourceCode` extends this same state machine for the
 * integrate-codebook editor (a third caller, alongside Create Codebook's
 * new/refine modes) rather than forking a second module: the
 * tray-to-draft flow, identity minting, dismissal memory and assist-run
 * bookkeeping are identical, and only what a proposal carries (which
 * source codes it merged) and what a researcher can do outside the tray
 * (copy a source code by hand) differ. A merge proposal's `sources` is
 * display provenance ONLY, shown on the tray card while a merge is
 * pending review -- it never reaches the draft tree (`cloneCodebookTree`
 * would silently drop it as an unknown field anyway) and never reaches
 * the server; the server's own merge-provenance record is
 * `artifact_assists.accepted_refs` pointing at the
 * `integrate_codebook_preview` job that produced it.
 *
 * There used to be a persistent "this source is covered" flag, set once
 * on accept/copy and never cleared. It was removed: once a code is in
 * the draft, the researcher is expected to rename it, merge it further,
 * or delete it outright, and a flag that only ever turns on can't track
 * any of that -- it would keep calling a source "covered" after the code
 * it produced was deleted, which is actively misleading for exactly the
 * editing work this tool exists to support. `copySourceCode` below does
 * a live, un-stored duplicate check instead (see its docstring), which
 * can't go stale because there is nothing to go stale.
 */

import { cloneCodebookTree, mintClientCodeUid } from "./codingUtils";

export const DRAFT_STORAGE_PREFIX = "codebookEditorDraft:";

/** Separator for `codeKey`. A NUL byte rather than ":" or "/" because a
 * family or code name may legitimately contain any printable character,
 * and a collision here would silently merge two distinct codes. */
const KEY_SEP = "\u0000";

/**
 * Normalized `(family, name)` identity for a code.
 *
 * This is what "already covered" means, and it must agree exactly with
 * `codebook_service._code_dedupe_key` server-side -- the backend drops
 * proposals matching the draft it was sent, and this drops the rest on
 * arrival. If the two normalizations disagreed, a code would be filtered
 * by one side and not the other, which reads to the user as the assistant
 * re-proposing something they already accepted.
 */
export function codeKey(familyName, name) {
  const family = String(familyName ?? "").trim().toLowerCase();
  const code = String(name ?? "").trim().toLowerCase();
  return `${family}${KEY_SEP}${code}`;
}

/** The zero state: an empty codebook, nothing proposed. */
export function emptyState() {
  return {
    draft: [], proposals: [], dismissed: new Set(), aiAccepted: new Set(),
    assistRuns: [], acceptedKeyToUid: {},
  };
}

function withState(state, mutate) {
  const next = {
    draft: cloneCodebookTree(state.draft),
    proposals: state.proposals.map((proposal) => ({ ...proposal })),
    dismissed: new Set(state.dismissed),
    aiAccepted: new Set(state.aiAccepted),
    assistRuns: (state.assistRuns || []).map((run) => ({ ...run, proposedKeys: [...run.proposedKeys] })),
    acceptedKeyToUid: { ...(state.acceptedKeyToUid || {}) },
  };
  mutate(next);
  return next;
}

/** Every `code_uid` present in a draft tree. */
function draftCodeUids(draft) {
  const uids = new Set();
  for (const family of Array.isArray(draft) ? draft : []) {
    for (const code of Array.isArray(family?.codes) ? family.codes : []) {
      if (code?.code_uid) uids.add(code.code_uid);
    }
  }
  return uids;
}

/** Every `codeKey` currently in the draft. */
export function draftKeys(draft) {
  const keys = new Set();
  for (const family of Array.isArray(draft) ? draft : []) {
    for (const code of Array.isArray(family?.codes) ? family.codes : []) {
      keys.add(codeKey(family?.family_name, code?.name));
    }
  }
  return keys;
}

/** Replace the draft tree wholesale -- what `CodeLegend`'s edit mode emits. */
export function setDraft(state, nextDraft) {
  return withState(state, (next) => {
    next.draft = cloneCodebookTree(nextDraft);
  });
}

/**
 * Seed the draft from an existing codebook's codes (Refine mode).
 *
 * Identity is carried through untouched -- real `code_uid`/`family_uid`,
 * and deliberately NO `is_new` flag. Marking an existing code as new would
 * make the next save read as "every code deleted, every code added" in the
 * version diff, which is exactly the failure
 * `codebook_service._resolve_code_rows` refuses to let a client cause
 * silently.
 */
export function seedDraftFromTree(state, tree) {
  return withState(state, (next) => {
    next.draft = cloneCodebookTree(tree);
    next.proposals = [];
    next.dismissed = new Set();
    next.aiAccepted = new Set();
    next.assistRuns = [];
    next.acceptedKeyToUid = {};
  });
}

/**
 * Fold one preview run's proposals into the review tray.
 *
 * Additive and non-destructive in both directions: it never writes to the
 * draft, and it drops any proposal already covered by a draft code, an
 * open proposal, or one the researcher dismissed. That last case is what
 * the `excluded` state does for the filter editor -- without it a second
 * run would keep re-offering codes the researcher just said no to.
 *
 * Returns `{ state, addedCount, skippedCount }` so the panel can report
 * what actually arrived rather than the raw size of the model's answer.
 */
export function addProposals(state, incoming = [], jobId = undefined) {
  let addedCount = 0;
  let skippedCount = 0;
  const addedKeys = [];
  const next = withState(state, (draftState) => {
    const seen = draftKeys(draftState.draft);
    for (const proposal of draftState.proposals) seen.add(proposal.key);

    for (const raw of Array.isArray(incoming) ? incoming : []) {
      const name = String(raw?.name ?? "").trim();
      if (!name) continue;
      const familyName = String(raw?.family_name ?? "").trim();
      const key = codeKey(familyName, name);
      if (seen.has(key) || draftState.dismissed.has(key)) {
        skippedCount += 1;
        continue;
      }
      seen.add(key);
      addedCount += 1;
      addedKeys.push(key);
      draftState.proposals.push({
        key,
        family_name: familyName,
        name,
        definition: raw?.definition ?? null,
        inclusion: raw?.inclusion ?? null,
        exclusion: raw?.exclusion ?? null,
        keywords: raw?.keywords ?? null,
        example: raw?.example ?? null,
        // Merge provenance -- only the integrate editor's proposals carry
        // these (Create Codebook's `ProposedCode` has neither), and both
        // default harmlessly for that case: an empty array/null render as
        // nothing in `CodebookProposalTray`.
        sources: Array.isArray(raw?.sources) ? raw.sources : [],
        rationale: raw?.rationale ?? null,
      });
    }
    if (jobId && addedKeys.length > 0) {
      draftState.assistRuns.push({ jobId, proposedKeys: addedKeys });
    }
  });
  return { state: next, addedCount, skippedCount };
}

/**
 * Move one proposal into the draft, minting its identity.
 *
 * Family identity is reused when the draft already has a family of that
 * name, and minted with `family_is_new` otherwise. That reuse is
 * load-bearing rather than cosmetic: `_resolve_code_rows` rejects a code
 * carrying neither a `family_uid` nor `family_is_new`, and two codes the
 * user sees under one family heading must share one `family_uid` or the
 * backend stores them as two same-named families (grouping is by uid,
 * never by name -- see `core/codebook_render.py`).
 *
 * The AI badge is tracked as a set of `code_uid`s beside the tree, not as
 * a field on the code, because `cloneCodebookTree` whitelists the fields
 * it copies -- an extra marker on the node would be silently dropped the
 * first time the draft was cloned. It is display provenance only and never
 * reaches the server: the artifact's real provenance is `origin=edited` on
 * its version, since an assist during editing is not the claim that a
 * model produced the codebook.
 */
export function acceptProposal(state, key) {
  return withState(state, (next) => {
    const proposal = next.proposals.find((entry) => entry.key === key);
    if (!proposal) return;
    next.proposals = next.proposals.filter((entry) => entry.key !== key);

    const familyName = proposal.family_name || "Untitled family";
    let family = next.draft.find(
      (entry) => String(entry?.family_name ?? "").trim().toLowerCase() === familyName.toLowerCase(),
    );
    if (!family) {
      family = {
        family_uid: mintClientCodeUid(),
        family_name: familyName,
        family_is_new: true,
        codes: [],
      };
      next.draft.push(family);
    }
    const codeUid = mintClientCodeUid();
    next.aiAccepted.add(codeUid);
    next.acceptedKeyToUid[key] = codeUid;
    family.codes.push({
      code_uid: codeUid,
      is_new: true,
      family_uid: family.family_uid,
      family_name: family.family_name,
      name: proposal.name,
      body: "",
      definition: proposal.definition ?? null,
      inclusion: proposal.inclusion ?? null,
      exclusion: proposal.exclusion ?? null,
      keywords: proposal.keywords ?? null,
      example: proposal.example ?? null,
    });
  });
}

/** Accept every open proposal, in tray order. */
export function acceptAll(state) {
  let next = state;
  for (const proposal of state.proposals) next = acceptProposal(next, proposal.key);
  return next;
}

/**
 * Dismiss one proposal.
 *
 * The key is remembered, not just dropped: a dismissal is a decision, and
 * a later run must not re-offer it. Same reason the filter editor tracks
 * `excluded` separately from "not yet included".
 */
export function dismissProposal(state, key) {
  return withState(state, (next) => {
    next.proposals = next.proposals.filter((entry) => entry.key !== key);
    next.dismissed.add(key);
  });
}

/** Dismiss every open proposal at once. */
export function dismissAll(state) {
  return withState(state, (next) => {
    for (const proposal of next.proposals) next.dismissed.add(proposal.key);
    next.proposals = [];
  });
}

/** Was this draft code accepted from a proposal? */
export function isAiAccepted(state, codeUid) {
  return Boolean(codeUid) && state.aiAccepted.has(codeUid);
}

/**
 * Copy one source code into the draft by hand, bypassing the AI tray
 * entirely -- the rescue path for a code the assistant dropped, merged
 * into something the researcher disagrees with, or never got the chance
 * to consider. `sourceCode` is `{family_name, name, definition,
 * inclusion, exclusion, keywords, example}` -- the left pane's own row
 * shape.
 *
 * Mints a fresh identity exactly like `acceptProposal` (never the
 * source's own `code_uid`/`family_uid` -- see this module's docstring
 * and `codebook_service.create_integrated_codebook`), and reuses an
 * existing same-named family the same way. Deliberately does NOT touch
 * `aiAccepted`/`acceptedKeyToUid` -- copying is a human act, and an AI
 * badge on it would be a lie.
 *
 * Guards against adding an exact duplicate of something already in the
 * draft (by `codeKey`), checked fresh against the CURRENT draft on every
 * call rather than a stored flag -- a stored "already added" marker is
 * exactly the thing this module used to keep as `coveredSources` and
 * removed: it can't track a code that was since renamed, merged further,
 * or deleted, so it drifts from the truth the moment the researcher
 * starts editing. A live check can't drift, because there's nothing to
 * remember between calls. Returns `state` unchanged (same reference) on
 * a no-op, so a caller can tell whether anything actually happened.
 */
export function copySourceCode(state, sourceCode) {
  const key = codeKey(sourceCode.family_name, sourceCode.name);
  if (draftKeys(state.draft).has(key)) return state;

  return withState(state, (next) => {
    const familyName = sourceCode.family_name || "Untitled family";
    let family = next.draft.find(
      (entry) => String(entry?.family_name ?? "").trim().toLowerCase() === familyName.toLowerCase(),
    );
    if (!family) {
      family = {
        family_uid: mintClientCodeUid(),
        family_name: familyName,
        family_is_new: true,
        codes: [],
      };
      next.draft.push(family);
    }
    family.codes.push({
      code_uid: mintClientCodeUid(),
      is_new: true,
      family_uid: family.family_uid,
      family_name: family.family_name,
      name: sourceCode.name,
      body: "",
      definition: sourceCode.definition ?? null,
      inclusion: sourceCode.inclusion ?? null,
      exclusion: sourceCode.exclusion ?? null,
      keywords: sourceCode.keywords ?? null,
      example: sourceCode.example ?? null,
    });
  });
}

export function counts(state) {
  const uids = draftCodeUids(state.draft);
  let aiAccepted = 0;
  for (const uid of state.aiAccepted) if (uids.has(uid)) aiAccepted += 1;
  return {
    draft: uids.size,
    proposed: state.proposals.length,
    dismissed: state.dismissed.size,
    aiAccepted,
  };
}

/**
 * Reduce `assistRuns`/`acceptedKeyToUid` into the submit payload's
 * `assist_runs` -- one `{job_id, proposed_count, accepted_count,
 * dismissed_count, accepted_refs}` per run. A proposed key with no
 * recorded `code_uid` (still in the tray, or dismissed) counts as
 * dismissed, evaluated at submit time rather than when the run happened.
 */
export function buildAssistRunsForSubmit(state) {
  return (state.assistRuns || []).map((run) => {
    const acceptedRefs = [];
    for (const key of run.proposedKeys) {
      const uid = state.acceptedKeyToUid?.[key];
      if (uid) acceptedRefs.push(uid);
    }
    return {
      job_id: run.jobId,
      proposed_count: run.proposedKeys.length,
      accepted_count: acceptedRefs.length,
      dismissed_count: run.proposedKeys.length - acceptedRefs.length,
      accepted_refs: acceptedRefs,
    };
  });
}

/** The codes to send as `existing_codes` on a preview run -- what the
 * prompt shows the model so it proposes what's missing. Narrow on
 * purpose: family/name/definition is all the prompt needs, and sending
 * whole code rows would eat the reserved prompt budget for nothing. */
export function existingCodeRefs(state) {
  const refs = [];
  for (const family of Array.isArray(state.draft) ? state.draft : []) {
    for (const code of Array.isArray(family?.codes) ? family.codes : []) {
      const name = String(code?.name ?? "").trim();
      if (!name) continue;
      refs.push({
        family_name: String(family?.family_name ?? "").trim(),
        name,
        definition: code?.definition ?? null,
      });
    }
  }
  return refs;
}

/**
 * One draft per (source data, target codebook) pair.
 *
 * The target is part of the key because the same source data is a
 * perfectly ordinary starting point for several different codebooks, and
 * a draft keyed on source alone would leak one into the next.
 */
export function draftStorageKey(sourceDatabase, targetCodebook = "") {
  return `${DRAFT_STORAGE_PREFIX}${sourceDatabase}:${targetCodebook || "new"}`;
}

/** Prefix for the integrate editor's own drafts, kept distinct from
 * `DRAFT_STORAGE_PREFIX` (Create Codebook's) so the two tools' localStorage
 * entries never collide even if a schema/ref string happened to coincide. */
export const INTEGRATE_DRAFT_STORAGE_PREFIX = "integrateCodebookDraft:";

/**
 * One draft per SET of source codebooks being integrated -- sorted and
 * deduped, unlike `draftStorageKey`'s ordered (source, target) pair,
 * because the integrate editor's selection genuinely is a set: checking
 * codebook A then B must resume the exact same in-progress draft as
 * checking B then A, or switching the click order would silently orphan
 * unsaved work.
 */
export function integrateDraftStorageKey(codebookRefs) {
  const sorted = [...new Set((codebookRefs || []).map(String))].sort();
  return `${INTEGRATE_DRAFT_STORAGE_PREFIX}${sorted.join("|")}`;
}

/** Sets aren't JSON-serializable; localStorage round-trips through arrays. */
export function serializeDraft(state) {
  return JSON.stringify({
    draft: state.draft,
    proposals: state.proposals,
    dismissed: [...state.dismissed],
    aiAccepted: [...state.aiAccepted],
    assistRuns: state.assistRuns || [],
    acceptedKeyToUid: state.acceptedKeyToUid || {},
  });
}

/**
 * Rebuild editor state from its serialized form, tolerating anything.
 *
 * A draft is read back from `localStorage`, which is shared, user-editable
 * and outlives any given version of this code -- so malformed, truncated
 * or half-shaped JSON is an expected input, not an exceptional one, and
 * must degrade to "no draft" rather than break the page.
 */
export function deserializeDraft(raw) {
  if (!raw) return emptyState();
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return emptyState();
  }
  if (!parsed || typeof parsed !== "object") return emptyState();

  const draft = cloneCodebookTree(parsed.draft);
  const dismissed = new Set(
    Array.isArray(parsed.dismissed)
      ? parsed.dismissed.filter((key) => typeof key === "string")
      : [],
  );
  const inDraft = draftKeys(draft);
  const seen = new Set();
  const proposals = [];
  for (const entry of Array.isArray(parsed.proposals) ? parsed.proposals : []) {
    const name = String(entry?.name ?? "").trim();
    if (!name) continue;
    const familyName = String(entry?.family_name ?? "").trim();
    const key = codeKey(familyName, name);
    // A proposal duplicating a code now in the draft, one already
    // dismissed, or a repeat of another proposal would render as a tray
    // entry offering something the researcher has already ruled on.
    if (inDraft.has(key) || dismissed.has(key) || seen.has(key)) continue;
    seen.add(key);
    const rawSources = Array.isArray(entry?.sources) ? entry.sources : [];
    const sources = rawSources.filter(
      (source) =>
        source &&
        typeof source.codebook === "string" &&
        typeof source.name === "string" &&
        source.name.trim(),
    );
    proposals.push({
      key,
      family_name: familyName,
      name,
      definition: entry?.definition ?? null,
      inclusion: entry?.inclusion ?? null,
      exclusion: entry?.exclusion ?? null,
      keywords: entry?.keywords ?? null,
      example: entry?.example ?? null,
      sources,
      rationale: typeof entry?.rationale === "string" ? entry.rationale : null,
    });
  }
  // A badge on a code that isn't in the draft any more would render as a
  // dangling "AI" note against nothing -- same guard `filterEditorState`
  // applies to `aiAdded`.
  const uids = draftCodeUids(draft);
  const aiAccepted = new Set(
    (Array.isArray(parsed.aiAccepted) ? parsed.aiAccepted : []).filter(
      (uid) => typeof uid === "string" && uids.has(uid),
    ),
  );
  const assistRuns = (Array.isArray(parsed.assistRuns) ? parsed.assistRuns : []).filter(
    (run) => run && typeof run.jobId !== "undefined" && Array.isArray(run.proposedKeys),
  );
  // Same dangling-reference guard as `aiAccepted` -- a code_uid this
  // mapping points at that isn't in the draft any more is noise.
  const acceptedKeyToUid = {};
  const rawMap = parsed.acceptedKeyToUid;
  if (rawMap && typeof rawMap === "object") {
    for (const [key, uid] of Object.entries(rawMap)) {
      if (typeof uid === "string" && uids.has(uid)) acceptedKeyToUid[key] = uid;
    }
  }
  return { draft, proposals, dismissed, aiAccepted, assistRuns, acceptedKeyToUid };
}
