/**
 * Provenance panel for a generated artifact: the system template, the
 * human's own instructions, and a one-line summary of the rendered LLM
 * input.
 *
 * The rendered prompt itself is deliberately not stored or shown -- it
 * embedded the whole batch of sampled post/comment text the artifact
 * already owns, which cost 119 MB across 61 version rows and was being
 * shipped in the JSON body of every page load (see
 * `backend/app/versioning_models.py::ArtifactVersion`). What's left is
 * the part anyone would actually read, plus a length + hash so the claim
 * "this version came from that input" stays checkable.
 */

import { hasPromptInfo } from "../../lib/promptInfo";

const boxClasses =
  "max-h-[200px] overflow-y-auto whitespace-pre-wrap border border-paper/20 bg-white/5 p-2.5 font-mono text-sm text-paper/80";

function MetaLine({ promptMeta }) {
  if (!promptMeta) return null;
  const chars = promptMeta.rendered_chars;
  const batches = promptMeta.batches;
  const sha = promptMeta.rendered_sha256;
  const parts = [];
  if (typeof chars === "number") parts.push(`${chars.toLocaleString()} chars`);
  // >1 batch means the stored hash covers only the last one -- say so
  // rather than implying it describes the whole input.
  if (typeof batches === "number" && batches > 1) parts.push(`last of ${batches} batches`);
  if (sha) parts.push(`sha256 ${String(sha).slice(0, 12)}`);
  if (parts.length === 0) return null;
  return <p className="text-xs text-paper/50">Rendered input: {parts.join(" · ")}</p>;
}

export default function PromptPanel({ systemPrompt, instructions, promptMeta }) {
  if (!hasPromptInfo({ systemPrompt, instructions, promptMeta })) return null;

  return (
    <div className="flex w-full max-w-[800px] flex-col gap-2">
      {systemPrompt && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-paper/50">System template</p>
          <div className={boxClasses}>{systemPrompt}</div>
        </div>
      )}
      {instructions && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-paper/50">Your instructions</p>
          <div className={boxClasses}>{instructions}</div>
        </div>
      )}
      <MetaLine promptMeta={promptMeta} />
    </div>
  );
}
