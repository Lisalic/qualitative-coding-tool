import MemoIndicator from "../data/MemoIndicator";
import EditorListPane from "../editor-shell/EditorListPane";
import Dropdown from "../primitives/Dropdown";
import { select, btnSm } from "../../lib/uiClasses";
import { PAGE_SIZE_OPTIONS } from "../../lib/pageSizes";


function preview(row) {
  if (row.rowType === "submission") return row.title || "(untitled)";
  const body = String(row.body || "").trim();
  return body ? body.slice(0, 80) : "(empty)";
}

/**
 * Left rail: the corpus a codebook is being written from, one row per
 * post/comment as a compact scannable list -- the reader pane in the
 * center is where the full text lives. Clicking a row makes it active.
 *
 * Nothing here is decided per row (unlike the filter editor's row list):
 * the researcher is reading for themes, and the artifact being built is
 * the code list on the right.
 */
export default function CodebookSourceReader({
  rows,
  activeKey,
  onSelectRow,
  loading,
  page,
  limit,
  onLimitChange,
  hasNextPage,
  onPrevPage,
  onNextPage,
  getMemo,
}) {
  return (
    <EditorListPane
      loading={loading}
      loadingMessage="Loading rows..."
      isEmpty={rows.length === 0}
      emptyMessage="No rows on this page."
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
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-paper/70">Source data</span>
          <Dropdown
            value={limit}
            options={PAGE_SIZE_OPTIONS}
            onChange={onLimitChange}
            triggerClassName={`${select} w-auto px-1.5 py-1 text-xs`}
            listLabel="Rows per page"
          />
        </div>
      }
    >
      <ul>
        {rows.map((row) => {
          const key = `${row.rowType}:${row.id}`;
          const isActive = key === activeKey;
          const memo = getMemo(row.rowType, row.id);
          return (
            <li
              key={key}
              className={`cursor-pointer border-b border-line-soft px-3 py-2.5 transition-colors ${
                isActive ? "bg-paper text-ink" : "hover:bg-white/5"
              }`}
              onClick={() => onSelectRow(row)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`truncate text-xs uppercase tracking-wide ${isActive ? "text-ink/60" : "text-paper/50"}`}>
                  {row.rowType === "submission" ? "Post" : "Comment"}
                  {row.author ? ` · ${row.author}` : ""}
                </span>
                {memo ? <MemoIndicator memo={memo} /> : null}
              </div>
              <div className="mt-0.5 truncate text-sm font-medium">{preview(row)}</div>
            </li>
          );
        })}
      </ul>
    </EditorListPane>
  );
}
