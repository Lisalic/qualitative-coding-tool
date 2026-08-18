import { useNavigate } from "react-router-dom";

/**
 * Shared success message shown whenever any pipeline stage (upload, filter,
 * generate codebook, apply codebook, compare codebooks/codings, summarize
 * coding) finishes creating a new artifact.
 *
 * Renders "{name} has been created." followed by a clickable "view" action
 * that navigates to the artifact's view page with it pre-selected via
 * `location.state`.
 */
export default function ArtifactCreatedMessage({ name, viewPath, viewState }) {
  const navigate = useNavigate();

  if (!name) return null;

  return (
    <p
      role="status"
      className="border border-success bg-success/10 px-4 py-3 text-center text-sm font-medium text-success"
    >
      <span className="font-semibold">{name}</span> has been created.{" "}
      <button
        type="button"
        onClick={() => navigate(viewPath, { state: viewState })}
        className="underline underline-offset-2 hover:opacity-70"
      >
        view
      </button>
    </p>
  );
}
