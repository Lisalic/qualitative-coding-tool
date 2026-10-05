import CodeLegend from "../CodeLegend";
import Panel from "../../shell/Panel";
import RailTabs from "../../primitives/RailTabs";
import CodingCoverageDashboard from "./CodingCoverageDashboard";
import { btnSm } from "../../../lib/uiClasses";
import DialogService from "../../feedback/DialogService";

function truncate(text, max = 60) {
  const value = String(text || "");
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

/**
 * Right rail: a three-mode sidebar -- Codebook browsing/editing, AI
 * Coding (`aiPanel`, rendered by the caller), and descriptive Corpus
 * Coverage analytics. AI Coding sits second, right after the codebook it
 * applies, because coding with AI is a primary way to use this screen.
 * The active tab is owned by the caller so other controls (the reader
 * pane's "recode this document") can switch to AI Coding.
 */
export default function CodingCodebookSidebar({
  activeTab,
  onTabChange,
  selectedCount = 0,
  aiPanel,
  schema,
  refreshKey,
  showingSaved = false,
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
  const handleCodeToggle = ({ code_uid: codeUid }) => {
    if (pendingSelection) {
      onApplyCode(codeUid);
      return;
    }
    onToggleFilterCode(codeUid);
  };

  // The tabs own the header line by themselves, so all three always fit
  // on one row; the codebook tab's Edit/Cancel/Done controls sit on their
  // own row just below it rather than competing with the tabs for width
  // (which used to wrap "Coverage" onto a second line in a narrow rail).
  const title = (
    <RailTabs
      tabs={[
        { value: "codebook", label: "Codebook" },
        { value: "ai", label: "AI Coding", count: selectedCount },
        { value: "coverage", label: "Coverage" },
      ]}
      activeTab={activeTab}
      onChange={onTabChange}
    />
  );

  // Cancel resets to the last SAVED codebook, which also undoes earlier
  // Edit -> Done rounds in this session -- not just this one -- so ask
  // whenever there are codebook edits to lose.
  const handleCancelEdit = async () => {
    if (
      isDirty &&
      !(await DialogService.confirm(
        "Discard every unsaved codebook edit in this session and go back to the saved codebook?",
        { title: "Discard codebook edits", confirmLabel: "Discard", danger: true },
      ))
    ) {
      return;
    }
    onCancelEdit();
  };

  const codebookToolbar = (
    <div className="flex shrink-0 items-center justify-between gap-2">
      <span className="text-xs text-paper/50">{isDirty ? "(edited)" : ""}</span>
      <div className="flex items-center gap-2">
        {!isEditMode ? (
          <button type="button" className={btnSm} onClick={onBeginEdit}>
            Edit
          </button>
        ) : (
          <>
            <button type="button" className={btnSm} onClick={handleCancelEdit}>
              Cancel
            </button>
            <button type="button" className={btnSm} onClick={onFinishEdit}>
              Done
            </button>
          </>
        )}
      </div>
    </div>
  );

  return (
    <Panel title={title} className="min-h-0 flex-1" bodyClassName="flex flex-col gap-2">
      {activeTab === "ai" ? (
        aiPanel
      ) : activeTab === "coverage" ? (
        <CodingCoverageDashboard
          schema={schema}
          refreshKey={refreshKey}
          showingSaved={showingSaved}
          getCodeColor={getCodeColor}
        />
      ) : (
        <>
          {codebookToolbar}

          {!isEditMode && pendingSelection && (
            <div className="shrink-0 border border-line bg-surface-raised px-2.5 py-2 text-xs">
              Click a code to tag &ldquo;{truncate(pendingSelection.text)}&rdquo;.
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
        </>
      )}
    </Panel>
  );
}
