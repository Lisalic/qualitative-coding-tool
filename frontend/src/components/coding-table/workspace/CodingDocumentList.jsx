import EditorListPane from "../../editor-shell/EditorListPane";
import Dropdown from "../../primitives/Dropdown";
import { select, btnSm } from "../../../lib/uiClasses";
import { rollUpCoder } from "../../../lib/codingUtils";

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
  onSelectUncoded,
  selectAllLoading,
  loading,
}) {
  const allMatchingSelected = matchingCount > 0 && selectedItemIds?.size >= matchingCount;
  const uncodedCount = Math.max(0, (totalRows || 0) - (totalCoded || 0));

  return (
    <EditorListPane
      loading={loading}
      isEmpty={rows.length === 0}
      footer={
        <>
          <button type="button" className={btnSm} onClick={onPrevPage} disabled={disabled || page <= 0}>
            Prev
          </button>
          <span className="text-xs text-paper/60">
            {pageCount === 0 ? 0 : page + 1} / {pageCount}
          </span>
          <button
            type="button"
            className={btnSm}
            onClick={onNextPage}
            disabled={disabled || page >= pageCount - 1}
          >
            Next
          </button>
        </>
      }
      header={
        <>
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs text-paper/70">
              {totalCoded} of {totalRows} rows coded
            </div>
            <div className="flex shrink-0 gap-1.5">
              <button
                type="button"
                className={btnSm}
                onClick={onSelectUncoded}
                disabled={disabled || selectAllLoading || uncodedCount === 0}
                title="Select every row that has no codes yet -- the rows an AI recode can help with without overwriting your own work"
              >
                {`Uncoded${uncodedCount ? ` (${uncodedCount})` : ""}`}
              </button>
              <button
                type="button"
                className={btnSm}
                onClick={onSelectAll}
                disabled={disabled || selectAllLoading || matchingCount === 0 || allMatchingSelected}
                title={
                  matchingCount > 0 ? `Select all ${matchingCount} rows matching the current filter/search` : undefined
                }
              >
                {selectAllLoading ? "Selecting..." : `Select all${matchingCount ? ` (${matchingCount})` : ""}`}
              </button>
            </div>
          </div>
          <input
            type="search"
            value={searchInput}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search..."
            className={select}
            disabled={disabled}
          />
          <Dropdown
            value={onlyFilter}
            options={ONLY_OPTIONS}
            onChange={onOnlyChange}
            disabled={disabled}
            triggerClassName={`w-full ${select}`}
            listLabel="Filter rows by coded status"
          />
          {activeFilterCode && (
            <div className="flex items-center justify-between gap-2 border border-line bg-surface-raised px-2 py-1 text-xs">
              <span className="truncate">
                Code: <strong>{activeFilterCode}</strong>
              </span>
              <button type="button" className="shrink-0 text-paper/60 hover:text-paper" onClick={onClearFilterCode}>
                ×
              </button>
            </div>
          )}
        </>
      }
    >
      <ul>
        {rows.map((row) => {
          const codeCount = Array.isArray(row.codes) ? row.codes.length : 0;
          const isActive = row.item_id === activeItemId;
          // Only surfaced when AI was actually involved -- a purely
          // hand-coded row stays as plain as it always was, matching
          // FilterRowList's "· AI" asymmetry (see rollUpCoder).
          const coderMark = rollUpCoder(row.codes);
          return (
            <li
              key={row.item_id}
              className={`flex cursor-pointer items-start gap-2 border-b border-line-soft px-3 py-2.5 transition-colors ${
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
                  {(coderMark === "ai" || coderMark === "both") &&
                    ` · ${coderMark === "both" ? "AI + Human" : "AI"}`}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </EditorListPane>
  );
}
