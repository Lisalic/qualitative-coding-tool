/**
 * Match a `files.schemaname` value that is a real per-artifact opaque
 * schema identifier (`proj_...`), as opposed to blank, a placeholder, or
 * something else entirely.
 *
 * One regex, formerly three separate copies: `FilterEditor.jsx`,
 * `CodebookEditor.jsx`, and `useRowMemos.js` each inlined their own.
 */
export const PROJ_SCHEMA_RE = /^proj_[A-Za-z0-9_]+$/;

export function isProjectSchema(value) {
  return PROJ_SCHEMA_RE.test(String(value || ""));
}
