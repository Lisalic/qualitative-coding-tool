import { useState } from "react";
import AiModelFormGroup from "../../models/AiModelFormGroup";
import PromptTextareaWithActions from "../../forms/PromptTextareaWithActions";
import ProgressBar from "../../feedback/ProgressBar";
import { EXAMPLE_PROMPTS } from "../../../lib/apiContracts";
import { btnPrimary, btnSm } from "../../../lib/uiClasses";

/**
 * The AI recode tool, at the foot of the right rail -- styled and
 * positioned like the filter and codebook editors' `AiAssistPanel` (same
 * collapsed-by-default disclosure, same progress/error/message chrome),
 * even though its semantics stay its own: it always runs over an
 * explicit row selection rather than a sampled percentage of the corpus,
 * so it has no sample-size or content-scope fields, and stays hidden
 * entirely until at least one row is checked -- recoding nothing isn't a
 * state worth showing a disclosure for.
 *
 * `POST /api/coding/{ref}/recode` replaces only the selected rows'
 * coding, staged into the session like a manual edit rather than
 * committed outright -- see `useViewCodingPage.handleRecodeSelected`.
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
  const [open, setOpen] = useState(false);
  if (!selectedCount) return null;

  return (
    <div className="border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-surface-raised"
        aria-expanded={open}
      >
        <span className="text-sm font-medium">Recode with AI ({selectedCount} selected)</span>
        <span className="text-sm text-paper/60">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="flex flex-col gap-3 border-t border-line p-3">
          <button type="button" className={`self-start ${btnSm}`} onClick={onClearSelection} disabled={loading}>
            Clear selection
          </button>

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

          <button type="button" className={btnPrimary} onClick={onRecode} disabled={loading}>
            {loading ? "Recoding…" : "Recode with AI"}
          </button>

          {loading && progress && (
            <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
          )}

          {error && (
            <div className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{error}</div>
          )}

          {!error && summary && (
            <div className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/80">{summary}</div>
          )}
        </div>
      )}
    </div>
  );
}
