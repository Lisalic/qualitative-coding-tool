export default function FormShell({
  children,
  onSubmit,
  submitButton,
  error,
  result,
  resultTitle,
}) {
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (onSubmit) await onSubmit(e);
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {children}
        {submitButton && (
          <button
            type="submit"
            disabled={submitButton.disabled}
            className="border-2 border-paper px-6 py-3 text-base font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-50"
          >
            {submitButton.disabled
              ? submitButton.loadingText
              : submitButton.text}
          </button>
        )}
      </form>

      {error && (
        <p className="mt-4 border border-error bg-error/10 px-4 py-3 text-sm text-error">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-4 border border-success bg-success/10 p-4">
          <h2 className="mb-2 text-lg font-semibold text-success">{resultTitle}</h2>
          <pre className="overflow-x-auto whitespace-pre-wrap border border-paper bg-ink p-3 text-xs text-paper">
            {typeof result === "string"
              ? result
              : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
