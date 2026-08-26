import CodingRecodeBar from "./CodingRecodeBar";

const inputClasses =
  "border border-paper bg-white/5 px-2.5 py-1.5 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";
const btnSmall =
  "border border-paper px-2 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

const ONLY_OPTIONS = [
  { value: "all", label: "All rows" },
  { value: "coded", label: "Coded" },
  { value: "uncoded", label: "Uncoded" },
];

function rowPreview(row) {
  if (row.title) return row.title;
  const content = String(row.content || "").trim();
  return content ? content.slice(0, 80) : "(empty)";
}

/**
 * Left rail of the View Coding workspace: every submission/comment the
 * coding artifact owns, coded or not, as a compact scannable list --
 * title/snippet plus a coded-count pill, not the full post text (that's
 * what the reader pane in the center is for). Clicking a row makes it
 * the active document; the checkbox is a separate multi-select for AI
 * recode, independent of which document is currently being read.
 */
export default function CodingDocumentList({
  rows,
  activeItemId,
  onSelectItem,
  selectedItemIds,
  onToggleItemSelected,
  onlyFilter,
  onOnlyChange,
  searchInput,
  onSearchChange,
  page,
  pageCount,
  onPrevPage,
  onNextPage,
  activeFilterCode,
  onClearFilterCode,
  totalRows,
  totalCoded,
  matchingCount,
  disabled,
  onSelectAll,
  selectAllLoading,
  recodeProps,
}) {
  const allMatchingSelected = matchingCount > 0 && selectedItemIds?.size >= matchingCount;
  return (
    <div className="flex h-full min-h-0 flex-col border border-paper">
      <div className="flex flex-col gap-2 border-b border-paper/30 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-paper/70">
            {totalCoded} of {totalRows} rows coded
          </div>
          <button
            type="button"
            className={btnSmall}
            onClick={onSelectAll}
            disabled={disabled || selectAllLoading || matchingCount === 0 || allMatchingSelected}
            title={
              matchingCount > 0 ? `Select all ${matchingCount} rows matching the current filter/search` : undefined
            }
          >
            {selectAllLoading ? "Selecting..." : `Select all${matchingCount ? ` (${matchingCount})` : ""}`}
          </button>
        </div>
        <input
          type="search"
          value={searchInput}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search..."
          className={inputClasses}
          disabled={disabled}
        />
        <select
          value={onlyFilter}
          onChange={(e) => onOnlyChange(e.target.value)}
          className={inputClasses}
          disabled={disabled}
          aria-label="Filter rows by coded status"
        >
          {ONLY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {activeFilterCode && (
          <div className="flex items-center justify-between gap-2 border border-paper/40 bg-white/5 px-2 py-1 text-xs">
            <span className="truncate">
              Code: <strong>{activeFilterCode}</strong>
            </span>
            <button type="button" className="shrink-0 text-paper/60 hover:text-paper" onClick={onClearFilterCode}>
              ×
            </button>
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.length === 0 ? (
          <div className="p-3 text-sm text-paper/60">No rows match.</div>
        ) : (
          <ul>
            {rows.map((row) => {
              const codeCount = Array.isArray(row.codes) ? row.codes.length : 0;
              const isActive = row.item_id === activeItemId;
              return (
                <li
                  key={row.item_id}
                  className={`flex cursor-pointer items-start gap-2 border-b border-paper/10 px-3 py-2.5 transition-colors ${
                    isActive ? "bg-paper text-ink" : "hover:bg-white/5"
                  }`}
                  onClick={() => onSelectItem(row.item_id)}
                >
                  <input
                    type="checkbox"
                    className="mt-1 shrink-0"
                    checked={selectedItemIds.has(row.item_id)}
                    onClick={(e) => e.stopPropagation()}
                    onChange={() => onToggleItemSelected(row.item_id)}
                    aria-label={`Select ${row.item_id} for recode`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{rowPreview(row)}</div>
                    <div className={`mt-0.5 text-xs ${isActive ? "text-ink/60" : "text-paper/50"}`}>
                      {codeCount > 0 ? `${codeCount} code${codeCount === 1 ? "" : "s"}` : "Not coded"}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-paper/30 p-2">
        <button type="button" className={btnSmall} onClick={onPrevPage} disabled={disabled || page <= 0}>
          Prev
        </button>
        <span className="text-xs text-paper/60">
          {pageCount === 0 ? 0 : page + 1} / {pageCount}
        </span>
        <button
          type="button"
          className={btnSmall}
          onClick={onNextPage}
          disabled={disabled || page >= pageCount - 1}
        >
          Next
        </button>
      </div>

      <CodingRecodeBar {...recodeProps} />
    </div>
  );
}
