// Helpers for editing a coding artifact's rows in the View Coding
// workspace.
//
// A row now comes from GET /api/coding/{ref}/rows already structured
// ({ item_id, row_type, title, content, codes: [{code, code_uid, quote,
// start_offset, end_offset, notes}] }), and edits are sent back the same
// way as the `rows` field of PUT /api/coding/{ref}/revision -- there is
// no POST_ID/CODE/EVIDENCE text blob to parse/format on the way in or
// out (see lib/codingUtils.js's header comment). Tagging (manual or an
// accepted AI recode proposal) is staged locally and flushed in one
// batched save alongside any codebook edit (see useViewCodingPage.js's
// pendingRowEdits/saveSession), so this validator normalizes every
// pending row at once, not one at a time.
//
// Identity for the wire is `code_uid`, not the display name `code` --
// the backend resolves the current name from the uid, so a code rename
// never orphans an entry (see coding_service.save_coding_rows). `code`
// may still be present on an entry read back from the server (for
// display), but it's never required or sent on the way out.

/**
 * Validate and trim a draft of edited rows before ``PUT
 * /api/coding/{ref}/rows``. A row with zero codes is valid -- it simply
 * means "not coded" (or every code was cleared), unlike the old
 * blob-backed editor where an uncoded row couldn't be represented at all.
 * A code entry needs a `code_uid`, a quote, and a valid `0 <= start < end`
 * offset pair (computed directly from the real DOM selection range in
 * HighlightedContent.jsx, never re-derived here) -- missing any of that
 * is rejected; a fully-blank entry is silently dropped.
 */
export const normalizeCodingRowEdits = (rows) => {
  if (!Array.isArray(rows)) {
    return { ok: false, error: "No rows to save." };
  }

  const normalizedRows = [];

  for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    const itemId = String(row?.itemId ?? row?.item_id ?? "").trim();
    if (!itemId) {
      return { ok: false, error: `Row ${rowIndex + 1} is missing an item id.` };
    }

    const codesInput = Array.isArray(row?.codes) ? row.codes : [];
    const normalizedCodes = [];
    for (let entryIndex = 0; entryIndex < codesInput.length; entryIndex += 1) {
      const entry = codesInput[entryIndex] || {};
      const codeUid = String(entry?.code_uid || "").trim();
      const quote = String(entry?.quote || "").trim();
      const notes = String(entry?.notes || "").trim();
      const startOffset = entry?.start_offset;
      const endOffset = entry?.end_offset;
      const hasOffsets =
        Number.isInteger(startOffset) && Number.isInteger(endOffset) && startOffset >= 0 && endOffset > startOffset;

      if (!codeUid && !quote && !notes) continue;
      if (!codeUid || !quote || !hasOffsets) {
        return {
          ok: false,
          error: `Row ${rowIndex + 1}, code ${entryIndex + 1} must include a code, a quote, and a valid offset range.`,
        };
      }
      const base = { code_uid: codeUid, quote, start_offset: startOffset, end_offset: endOffset };
      normalizedCodes.push(notes ? { ...base, notes } : base);
    }

    normalizedRows.push({ item_id: itemId, entries: normalizedCodes });
  }

  return { ok: true, rows: normalizedRows };
};
