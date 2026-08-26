import AiModelFormGroup from "../../models/AiModelFormGroup";
import ProgressBar from "../../feedback/ProgressBar";

const inputClasses =
  "border border-paper bg-white/5 px-2.5 py-2 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";
const btnClasses =
  "w-full border-2 border-paper px-3 py-2 text-sm font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";
const btnSmall =
  "border border-paper px-2.5 py-1.5 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

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
    <div className="flex flex-col gap-2.5 border-t-2 border-paper bg-ink p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold">
          {selectedCount} selected
        </div>
        <button type="button" className={btnSmall} onClick={onClearSelection} disabled={loading}>
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

      <input
        type="text"
        className={inputClasses}
        value={methodology}
        onChange={(e) => onMethodologyChange(e.target.value)}
        placeholder="Methodology (optional)"
        disabled={loading}
      />

      <button type="button" className={btnClasses} onClick={onRecode} disabled={loading}>
        {loading ? "Recoding..." : "Recode with AI"}
      </button>

      {loading && progress && (
        <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
      )}

      {error && (
        <div className="border border-error bg-error/10 px-2.5 py-2 text-xs text-error">{error}</div>
      )}

      {!error && summary && (
        <div className="border border-paper/30 bg-white/5 px-2.5 py-2 text-xs text-paper/80">{summary}</div>
      )}
    </div>
  );
}
