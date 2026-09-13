import AiModelFormGroup from "../../models/AiModelFormGroup";
import PromptTextareaWithActions from "../../forms/PromptTextareaWithActions";
import ProgressBar from "../../feedback/ProgressBar";
import { EXAMPLE_PROMPTS } from "../../../lib/apiContracts";
import { btnPrimary, btnSm } from "../../../lib/uiClasses";

/**
 * Compact panel shown at the bottom of the document list whenever at
 * least one row is checked: pick a model (and optional methodology),
 * then re-run the AI classifier over just the selected rows
 * (`POST /api/coding/{ref}/recode`), replacing only their coding. Always
 * stacked vertically -- it lives in a narrow sidebar column, not a
 * full-width bar.
 */
export default function CodingRecodeBar({
  selectedCount,
  model,
  onModelChange,
  methodology,
  onMethodologyChange,
  onRecode,
  onClearSelection,
  loading,
  progress,
  error,
  summary,
}) {
  if (!selectedCount) return null;

  return (
    <div className="flex flex-col gap-2.5 border-t-2 border-line-strong bg-ink p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">
          {selectedCount} selected
        </div>
        <button type="button" className={btnSm} onClick={onClearSelection} disabled={loading}>
          Clear
        </button>
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
        rows={2}
        promptType="apply"
        exampleText={EXAMPLE_PROMPTS.apply}
        disabled={loading}
      />

      <button type="button" className={`w-full ${btnPrimary}`} onClick={onRecode} disabled={loading}>
        {loading ? "Recoding…" : "Recode with AI"}
      </button>

      {loading && progress && (
        <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
      )}

      {error && (
        <div className="border border-error bg-error/10 px-2.5 py-2 text-xs text-error">{error}</div>
      )}

      {!error && summary && (
        <div className="border border-line bg-surface-raised px-2.5 py-2 text-xs text-paper/80">{summary}</div>
      )}
    </div>
  );
}
