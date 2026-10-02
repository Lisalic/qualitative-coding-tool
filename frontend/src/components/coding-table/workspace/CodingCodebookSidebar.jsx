import CodeLegend from "../CodeLegend";
import Panel from "../../shell/Panel";
import RailTabs from "../../primitives/RailTabs";
import CodingCoverageDashboard from "./CodingCoverageDashboard";
import { btnSm } from "../../../lib/uiClasses";

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
      onApplyCode(codeUid);
      return;
    }
    onToggleFilterCode(name);
  };

  const title = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <RailTabs
        tabs={[
          { value: "codebook", label: "Codebook" },
          { value: "ai", label: "AI Coding", count: selectedCount },
          { value: "coverage", label: "Coverage" },
        ]}
        activeTab={activeTab}
        onChange={onTabChange}
      />
      {isDirty && activeTab === "codebook" && (
        <span className="text-xs font-normal normal-case text-paper/50">(edited)</span>
      )}
    </div>
  );

  const actions = activeTab === "codebook" ? (
    !isEditMode ? (
      <button type="button" className={btnSm} onClick={onBeginEdit}>
        Edit
      </button>
    ) : (
      <>
        <button type="button" className={btnSm} onClick={onCancelEdit}>
          Cancel
        </button>
        <button type="button" className={btnSm} onClick={onFinishEdit}>
          Done
        </button>
      </>
    )
  ) : null;

  return (
    <Panel title={title} actions={actions} className="min-h-0 flex-1" bodyClassName="flex flex-col gap-2">
      {activeTab === "ai" ? (
        aiPanel
      ) : activeTab === "coverage" ? (
        <CodingCoverageDashboard
          schema={schema}
          refreshKey={refreshKey}
          getCodeColor={getCodeColor}
        />
      ) : (
        <>
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
