/**
 * One date format for the whole app: the viewer's locale, to the minute.
 * Seconds were noise in every list that showed them, and the app had
 * drifted into several hand-rolled `toLocaleString()` variants.
 *
 * Returns "" for a missing or unparseable value, so a caller can render it
 * unconditionally.
 */
export function formatDate(value) {
  if (value === null || value === undefined || value === "") return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
