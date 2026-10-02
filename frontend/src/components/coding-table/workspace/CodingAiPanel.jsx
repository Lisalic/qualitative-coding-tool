import AiModelFormGroup from "../../models/AiModelFormGroup";
import PromptTextareaWithActions from "../../forms/PromptTextareaWithActions";
import ProgressBar from "../../feedback/ProgressBar";
import { EXAMPLE_PROMPTS } from "../../../lib/apiContracts";
import { btnPrimary, btnSm } from "../../../lib/uiClasses";

/**
 * The right rail's "AI Coding" tab: code documents with the AI, as a
 * first-class mode next to the codebook rather than a disclosure hidden
 * at the rail's foot. Always visible, even with nothing selected -- the
 * quick-select buttons are how most runs start ("code everything still
 * uncoded"), and ticking rows in the document list works too.
 *
 * It always runs over an explicit row selection rather than a sampled
 * percentage of the corpus, so it has no sample-size or content-scope
 * fields. `POST /api/coding/{ref}/recode` replaces only the selected
 * rows' coding, staged into the session like a manual edit rather than
 * committed outright -- see `useViewCodingPage.handleRecodeSelected`.
 */
export default function CodingAiPanel({
  selectedCount,
  matchingCount,
  hasActiveDocument,
  onSelectAll,
  onSelectUncoded,
  onSelectThisDocument,
  onClearSelection,
  selectAllLoading,
  model,
  onModelChange,
  methodology,
  onMethodologyChange,
  onRecode,
  loading,
  progress,
  error,
  summary,
}) {
  const busy = loading || selectAllLoading;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-paper/70">
        Apply the codebook to documents with AI. Results are staged for review -- nothing is saved until you
        click Save.
      </p>

      <div className="flex flex-col gap-2 border border-line bg-surface-raised px-2.5 py-2">
        <div className="text-sm">
          <span className="font-semibold">{selectedCount}</span> document{selectedCount === 1 ? "" : "s"} selected
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button type="button" className={btnSm} onClick={onSelectUncoded} disabled={busy}>
            Select uncoded
          </button>
          <button type="button" className={btnSm} onClick={onSelectAll} disabled={busy}>
            Select all{matchingCount != null ? ` (${matchingCount})` : ""}
          </button>
          <button type="button" className={btnSm} onClick={onSelectThisDocument} disabled={busy || !hasActiveDocument}>
            This document
          </button>
          {selectedCount > 0 && (
            <button type="button" className={btnSm} onClick={onClearSelection} disabled={busy}>
              Clear
            </button>
          )}
        </div>
      </div>

      <AiModelFormGroup
        model={model}
        onModelChange={onModelChange}
        disabled={loading}
        selectPlaceholder="dash"
        label="Model"
      />

      <PromptTextareaWithActions
        id="codingRecodeMethodology"
        label="Methodology"
        value={methodology}
        onChange={onMethodologyChange}
        placeholder="Optional instructions for the classifier"
        rows={3}
        promptType="apply"
        exampleText={EXAMPLE_PROMPTS.apply}
        disabled={loading}
      />

      <button type="button" className={btnPrimary} onClick={onRecode} disabled={loading || selectedCount === 0}>
        {loading
          ? "Coding…"
          : selectedCount > 0
            ? `Code ${selectedCount} document${selectedCount === 1 ? "" : "s"} with AI`
            : "Code with AI"}
      </button>
      {selectedCount === 0 && !loading && (
        <p className="text-xs text-paper/50">Tick documents in the list, or use the buttons above.</p>
      )}

      {loading && progress && (
        <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
      )}

      {error && <div className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{error}</div>}

      {!error && summary && (
        <div className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/80">{summary}</div>
      )}
    </div>
  );
}
