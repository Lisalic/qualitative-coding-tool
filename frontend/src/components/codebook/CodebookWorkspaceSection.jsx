import { useState } from "react";
import { useNavigate } from "react-router-dom";
import CodeLegend from "../coding-table/CodeLegend";
import PageEmptyState from "../primitives/PageEmptyState";
import PromptPanel from "../primitives/PromptPanel";
import { hasPromptInfo } from "../../lib/promptInfo";
import VersionHistoryPanel from "../versioning/VersionHistoryPanel";
import useVersionHistory from "../versioning/useVersionHistory";
import { getCodeColor } from "../../lib/codingUtils";

const btnClasses =
  "border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink";
const btnPrimary =
  "border-2 border-paper px-4 py-2 text-sm font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";
const inputClasses =
  "border border-paper bg-white/5 px-2.5 py-1.5 text-paper focus:outline-none focus:ring-2 focus:ring-paper";

const noop = () => {};

/**
 * A codebook file's content is structured code rows (see
 * lib/codingUtils.js), rendered/edited via the same `CodeLegend` tree
 * component the coding workspace uses for a coding artifact's own
 * snapshot -- one editor, not two. Filtering (`onCodeToggle` outside
 * edit mode) has no meaning on this standalone page, so it's a no-op
 * here; only the coding workspace wires it to a row filter.
 */
export default function CodebookWorkspaceSection({
  selectedCodebook,
  selectedCodebookName,
  systemPrompt,
  instructions,
  promptMeta,
  codebookTree,
  loading,
  error,
  isEditMode,
  codebookDraft,
  setCodebookDraft,
  saveState,
  onBeginEdit,
  onCancelEdit,
  onSaveEdit,
  onDuplicateFrom,
}) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const promptInfo = { systemPrompt, instructions, promptMeta };
  const [nameDraft, setNameDraft] = useState(selectedCodebookName || "");
  const navigate = useNavigate();
  const history = useVersionHistory(selectedCodebook);

  if (!selectedCodebook) {
    return (
      <section className="border-2 border-paper p-6">
        <PageEmptyState message="Select a codebook file to view" />
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4 border-2 border-paper p-6">
      <div className="flex w-full items-start gap-2">
        <div className="flex-1" />
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">{selectedCodebookName || selectedCodebook}</h1>
        </div>
        <div className="flex flex-1 flex-col items-end justify-end gap-2">
          <div className="flex gap-2">
            <button
              type="button"
              className={btnClasses}
              onClick={() => navigate("/compare-codebook", { state: { codebookA: selectedCodebook } })}
            >
              Compare
            </button>
            <button type="button" className={btnClasses} onClick={() => setShowHistory((v) => !v)}>
              {showHistory ? "Hide" : "Show"} History
            </button>
            <button
              type="button"
              className={btnClasses}
              onClick={() => navigate("/lineage", { state: { ref: selectedCodebook } })}
            >
              Lineage
            </button>
            {!isEditMode ? (
              <button
                type="button"
                className={btnClasses}
                onClick={() => {
                  setNameDraft(selectedCodebookName || "");
                  onBeginEdit();
                }}
              >
                Edit
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className={btnClasses}
                  onClick={onCancelEdit}
                  disabled={saveState.status === "saving"}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className={btnPrimary}
                  onClick={() => onSaveEdit(nameDraft.trim())}
                  disabled={saveState.status === "saving"}
                >
                  {saveState.status === "saving" ? "Saving..." : "Save"}
                </button>
              </>
            )}
          </div>
          {hasPromptInfo(promptInfo) && (
            <button type="button" className={btnClasses} onClick={() => setShowPrompt((v) => !v)}>
              {showPrompt ? "Hide" : "Show"} Prompt
            </button>
          )}
        </div>
      </div>

      {isEditMode && (
        <div className="flex items-center justify-center gap-2.5">
          <label>Name:</label>
          <input
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            className={inputClasses}
          />
        </div>
      )}

      {showPrompt && (
        <div className="flex w-full justify-start">
          <PromptPanel {...promptInfo} />
        </div>
      )}

      {loading && <p className="text-paper/70">Loading...</p>}
      {error && (
        <p className="border border-error bg-error/10 px-4 py-3 text-sm text-error">{error}</p>
      )}

      {saveState.status === "error" && saveState.message && (
        <div className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{saveState.message}</div>
      )}
      {saveState.status === "success" && (
        <div className="border border-success bg-success/10 px-3 py-2 text-sm text-success">Saved.</div>
      )}

      <div className={showHistory ? "grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]" : ""}>
        {!loading && !error && codebookTree.length === 0 && !isEditMode ? (
          <PageEmptyState message="No codebook selected or found. Generate a codebook first." />
        ) : (
          <CodeLegend
            codebookTree={codebookTree}
            isEditMode={isEditMode}
            draftTree={codebookDraft}
            onDraftTreeChange={setCodebookDraft}
            disabled={saveState.status === "saving"}
            selectedFilterCodes={[]}
            onCodeToggle={noop}
            getCodeColor={getCodeColor}
            showDetails
          />
        )}
        {showHistory && (
          <div className="h-[600px]">
            <VersionHistoryPanel history={history} onDuplicateFrom={onDuplicateFrom} />
          </div>
        )}
      </div>
    </section>
  );
}
