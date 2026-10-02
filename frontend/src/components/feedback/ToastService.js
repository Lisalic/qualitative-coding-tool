/**
 * Non-blocking notices ("API Key saved!", a failed delete, ...) shown as a
 * small auto-dismissing toast at the bottom of the screen. Anything that
 * needs an answer goes through DialogService.confirm instead.
 *
 * Same shape as DialogService: a module-level store with no React
 * dependency, rendered by `ToastHost` (mounted once in App.jsx).
 */

const VALID_TYPES = new Set(["success", "error", "info"]);

/** How long a toast stays up before it fades out. */
export const TOAST_DURATION_MS = 15000;

let toasts = [];
let nextId = 1;
const listeners = new Set();

function emit() {
  listeners.forEach((listener) => listener());
}

const ToastService = {
  show(message, type = "info") {
    const normalizedType = VALID_TYPES.has(type) ? type : "info";
    toasts = [...toasts, { id: nextId++, message: String(message ?? ""), type: normalizedType }];
    emit();
  },

  dismiss(id) {
    toasts = toasts.filter((toast) => toast.id !== id);
    emit();
  },

  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  getSnapshot() {
    return toasts;
  },
};

export default ToastService;
