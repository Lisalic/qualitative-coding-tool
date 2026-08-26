// Helpers for editing a coding artifact's rows in the View Coding
// workspace.
//
// A row now comes from GET /api/coding/{ref}/rows already structured
// ({ item_id, row_type, title, content, codes: [{code, quote,
// start_offset, end_offset, notes}] }), and edits are sent back the same
// way via PUT /api/coding/{ref}/rows -- there is no POST_ID/CODE/EVIDENCE
// text blob to parse/format on the way in or out (see lib/codingUtils.js's
// header comment). Tagging auto-saves per action (see
// useViewCodingPage.js's putRowEntries), so there's no page-wide draft to
// clone any more -- only this validator, reused for every single-row PUT.

/**
 * Validate and trim a draft of edited rows before ``PUT
 * /api/coding/{ref}/rows``. A row with zero codes is valid -- it simply
 * means "not coded" (or every code was cleared), unlike the old
 * blob-backed editor where an uncoded row couldn't be represented at all.
 * A code entry needs a code, a quote, and a valid `0 <= start < end`
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
      const code = String(entry?.code || "").trim();
      const quote = String(entry?.quote || "").trim();
      const notes = String(entry?.notes || "").trim();
      const startOffset = entry?.start_offset;
      const endOffset = entry?.end_offset;
      const hasOffsets =
        Number.isInteger(startOffset) && Number.isInteger(endOffset) && startOffset >= 0 && endOffset > startOffset;

      if (!code && !quote && !notes) continue;
      if (!code || !quote || !hasOffsets) {
        return {
          ok: false,
          error: `Row ${rowIndex + 1}, code ${entryIndex + 1} must include a code, a quote, and a valid offset range.`,
        };
      }
      const base = { code, quote, start_offset: startOffset, end_offset: endOffset };
      normalizedCodes.push(notes ? { ...base, notes } : base);
    }

    normalizedRows.push({ item_id: itemId, entries: normalizedCodes });
  }

  return { ok: true, rows: normalizedRows };
};
