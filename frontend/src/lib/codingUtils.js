// Utility functions for coding operations.
//
// A coding artifact's rows and their codes now come from the backend
// already structured (GET /api/coding/{ref}/rows -- see
// coding-table/workspace/useViewCodingPage.js), each row shaped as
// { item_id, row_type, title, content, codes: [{code, quote, start_offset,
// end_offset, notes}] } -- one entry per quote (coding_entries is now one
// row per quote, see storage_models.CodingEntry), each already resolved
// to exact character offsets into `content` server-side. There is no
// POST_ID/CODE/EVIDENCE text blob to parse on the way in or format on the
// way out, and (since offsets replace the old §-joined evidence string)
// no client-side snippet-splitting either -- HighlightedContent renders
// straight from `start_offset`/`end_offset`, see its own module comment.

/** Deep clone codebook tree (family_name, content, codes[].code_name, codes[].content). */
export const cloneCodebookTree = (tree) => {
  if (!Array.isArray(tree)) return [];
  return tree.map((family) => ({
    family_name:
      typeof family?.family_name === "string" ? family.family_name : "",
    content: typeof family?.content === "string" ? family.content : "",
    codes: (Array.isArray(family?.codes) ? family.codes : []).map((code) => ({
      code_name: typeof code?.code_name === "string" ? code.code_name : "",
      content: typeof code?.content === "string" ? code.content : "",
    })),
  }));
};

/**
 * Serialize tree to markdown matching backend/scripts/display_codebook.py parse_codebook_to_json input.
 */
export const serializeCodebookTreeToText = (tree) => {
  if (!Array.isArray(tree) || tree.length === 0) return "";

  const lines = [];
  for (const family of tree) {
    const fname = String(family?.family_name ?? "").trim() || "Unnamed family";
    lines.push(`### Code Family: ${fname}`);

    const fc = String(family?.content ?? "").trimEnd();
    if (fc) {
      for (const part of fc.split("\n")) {
        lines.push(part);
      }
    }

    const codes = Array.isArray(family?.codes) ? family.codes : [];
    for (const code of codes) {
      const cname = String(code?.code_name ?? "").trim();
      lines.push(`#### Code Name: ${cname}`);
      const cc = String(code?.content ?? "").trimEnd();
      if (cc) {
        for (const part of cc.split("\n")) {
          lines.push(part);
        }
      }
    }

    lines.push("");
  }

  return lines.join("\n").trim();
};

/** Every code name defined in a codebook tree, deduped and sorted --
 * used to populate the "pick a code" list for tagging a text selection
 * (see HighlightedContent's selection popover and CodingCodebookSidebar).
 */
export const flattenCodebookCodeNames = (tree) => {
  if (!Array.isArray(tree)) return [];
  const names = new Set();
  tree.forEach((family) => {
    (Array.isArray(family?.codes) ? family.codes : []).forEach((entry) => {
      const name =
        typeof entry === "string" ? entry.trim() : String(entry?.code_name || "").trim();
      if (name) names.add(name);
    });
  });
  return Array.from(names).sort((a, b) => a.localeCompare(b));
};

// Color assignment for codes
export const getCodeColor = (code) => {
  // Simple hash function for consistent colors
  let hash = 0;
  for (let i = 0; i < code.length; i++) {
    hash = code.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  // Use higher saturation and varied lightness for better distinction
  const saturation = 85;
  const lightness = 55 + (Math.abs(hash) % 20); // Vary lightness between 55-75%
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};

// Get all unique codes for legend, from a page of rows shaped like
// GET /api/coding/{ref}/rows's response ({ codes: [{code}] } per row).
export const getUniqueCodes = (rows) => {
  if (!Array.isArray(rows)) return [];
  const codes = new Set();
  rows.forEach((row) => {
    (row.codes || []).forEach(({ code }) => {
      if (code) codes.add(code);
    });
  });
  return Array.from(codes).sort();
};

// Get filtered rows based on selected filter codes (client-side filter
// over an already-fetched page; server-side filtering for the full
// artifact happens via the `code`/`only`/`q` query params on
// GET /api/coding/{ref}/rows).
export const getFilteredCoding = (rows, selectedFilterCodes) => {
  if (!Array.isArray(rows)) return [];
  if (!selectedFilterCodes || selectedFilterCodes.length === 0) {
    return rows;
  }
  const filterSet = new Set(selectedFilterCodes);
  return rows.filter((row) =>
    (row.codes || []).some((entry) => filterSet.has(entry.code)),
  );
};
