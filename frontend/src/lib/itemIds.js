// Shared vocabulary for the two kinds of coded content: "submission"
// (post) and "comment". Mirrors backend/app/core/item_types.py exactly
// -- keep the two in sync. See that module's docstring for why the type
// is encoded as an id prefix (Reddit's own t3_/t1_ fullname convention)
// rather than a separate line in the coding DSL: this file's
// parseCodingData/formatCodingData round-trip every coding artifact's
// text on each edit-and-save, so a sibling "TYPE:" line would be
// silently dropped, while a prefix embedded in the id (already treated
// as an opaque string everywhere) survives for free.

export const SUBMISSION = "submission";
export const COMMENT = "comment";

const PREFIXES = {
  [SUBMISSION]: "t3_",
  [COMMENT]: "t1_",
};

/** ("comment", "abc") -> "t1_abc" */
export const qualifyItemId = (rowType, rawId) => {
  const prefix = PREFIXES[rowType];
  if (prefix === undefined) {
    throw new Error(`Unknown row type: ${rowType}`);
  }
  return `${prefix}${rawId}`;
};

/**
 * Split a possibly-prefixed id back into { rowType, rawId }. An id with
 * no recognized prefix is treated as SUBMISSION -- the historical
 * default every pre-existing coding artifact already assumes.
 */
export const splitItemId = (qualifiedId) => {
  const value = String(qualifiedId ?? "");
  for (const [rowType, prefix] of Object.entries(PREFIXES)) {
    if (value.startsWith(prefix)) {
      return { rowType, rawId: value.slice(prefix.length) };
    }
  }
  return { rowType: SUBMISSION, rawId: value };
};
