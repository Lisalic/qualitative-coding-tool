import { useEffect, useRef } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Keyboard behaviour every modal in the app shares: Escape closes it,
 * focus moves into it on open (to `initialFocusRef` when given, else the
 * first focusable element), Tab stays inside it, and focus returns to
 * whatever had it before the modal opened.
 *
 * Returns the ref to put on the dialog element itself. `onClose` may
 * change identity every render; the latest one is always used.
 */
export function useModalBehavior(onClose, { initialFocusRef, enabled = true } = {}) {
  const dialogRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!enabled) return undefined;
    const previouslyFocused = document.activeElement;
    const dialog = dialogRef.current;
    const first = initialFocusRef?.current || dialog?.querySelector(FOCUSABLE);
    first?.focus();

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onCloseRef.current?.();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const items = Array.from(dialog.querySelectorAll(FOCUSABLE));
      if (items.length === 0) return;
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      } else if (!dialog.contains(document.activeElement)) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [enabled, initialFocusRef]);

  return dialogRef;
}
