import { useState } from "react";
import { postJsonAndPoll } from "../../api";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import SliderField from "../forms/SliderField";
import AiModelFormGroup from "../models/AiModelFormGroup";
import ProgressBar from "../feedback/ProgressBar";
import ContentScopeFormGroup from "../tool-panels/ContentScopeFormGroup";
import {
  EXAMPLE_PROMPTS,
  MissingFieldsError,
  buildCodebookPreviewPayload,
} from "../../lib/apiContracts";
import { btn } from "../../lib/uiClasses";

/**
 * The codebook generator, as an assistive tool inside the editor.
 *
 * Same knobs as the standalone `/codebook-generate` panel, but `POST
 * /api/codebook-preview/` creates nothing: it returns codes it would add,
 * and they land in the review tray for the researcher to accept or
 * dismiss one at a time. Re-runnable as often as they like -- the current
 * draft goes along as `existing_codes`, so each run is asked for what is
 * still missing rather than restating the codebook that already exists.
 *
 * Collapsed by default: the editor's primary mode is reading the corpus
 * and writing codes by hand, and the AI is opt-in help rather than the
 * main event. Same placement decision as `FilterAiPanel`.
 *
 * `promptType="generate"` deliberately matches the one-shot panel's, so a
 * prompt saved on either screen shows up in the other's library.
 */
export default function CodebookAiPanel({ database, existingCodes, onProposals, disabled }) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("");
  const [samplePercentage, setSamplePercentage] = useState(100);
  const [contentScope, setContentScope] = useState("both");
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleRun = async () => {
    setRunning(true);
    setError("");
    setMessage("");
    setProgress(null);
    try {
      const savedApiKey = localStorage.getItem("apiKey");
      if (!savedApiKey) {
        setError("API key not set. Please set your API key in the navbar.");
        return;
      }

      let payload;
      try {
        payload = buildCodebookPreviewPayload({
          apiKey: savedApiKey,
          database,
          model,
          prompt,
          samplePercentage,
          contentScope,
          existingCodes,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: runError } = await postJsonAndPoll(
        "/api/codebook-preview/",
        payload,
        { onProgress: setProgress },
      );
      if (!ok) {
        setError(runError || "AI codebook assistant failed");
        return;
      }

      const proposed = data?.proposals || [];
      const { added, skipped } = onProposals(proposed);
      const parts = [
        `AI proposed ${proposed.length} code${proposed.length === 1 ? "" : "s"}; ` +
          `${added} new for review${skipped > 0 ? `, ${skipped} already covered` : ""}.`,
      ];
      if (data?.partial) {
        parts.push(
          data.partial_error
            ? `Coverage was partial -- stopped early after an error: ${data.partial_error}`
            : "Coverage was partial -- likely a free model's batch limit. Use a paid model or a smaller sample for full coverage.",
        );
      }
      setMessage(parts.join(" "));
    } catch (err) {
      setError(err?.message || "AI codebook assistant failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-white/5"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold uppercase tracking-wide">
          AI codebook assistant
        </span>
        <span className="text-sm text-paper/60">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="flex flex-col gap-3 border-t border-line p-3">
          <p className="text-xs text-paper/60">
            Suggests codes to add to your draft. Nothing is created, and nothing enters
            your codebook until you accept it.
          </p>

          <PromptTextareaWithActions
            id="codebookEditorPrompt"
            label="Enter prompt"
            value={prompt}
            onChange={setPrompt}
            placeholder="What should the assistant look for? (optional)"
            rows={3}
            promptType="generate"
            exampleText={EXAMPLE_PROMPTS.generate}
            disabled={running || disabled}
          />

          <AiModelFormGroup
            model={model}
            onModelChange={setModel}
            disabled={running || disabled}
            id="codebookEditorModel"
            selectPlaceholder="dash"
          />

          <ContentScopeFormGroup
            contentScope={contentScope}
            onContentScopeChange={setContentScope}
            disabled={running || disabled}
            radioName="codebook-editor-content-scope"
          />

          <SliderField
            id="codebookEditorSample"
            label="Sample Size"
            value={samplePercentage}
            onChange={setSamplePercentage}
            min={1}
            max={100}
            step={1}
            disabled={running || disabled}
            valueDisplay={`${samplePercentage}%`}
            valueMinWidth="70px"
            caption="Percentage of the source rows to send to the model."
          />

          <button
            type="button"
            className={btn}
            onClick={handleRun}
            disabled={running || disabled || !database}
          >
            {running ? "Asking..." : "Suggest codes"}
          </button>

          {running && progress && (
            <ProgressBar
              current={progress.current}
              total={progress.total}
              label={progress.label}
            />
          )}

          {error && (
            <div className="border border-error bg-error/10 px-3 py-2 text-sm text-error">
              {error}
            </div>
          )}

          {!error && message && (
            <div className="border border-line bg-white/5 px-3 py-2 text-sm text-paper/80">
              {message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
