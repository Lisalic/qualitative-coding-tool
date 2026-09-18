const TONE_CLASSES = {
  error: "text-error border-error bg-error/10",
  warning: "text-amber-300 border-amber-400/40 bg-amber-400/10",
  success: "text-success border-success bg-success/10",
  info: "text-paper/70 border-paper/20 bg-white/5",
};

export default function ErrorDisplay({
  message,
  onDismiss,
  onRetry,
  type = "error",
  variant = "display",
  details = null,
}) {
  if (!message) return null;
  const tone = TONE_CLASSES[type] || TONE_CLASSES.error;

  if (variant === "message") {
    return (
      <div className={`border px-4 py-3 text-sm font-medium ${tone}`}>
        <p className="text-center">{message}</p>
        {details && <p className="mt-1 text-xs opacity-80">{details}</p>}
        {onRetry && (
          <div className="mt-2 flex justify-center">
            <button
              type="button"
              onClick={onRetry}
              className="border border-current px-3 py-1 text-xs uppercase tracking-wider hover:opacity-80"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    );
  }

  if (variant === "alert") {
    return (
      <div className={`border px-4 py-3 text-sm ${tone}`}>
        <p>{message}</p>
        {details && <p className="mt-1 text-xs opacity-80">{details}</p>}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 border border-current px-3 py-1 text-xs uppercase tracking-wider hover:opacity-80"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      role="alert"
      className={`flex items-center justify-between gap-3 border px-4 py-3 text-sm ${tone}`}
    >
      <div className="flex-1">
        <p className="font-medium">{message}</p>
        {details && <p className="mt-1 text-xs opacity-80">{details}</p>}
      </div>
      <div className="flex items-center gap-2">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="border border-current px-2.5 py-0.5 text-xs uppercase tracking-wider hover:opacity-80"
          >
            Retry
          </button>
        )}
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss message"
            className="shrink-0 text-lg leading-none hover:opacity-70"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}
