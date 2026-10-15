/**
 * Citation formatting utilities for evidence quotes (QC-008).
 * Ensures privacy guardrails: author and URL are NEVER included unless
 * explicitly chosen by the user.
 */

export const DEFAULT_CITATION_OPTIONS = {
  includeAuthor: false,
  includeUrl: false,
  includeCoder: true,
  includeOffsets: true,
  includeNotes: false,
};

/**
 * Formats a coded quote into a citation string for scholarly writing drafts.
 *
 * @param {Object} quote
 * @param {string} quote.quote - The quote text
 * @param {string} quote.code - The applied code name
 * @param {string} [quote.coder] - 'human' or 'ai'
 * @param {string} [quote.coder_model] - AI model identifier if applicable
 * @param {string|number} [quote.post_id] - Target item / post id
 * @param {string} [quote.row_type] - 'submission' or 'comment'
 * @param {number} [quote.start_offset] - Exact start character offset
 * @param {number} [quote.end_offset] - Exact end character offset
 * @param {string} [quote.title] - Source document / post title
 * @param {string} [quote.author] - Source author username (privacy sensitive)
 * @param {string} [quote.url] - Source permalink / URL (privacy sensitive)
 * @param {string} [quote.notes] - Researcher notes on this quote
 * @param {Object} [options] - Configurable options
 * @returns {string} Formatted citation string
 */
export function formatCitation(quote, options = {}) {
  if (!quote || (!quote.quote && !quote.code && !quote.post_id)) return "";

  const opts = { ...DEFAULT_CITATION_OPTIONS, ...options };
  const parts = [];

  // Quote body
  const quoteText = quote.quote ? `"${quote.quote.trim()}"` : '""';
  parts.push(quoteText);

  // Attribution line
  const meta = [];

  if (quote.code) {
    meta.push(`Code: ${quote.code}`);
  }

  if (opts.includeCoder) {
    if (quote.coder === "ai") {
      meta.push(`Coder: AI${quote.coder_model ? ` (${quote.coder_model})` : ""}`);
    } else {
      meta.push("Coder: Human");
    }
  }

  const itemId = quote.post_id ? `${quote.row_type || "item"} #${quote.post_id}` : null;
  const offsets =
    opts.includeOffsets && quote.start_offset != null && quote.end_offset != null
      ? `chars ${quote.start_offset}–${quote.end_offset}`
      : null;

  if (itemId && offsets) {
    meta.push(`${itemId} (${offsets})`);
  } else if (itemId) {
    meta.push(itemId);
  } else if (offsets) {
    meta.push(offsets);
  }

  // Privacy-sensitive fields: STRICTLY guarded by options
  if (opts.includeAuthor && quote.author) {
    meta.push(`Author: ${quote.author}`);
  }

  if (opts.includeUrl && (quote.url || quote.permalink)) {
    meta.push(`URL: ${quote.url || quote.permalink}`);
  }

  if (meta.length > 0) {
    parts.push(`— ${meta.join(" | ")}`);
  }

  if (opts.includeNotes && quote.notes) {
    parts.push(`Note: ${quote.notes.trim()}`);
  }

  return parts.join("\n");
}
