/**
 * Rows-per-page choices, shared by every paged list in the app.
 *
 * These had drifted: the filter editor and the data table offered
 * `[10,25,50,100,200]` while the codebook editor's source reader stopped at
 * 100, so the same control offered different choices depending on which
 * editor you were in.
 */
const PAGE_SIZES = [10, 25, 50, 100, 200];

/** `{value,label}` options for a `Dropdown`. Values stay numbers. */
export const PAGE_SIZE_OPTIONS = PAGE_SIZES.map((size) => ({
  value: size,
  label: `${size} / page`,
}));
