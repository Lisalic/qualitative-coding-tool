import MemoEditor from "../data/MemoEditor";
import Panel from "../shell/Panel";
import PageEmptyState from "../primitives/PageEmptyState";
import { btn, btnActive } from "../../lib/uiClasses";

/**
 * Center pane: the active row's full text, the one place it's shown in
 * full (the list keeps to a short preview). Keep/Skip live here, next to
 * what they decide, rather than only in the list's compact buttons --
 * reading the whole thing is exactly when a first impression might
 * change.
 */
export default function FilterReaderPane({ activeRow, state, isAiAdded, onInclude, onExclude, memo, onSaveMemo }) {
  if (!activeRow) {
    return (
      <Panel className="h-full">
        <PageEmptyState message="Select a row from the list to read it." />
      </Panel>
    );
  }

  const { rowType, id } = activeRow;
  const title = rowType === "submission" ? activeRow.title : null;
  const body = rowType === "submission" ? activeRow.selftext : activeRow.body;

  return (
    <Panel key={`${rowType}:${id}`} className="h-full" bodyClassName="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide text-paper/50">
            {rowType === "submission" ? "Post" : "Comment"} &middot; {id}
            {isAiAdded && (
              <span className="ml-2 border border-paper/40 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-paper/70">
                AI added
              </span>
            )}
          </div>
          {title && <h3 className="mt-0.5 text-lg font-semibold">{title}</h3>}
          {activeRow.author && <div className="mt-0.5 text-xs text-paper/50">by {activeRow.author}</div>}
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button
            type="button"
            className={`${btn} ${state === "included" ? btnActive : ""}`}
            aria-pressed={state === "included"}
            onClick={() => onInclude(rowType, id)}
          >
            Keep
          </button>
          <button
            type="button"
            className={`${btn} ${state === "excluded" ? btnActive : ""}`}
            aria-pressed={state === "excluded"}
            onClick={() => onExclude(rowType, id)}
          >
            Skip
          </button>
        </div>
      </div>

      <div className="whitespace-pre-wrap text-sm text-paper/90">{body || "(no content)"}</div>

      <MemoEditor
        key={`${rowType}:${id}`}
        memo={memo}
        onSave={(saveBody) => onSaveMemo(rowType, id, saveBody)}
      />
    </Panel>
  );
}
