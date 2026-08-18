const TONE_CLASSES = {
  error: "text-error border-error bg-error/10",
  success: "text-success border-success bg-success/10",
  info: "text-paper/70 border-paper/20 bg-white/5",
};

export default function ErrorDisplay({
  message,
  onDismiss,
  type = "error",
  variant = "display",
}) {
  if (!message) return null;
  const tone = TONE_CLASSES[type] || TONE_CLASSES.error;

  if (variant === "message") {
    return (
      <p className={`border px-4 py-3 text-center text-sm font-medium ${tone}`}>
        {message}
      </p>
    );
  }

  if (variant === "alert") {
    return <div className={`border px-4 py-3 text-sm ${tone}`}>{message}</div>;
  }

  return (
    <div
      role="alert"
      className={`flex items-center justify-between gap-3 border px-4 py-3 text-sm ${tone}`}
    >
      <p className="font-medium">{message}</p>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className="shrink-0 text-lg leading-none hover:opacity-70"
        >
          ×
        </button>
      )}
    </div>
  );
}
