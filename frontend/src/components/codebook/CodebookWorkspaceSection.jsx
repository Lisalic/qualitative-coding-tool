import { useState } from "react";
import { useNavigate } from "react-router-dom";
import CodeLegend from "../coding-table/CodeLegend";
import PageEmptyState from "../primitives/PageEmptyState";
import PromptPanel from "../primitives/PromptPanel";
import PageShell from "../shell/PageShell";
import Panel from "../shell/Panel";
import { hasPromptInfo } from "../../lib/promptInfo";
import { getCodeColor } from "../../lib/codingUtils";
import { btn, btnPrimary as btnPrimaryClasses, input } from "../../lib/uiClasses";

const btnClasses = btn;
const btnPrimary = btnPrimaryClasses;
const inputClasses = input;

const noop = () => {};

/**
 * A codebook file's content is structured code rows (see
 * lib/codingUtils.js), rendered/edited via the same `CodeLegend` tree
 * component the coding workspace uses for a coding artifact's own
 * snapshot -- one editor, not two. Filtering (`onCodeToggle` outside
 * edit mode) has no meaning on this standalone page, so it's a no-op
 * here; only the coding workspace wires it to a row filter.
 *
 * `picker` is the artifact selector; it and the per-codebook actions live in
 * the PageShell toolbar. This section used to render its own centred <h1>
 * directly beneath the shell's centred page title -- two headings, plus a
 * pair of `flex-1` spacers whose only job was faking that centring.
 */
export default function CodebookWorkspaceSection({
  picker = null,
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
}) {
  const [showPrompt, setShowPrompt] = useState(false);
  const promptInfo = { systemPrompt, instructions, promptMeta };
  const [nameDraft, setNameDraft] = useState(selectedCodebookName || "");
  const navigate = useNavigate();

  if (!selectedCodebook) {
    return (
      <PageShell title="View Codebook" actions={picker} width="wide">
        <PageEmptyState message="Select a codebook to view" />
      </PageShell>
    );
  }

  const actions = (
    <>
      {picker}
      <button
        type="button"
        className={btnClasses}
        onClick={() => navigate("/compare-codebook", { state: { codebookA: selectedCodebook } })}
      >
        Compare
      </button>
      <button
        type="button"
        className={btnClasses}
        onClick={() => navigate(`/versions?ref=${encodeURIComponent(selectedCodebook)}`)}
      >
        History
      </button>
      <button
        type="button"
        className={btnClasses}
        onClick={() => navigate("/lineage", { state: { ref: selectedCodebook } })}
      >
        Lineage
      </button>
      {hasPromptInfo(promptInfo) && (
        <button type="button" className={btnClasses} onClick={() => setShowPrompt((v) => !v)}>
          {showPrompt ? "Hide" : "Show"} Prompt
        </button>
      )}
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
    </>
  );

  return (
    <PageShell
      title={selectedCodebookName || selectedCodebook}
      actions={actions}
      width="wide"
      bodyClassName="flex flex-col gap-3"
    >
      {isEditMode && (
        <div className="flex items-center gap-2.5">
          <label htmlFor="codebook-name">Name:</label>
          <input
            id="codebook-name"
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            className={inputClasses}
          />
        </div>
      )}

      {showPrompt && <PromptPanel {...promptInfo} />}

      {loading && <p className="text-paper/70">Loading...</p>}
      {error && (
        <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{error}</p>
      )}

      {saveState.status === "error" && saveState.message && (
        <div className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{saveState.message}</div>
      )}
      {saveState.status === "success" && (
        <div className="border border-success bg-success/10 px-3 py-2 text-sm text-success">Saved.</div>
      )}

      {!loading && !error && codebookTree.length === 0 && !isEditMode ? (
        <PageEmptyState message="This codebook has no codes yet." />
      ) : (
        <Panel title="Codes">
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
        </Panel>
      )}
    </PageShell>
  );
}
