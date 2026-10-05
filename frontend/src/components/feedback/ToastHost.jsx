import { useEffect, useState, useSyncExternalStore } from "react";
import ToastService, { toastDuration } from "./ToastService";

const TICK_MS = 100;
const FADE_MS = 500;

const TYPE_STYLES = {
  info: { label: "Notice", border: "border-paper", accent: "text-paper", bar: "bg-paper" },
  success: { label: "Success", border: "border-success", accent: "text-success", bar: "bg-success" },
  error: { label: "Error", border: "border-error", accent: "text-error", bar: "bg-error" },
};

/**
 * One toast: counts down from its type's duration (paused while hovered),
 * showing the seconds left and a shrinking bar, then fades and dismisses.
 */
function Toast({ toast }) {
  const duration = toastDuration(toast.type);
  const [remaining, setRemaining] = useState(duration);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return undefined;
    const interval = setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - TICK_MS));
    }, TICK_MS);
    return () => clearInterval(interval);
  }, [paused]);

  useEffect(() => {
    if (remaining <= 0) ToastService.dismiss(toast.id);
  }, [remaining, toast.id]);

  const style = TYPE_STYLES[toast.type] ?? TYPE_STYLES.info;
  const fading = remaining <= FADE_MS;

  return (
    <div
      role={toast.type === "error" ? "alert" : "status"}
      className={`pointer-events-auto w-full border bg-ink text-paper transition-opacity duration-500 ${style.border} ${
        fading ? "opacity-0" : "opacity-100"
      }`}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex items-start gap-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className={`text-[10px] font-semibold uppercase tracking-wide ${style.accent}`}>{style.label}</div>
          <div className="mt-0.5 whitespace-pre-wrap break-words text-sm">{toast.message}</div>
        </div>
        <span className="shrink-0 pt-0.5 text-xs tabular-nums text-paper/50">{Math.ceil(remaining / 1000)}s</span>
        <button
          type="button"
          className="flex h-6 w-6 shrink-0 items-center justify-center text-base transition-colors hover:bg-white/10"
          onClick={() => ToastService.dismiss(toast.id)}
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
      <div className="h-0.5 w-full bg-surface-raised">
        <div
          className={`h-full ${style.bar}`}
          style={{ width: `${(remaining / duration) * 100}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Bottom-right stack of live toasts. Mounted once in App.jsx. Sits above
 * the editors' pinned action bar (`bottom-16`) so a toast never covers
 * the Save button it is reporting on.
 */
export default function ToastHost() {
  const toasts = useSyncExternalStore(ToastService.subscribe, ToastService.getSnapshot);
  if (!toasts.length) return null;

  return (
    <div className="pointer-events-none fixed right-4 bottom-16 left-4 z-[19000] flex flex-col items-end gap-2 sm:left-auto sm:w-[360px]">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
