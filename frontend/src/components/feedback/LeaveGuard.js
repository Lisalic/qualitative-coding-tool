import { useEffect } from "react";
import DialogService from "./DialogService";

/**
 * "You have unsaved changes" for in-app navigation.
 *
 * The app runs on `BrowserRouter`, which has no `useBlocker`, so a sidebar
 * click used to drop an editor's unsaved work without a word. Instead, a
 * page with unsaved work registers itself here (`useLeaveGuard`), and the
 * app-level navigation controls (Sidebar, Navbar, a workspace's Tools
 * links) `await confirmLeave()` before navigating. The same hook also
 * installs the `beforeunload` prompt for closing or reloading the tab.
 */

const dirtySources = new Set();

export function confirmLeave() {
  if (dirtySources.size === 0) return Promise.resolve(true);
  return DialogService.confirm(
    "You have unsaved changes on this page. Leave and discard them?",
    { title: "Unsaved changes", confirmLabel: "Leave", cancelLabel: "Stay", danger: true },
  );
}

/** Registers the calling page as holding unsaved work while `dirty` is true. */
export function useLeaveGuard(dirty) {
  useEffect(() => {
    if (!dirty) return undefined;
    const token = Symbol("leave-guard");
    dirtySources.add(token);
    const onBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      dirtySources.delete(token);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [dirty]);
}
