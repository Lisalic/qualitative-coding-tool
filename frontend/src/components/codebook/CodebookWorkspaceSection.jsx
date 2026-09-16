import { useState } from "react";
import { useNavigate } from "react-router-dom";
import CodeLegend from "../coding-table/CodeLegend";
import ExportDropdown from "../export/ExportDropdown";
import PageEmptyState from "../primitives/PageEmptyState";
import PromptPanel from "../primitives/PromptPanel";
import PageShell from "../shell/PageShell";
import Panel from "../shell/Panel";
import { getCodeColor } from "../../lib/codingUtils";
import { hasPromptInfo } from "../../lib/promptInfo";
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
  const isSaving = saveState?.status === "saving";

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
        onClick={() => navigate("/integrate-codebook", { state: { codebookA: selectedCodebook } })}
      >
        Integrate
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
      <ExportDropdown fileId={selectedCodebook} artifactType="codebook" />
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
            className={btnPrimary}
            onClick={() => onSaveEdit(nameDraft.trim() || undefined)}
            disabled={isSaving}
          >
            {isSaving ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            className={btnClasses}
            onClick={onCancelEdit}
            disabled={isSaving}
          >
            Cancel
          </button>
        </>
      )}
    </>
  );

  return (
    <PageShell
      title={selectedCodebookName || "View Codebook"}
      actions={actions}
      width="wide"
      bodyClassName="flex flex-col gap-3"
    >
      {showPrompt && (
        <PromptPanel {...promptInfo} />
      )}
      {saveState?.status === "error" && saveState.message && (
        <div className="border border-line bg-paper px-3 py-2 text-sm text-ink font-mono">
          {saveState.message}
        </div>
      )}
      {error && (
        <div className="border border-line bg-paper px-3 py-2 text-sm text-ink font-mono">
          {error}
        </div>
      )}
      <Panel title={isEditMode ? "Edit Codebook" : "Codebook Contents"}>
        {loading ? (
          <div className="text-sm text-paper/60 py-4">Loading codebook…</div>
        ) : isEditMode ? (
          <div className="flex flex-col gap-3">
            <div>
              <label className="block text-xs uppercase tracking-wider text-paper/60 font-semibold mb-1">
                Codebook Name
              </label>
              <input
                type="text"
                className={inputClasses}
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
              />
            </div>
            <CodeLegend
              codebookTree={codebookDraft}
              isEditMode
              draftTree={codebookDraft}
              onDraftTreeChange={setCodebookDraft}
              disabled={isSaving}
              selectedFilterCodes={[]}
              onCodeToggle={noop}
              getCodeColor={getCodeColor}
              showDetails
            />
          </div>
        ) : (
          <CodeLegend
            codebookTree={codebookTree}
            selectedFilterCodes={[]}
            onCodeToggle={noop}
            getCodeColor={getCodeColor}
            showDetails
          />
        )}
      </Panel>
    </PageShell>
  );
}
