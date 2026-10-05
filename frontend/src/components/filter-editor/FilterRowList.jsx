import MemoIndicator from "../data/MemoIndicator";
import EditorListPane from "../editor-shell/EditorListPane";
import Dropdown from "../primitives/Dropdown";
import { select, btnSm } from "../../lib/uiClasses";
import { PAGE_SIZE_OPTIONS } from "../../lib/pageSizes";
import { filterRowsByStatus } from "../../lib/filterEditorState";

const STATUS_OPTIONS = [
  { value: "all", label: "All rows" },
  { value: "undecided", label: "Undecided" },
  { value: "included", label: "Kept" },
  { value: "excluded", label: "Skipped" },
];

function rowPreview(row) {
  if (row.rowType === "submission") return row.title || "(untitled)";
  const body = String(row.body || "").trim();
  return body ? body.slice(0, 80) : "(empty)";
}

function markState(state) {
  if (state === "included") return { symbol: "✓", className: "text-paper" };
  if (state === "excluded") return { symbol: "✕", className: "text-paper/40" };
  return { symbol: "·", className: "text-paper/30" };
}

/**
 * Left rail of the filter editor: every submission/comment on the current
 * page as a compact scannable list -- a decision mark, a type badge, and
 * a preview, not the full text (that's the reader pane). Clicking a row
 * makes it active; the small Keep/Skip buttons let a short preview be
 * decided without opening it, the same fast path the old table gave.
 *
 * `statusFilter` narrows what's shown to rows already loaded on this
 * page -- there is no server-side equivalent to the coding workspace's
 * coded/uncoded row filter here, so it is scoped honestly to the page
 * rather than pretending to search the whole database.
 */
export default function FilterRowList({
  rows,
  activeKey,
  onSelectRow,
  editor,
  getMemo,
  statusFilter,
  onStatusFilterChange,
  page,
  limit,
  onLimitChange,
  hasNextPage,
  onPrevPage,
  onNextPage,
  loading,
}) {
  const { included, excluded } = editor.counts;
  const visibleRows = filterRowsByStatus(rows, statusFilter, editor);

  return (
    <EditorListPane
      loading={loading}
      isEmpty={visibleRows.length === 0}
      activeKey={activeKey}
      footer={
        <>
          <button type="button" className={btnSm} onClick={onPrevPage} disabled={page === 0}>
            Prev
          </button>
          <span className="text-xs text-paper/60">Page {page + 1}</span>
          <button type="button" className={btnSm} onClick={onNextPage} disabled={!hasNextPage}>
            Next
          </button>
        </>
      }
      header={
        <>
          <div className="flex items-center justify-between gap-2 text-xs text-paper/70">
            <span>
              {included} kept &middot; {excluded} skipped
            </span>
            <Dropdown
              value={limit}
              options={PAGE_SIZE_OPTIONS}
              onChange={onLimitChange}
              triggerClassName={`${select} w-auto px-1.5 py-1 text-xs`}
              listLabel="Rows per page"
            />
          </div>
          <Dropdown
            value={statusFilter}
            options={STATUS_OPTIONS}
            onChange={onStatusFilterChange}
            triggerClassName={`w-full ${select} text-sm`}
            listLabel="Filter rows by decision"
          />
        </>
      }
    >
      <ul>
        {visibleRows.map((row) => {
          const key = `${row.rowType}:${row.id}`;
          const state = editor.stateOf(row.rowType, row.id);
          const mark = markState(state);
          const isActive = key === activeKey;
          const memo = getMemo(row.rowType, row.id);
          return (
            <li
              key={key}
              tabIndex={0}
              aria-current={isActive || undefined}
              data-active-row={isActive || undefined}
              className={`flex cursor-pointer items-start gap-2 border-b border-line-soft px-3 py-2.5 transition-colors ${
                isActive ? "bg-paper text-ink" : "hover:bg-white/5"
              }`}
              onClick={() => onSelectRow(row)}
              onKeyDown={(e) => {
                if (e.target !== e.currentTarget) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectRow(row);
                }
              }}
            >
              <span
                className={`mt-0.5 shrink-0 font-semibold ${isActive ? "text-ink" : mark.className}`}
                aria-hidden="true"
              >
                {mark.symbol}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 items-center gap-1 text-sm font-medium">
                  <span className="truncate" title={rowPreview(row)}>
                    {rowPreview(row)}
                  </span>
                  {memo && <MemoIndicator memo={memo} />}
                </div>
                <div className={`mt-0.5 text-xs ${isActive ? "text-ink/60" : "text-paper/50"}`}>
                  {row.rowType === "submission" ? "Post" : "Comment"} &middot; {row.id}
                  {editor.isAiDecided(row.rowType, row.id) && " · AI"}
                </div>
              </div>
              <div className="flex shrink-0 gap-1" onClick={(e) => e.stopPropagation()}>
                <button
                  type="button"
                  aria-label={`Keep ${row.rowType} ${row.id}`}
                  aria-pressed={state === "included"}
                  onClick={() => editor.include(row.rowType, row.id)}
                  className={`${btnSm} ${isActive ? "border-ink text-ink hover:bg-ink hover:text-paper" : ""} ${state === "included" ? (isActive ? "bg-ink text-paper" : "bg-paper text-ink") : ""}`}
                >
                  Keep
                </button>
                <button
                  type="button"
                  aria-label={`Skip ${row.rowType} ${row.id}`}
                  aria-pressed={state === "excluded"}
                  onClick={() => editor.exclude(row.rowType, row.id)}
                  className={`${btnSm} ${isActive ? "border-ink text-ink hover:bg-ink hover:text-paper" : ""} ${state === "excluded" ? (isActive ? "bg-ink text-paper" : "bg-paper text-ink") : ""}`}
                >
                  Skip
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </EditorListPane>
  );
}
