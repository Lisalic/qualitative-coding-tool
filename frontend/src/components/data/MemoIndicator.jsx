/**
 * The "this row has a memo" marker shown in a table row's ID cell.
 *
 * Renders nothing when there is no memo, so callers can drop it in
 * unconditionally. The memo's text is the `title`, which makes the note
 * readable on hover without opening the row -- scanning a table for
 * "which of these did I already have a thought about" is the whole
 * reason the indicator exists.
 */
export default function MemoIndicator({ memo }) {
  if (!memo) return null;
  return (
    <span
      className="ml-1.5 text-paper/70"
      title={memo.body}
      aria-label="Has a memo"
    >
      ✎
    </span>
  );
}
