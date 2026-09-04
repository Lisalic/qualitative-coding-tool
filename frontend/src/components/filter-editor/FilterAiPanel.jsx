import { useState } from "react";
import { postJsonAndPoll } from "../../api";
import AiLabel from "../forms/AiLabel";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import SliderField from "../forms/SliderField";
import AiModelFormGroup from "../models/AiModelFormGroup";
import ProgressBar from "../feedback/ProgressBar";
import ContentScopeFormGroup from "../tool-panels/ContentScopeFormGroup";
import {
  EXAMPLE_PROMPTS,
  MissingFieldsError,
  buildFilterPreviewPayload,
} from "../../lib/apiContracts";

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

/**
 * The AI filter, as an assistive tool inside the editor.
 *
 * Same knobs as the standalone `/filter` panel, but `POST
 * /api/filter-preview/` creates nothing: it returns the ids it would keep
 * and the editor marks them as included with an "(added by AI)" badge for
 * the user to accept, reject or extend. Re-runnable as often as the user
 * likes -- the rows they have already ruled on are sent along and dropped
 * from the candidate pool server-side, so each run proposes rows that are
 * still undecided rather than re-litigating settled ones.
 *
 * Collapsed by default: the editor's primary mode is reading and checking
 * rows by hand, and the AI is opt-in help rather than the main event.
 */
export default function FilterAiPanel({ database, decided, onAccept, disabled }) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [filterTags, setFilterTags] = useState("");
  const [model, setModel] = useState("");
  const [minWords, setMinWords] = useState(0);
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
        payload = buildFilterPreviewPayload({
          apiKey: savedApiKey,
          database,
          model,
          prompt,
          filterTags,
          minWords,
          samplePercentage,
          contentScope,
          decidedPostIds: decided.postIds,
          decidedCommentIds: decided.commentIds,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: runError } = await postJsonAndPoll(
        "/api/filter-preview/",
        payload,
        { onProgress: setProgress },
      );
      if (!ok) {
        setError(runError || "AI filter failed");
        return;
      }

      const added = onAccept({
        postIds: data?.post_ids || [],
        commentIds: data?.comment_ids || [],
      });
      const proposed = (data?.post_ids?.length || 0) + (data?.comment_ids?.length || 0);
      const parts = [
        `AI proposed ${proposed} row${proposed === 1 ? "" : "s"}; ${added} newly marked as included.`,
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
      setError(err?.message || "AI filter failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="mb-6 border border-paper">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-white/5"
        aria-expanded={open}
      >
        <span className="font-medium">AI filter assistant</span>
        <span className="text-sm text-paper/60">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="flex flex-col gap-5 border-t border-paper/30 p-4">
          <PromptTextareaWithActions
            id="filterEditorPrompt"
            label="Enter prompt"
            value={prompt}
            onChange={setPrompt}
            placeholder="Enter your filter prompt..."
            rows={3}
            promptType="filter"
            exampleText={EXAMPLE_PROMPTS.filter}
            disabled={running || disabled}
          />

          <div className="flex flex-col gap-1.5">
            <AiLabel htmlFor="filterEditorTags" text="Keywords (optional)" />
            <textarea
              id="filterEditorTags"
              value={filterTags}
              onChange={(e) => setFilterTags(e.target.value)}
              placeholder="Comma-separated keywords (optional)."
              rows={2}
              className={`${inputClasses} resize-y`}
              disabled={running || disabled}
            />
          </div>

          <AiModelFormGroup
            model={model}
            onModelChange={setModel}
            disabled={running || disabled}
            id="filterEditorModel"
            selectPlaceholder="filter"
          />

          <ContentScopeFormGroup
            contentScope={contentScope}
            onContentScopeChange={setContentScope}
            disabled={running || disabled}
            radioName="filter-editor-content-scope"
          />

          <SliderField
            id="filterEditorMinWords"
            label="Minimum Words"
            value={minWords}
            onChange={setMinWords}
            min={0}
            max={1000}
            step={10}
            disabled={running || disabled}
            valueDisplay={minWords}
            caption="Rows shorter than this are never proposed."
          />

          <SliderField
            id="filterEditorSample"
            label="Sample Size"
            value={samplePercentage}
            onChange={setSamplePercentage}
            min={1}
            max={100}
            step={1}
            disabled={running || disabled}
            valueDisplay={`${samplePercentage}%`}
            valueMinWidth="70px"
            caption="Percentage of the still-undecided rows to send to the model."
          />

          <button
            type="button"
            onClick={handleRun}
            disabled={running || disabled}
            className="border-2 border-paper px-6 py-3 text-base font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-50"
          >
            {running ? "Running AI filter..." : "Run AI filter"}
          </button>

          {running && progress && (
            <ProgressBar
              current={progress.current}
              total={progress.total}
              label={progress.label}
            />
          )}

          {message && (
            <p className="border border-paper bg-white/5 px-4 py-3 text-sm text-paper">
              {message}
            </p>
          )}
          {error && (
            <p className="border border-paper/40 bg-white/5 px-4 py-3 text-sm text-paper">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
