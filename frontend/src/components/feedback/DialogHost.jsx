import { useRef, useSyncExternalStore } from "react";
import { btn, btnDanger, btnPrimary } from "../../lib/uiClasses";
import DialogService from "./DialogService";
import { useModalBehavior } from "./useModalBehavior";

/**
 * Renders whichever DialogService confirm is at the head of the queue, using
 * the app's single modal pattern (see documentation/style-guide.md). Mounted
 * once in App.jsx.
 */
export default function DialogHost() {
  const dialog = useSyncExternalStore(DialogService.subscribe, DialogService.getSnapshot);
  if (!dialog) return null;
  return <ConfirmDialog key={dialog.id} dialog={dialog} />;
}

function ConfirmDialog({ dialog }) {
  const { options } = dialog;
  const cancelRef = useRef(null);
  const primaryRef = useRef(null);
  const cancel = () => DialogService.resolveCurrent(false);
  // A destructive confirm opens on Cancel, so a reflexive Enter can't
  // delete anything; an ordinary one opens on its primary action.
  const dialogRef = useModalBehavior(cancel, {
    initialFocusRef: options.danger ? cancelRef : primaryRef,
  });

  const titleId = `app-dialog-title-${dialog.id}`;
  const bodyId = `app-dialog-body-${dialog.id}`;

  return (
    <div className="fixed inset-0 z-[20000] flex items-center justify-center bg-black/80 p-4" onClick={cancel}>
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        className="flex max-h-[90vh] w-full max-w-[480px] flex-col border-2 border-paper bg-ink text-paper"
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
          <button ref={cancelRef} type="button" className={btn} onClick={cancel}>
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
