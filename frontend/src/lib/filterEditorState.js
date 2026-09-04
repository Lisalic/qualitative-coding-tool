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
  return { included: new Set(), excluded: new Set(), aiAdded: new Set() };
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
    aiAdded: new Set(selection.aiAdded),
  };
  mutate(next);
  return next;
}

/**
 * Toggle a row into or out of `included`.
 *
 * Including a row always clears any `excluded` mark: the three states are
 * mutually exclusive, and a row can never be both. Un-including drops the
 * `(added by AI)` badge too -- once the user has taken the suggestion back
 * off, the provenance of a mark that no longer exists is noise.
 */
export function toggleInclude(selection, rowType, id) {
  const key = keyFor(rowType, id);
  return withSets(selection, (next) => {
    if (next.included.has(key)) {
      next.included.delete(key);
      next.aiAdded.delete(key);
    } else {
      next.included.add(key);
      next.excluded.delete(key);
    }
  });
}

/** Toggle a row into or out of `excluded`, clearing any inclusion. */
export function toggleExclude(selection, rowType, id) {
  const key = keyFor(rowType, id);
  return withSets(selection, (next) => {
    if (next.excluded.has(key)) {
      next.excluded.delete(key);
    } else {
      next.excluded.add(key);
      next.included.delete(key);
      next.aiAdded.delete(key);
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
        next.aiAdded.delete(key);
      } else {
        next.included.add(key);
        next.excluded.delete(key);
      }
    }
  });
}

/**
 * Fold one AI preview run's suggestions into the selection.
 *
 * Additive and non-destructive: a suggested row is included and badged
 * `(added by AI)`, but a row the user already excluded is left alone even
 * if the model proposes it. The backend already omits decided rows from
 * the candidate pool (`data_service._sample_source_rows`'s `exclude_*`
 * arguments); this is the client-side belt to that braces, so a stale
 * in-flight run can never silently undo a decision made while it ran.
 *
 * Returns `{ selection, addedCount }` -- the count is what the panel
 * reports back ("12 rows added by AI"), and counts only rows this run
 * actually changed, not the size of the model's response.
 */
export function applyAiResult(selection, { postIds = [], commentIds = [] } = {}) {
  let addedCount = 0;
  const next = withSets(selection, (draft) => {
    const add = (rowType, ids) => {
      for (const id of ids) {
        const key = keyFor(rowType, id);
        if (draft.excluded.has(key) || draft.included.has(key)) continue;
        draft.included.add(key);
        draft.aiAdded.add(key);
        addedCount += 1;
      }
    };
    add("submission", postIds);
    add("comment", commentIds);
  });
  return { selection: next, addedCount };
}

/** Was this row included because the AI proposed it? */
export function isAiAdded(selection, rowType, id) {
  return selection.aiAdded.has(keyFor(rowType, id));
}

/**
 * Split a key set into `{ postIds, commentIds }`.
 *
 * Used twice with different inputs: for the AI preview call, which needs
 * every decided row (included AND excluded) so it can skip them; and for
 * submit, which needs only the included ones.
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

export function counts(selection) {
  return {
    included: selection.included.size,
    excluded: selection.excluded.size,
    aiAdded: selection.aiAdded.size,
  };
}

export function draftStorageKey(sourceDatabase) {
  return `${DRAFT_STORAGE_PREFIX}${sourceDatabase}`;
}

/** Sets aren't JSON-serializable; localStorage round-trips through arrays. */
export function serializeDraft(selection) {
  return JSON.stringify({
    included: [...selection.included],
    excluded: [...selection.excluded],
    aiAdded: [...selection.aiAdded],
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
  // A badge on a row that isn't included any more would render as a
  // dangling "(added by AI)" note next to an unchecked row.
  const aiAdded = new Set([...toSet(parsed.aiAdded)].filter((k) => included.has(k)));
  return { included, excluded, aiAdded };
}
