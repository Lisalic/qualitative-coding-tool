import MemoIndicator from "../data/MemoIndicator";
import { input, btnSm } from "../../lib/uiClasses";

const PAGE_SIZES = [10, 25, 50, 100, 200];

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
  const { included, excluded, undecided } = editor.counts;
  const visibleRows = rows.filter((row) => {
    if (statusFilter === "all") return true;
    return editor.stateOf(row.rowType, row.id) === statusFilter;
  });

  return (
    <div className="flex h-full min-h-0 flex-col border border-line bg-surface">
      <div className="flex shrink-0 flex-col gap-2 border-b border-line p-2.5">
        <div className="flex items-center justify-between gap-2 text-xs text-paper/70">
          <span>
            {included} kept &middot; {excluded} skipped &middot; {undecided} undecided
          </span>
          <select
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            className={`${input} w-auto px-1.5 py-1 text-xs`}
            aria-label="Rows per page"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size} / page
              </option>
            ))}
          </select>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => onStatusFilterChange(e.target.value)}
          className={`${input} text-sm`}
          aria-label="Filter rows by decision"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-3 text-sm text-paper/60">Loading rows...</div>
        ) : visibleRows.length === 0 ? (
          <div className="p-3 text-sm text-paper/60">No rows match.</div>
        ) : (
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
                  className={`flex cursor-pointer items-start gap-2 border-b border-line-soft px-3 py-2.5 transition-colors ${
                    isActive ? "bg-paper text-ink" : "hover:bg-white/5"
                  }`}
                  onClick={() => onSelectRow(row)}
                >
                  <span
                    className={`mt-0.5 shrink-0 font-semibold ${isActive ? "text-ink" : mark.className}`}
                    aria-hidden="true"
                  >
                    {mark.symbol}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {rowPreview(row)}
                      {memo && <MemoIndicator memo={memo} />}
                    </div>
                    <div className={`mt-0.5 text-xs ${isActive ? "text-ink/60" : "text-paper/50"}`}>
                      {row.rowType === "submission" ? "Post" : "Comment"} &middot; {row.id}
                      {editor.isAiAdded(row.rowType, row.id) && " · AI"}
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
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-line p-2">
        <button type="button" className={btnSm} onClick={onPrevPage} disabled={page === 0}>
          Prev
        </button>
        <span className="text-xs text-paper/60">Page {page + 1}</span>
        <button type="button" className={btnSm} onClick={onNextPage} disabled={!hasNextPage}>
          Next
        </button>
      </div>
    </div>
  );
}
