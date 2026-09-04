import { btnPrimary } from "../../lib/uiClasses";

/**
 * Form plumbing shared by the tool panels (filter, generate codebook, apply
 * codebook): submit button, error, and optional raw result.
 *
 * `columns` lays the children out side by side on large screens, matching
 * the compare and summarize pages. These forms used to be a single narrow
 * stack inside a max-w-3xl shell, which left most of a wide page empty and
 * pushed the submit button below the fold.
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
              {submitButton.disabled
                ? submitButton.loadingText
                : submitButton.text}
            </button>
          </div>
        )}
      </form>

      {error && (
        <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">
          {error}
        </p>
      )}

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
