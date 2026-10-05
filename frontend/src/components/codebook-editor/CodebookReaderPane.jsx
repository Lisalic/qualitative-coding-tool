import MemoEditor from "../data/MemoEditor";

/**
 * Reference rail's "Row" tab: the active row's full text. Read-only,
 * unlike the filter editor's reader -- nothing here is decided per row,
 * the researcher is reading for themes while building the code list in
 * the center pane. Rendered inside the rail's tabbed `Panel`, so it
 * draws no border of its own.
 */
export default function CodebookReaderPane({ activeRow, memo, onSaveMemo }) {
  if (!activeRow) {
    return <p className="italic text-paper/60">Select a row from the list to read it.</p>;
  }

  const { rowType, id } = activeRow;
  const title = rowType === "submission" ? activeRow.title : null;
  const body = rowType === "submission" ? activeRow.selftext : activeRow.body;

  return (
    <div key={`${rowType}:${id}`} className="flex flex-col gap-3">
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wide text-paper/50">
          {rowType === "submission" ? "Post" : "Comment"} &middot; {id}
        </div>
        {title && <h3 className="mt-0.5 text-lg font-semibold">{title}</h3>}
        {activeRow.author && <div className="mt-0.5 text-xs text-paper/50">by {activeRow.author}</div>}
      </div>

      <div className="whitespace-pre-wrap text-sm text-paper/90">{body || "(no content)"}</div>

      <MemoEditor
        key={`${rowType}:${id}`}
        memo={memo}
        onSave={(saveBody) => onSaveMemo(rowType, id, saveBody)}
      />
    </div>
  );
}
