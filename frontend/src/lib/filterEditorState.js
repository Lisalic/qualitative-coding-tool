/**
 * The filter editor's tri-state row selection, as pure functions.
 *
 * A row in the editor is in exactly one of three states:
 *
 *   included  -- the user checked it; it goes into the filtered database
 *   excluded  -- the user explicitly ruled it out
 *   undecided -- neither; the only rows the AI filter tool may propose
 *
 * That third state is the whole point. "Not checked" and "rejected" look
 * the same in a plain checkbox list, which would leave the AI tool no way
 * to tell "I haven't looked at this yet" from "I already said no" -- so a
 * second run would keep re-proposing rows the user just dismissed.
 *
 * Kept here rather than inside the React hook because `frontend/src/lib/**`
 * is the layer the Vitest suite covers (see CLAUDE.md); `useFilterEditorState`
 * is a thin stateful wrapper over these.
 *
 * Keys are `"<rowType>:<id>"`, matching the convention `keyFor` already
 * uses in `components/data/useDataTableActions.js`, so a selection can move
 * between the two surfaces unchanged. Ids may themselves contain colons,
 * so `parseKey` splits on the FIRST colon only.
 *
 * `assistRuns` is the C2 AI-assist provenance channel (closes GAP-4 in
 * `documentation/research/qualitative-coding-landscape-and-expansion.md`):
 * one record per `applyAiResult` call that carried a `jobId`, remembering
 * which keys THAT run proposed and in which direction (`{key, decision}`,
 * `decision` one of `"include"`/`"exclude"`). `buildAssistRunsForSubmit`
 * turns those into `{job_id, proposed_count, accepted_count,
 * dismissed_count, accepted_refs}` at submit time by re-checking each
 * run's proposed keys against the CURRENT selection -- so a proposal is
 * "accepted" iff the row still sits in the direction the AI proposed
 * (whether that's `included` or `excluded`), without a separate write
 * path to keep in sync. The server re-derives model/prompts from the job
 * itself (`services/assist_service.py`) rather than trusting this.
 */

export const DRAFT_STORAGE_PREFIX = "filterEditorDraft:";

export function keyFor(rowType, id) {
  return `${rowType}:${id}`;
}

export function parseKey(key) {
  const idx = String(key).indexOf(":");
  if (idx === -1) return { rowType: "submission", id: String(key) };
  return { rowType: key.slice(0, idx), id: key.slice(idx + 1) };
}

/** The zero state: nothing decided, nothing suggested. */
export function emptySelection() {
  return { included: new Set(), excluded: new Set(), aiDecided: new Set(), assistRuns: [] };
}

/** `"included" | "excluded" | "undecided"` for one row. */
export function stateOf(selection, rowType, id) {
  const key = keyFor(rowType, id);
  if (selection.included.has(key)) return "included";
  if (selection.excluded.has(key)) return "excluded";
  return "undecided";
}

function withSets(selection, mutate) {
  const next = {
    included: new Set(selection.included),
    excluded: new Set(selection.excluded),
    aiDecided: new Set(selection.aiDecided),
    assistRuns: selection.assistRuns ? [...selection.assistRuns] : [],
  };
  mutate(next);
  return next;
}

/**
 * Toggle a row into or out of `included`.
 *
 * Including a row always clears any `excluded` mark: the three states are
 * mutually exclusive, and a row can never be both. Un-including drops the
 * AI badge too -- once the user has taken the suggestion back off, the
 * provenance of a mark that no longer exists is noise.
 */
export function toggleInclude(selection, rowType, id) {
  const key = keyFor(rowType, id);
  return withSets(selection, (next) => {
    if (next.included.has(key)) {
      next.included.delete(key);
      next.aiDecided.delete(key);
    } else {
      next.included.add(key);
      next.excluded.delete(key);
      next.aiDecided.delete(key);
    }
  });
}

/** Toggle a row into or out of `excluded`, clearing any inclusion. */
export function toggleExclude(selection, rowType, id) {
  const key = keyFor(rowType, id);
  return withSets(selection, (next) => {
    if (next.excluded.has(key)) {
      next.excluded.delete(key);
      next.aiDecided.delete(key);
    } else {
      next.excluded.add(key);
      next.included.delete(key);
      next.aiDecided.delete(key);
    }
  });
}

/** Set every row in `rows` to `included`, or clear them all if all are already included. */
export function toggleAll(selection, rowType, ids) {
  const keys = ids.map((id) => keyFor(rowType, id));
  const allIncluded = keys.length > 0 && keys.every((k) => selection.included.has(k));
  return withSets(selection, (next) => {
    for (const key of keys) {
      if (allIncluded) {
        next.included.delete(key);
        next.aiDecided.delete(key);
      } else {
        next.included.add(key);
        next.excluded.delete(key);
        next.aiDecided.delete(key);
      }
    }
  });
}

/**
 * Fold one AI preview run's suggestions into the selection, in EITHER
 * direction.
 *
 * Additive and non-destructive: a row the user already ruled on (in
 * either direction) is left alone even if the model proposes the
 * opposite for it. The backend already omits decided rows from the
 * candidate pool (`data_service._sample_source_rows`'s `exclude_*`
 * arguments); this is the client-side belt to that braces, so a stale
 * in-flight run can never silently undo a decision made while it ran.
 *
 * Returns `{ selection, includedCount, excludedCount }` -- the counts
 * are what the panel reports back ("3 included, 2 excluded"), counting
 * only rows this run actually changed, not the size of the model's
 * response.
 */
export function applyAiResult(
  selection,
  { jobId, includePostIds = [], includeCommentIds = [], excludePostIds = [], excludeCommentIds = [] } = {},
) {
  let includedCount = 0;
  let excludedCount = 0;
  const proposed = [];
  const next = withSets(selection, (draft) => {
    const apply = (rowType, ids, decision) => {
      for (const id of ids) {
        const key = keyFor(rowType, id);
        proposed.push({ key, decision });
        if (draft.excluded.has(key) || draft.included.has(key)) continue;
        if (decision === "include") {
          draft.included.add(key);
          includedCount += 1;
        } else {
          draft.excluded.add(key);
          excludedCount += 1;
        }
        draft.aiDecided.add(key);
      }
    };
    apply("submission", includePostIds, "include");
    apply("comment", includeCommentIds, "include");
    apply("submission", excludePostIds, "exclude");
    apply("comment", excludeCommentIds, "exclude");
    if (jobId && proposed.length > 0) {
      draft.assistRuns.push({ jobId, proposed });
    }
  });
  return { selection: next, includedCount, excludedCount };
}

/** Was this row decided by the AI (in either direction)? */
export function isAiDecided(selection, rowType, id) {
  return selection.aiDecided.has(keyFor(rowType, id));
}

/**
 * Split a key set into `{ postIds, commentIds }`.
 *
 * Used to shape ids for both the AI preview call (which needs the
 * decided rows so it can skip them, split by include/exclude) and
 * submit (which needs only the included ones).
 */
export function splitByType(keys) {
  const postIds = [];
  const commentIds = [];
  for (const key of keys) {
    const { rowType, id } = parseKey(key);
    if (rowType === "comment") commentIds.push(id);
    else postIds.push(id);
  }
  return { postIds, commentIds };
}

/** Every row the user has ruled on, in either direction. */
export function decidedIds(selection) {
  return splitByType([...selection.included, ...selection.excluded]);
}

/** The rows that will actually be copied into the new filtered database. */
export function includedIds(selection) {
  return splitByType([...selection.included]);
}

/** The rows the user has explicitly ruled out. */
export function excludedIds(selection) {
  return splitByType([...selection.excluded]);
}

export function counts(selection) {
  return {
    included: selection.included.size,
    excluded: selection.excluded.size,
    aiDecided: selection.aiDecided.size,
  };
}

/**
 * Reduce `assistRuns` into the submit payload's `assist_runs` -- one
 * `{job_id, proposed_count, accepted_count, dismissed_count,
 * accepted_refs}` per run, computed against the CURRENT selection so a
 * row proposed then later reversed counts as dismissed even though
 * `applyAiResult` ran before that reversal happened. A proposal is
 * "accepted" iff the row currently sits in the direction the AI
 * proposed it for -- an AI-proposed EXCLUSION the user kept counts as
 * accepted even though it never entered `included`.
 */
export function buildAssistRunsForSubmit(selection) {
  return (selection.assistRuns || []).map((run) => {
    const acceptedRefs = run.proposed
      .filter(({ key, decision }) =>
        decision === "include" ? selection.included.has(key) : selection.excluded.has(key),
      )
      .map(({ key }) => key);
    return {
      job_id: run.jobId,
      proposed_count: run.proposed.length,
      accepted_count: acceptedRefs.length,
      dismissed_count: run.proposed.length - acceptedRefs.length,
      accepted_refs: acceptedRefs,
    };
  });
}

export function draftStorageKey(sourceDatabase) {
  return `${DRAFT_STORAGE_PREFIX}${sourceDatabase}`;
}

/** Sets aren't JSON-serializable; localStorage round-trips through arrays. */
export function serializeDraft(selection) {
  return JSON.stringify({
    included: [...selection.included],
    excluded: [...selection.excluded],
    aiDecided: [...selection.aiDecided],
    assistRuns: selection.assistRuns || [],
  });
}

/**
 * Rebuild a selection from its serialized form, tolerating anything.
 *
 * A draft is read back from `localStorage`, which is shared, user-editable
 * and outlives any given version of this code -- so malformed, truncated
 * or half-shaped JSON is an expected input, not an exceptional one, and
 * must degrade to "no draft" rather than break the page.
 */
export function deserializeDraft(raw) {
  if (!raw) return emptySelection();
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return emptySelection();
  }
  if (!parsed || typeof parsed !== "object") return emptySelection();
  const toSet = (value) => new Set(Array.isArray(value) ? value.filter((v) => typeof v === "string") : []);
  const included = toSet(parsed.included);
  const excluded = toSet(parsed.excluded);
  // A key can't be in both; inclusion wins, matching `toggleInclude`.
  for (const key of included) excluded.delete(key);
  // A badge on a row that isn't decided any more would render as a
  // dangling AI note next to an undecided row.
  const aiDecided = new Set(
    [...toSet(parsed.aiDecided)].filter((k) => included.has(k) || excluded.has(k)),
  );
  const assistRuns = Array.isArray(parsed.assistRuns)
    ? parsed.assistRuns.filter(
        (run) =>
          run &&
          typeof run.jobId !== "undefined" &&
          Array.isArray(run.proposed) &&
          run.proposed.every((p) => p && typeof p.key === "string" && typeof p.decision === "string"),
      )
    : [];
  return { included, excluded, aiDecided, assistRuns };
}
