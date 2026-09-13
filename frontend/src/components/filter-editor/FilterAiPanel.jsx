import { useState } from "react";
import { postJsonAndPoll } from "../../api";
import AiAssistPanel from "../forms/AiAssistPanel";
import AiLabel from "../forms/AiLabel";
import SliderField from "../forms/SliderField";
import { EXAMPLE_PROMPTS, MissingFieldsError, buildFilterPreviewPayload } from "../../lib/apiContracts";
import { input } from "../../lib/uiClasses";

/**
 * The AI filter, as an assistive tool inside the editor.
 *
 * `POST /api/filter-preview/` creates nothing: it returns the ids it
 * would keep and the editor marks them as included with an "(added by
 * AI)" badge for the user to accept, reject or extend. Re-runnable as
 * often as the user likes -- the rows they have already ruled on are
 * sent along and dropped from the candidate pool server-side, so each
 * run proposes rows that are still undecided rather than re-litigating
 * settled ones.
 */
export default function FilterAiPanel({ database, decided, onAccept, disabled }) {
  const [filterTags, setFilterTags] = useState("");
  const [minWords, setMinWords] = useState(0);

  const runAiFilter = async ({ apiKey, model, prompt, samplePercentage, contentScope, setProgress }) => {
    const payload = buildFilterPreviewPayload({
      apiKey,
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

    const { ok, data, error: runError } = await postJsonAndPoll(
      "/api/filter-preview/",
      payload,
      { onProgress: setProgress },
    );
    if (!ok) return { error: runError || "AI filter failed" };

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
    return { message: parts.join(" ") };
  };

  const handleRun = async (values) => {
    try {
      return await runAiFilter(values);
    } catch (err) {
      if (err instanceof MissingFieldsError) return { error: err.message };
      throw err;
    }
  };

  return (
    <AiAssistPanel
      promptType="filter"
      promptPlaceholder="Enter your filter prompt..."
      exampleText={EXAMPLE_PROMPTS.filter}
      runLabel="Run AI filter"
      runningLabel="Running AI filter..."
      contentScopeRadioName="filter-ai-content-scope"
      disabled={disabled}
      onRun={handleRun}
    >
      {(fieldsDisabled) => (
        <>
          <div className="flex flex-col gap-1.5">
            <AiLabel htmlFor="filterEditorTags" text="Keywords (optional)" />
            <textarea
              id="filterEditorTags"
              value={filterTags}
              onChange={(e) => setFilterTags(e.target.value)}
              placeholder="Comma-separated keywords (optional)."
              rows={2}
              className={`${input} w-full resize-y`}
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
            caption="Rows shorter than this are never proposed."
          />
        </>
      )}
    </AiAssistPanel>
  );
}
