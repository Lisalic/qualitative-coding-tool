import CodeLegend from "../CodeLegend";

const btnSmall =
  "border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";
const btnPrimary =
  "border-2 border-paper px-2.5 py-1 text-xs font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

function truncate(text, max = 60) {
  const value = String(text || "");
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

/**
 * Right rail: the codebook, dual-purpose depending on context. With no
 * text selected in the reader pane, clicking a code filters the document
 * list to rows carrying it (server-side, across the whole artifact, not
 * just the loaded page). With a pending text selection, clicking a code
 * instead tags that selection onto the active document -- the sidebar
 * equivalent of the code-picker popup that appears at the selection
 * itself (see HighlightedContent), for discoverability.
 *
 * Renaming/adding/removing families and codes is a separate explicit
 * edit/save step (unlike row tagging, which auto-saves per action) since
 * it's a batch of related changes composed together, not a single
 * one-off. A code renamed here is not retroactively renamed on rows
 * already tagged with its old name -- see useViewCodingPage's module
 * docstring for that trade-off.
 */
export default function CodingCodebookSidebar({
  codebookTree,
  getCodeColor,
  pendingSelection,
  onApplyCode,
  activeFilterCode,
  onToggleFilterCode,
  isEditMode,
  draftTree,
  onDraftTreeChange,
  saveState,
  onBeginEdit,
  onCancelEdit,
  onSaveEdit,
}) {
  const handleCodeToggle = (code) => {
    if (pendingSelection) {
      onApplyCode(code);
      return;
    }
    onToggleFilterCode(code);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-y-auto border border-paper p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Codebook</h3>
        {!isEditMode ? (
          <button type="button" className={btnSmall} onClick={onBeginEdit}>
            Edit
          </button>
        ) : (
          <div className="flex gap-1.5">
            <button type="button" className={btnSmall} onClick={onCancelEdit} disabled={saveState.status === "saving"}>
              Cancel
            </button>
            <button
              type="button"
              className={btnPrimary}
              onClick={onSaveEdit}
              disabled={saveState.status === "saving"}
            >
              {saveState.status === "saving" ? "Saving..." : "Save"}
            </button>
          </div>
        )}
      </div>

      {saveState.status === "error" && saveState.message && (
        <div className="border border-error bg-error/10 px-2 py-1.5 text-xs text-error">{saveState.message}</div>
      )}
      {saveState.status === "success" && (
        <div className="border border-success bg-success/10 px-2 py-1.5 text-xs text-success">Saved.</div>
      )}

      {!isEditMode && pendingSelection && (
        <div className="border border-paper bg-white/5 px-2.5 py-2 text-xs">
          Tagging &ldquo;{truncate(pendingSelection.text)}&rdquo; &mdash; click a code below.
        </div>
      )}

      <CodeLegend
        codebookTree={codebookTree}
        isEditMode={isEditMode}
        draftTree={draftTree}
        onDraftTreeChange={onDraftTreeChange}
        disabled={saveState.status === "saving"}
        selectedFilterCodes={!isEditMode && activeFilterCode ? [activeFilterCode] : []}
        onCodeToggle={handleCodeToggle}
        getCodeColor={getCodeColor}
      />
    </div>
  );
}
