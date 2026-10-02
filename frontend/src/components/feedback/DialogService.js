/**
 * The app's one confirm path, replacing the browser's native
 * `window.confirm` box with a themed modal. Non-blocking notices go
 * through ToastService instead.
 *
 * A module-level FIFO queue with no React dependency, so plain hooks and
 * event handlers can `await DialogService.confirm(...)` exactly like they
 * used to `await` the native box. `DialogHost` (mounted once in App.jsx)
 * renders the head of the queue via `useSyncExternalStore`.
 */

let queue = [];
let nextId = 1;
const listeners = new Set();

function emit() {
  listeners.forEach((listener) => listener());
}

const DialogService = {
  /** Yes/no pop-up; resolves `true` only when the user confirms. */
  confirm(message, { title, confirmLabel, cancelLabel, danger = false } = {}) {
    return new Promise((resolve) => {
      queue = [
        ...queue,
        { id: nextId++, message: String(message ?? ""), options: { title, confirmLabel, cancelLabel, danger }, resolve },
      ];
      emit();
    });
  },

  /** Closes the dialog currently shown, resolving its promise with `result`. */
  resolveCurrent(result) {
    const [head, ...rest] = queue;
    if (!head) return;
    queue = rest;
    emit();
    head.resolve(result);
  },

  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  getSnapshot() {
    return queue[0] ?? null;
  },
};

export default DialogService;
