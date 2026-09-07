import Panel from "../shell/Panel";
import MemoIndicator from "../data/MemoIndicator";
import { btnSm, select } from "../../lib/uiClasses";

const PAGE_SIZES = [10, 25, 50, 100];

function preview(text, limit = 320) {
  const value = String(text || "").trim();
  if (value.length <= limit) return value;
  return `${value.slice(0, limit).trimEnd()}...`;
}

function Row({ row, rowType, memo, onOpen }) {
  const title = rowType === "submission" ? row.title : null;
  const body = rowType === "submission" ? row.selftext : row.body;

  return (
    <button
      type="button"
      onClick={() => onOpen(row, rowType)}
      className="w-full border border-line bg-white/5 p-2.5 text-left transition-colors hover:bg-white/10"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-xs uppercase tracking-wide text-paper/50">
          {rowType === "submission" ? "Post" : "Comment"}
          {row.author ? ` · ${row.author}` : ""}
        </span>
        {memo ? <MemoIndicator memo={memo} /> : null}
      </div>
      {title ? <div className="mt-1 truncate text-sm font-semibold">{title}</div> : null}
      {body ? (
        <p className="mt-1 whitespace-pre-wrap text-xs text-paper/70">{preview(body)}</p>
      ) : null}
    </button>
  );
}

/**
 * The corpus, alongside the codebook being written from it.
 *
 * Read-only on purpose: unlike the filter editor, where every row carries
 * a keep/skip decision, nothing here is decided per row -- the researcher
 * is reading for themes, and the artifact being built is the code list on
 * the other side of the screen. Clicking a row opens the same `EntryModal`
 * the data viewer and filter editor use, where its full text and its memo
 * live.
 */
export default function CodebookSourceReader({
  entries,
  loading,
  page,
  limit,
  onPageChange,
  onLimitChange,
  getMemo,
  onOpenRow,
}) {
  const submissions = entries?.submissions || [];
  const comments = entries?.comments || [];
  const totalSubmissions = entries?.total_submissions || 0;
  const totalComments = entries?.total_comments || 0;
  const hasNextPage =
    totalSubmissions > (page + 1) * limit || totalComments > (page + 1) * limit;

  return (
    <Panel
      title="Source data"
      actions={
        <>
          <span className="text-xs text-paper/50">
            {totalSubmissions} posts · {totalComments} comments
          </span>
          <select
            aria-label="Rows per page"
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
            className={`${select} py-1 text-xs`}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size} / page
              </option>
            ))}
          </select>
        </>
      }
      bodyClassName="flex flex-col gap-2"
    >
      {loading ? <p className="text-sm text-paper/60">Loading rows...</p> : null}

      {!loading && submissions.length === 0 && comments.length === 0 ? (
        <p className="text-sm text-paper/60">No rows on this page.</p>
      ) : null}

      {submissions.map((row) => (
        <Row
          key={`submission-${row.id}`}
          row={row}
          rowType="submission"
          memo={getMemo("submission", row.id)}
          onOpen={onOpenRow}
        />
      ))}
      {comments.map((row) => (
        <Row
          key={`comment-${row.id}`}
          row={row}
          rowType="comment"
          memo={getMemo("comment", row.id)}
          onOpen={onOpenRow}
        />
      ))}

      <div className="flex items-center justify-between gap-2 pt-1">
        <button
          type="button"
          className={btnSm}
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0 || loading}
        >
          Previous
        </button>
        <span className="text-xs text-paper/50">Page {page + 1}</span>
        <button
          type="button"
          className={btnSm}
          onClick={() => onPageChange(page + 1)}
          disabled={!hasNextPage || loading}
        >
          Next
        </button>
      </div>
    </Panel>
  );
}
