import CodeLegend from "../CodeLegend";

const btnSmall =
  "border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

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
 * The Edit/Done toggle only switches PRESENTATION -- which of
 * CodeLegend's two renderings (editable rows vs. filter/tag rows) is on
 * screen -- it is not a save boundary any more. `draftTree` is the same
 * live draft whichever mode is showing (see useViewCodingPage's
 * docstring), so a code added in edit mode is immediately taggable after
 * hitting Done, with nothing saved yet. "Cancel" reverts the draft to
 * the last-saved codebook and drops back to the read-only view; "Done"
 * just drops back to the read-only view, keeping the draft as-is for
 * whenever the bottom bar's Save Changes runs. A code renamed here is
 * not retroactively renamed on rows already tagged with its old name --
 * see useViewCodingPage's module docstring for that trade-off.
 */
export default function CodingCodebookSidebar({
  codebookTree,
  getCodeColor,
  pendingSelection,
  onApplyCode,
  activeFilterCode,
  onToggleFilterCode,
  isEditMode,
  isDirty,
  draftTree,
  onDraftTreeChange,
  onBeginEdit,
  onFinishEdit,
  onCancelEdit,
}) {
  const handleCodeToggle = ({ code_uid: codeUid, name }) => {
    if (pendingSelection) {
      // Tagging needs the stable identity.
      onApplyCode(codeUid);
      return;
    }
    // The server-side row filter (`GET /api/coding/{ref}/rows?code=`) is
    // still name-based.
    onToggleFilterCode(name);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-y-auto border border-paper p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">
          Codebook
          {isDirty && <span className="ml-1.5 text-xs font-normal text-paper/50">(edited)</span>}
        </h3>
        {!isEditMode ? (
          <button type="button" className={btnSmall} onClick={onBeginEdit}>
            Edit
          </button>
        ) : (
          <div className="flex gap-1.5">
            <button type="button" className={btnSmall} onClick={onCancelEdit}>
              Cancel
            </button>
            <button type="button" className={btnSmall} onClick={onFinishEdit}>
              Done
            </button>
          </div>
        )}
      </div>

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
        selectedFilterCodes={!isEditMode && activeFilterCode ? [activeFilterCode] : []}
        onCodeToggle={handleCodeToggle}
        getCodeColor={getCodeColor}
      />
    </div>
  );
}
