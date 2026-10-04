/**
 * Stored quote offsets (`start_offset`/`end_offset`) count Unicode code
 * points -- what Python's string indexing counts, and what the backend's
 * evidence matcher computes. JS strings index UTF-16 units, where an emoji
 * takes two, so slicing with a stored offset directly drifts one character
 * per emoji before the quote. Convert at the boundary, in both directions.
 */

export function codePointToUtf16Index(text, codePointIndex) {
  let units = 0;
  let points = 0;
  for (const char of text) {
    if (points >= codePointIndex) break;
    units += char.length;
    points += 1;
  }
  return units;
}

export function utf16ToCodePointIndex(text, utf16Index) {
  let units = 0;
  let points = 0;
  for (const char of text) {
    if (units >= utf16Index) break;
    units += char.length;
    points += 1;
  }
  return points;
}

/** `text` between two stored (code point) offsets. */
export function sliceByCodePoints(text, start, end) {
  return text.slice(codePointToUtf16Index(text, start), end === undefined ? undefined : codePointToUtf16Index(text, end));
}
