import { useEffect, useState } from "react";
import PromptTextareaWithActions from "./PromptTextareaWithActions";
import SliderField from "./SliderField";
import HelpTip from "./HelpTip";
import AiModelFormGroup from "../models/AiModelFormGroup";
import ContentScopeFormGroup from "../tool-panels/ContentScopeFormGroup";
import ProgressBar from "../feedback/ProgressBar";
import ErrorDisplay from "../feedback/ErrorDisplay";
import { fetchJobEstimate } from "../../api";
import { btn, btnPrimary } from "../../lib/uiClasses";

export default function AiAssistPanel({
  promptType,
  promptLabel = "Prompt",
  promptPlaceholder,
  exampleText,
  runLabel,
  runningLabel,
  minSamplePercentage = 1,
  contentScopeRadioName,
  showSampleSize = true,
  showContentScope = true,
  openByDefault = false,
  disabled: parentDisabled,
  onRun,
  extraActions,
  promptValue,
  onPromptChange,
  renderBeforePrompt,
  children,
}) {
  const [open, setOpen] = useState(openByDefault);
  const [internalPrompt, setInternalPrompt] = useState("");
  const promptControlled = onPromptChange != null;
  const prompt = promptControlled ? promptValue : internalPrompt;
  const setPrompt = promptControlled ? onPromptChange : setInternalPrompt;
  const [model, setModel] = useState("");
  const [samplePercentage, setSamplePercentage] = useState(100);
  const [contentScope, setContentScope] = useState("both");
  const [runningKey, setRunningKey] = useState(null);
  const [progress, setProgress] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [estimate, setEstimate] = useState(null);
  const [accounting, setAccounting] = useState(null);
  const [partialState, setPartialState] = useState(null);

  const running = runningKey !== null;
  const disabled = running || parentDisabled;

  // Upfront pre-run batch estimate (QC-005)
  useEffect(() => {
    if (!model) {
      setEstimate(null);
      return;
    }
    let cancelled = false;
    const estBatches = Math.max(1, Math.round(samplePercentage / 20));
    fetchJobEstimate(model, estBatches)
      .then((data) => {
        if (!cancelled) setEstimate(data);
      })
      .catch(() => {
        if (!cancelled) setEstimate(null);
      });
    return () => {
      cancelled = true;
    };
  }, [model, samplePercentage]);

  const runWithGuard = async (key, runFn, extraValues) => {
    setRunningKey(key);
    setError("");
    setMessage("");
    setProgress(null);
    setPartialState(null);
    try {
      const apiKey = localStorage.getItem("apiKey");
      if (!apiKey) {
        setError("API key not set. Please set your API key in the navbar.");
        return;
      }

      const result = await runFn({
        apiKey,
        model,
        prompt,
        samplePercentage,
        contentScope,
        setProgress,
        ...extraValues,
      });

      if (result?.accounting) {
        setAccounting(result.accounting);
      }

      if (result?.isPartial) {
        setPartialState({
          salvaged: result.data,
          error: result.error || "Partial run completed with salvaged output",
          runFn,
          extraValues,
        });
        setMessage(result?.message || "Partial run: salvaged output was saved.");
        return;
      }

      if (result?.error) {
        setError(result.error);
        return;
      }
      setMessage(result?.message || "");
    } catch (err) {
      setError(err?.message || "AI assist failed");
    } finally {
      setRunningKey(null);
    }
  };

  const handleRun = () => runWithGuard("primary", onRun);

  return (
    <div className="border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-surface-raised"
        aria-expanded={open}
      >
        <span className="text-sm font-medium">AI assist</span>
        <span className="text-sm text-paper/60">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="flex flex-col gap-3 border-t border-line p-3">
          {renderBeforePrompt && renderBeforePrompt(disabled)}

          <PromptTextareaWithActions
            id={`${promptType}-ai-assist-prompt`}
            label={promptLabel}
            value={prompt}
            onChange={setPrompt}
            placeholder={promptPlaceholder}
            rows={3}
            promptType={promptType}
            exampleText={exampleText}
            disabled={disabled}
          />

          {typeof children === "function" ? children(disabled) : children}

          <div>
            <AiModelFormGroup
              model={model}
              onModelChange={setModel}
              disabled={disabled}
              id={`${promptType}-ai-assist-model`}
              selectPlaceholder="dash"
            />
            {estimate && (
              <div className="mt-1.5 flex items-center justify-between text-xs text-paper/60">
                <span>
                  Est. time: ~{estimate.estimated_duration_s}s
                </span>
                <span>
                  Est. cost:{" "}
                  {estimate.estimated_cost_usd == null
                    ? "unknown"
                    : estimate.is_paid
                      ? `~$${estimate.estimated_cost_usd.toFixed(4)} USD`
                      : "$0.00 (free tier)"}
                </span>
              </div>
            )}
          </div>

          {showContentScope && (
            <ContentScopeFormGroup
              contentScope={contentScope}
              onContentScopeChange={setContentScope}
              disabled={disabled}
              radioName={contentScopeRadioName}
            />
          )}

          {showSampleSize && (
            <SliderField
              id={`${promptType}-ai-assist-sample`}
              label="Sample Size"
              value={samplePercentage}
              onChange={setSamplePercentage}
              min={minSamplePercentage}
              max={100}
              step={1}
              disabled={disabled}
              valueDisplay={`${samplePercentage}%`}
              valueMinWidth="70px"
              caption="Percentage of the still-undecided rows to send to the model."
            />
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className={btnPrimary} onClick={handleRun} disabled={disabled}>
              {runningKey === "primary" ? runningLabel : runLabel}
            </button>

            {(extraActions || []).map((action) => (
              <span key={action.key} className="inline-flex items-center gap-1.5">
                <button
                  type="button"
                  className={btn}
                  onClick={() => runWithGuard(action.key, action.onRun, action.extraValues)}
                  disabled={disabled || action.disabled}
                >
                  {runningKey === action.key ? action.runningLabel || action.label : action.label}
                </button>
                {action.help && <HelpTip text={action.help} />}
              </span>
            ))}
          </div>

          {running && progress && (
            <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
          )}

          {partialState && (
            <ErrorDisplay
              type="warning"
              message="Partial Run: Salvaged output preserved"
              details={partialState.error}
              onRetry={() => runWithGuard("retry", partialState.runFn, partialState.extraValues)}
            />
          )}

          {error && (
            <ErrorDisplay
              type="error"
              message={error}
              onDismiss={() => setError("")}
            />
          )}

          {!error && message && (
            <div className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/80">
              {message}
            </div>
          )}

          {accounting && (
            <div className="border border-line/60 bg-surface-raised/50 px-3 py-1.5 text-xs text-paper/70">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  Calls: {accounting.call_count} • Tokens:{" "}
                  {accounting.total_tokens != null
                    ? accounting.total_tokens
                    : accounting.prompt_tokens != null && accounting.completion_tokens != null
                      ? accounting.prompt_tokens + accounting.completion_tokens
                      : "unknown"}
                </span>
                <span>
                  Duration: {accounting.duration_ms}ms • Cost:{" "}
                  {accounting.estimated_cost_usd != null ? `$${accounting.estimated_cost_usd.toFixed(4)} USD` : "unknown"}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
