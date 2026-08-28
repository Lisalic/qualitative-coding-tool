// Utility functions for coding operations.
//
// A coding artifact's rows and their codes now come from the backend
// already structured (GET /api/coding/{ref}/rows -- see
// coding-table/workspace/useViewCodingPage.js), each row shaped as
// { item_id, row_type, title, content, codes: [{code, code_uid, quote,
// start_offset, end_offset, notes}] } -- one entry per quote
// (coding_entries is one row per quote, see storage_models.CodingEntry),
// each already resolved to exact character offsets into `content`
// server-side. There is no POST_ID/CODE/EVIDENCE text blob to parse on
// the way in or format on the way out, and no client-side snippet-
// splitting either -- HighlightedContent renders straight from
// `start_offset`/`end_offset`, see its own module comment.
//
// A codebook's own codes (GET /api/coding/{ref}, GET /api/codebook) come
// as a FLAT list -- one entry per code, each carrying a stable `code_uid`
// (identity that survives a rename) and `family_uid` (identity for the
// family it belongs to). `groupCodesByFamily`/`flattenTreeToCodes` are
// the adapter pair between that flat wire shape and the nested
// family->codes tree the editor UI (CodeLegend, CodingCodebookSidebar)
// renders -- grouping is a pure display-time transform, matching how
// `backend/app/core/codebook_render.py` groups server-side: by
// `family_uid` (never by name -- two families can share a name, see that
// module's docstring), in `position` order.

/** Group a flat `codes` list (as returned by the backend) into a nested
 * family->codes tree for display, preserving `code_uid`/`family_uid` on
 * every node -- the identity that makes a rename a rename instead of a
 * delete+add. Families appear in the order their first code was seen
 * (matching `position` order from the backend).
 */
export const groupCodesByFamily = (codes) => {
  if (!Array.isArray(codes)) return [];
  const byFamily = new Map();
  const order = [];
  for (const code of codes) {
    const familyUid = String(code?.family_uid ?? "");
    if (!byFamily.has(familyUid)) {
      byFamily.set(familyUid, {
        family_uid: familyUid,
        family_name: String(code?.family_name ?? ""),
        codes: [],
      });
      order.push(familyUid);
    }
    byFamily.get(familyUid).codes.push({
      code_uid: String(code?.code_uid ?? ""),
      family_uid: familyUid,
      family_name: String(code?.family_name ?? ""),
      name: String(code?.name ?? ""),
      body: typeof code?.body === "string" ? code.body : "",
      definition: code?.definition ?? null,
      inclusion: code?.inclusion ?? null,
      exclusion: code?.exclusion ?? null,
      keywords: code?.keywords ?? null,
      example: code?.example ?? null,
    });
  }
  return order.map((familyUid) => byFamily.get(familyUid));
};

/** A fresh 32-hex-char id in the same shape `uuid.uuid4().hex` mints
 * server-side (see `codebook_service._resolve_code_rows`) -- used to
 * give a code/family created client-side (`CodeLegend`'s "add" actions)
 * a real, stable `code_uid`/`family_uid` the moment it's created, rather
 * than leaving it identity-less until the next save. A code carrying one
 * of these is still marked `is_new: true` alongside it (see
 * `flattenTreeToCodes`) -- the client-minted id is what the server ends
 * up storing (`code_uid or uuid.uuid4().hex`), `is_new` is what tells
 * the server this is a creation, not an edit.
 */
export const mintClientCodeUid = () =>
  (typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID().replace(/-/g, "")
    : `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`.padEnd(32, "0").slice(0, 32));

/** Deep clone a family->codes tree, preserving `code_uid`/`family_uid`
 * and every code field -- unlike the old whitelist this replaces, which
 * silently stripped any field it didn't know about (including
 * `code_uid` itself, the exact bug that made every save mint fresh
 * identities and rename every code -- see this module's history).
 * `is_new`/`family_is_new` are preserved too, so cloning a draft that
 * already has a client-minted code/family (see `mintClientCodeUid`)
 * doesn't lose the "this is a creation" flag.
 */
export const cloneCodebookTree = (tree) => {
  if (!Array.isArray(tree)) return [];
  return tree.map((family) => ({
    family_uid: typeof family?.family_uid === "string" ? family.family_uid : "",
    family_name: typeof family?.family_name === "string" ? family.family_name : "",
    ...(family?.family_is_new ? { family_is_new: true } : {}),
    codes: (Array.isArray(family?.codes) ? family.codes : []).map((code) => ({
      code_uid: typeof code?.code_uid === "string" ? code.code_uid : "",
      family_uid: typeof code?.family_uid === "string" ? code.family_uid : "",
      family_name: typeof code?.family_name === "string" ? code.family_name : "",
      name: typeof code?.name === "string" ? code.name : "",
      body: typeof code?.body === "string" ? code.body : "",
      definition: code?.definition ?? null,
      inclusion: code?.inclusion ?? null,
      exclusion: code?.exclusion ?? null,
      keywords: code?.keywords ?? null,
      example: code?.example ?? null,
      ...(code?.is_new ? { is_new: true } : {}),
    })),
  }));
};

/** Flatten a family->codes tree back into the flat `codes` list the
 * structured save endpoint (`PUT /api/coding/{ref}/revision`'s `codes`,
 * or `PUT /api/codebook/{ref}`) expects, assigning `position` from
 * traversal order. Identity is explicit: a code/family created via
 * `CodeLegend`'s "add" actions already carries a client-minted
 * `code_uid`/`family_uid` (see `mintClientCodeUid`) plus
 * `is_new`/`family_is_new: true`, and both are forwarded together --
 * the backend uses the supplied uid as-is (`code_uid or
 * uuid.uuid4().hex`) rather than minting its own, while `is_new` is what
 * tells it this is a creation, not an edit. A code with no `code_uid` at
 * all (defensive fallback, shouldn't happen once every "add" mints one)
 * still falls back to `is_new: true` with no uid, which the backend
 * mints one for -- it refuses a code with neither (see
 * `codebook_service._resolve_code_rows`).
 */
export const flattenTreeToCodes = (tree) => {
  if (!Array.isArray(tree)) return [];
  const codes = [];
  let position = 0;
  for (const family of tree) {
    const familyUid = family?.family_uid || null;
    const familyIsNew = Boolean(family?.family_is_new) || !familyUid;
    const familyName = String(family?.family_name ?? "").trim() || "Untitled family";
    const familyCodes = Array.isArray(family?.codes) ? family.codes : [];
    for (const code of familyCodes) {
      const codeUid = code?.code_uid || null;
      const codeIsNew = Boolean(code?.is_new) || !codeUid;
      codes.push({
        ...(codeUid ? { code_uid: codeUid } : {}),
        ...(codeIsNew ? { is_new: true } : {}),
        ...(familyUid ? { family_uid: familyUid } : {}),
        ...(familyIsNew ? { family_is_new: true } : {}),
        family_name: familyName,
        name: String(code?.name ?? "").trim(),
        body: typeof code?.body === "string" ? code.body : "",
        definition: code?.definition ?? null,
        inclusion: code?.inclusion ?? null,
        exclusion: code?.exclusion ?? null,
        keywords: code?.keywords ?? null,
        example: code?.example ?? null,
        position: position++,
      });
    }
  }
  return codes;
};

/** Every `{code_uid, name}` defined in a codebook tree, deduped by
 * `code_uid` and sorted by name -- used to populate the "pick a code"
 * list for tagging a text selection (see HighlightedContent's selection
 * popover and CodingCodebookSidebar). Identity is the uid; `name` is
 * only ever the display label.
 */
export const flattenCodebookCodes = (tree) => {
  if (!Array.isArray(tree)) return [];
  const byUid = new Map();
  tree.forEach((family) => {
    (Array.isArray(family?.codes) ? family.codes : []).forEach((entry) => {
      const uid = typeof entry?.code_uid === "string" ? entry.code_uid : "";
      const name = typeof entry?.name === "string" ? entry.name.trim() : "";
      if (uid && name && !byUid.has(uid)) byUid.set(uid, { code_uid: uid, name });
    });
  });
  return Array.from(byUid.values()).sort((a, b) => a.name.localeCompare(b.name));
};

// Color assignment for codes -- hashes `code_uid` (stable identity), not
// the display name, so a rename never changes a code's color.
export const getCodeColor = (codeUid) => {
  const key = String(codeUid ?? "");
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = key.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  // Use higher saturation and varied lightness for better distinction
  const saturation = 85;
  const lightness = 55 + (Math.abs(hash) % 20); // Vary lightness between 55-75%
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};
