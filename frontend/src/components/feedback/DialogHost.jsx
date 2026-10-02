import { useEffect, useRef, useSyncExternalStore } from "react";
import { btn, btnDanger, btnPrimary } from "../../lib/uiClasses";
import DialogService from "./DialogService";

/**
 * Renders whichever DialogService confirm is at the head of the queue, using
 * the app's single modal pattern (see documentation/style-guide.md). Mounted
 * once in App.jsx.
 */
export default function DialogHost() {
  const dialog = useSyncExternalStore(DialogService.subscribe, DialogService.getSnapshot);
  const primaryRef = useRef(null);

  useEffect(() => {
    if (!dialog) return undefined;
    const previouslyFocused = document.activeElement;
    primaryRef.current?.focus();

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        DialogService.resolveCurrent(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [dialog]);

  if (!dialog) return null;

  const { options } = dialog;
  const titleId = `app-dialog-title-${dialog.id}`;
  const bodyId = `app-dialog-body-${dialog.id}`;
  const cancel = () => DialogService.resolveCurrent(false);

  return (
    <div className="fixed inset-0 z-[20000] flex items-center justify-center bg-black/80 p-4" onClick={cancel}>
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        className="flex max-h-[90vh] w-full max-w-[480px] flex-col border-2 border-paper bg-ink text-paper shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-paper px-5 py-3.5">
          <h2 id={titleId} className="text-sm font-semibold uppercase tracking-wide">
            {options.title || "Confirm"}
          </h2>
          <button
            type="button"
            className="flex h-7 w-7 items-center justify-center text-lg transition-colors hover:bg-white/10"
            onClick={cancel}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div id={bodyId} className="flex-1 overflow-y-auto whitespace-pre-wrap break-words p-5 text-sm">
          {dialog.message}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-paper px-5 py-3.5">
          <button type="button" className={btn} onClick={cancel}>
            {options.cancelLabel || "Cancel"}
          </button>
          <button
            ref={primaryRef}
            type="button"
            className={options.danger ? btnDanger : btnPrimary}
            onClick={() => DialogService.resolveCurrent(true)}
          >
            {options.confirmLabel || "OK"}
          </button>
        </div>
      </div>
    </div>
  );
}
