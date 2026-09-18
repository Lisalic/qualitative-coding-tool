import { postJsonAndPoll } from "../../api";
import AiAssistPanel from "../forms/AiAssistPanel";
import { EXAMPLE_PROMPTS, MissingFieldsError, buildIntegratePreviewPayload } from "../../lib/apiContracts";

/**
 * The merge assistant, as an assistive tool inside the integrate editor
 * -- structurally identical to `CodebookAiPanel`, one level up (merging
 * codebooks rather than generating from raw data).
 *
 * `POST /api/integrate-codebook-preview/` creates nothing: it returns
 * merged codes it would propose, each carrying which source code(s) it
 * came from, and they land in the review tray. `showSampleSize`/
 * `showContentScope` are both off -- nothing here is sampled, the model
 * reads every source codebook in full. Re-runnable as often as needed:
 * the current draft goes along as `existing_codes`, so a second pass
 * asks for what's still missing rather than restating accepted merges.
 */
export default function IntegrateAiPanel({ codebooks, existingCodes, onProposals, disabled }) {
  const handleRun = async ({ apiKey, model, prompt, setProgress }) => {
    let payload;
    try {
      payload = buildIntegratePreviewPayload({
        apiKey,
        codebooks,
        model,
        prompt,
        existingCodes,
      });
    } catch (err) {
      if (err instanceof MissingFieldsError) return { error: err.message };
      throw err;
    }

    const { ok, data, jobId, error: runError } = await postJsonAndPoll(
      "/api/integrate-codebook-preview/",
      payload,
      { onProgress: setProgress },
    );
    if (!ok) return { error: runError || "AI integrate assistant failed" };

    const proposed = data?.proposals || [];
    const { added, skipped } = onProposals(proposed, jobId);
    const parts = [
      `AI proposed ${proposed.length} merged code${proposed.length === 1 ? "" : "s"}; ` +
        `${added} new for review${skipped > 0 ? `, ${skipped} already covered` : ""}.`,
    ];
    if (data?.partial) {
      parts.push(
        data.partial_error
          ? `Coverage was partial -- stopped early after an error: ${data.partial_error}`
          : "Coverage was partial -- likely a free model's batch limit. Use a paid model for full coverage.",
      );
    }
    return { message: parts.join(" ") };
  };

  return (
    <AiAssistPanel
      promptType="generate"
      promptPlaceholder="Anything the merge should pay special attention to? (optional)"
      exampleText={EXAMPLE_PROMPTS.integrate}
      runLabel="Propose merged codes"
      runningLabel="Merging..."
      showSampleSize={false}
      showContentScope={false}
      disabled={disabled || codebooks.length < 2}
      onRun={handleRun}
    />
  );
}
