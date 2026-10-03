/**
 * Plain-language summary of the records an upload left out, from the
 * upload response's `skipped_counts` (see backend/scripts/import_db.py's
 * `iter_zst_records`). `null` when nothing was skipped.
 */
const SKIP_REASONS = [
  ["no_text", "had no text, or were deleted or removed"],
  ["duplicate", "repeated an earlier id"],
  ["unreadable", "weren't readable JSON records"],
  ["no_id", "had no id"],
];

export function describeSkippedRecords(skippedCounts) {
  const parts = SKIP_REASONS.filter(([key]) => skippedCounts?.[key] > 0).map(
    ([key, reason]) => `${skippedCounts[key].toLocaleString()} ${reason}`,
  );
  if (parts.length === 0) return null;
  return `Skipped records: ${parts.join("; ")}.`;
}
