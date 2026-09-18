import { useState } from "react";
import CodeLegend from "../CodeLegend";
import Panel from "../../shell/Panel";
import CodingCoverageDashboard from "./CodingCoverageDashboard";
import { btnSm } from "../../../lib/uiClasses";

function truncate(text, max = 60) {
  const value = String(text || "");
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

/**
 * Right rail: dual-mode sidebar supporting Codebook browsing/editing
 * and descriptive Corpus Coverage analytics.
 */
export default function CodingCodebookSidebar({
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
  const [activeTab, setActiveTab] = useState("codebook");

  const handleCodeToggle = ({ code_uid: codeUid, name }) => {
    if (pendingSelection) {
      onApplyCode(codeUid);
      return;
    }
    onToggleFilterCode(name);
  };

  const title = (
    <div className="flex items-center gap-3">
      <button
        type="button"
        className={`text-xs font-semibold uppercase tracking-wider pb-0.5 border-b-2 transition-colors ${
          activeTab === "codebook"
            ? "border-paper text-paper"
            : "border-transparent text-paper/50 hover:text-paper"
        }`}
        onClick={() => setActiveTab("codebook")}
      >
        Codebook
      </button>
      <button
        type="button"
        className={`text-xs font-semibold uppercase tracking-wider pb-0.5 border-b-2 transition-colors ${
          activeTab === "coverage"
            ? "border-paper text-paper"
            : "border-transparent text-paper/50 hover:text-paper"
        }`}
        onClick={() => setActiveTab("coverage")}
      >
        Coverage
      </button>
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
      {activeTab === "coverage" ? (
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
