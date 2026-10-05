import { btnSm } from "../../lib/uiClasses";

// Error and success are the palette's only two colors; a "warning" is a
// notice, so it shares the neutral info treatment rather than adding an
// off-palette amber.
const TONE_CLASSES = {
  error: "text-error border-error bg-error/10",
  warning: "text-paper/80 border-line bg-surface-raised",
  success: "text-success border-success bg-success/10",
  info: "text-paper/70 border-line bg-surface-raised",
};

const retryBtn = `${btnSm} border-current`;

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
  // Errors interrupt (role="alert"); everything else is announced politely.
  const role = type === "error" ? "alert" : "status";

  if (variant === "message") {
    return (
      <div role={role} className={`border px-4 py-3 text-sm font-medium ${tone}`}>
        <p className="text-center">{message}</p>
        {details && <p className="mt-1 text-xs opacity-80">{details}</p>}
        {onRetry && (
          <div className="mt-2 flex justify-center">
            <button
              type="button"
              onClick={onRetry}
              className={retryBtn}
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
      <div role={role} className={`border px-4 py-3 text-sm ${tone}`}>
        <p>{message}</p>
        {details && <p className="mt-1 text-xs opacity-80">{details}</p>}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className={`mt-2 ${retryBtn}`}
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      role={role}
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
            className={retryBtn}
          >
            Retry
          </button>
        )}
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss message"
            className="shrink-0 px-1.5 text-lg leading-none hover:opacity-70"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}
