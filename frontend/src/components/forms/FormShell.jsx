import "../../styles/Home.css";

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
    <div className="action-form-wrapper">
      <form onSubmit={handleSubmit} className="action-form">
        {children}
        {submitButton && (
          <button
            type="submit"
            disabled={submitButton.disabled}
            className="form-submit-btn"
          >
            {submitButton.disabled
              ? submitButton.loadingText
              : submitButton.text}
          </button>
        )}
      </form>

      {error && <p className="form-message">{error}</p>}

      {result && (
        <div className="result">
          <h2>{resultTitle}</h2>
          <pre>
            {typeof result === "string"
              ? result
              : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
