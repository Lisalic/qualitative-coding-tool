import { useNavigate } from "react-router-dom";

/**
 * Shared success message shown whenever any pipeline stage (upload, filter,
 * generate codebook, apply codebook, compare codebooks/codings, summarize
 * coding) finishes creating a new artifact.
 *
 * Renders "{name} has been created." followed by a clickable "view" action
 * that navigates to the artifact's view page with it pre-selected via
 * `location.state`. `note` adds a second line (e.g. that a run only
 * partly finished), and a partial result passes `neutral` so it doesn't
 * read as an unqualified success.
 */
export default function ArtifactCreatedMessage({ name, viewPath, viewState, neutral = false, note = "" }) {
  const navigate = useNavigate();

  if (!name) return null;

  return (
    <p
      role="status"
      className={`px-4 py-3 text-center text-sm font-medium ${
        neutral
          ? "border border-line bg-surface-raised text-paper"
          : "border border-success bg-success/10 text-success"
      }`}
    >
      <span className="font-semibold">{name}</span> has been created.{" "}
      <button
        type="button"
        onClick={() => navigate(viewPath, { state: viewState })}
        className="underline underline-offset-2 hover:opacity-70"
      >
        View it
      </button>
      {note ? <span className="mt-1 block text-xs font-normal">{note}</span> : null}
    </p>
  );
}
