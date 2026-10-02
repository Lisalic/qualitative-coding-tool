import { useState } from "react";
import { postJsonAndPoll } from "../../api";
import AiAssistPanel from "../forms/AiAssistPanel";
import AiLabel from "../forms/AiLabel";
import SliderField from "../forms/SliderField";
import { EXAMPLE_PROMPTS, MissingFieldsError, buildFilterPreviewPayload } from "../../lib/apiContracts";
import { textarea } from "../../lib/uiClasses";

const AUTOFILL_HELP =
  "Prompts the AI to give decisions on entries by making decisions similar to those already made in this file.";

const MODES = [
  { value: "include", label: "Include" },
  { value: "exclude", label: "Exclude" },
];

/**
 * The AI filter, as an assistive tool inside the editor.
 *
 * `POST /api/filter-preview/` creates nothing: it returns the ids it
 * would include and the ids it would exclude, and the editor marks them
 * accordingly with an AI badge for the user to accept, reverse or extend.
 * Re-runnable as often as the user likes -- the rows they have already
 * ruled on (in either direction) are sent along and dropped from the
 * candidate pool server-side, so each run proposes rows that are still
 * undecided rather than re-litigating settled ones.
 *
 * The include and exclude criteria share one prompt box, toggled by an
 * Include/Exclude mode switch -- each mode keeps its own text, but only
 * the active mode's criterion is ever sent, and only that mode's ids are
 * ever applied from the response. Include mode proposes new includes
 * only; exclude mode proposes new excludes only. No cross-direction
 * results, even if the model's response carries any (a free model in
 * particular can be sloppy about honoring "leave it out of both" when it
 * lacks a criterion for the other direction).
 *
 * Two run modes share one job:
 *   - "Run AI filter" -- driven by the active mode's criterion typed
 *     into the prompt box.
 *   - "Autofill with AI" -- ignores the prompt box and instead sends
 *     the researcher's own already-decided rows as labelled "similar
 *     examples", so the model imitates the judgement already applied in
 *     this file rather than following new criteria. Still scoped to the
 *     active mode -- same no-cross-direction rule applies.
 */
export default function FilterAiPanel({ database, included, excluded, onAccept, disabled }) {
  const [mode, setMode] = useState("include");
  const [includePrompt, setIncludePrompt] = useState("");
  const [excludePrompt, setExcludePrompt] = useState("");
  const [filterTags, setFilterTags] = useState("");
  const [minWords, setMinWords] = useState(0);

  const setPromptForMode = (value) => {
    if (mode === "include") setIncludePrompt(value);
    else setExcludePrompt(value);
  };

  const hasDecisions =
    (included?.postIds?.length || 0) > 0 ||
    (included?.commentIds?.length || 0) > 0 ||
    (excluded?.postIds?.length || 0) > 0 ||
    (excluded?.commentIds?.length || 0) > 0;

  const runFilter = async ({ apiKey, model, samplePercentage, contentScope, setProgress, useExamples }) => {
    const payload = buildFilterPreviewPayload({
      apiKey,
      database,
      model,
      includePrompt: mode === "include" ? includePrompt : "",
      excludePrompt: mode === "exclude" ? excludePrompt : "",
      useExamples,
      filterTags,
      minWords,
      samplePercentage,
      contentScope,
      includedPostIds: included?.postIds,
      includedCommentIds: included?.commentIds,
      excludedPostIds: excluded?.postIds,
      excludedCommentIds: excluded?.commentIds,
    });

    const { ok, data, jobId, error: runError } = await postJsonAndPoll(
      "/api/filter-preview/",
      payload,
      { onProgress: setProgress },
    );
    if (!ok) return { error: runError || "AI filter failed" };

    // Only the active mode's ids are ever applied -- no cross-direction
    // results, even if the response carried any.
    const includePostIds = mode === "include" ? data?.include_post_ids || [] : [];
    const includeCommentIds = mode === "include" ? data?.include_comment_ids || [] : [];
    const excludePostIds = mode === "exclude" ? data?.exclude_post_ids || [] : [];
    const excludeCommentIds = mode === "exclude" ? data?.exclude_comment_ids || [] : [];

    const { includedCount, excludedCount } = onAccept({
      jobId,
      includePostIds,
      includeCommentIds,
      excludePostIds,
      excludeCommentIds,
    });
    const proposed =
      includePostIds.length + includeCommentIds.length + excludePostIds.length + excludeCommentIds.length;
    const parts = [
      `AI proposed ${proposed} row${proposed === 1 ? "" : "s"}: ${includedCount} newly included, ${excludedCount} newly excluded.`,
    ];
    if (data?.partial) {
      parts.push(
        data.partial_error
          ? `Stopped early: ${data.partial_error}`
          : "Only part of the sample was processed. Try a paid model or a smaller sample.",
      );
    }
    return { message: parts.join(" ") };
  };

  const handleRun = async (values) => {
    try {
      return await runFilter({ ...values, useExamples: false });
    } catch (err) {
      if (err instanceof MissingFieldsError) return { error: err.message };
      throw err;
    }
  };

  const handleAutofill = async (values) => {
    try {
      return await runFilter({ ...values, useExamples: true });
    } catch (err) {
      if (err instanceof MissingFieldsError) return { error: err.message };
      throw err;
    }
  };

  return (
    <AiAssistPanel
      promptType={mode === "include" ? "filter_include" : "filter_exclude"}
      promptLabel={mode === "include" ? "Include criteria" : "Exclude criteria"}
      promptPlaceholder={
        mode === "include" ? "Enter your include criteria..." : "Enter your exclude criteria..."
      }
      exampleText={mode === "include" ? EXAMPLE_PROMPTS.filterInclude : EXAMPLE_PROMPTS.filterExclude}
      promptValue={mode === "include" ? includePrompt : excludePrompt}
      onPromptChange={setPromptForMode}
      renderBeforePrompt={(fieldsDisabled) => (
        <div className="flex w-full gap-2" role="group" aria-label="Criteria mode">
          {MODES.map((opt) => (
            <div key={opt.value} className="flex-1">
              <input
                type="radio"
                id={`filter-ai-mode-${opt.value}`}
                name="filter-ai-mode"
                value={opt.value}
                checked={mode === opt.value}
                onChange={() => setMode(opt.value)}
                disabled={fieldsDisabled}
                className="peer hidden"
              />
              <label
                htmlFor={`filter-ai-mode-${opt.value}`}
                className="block cursor-pointer border border-paper px-3 py-2 text-center text-sm transition-colors hover:bg-paper hover:text-ink peer-checked:bg-paper peer-checked:text-ink peer-disabled:cursor-not-allowed peer-disabled:opacity-40 peer-disabled:hover:bg-transparent peer-disabled:hover:text-paper"
              >
                {opt.label}
              </label>
            </div>
          ))}
        </div>
      )}
      runLabel="Run AI filter"
      runningLabel="Running AI filter..."
      contentScopeRadioName="filter-ai-content-scope"
      disabled={disabled}
      onRun={handleRun}
      extraActions={[
        {
          key: "autofill",
          label: "Autofill with AI",
          runningLabel: "Autofilling...",
          help: AUTOFILL_HELP,
          disabled: !hasDecisions,
          onRun: handleAutofill,
        },
      ]}
    >
      {(fieldsDisabled) => (
        <>
          <div className="flex flex-col gap-1.5">
            <AiLabel htmlFor="filterEditorTags" text="Keywords (optional)" />
            <textarea
              id="filterEditorTags"
              value={filterTags}
              onChange={(e) => setFilterTags(e.target.value)}
              placeholder="Comma-separated"
              rows={2}
              className={textarea}
              disabled={fieldsDisabled}
            />
          </div>

          <SliderField
            id="filterEditorMinWords"
            label="Minimum Words"
            value={minWords}
            onChange={setMinWords}
            min={0}
            max={1000}
            step={10}
            disabled={fieldsDisabled}
            valueDisplay={minWords}
          />
        </>
      )}
    </AiAssistPanel>
  );
}
