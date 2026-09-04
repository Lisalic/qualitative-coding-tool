import { useState } from "react";
import MemoEditor from "../data/MemoEditor";

const thClasses =
  "truncate border-b-2 border-r border-paper px-2 py-2.5 text-left font-medium last:border-r-0";
const tdClasses = "overflow-hidden border-b border-r border-paper/20 px-2 py-2.5 last:border-r-0";

const markBtn = "min-w-[52px] whitespace-nowrap border px-1.5 py-1 text-xs font-medium transition-colors";

const COLUMN_WIDTHS = {
  submission: ["17%", "9%", "25%", "28%", "12%", "9%"],
  comment: ["17%", "9%", "50%", "15%", "9%"],
};

/**
 * Per-row include/exclude controls.
 *
 * Two explicit buttons rather than one checkbox, because the row has three
 * states, not two: "excluded" has to be distinguishable from "not looked at
 * yet", or the AI tool can't tell a rejection from a gap and will keep
 * re-proposing rows the user already dismissed. See
 * `lib/filterEditorState.js`.
 */
function RowMarks({ rowType, id, state, aiAdded, onInclude, onExclude }) {
  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        aria-label={`Keep ${rowType} ${id}`}
        aria-pressed={state === "included"}
        onClick={() => onInclude(rowType, id)}
        className={`${markBtn} ${
          state === "included"
            ? "border-paper bg-paper text-ink"
            : "border-paper/40 text-paper/60 hover:border-paper hover:text-paper"
        }`}
      >
        ✓ Keep
      </button>
      <button
        type="button"
        aria-label={`Skip ${rowType} ${id}`}
        aria-pressed={state === "excluded"}
        onClick={() => onExclude(rowType, id)}
        className={`${markBtn} ${
          state === "excluded"
            ? "border-paper bg-white/10 text-paper"
            : "border-paper/40 text-paper/60 hover:border-paper hover:text-paper"
        }`}
      >
        ✕ Skip
      </button>
      {aiAdded && (
        <span className="whitespace-nowrap border border-paper/30 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-paper/60">
          AI
        </span>
      )}
    </div>
  );
}

function rowClasses(state) {
  if (state === "included") return "bg-white/5";
  if (state === "excluded") return "opacity-40";
  return "";
}

/**
 * One content type's rows in the filter editor.
 *
 * Rendered separately for submissions and comments (rather than one merged
 * table) because the two have genuinely different columns, exactly as the
 * data viewer's `DataTable` does.
 *
 * Two things are deliberately NOT a row-opening click:
 *
 * - the Include cell, because marking rows in and out is the coder's main
 *   loop and a full-screen modal on every mark would make it unusable;
 * - the Memo cell, which expands the note inline underneath the row instead
 *   (see `expandedMemoId`). Writing a memo while filtering is a
 *   read-and-annotate rhythm, so it has to stay in the table -- the modal
 *   is still there via the content cells for the full post and its comments.
 */
export default function FilterEditorTable({
  rowType,
  rows,
  columns,
  editor,
  getMemo,
  onSaveMemo,
  onOpenRow,
}) {
  const [expandedMemoId, setExpandedMemoId] = useState(null);

  if (!rows || rows.length === 0) return null;

  const label = rowType === "submission" ? "Posts" : "Comments";
  const allIncluded = rows.every((row) => editor.stateOf(rowType, row.id) === "included");
  // Include + ID + content columns + Memo.
  const totalColumns = columns.length + 3;

  return (
    <div className="mb-6">
      <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
        <h3 className="text-lg font-medium">{label}</h3>
        <button
          type="button"
          className="border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink"
          onClick={() => editor.includeAll(rowType, rows.map((row) => row.id))}
        >
          {allIncluded ? "Clear kept on page" : "Keep all on page"}
        </button>
      </div>
      <div className="overflow-x-auto border border-paper">
        <table className="w-full min-w-[760px] table-fixed border-collapse text-sm">
          <colgroup>
            {COLUMN_WIDTHS[rowType].map((width, index) => (
              <col key={index} style={{ width }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th className={thClasses}>
                Decision
              </th>
              <th className={thClasses}>ID</th>
              {columns.map((col) => (
                <th key={col.key} className={thClasses}>
                  {col.label}
                </th>
              ))}
              <th className={thClasses}>
                Memo
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const state = editor.stateOf(rowType, row.id);
              const memo = getMemo(rowType, row.id);
              const expanded = expandedMemoId === row.id;
              return [
                <tr
                  key={row.id}
                  className={`transition-colors hover:bg-white/5 ${rowClasses(state)}`}
                >
                  <td className={tdClasses} onClick={(e) => e.stopPropagation()}>
                    <RowMarks
                      rowType={rowType}
                      id={row.id}
                      state={state}
                      aiAdded={editor.isAiAdded(rowType, row.id)}
                      onInclude={editor.include}
                      onExclude={editor.exclude}
                    />
                  </td>
                  <td
                    className={tdClasses}
                  >
                    <button
                      type="button"
                      onClick={() => onOpenRow(row, rowType)}
                      className="block w-full truncate text-left hover:underline focus:outline-none focus:ring-2 focus:ring-paper"
                      title="Open full row"
                    >
                      {row.id}
                    </button>
                  </td>
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`${tdClasses} ${col.truncate ? "max-w-[300px]" : ""}`}
                    >
                      <button
                        type="button"
                        onClick={() => onOpenRow(row, rowType)}
                        className="block w-full truncate text-left hover:underline focus:outline-none focus:ring-2 focus:ring-paper"
                        title={String(row[col.key] || "")}
                      >
                        {row[col.key]}
                      </button>
                    </td>
                  ))}
                  <td className={tdClasses}>
                    <button
                      type="button"
                      aria-label={`memo-${rowType}-${row.id}`}
                      aria-expanded={expanded}
                      onClick={() => setExpandedMemoId(expanded ? null : row.id)}
                      title={memo ? memo.body : "Add a memo"}
                      className={`${markBtn} ${
                        memo
                          ? "border-paper bg-white/10 text-paper"
                          : "border-paper/40 text-paper/60 hover:border-paper hover:text-paper"
                      }`}
                    >
                      {memo ? "✎ note" : "+ note"}
                    </button>
                  </td>
                </tr>,
                expanded ? (
                  <tr key={`${row.id}-memo`} className={rowClasses(state)}>
                    <td className="border-b border-paper/20 px-3 pb-4" colSpan={totalColumns}>
                      <MemoEditor
                        compact
                        memo={memo}
                        onSave={(body) => onSaveMemo(rowType, row.id, body)}
                      />
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
