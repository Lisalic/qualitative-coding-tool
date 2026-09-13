import { postJsonAndPoll } from "../../api";
import AiAssistPanel from "../forms/AiAssistPanel";
import { EXAMPLE_PROMPTS, MissingFieldsError, buildCodebookPreviewPayload } from "../../lib/apiContracts";

/**
 * The codebook generator, as an assistive tool inside the editor.
 *
 * `POST /api/codebook-preview/` creates nothing: it returns codes it
 * would add, and they land in the review tray for the researcher to
 * accept or dismiss one at a time. Re-runnable as often as they like --
 * the current draft goes along as `existing_codes`, so each run is asked
 * for what is still missing rather than restating the codebook that
 * already exists.
 */
export default function CodebookAiPanel({ database, existingCodes, onProposals, disabled }) {
  const handleRun = async ({ apiKey, model, prompt, samplePercentage, contentScope, setProgress }) => {
    let payload;
    try {
      payload = buildCodebookPreviewPayload({
        apiKey,
        database,
        model,
        prompt,
        samplePercentage,
        contentScope,
        existingCodes,
      });
    } catch (err) {
      if (err instanceof MissingFieldsError) return { error: err.message };
      throw err;
    }

    const { ok, data, error: runError } = await postJsonAndPoll(
      "/api/codebook-preview/",
      payload,
      { onProgress: setProgress },
    );
    if (!ok) return { error: runError || "AI codebook assistant failed" };

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
    return { message: parts.join(" ") };
  };

  return (
    <AiAssistPanel
      promptType="generate"
      promptPlaceholder="What should the assistant look for? (optional)"
      exampleText={EXAMPLE_PROMPTS.generate}
      runLabel="Suggest codes"
      runningLabel="Asking..."
      contentScopeRadioName="codebook-ai-content-scope"
      disabled={disabled || !database}
      onRun={handleRun}
    />
  );
}
