import "../../styles/ErrorDisplay.css";

export default function ErrorDisplay({
  message,
  onDismiss,
  type = "error",
  variant = "display",
}) {
  if (!message) return null;

  if (variant === "message") {
    return <p className={`${type}-message`}>{message}</p>;
  }

  if (variant === "alert") {
    return <div className={`alert alert--${type}`}>{message}</div>;
  }

  return (
    <div className="error-display" role="alert">
      <p className={`${type}-message`}>{message}</p>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="dismiss-btn"
          aria-label="Dismiss error"
        >
          ×
        </button>
      )}
    </div>
  );
}
