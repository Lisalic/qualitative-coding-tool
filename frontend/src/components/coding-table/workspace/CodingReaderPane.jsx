import { useState } from "react";
import HighlightedContent from "../HighlightedContent";
import PageEmptyState from "../../primitives/PageEmptyState";

const btnSmall =
  "border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

function AppliedCodeRow({ entry, getCodeColor, onRemove, onUpdateNotes }) {
  const [notesDraft, setNotesDraft] = useState(entry.notes || "");
  const [editingNotes, setEditingNotes] = useState(false);

  const commitNotes = () => {
    setEditingNotes(false);
    if (notesDraft !== (entry.notes || "")) onUpdateNotes(notesDraft);
  };

  return (
    <div className="flex flex-col gap-1 border border-paper/20 bg-white/[0.03] px-2.5 py-2">
      <div className="flex items-start gap-2">
        <span
          className="mt-0.5 h-2.5 w-2.5 shrink-0"
          style={{ backgroundColor: getCodeColor(entry.code_uid) }}
        />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">{entry.code}</div>
          <div className="truncate text-xs italic text-paper/60" title={entry.quote}>
            &ldquo;{entry.quote}&rdquo;
          </div>
        </div>
        <button
          type="button"
          className="shrink-0 text-paper/50 hover:text-error"
          onClick={onRemove}
          aria-label={`Remove ${entry.code}`}
          title="Remove code"
        >
          ×
        </button>
      </div>
      {editingNotes ? (
        <input
          autoFocus
          type="text"
          value={notesDraft}
          onChange={(e) => setNotesDraft(e.target.value)}
          onBlur={commitNotes}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            if (e.key === "Escape") {
              setNotesDraft(entry.notes || "");
              setEditingNotes(false);
            }
          }}
          placeholder="Add a note..."
          className="border border-paper bg-white/5 px-2 py-1 text-xs text-paper placeholder:text-paper/40 focus:outline-none focus:ring-1 focus:ring-paper"
        />
      ) : (
        <button
          type="button"
          className="self-start text-xs text-paper/50 underline decoration-dotted hover:text-paper"
          onClick={() => setEditingNotes(true)}
        >
          {entry.notes ? entry.notes : "+ note"}
        </button>
      )}
    </div>
  );
}

/**
 * Center pane: the active document's full title/content (with inline
 * evidence highlighting) plus the list of codes applied to it. This is
 * the one thing on screen that shows full post/comment text -- unlike
 * the old table, which stacked every visible row's full text at once.
 */
export default function CodingReaderPane({
  activeRow,
  availableCodes,
  getCodeColor,
  pendingSelection,
  onSelectionChange,
  onApplyCode,
  onRemoveEntry,
  onUpdateNotes,
  onRecodeThisDocument,
  isAiProposed,
}) {
  if (!activeRow) {
    return <PageEmptyState message="Select a row from the list to read and code it." />;
  }

  const codes = Array.isArray(activeRow.codes) ? activeRow.codes : [];

  return (
    <div
      key={activeRow.item_id}
      className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto border border-paper p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide text-paper/50">
            {activeRow.row_type === "comment" ? "Comment" : "Post"} &middot; {activeRow.item_id}
            {isAiProposed && (
              <span className="ml-2 border border-paper/40 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-paper/70">
                AI proposal
              </span>
            )}
          </div>
          {activeRow.title && <h3 className="mt-0.5 text-lg font-semibold">{activeRow.title}</h3>}
        </div>
        <button type="button" className={`${btnSmall} shrink-0`} onClick={onRecodeThisDocument}>
          Recode with AI
        </button>
      </div>

      <HighlightedContent
        content={activeRow.content || ""}
        codeEvidence={codes}
        getCodeColor={getCodeColor}
        availableCodes={availableCodes}
        onApplyCode={onApplyCode}
        pendingSelection={pendingSelection}
        onSelectionChange={onSelectionChange}
      />

      <div>
        <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-paper/50">
          Applied codes ({codes.length})
        </div>
        {codes.length === 0 ? (
          <div className="text-sm text-paper/50">
            Not coded yet. Select text above and pick a code to tag it.
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {codes.map((entry, index) => (
              <AppliedCodeRow
                key={`${entry.code_uid}-${index}`}
                entry={entry}
                getCodeColor={getCodeColor}
                onRemove={() => onRemoveEntry(index)}
                onUpdateNotes={(notes) => onUpdateNotes(index, notes)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Rendered AFTER the content, not above it -- appearing here can't
          shift the position of the text the popup is already anchored
          to (see HighlightedContent's module comment for why that used
          to make the popup jump the instant it opened). */}
      {pendingSelection && (
        <div className="border border-paper bg-white/5 px-3 py-2 text-sm">
          Text selected &mdash; pick a code from the popup or the codebook on the right to tag it.
          <button
            type="button"
            className="ml-2 text-paper/60 underline hover:text-paper"
            onClick={() => onSelectionChange(null)}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
