import { postJsonAndPoll } from "../../api";
import AiAssistPanel from "../forms/AiAssistPanel";
import { EXAMPLE_PROMPTS, MissingFieldsError, buildIntegratePreviewPayload } from "../../lib/apiContracts";
import { useUnmountSignal } from "../primitives/useUnmountSignal";

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
 *
 * `comparison` (optional, `{ref, name}`) is the Compare Codebook report
 * the researcher chose in the rail's Comparison tab; when set it goes
 * along as `comparisons`, so the model follows its recommendations. The
 * prompt box carries the researcher's own suggestions on top of that.
 */
export default function IntegrateAiPanel({ codebooks, existingCodes, onProposals, comparison, disabled }) {
  // Leaving the page stops job polling (the job itself keeps running).
  const pollSignal = useUnmountSignal();
  const handleRun = async ({ apiKey, model, prompt, setProgress }) => {
    let payload;
    try {
      payload = buildIntegratePreviewPayload({
        apiKey,
        codebooks,
        model,
        prompt,
        existingCodes,
        comparisons: comparison ? [comparison.ref] : [],
      });
    } catch (err) {
      if (err instanceof MissingFieldsError) return { error: err.userMessage };
      throw err;
    }

    const { ok, data, jobId, error: runError } = await postJsonAndPoll(
      "/api/integrate-codebook-preview/",
      payload,
      { onProgress: setProgress, signal: pollSignal() },
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
          ? `Stopped early: ${data.partial_error}`
          : "Only part of the codebooks was processed. Try a paid model.",
      );
    }
    return { message: parts.join(" ") };
  };

  return (
    <AiAssistPanel
      promptType="generate"
      promptLabel="Your suggestions"
      exampleText={EXAMPLE_PROMPTS.integrate}
      runLabel="Propose merged codes"
      runningLabel="Merging..."
      showSampleSize={false}
      showContentScope={false}
      disabled={disabled || codebooks.length < 2}
      onRun={handleRun}
      renderBeforePrompt={() =>
        comparison ? (
          <p className="border border-line bg-surface-raised px-2.5 py-2 text-xs text-paper/80">
            Guided by comparison &ldquo;{comparison.name}&rdquo;.
          </p>
        ) : null
      }
    />
  );
}
