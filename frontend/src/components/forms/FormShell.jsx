import { btnPrimary } from "../../lib/uiClasses";
import ErrorDisplay from "../feedback/ErrorDisplay";

/**
 * Form plumbing shared by the tool panels (filter, generate codebook, apply
 * codebook): submit button, error, and optional raw result.
 *
 * `columns` lays the children out side by side on large screens, matching
 * the compare and summarize pages. These forms used to be a single narrow
 * stack inside a max-w-3xl shell, which left most of a wide page empty and
 * pushed the submit button below the fold.
 *
 * `submitButton.disabled` and `submitButton.loading` are separate on
 * purpose: `disabled` is whatever a caller wants to gate clicking on
 * (required fields, an in-flight request, ...), while `loading` alone
 * decides the label -- otherwise a required-fields gate reads the button
 * as "in progress" the instant something is missing, before the user has
 * clicked anything.
 */
export default function FormShell({
  children,
  onSubmit,
  submitButton,
  error,
  result,
  resultTitle,
  columns = false,
}) {
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (onSubmit) await onSubmit(e);
  };

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {columns ? (
          <div className="flex flex-col gap-3 lg:flex-row">{children}</div>
        ) : (
          children
        )}
        {submitButton && (
          <div className={columns ? "flex justify-center" : undefined}>
            <button
              type="submit"
              disabled={submitButton.disabled}
              className={btnPrimary}
            >
              {submitButton.loading ? submitButton.loadingText : submitButton.text}
            </button>
          </div>
        )}
      </form>

      <ErrorDisplay message={error} variant="alert" />

      {result && (
        <div className="border border-success bg-success/10 p-3">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-success">
            {resultTitle}
          </h2>
          <pre className="overflow-x-auto whitespace-pre-wrap border border-line bg-ink p-3 text-xs text-paper">
            {typeof result === "string"
              ? result
              : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
