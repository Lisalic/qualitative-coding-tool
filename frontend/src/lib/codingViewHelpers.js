// Helpers for editing a coding artifact's rows in the View Coding
// workspace. Row shape matches lib/codingUtils.js's header comment;
// edits are sent back as the `rows` field of PUT /api/coding/{ref}/revision.
// Tagging is staged locally and flushed in one batched save alongside any
// codebook edit (see useViewCodingPage.js), so this validator normalizes
// every pending row at once, not one at a time.
//
// Identity for the wire is `code_uid`, not the display name `code` --
// the backend resolves the current name from the uid, so a rename never
// orphans an entry (see coding_service.save_coding_rows).

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
      if (notes) base.notes = notes;
      // B1 per-quote attribution -- see storage_models.CodingEntry. Carried
      // through unchanged; useViewCodingPage.js is what stamps `coder`/
      // `assist_job_id` onto an entry (human edit vs. accepted AI recode).
      if (entry?.coder) base.coder = entry.coder;
      if (entry?.assist_job_id) base.assist_job_id = entry.assist_job_id;
      normalizedCodes.push(base);
    }

    normalizedRows.push({ item_id: itemId, entries: normalizedCodes });
  }

  return { ok: true, rows: normalizedRows };
};
