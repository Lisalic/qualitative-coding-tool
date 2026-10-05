import { useEffect, useRef } from "react";

/**
 * One `keydown` subscription for a page-level shortcut map, mounted once
 * regardless of how often the handlers -- or the state they close over --
 * change identity between renders.
 *
 * `handlers` is `{ [event.key]: (event) => void }`. It is stashed in a
 * ref that is refreshed on every render, so a shortcut always reaches the
 * latest closure without the listener itself being torn down and
 * re-added. The coding workspace's j/k navigation used to do exactly
 * that on every render, because the object it read state from was a
 * fresh literal each time; this hook's own `document` listener only
 * mounts/unmounts when `enabled` actually changes.
 *
 * Ignored while focus is in a form field (input/textarea/contentEditable),
 * with one opt-in exception: an element carrying
 * `data-shortcut-input="true"` still receives the shortcut. That is for
 * a search box that autofocuses the instant the shortcut becomes
 * relevant (e.g. the code-picker popup's "Search codes..." input) --
 * swallowing the key there would make the shortcut impossible to use at
 * the moment someone would actually reach for it. Only the digit
 * shortcuts (1-9, "apply code N") get through such an input -- letters
 * are what the user is typing into it, so j/k there must stay text.
 *
 * Keys pressed with Cmd/Ctrl/Alt are never shortcuts: Cmd+1 switches
 * browser tabs, it shouldn't also apply code 1.
 */
export function useEditorShortcuts(handlers, { enabled = true } = {}) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!enabled) return undefined;
    const onKeyDown = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const handler = handlersRef.current?.[e.key];
      if (!handler) return;
      const tag = e.target?.tagName;
      const isShortcutInput = e.target?.dataset?.shortcutInput === "true";
      if (isShortcutInput) {
        if (!/^[1-9]$/.test(e.key)) return;
      } else if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.target?.isContentEditable) {
        return;
      }
      handler(e);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
