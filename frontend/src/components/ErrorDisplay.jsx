import "../styles/ErrorDisplay.css";

export default function ErrorDisplay({ message, onDismiss }) {
  if (!message) return null;

  return (
    <div className="error-display" role="alert">
      <p className="error-message">{message}</p>
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
