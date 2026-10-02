import { useEffect, useRef, useState } from "react";
import { btn } from "../../lib/uiClasses";

/** Full-width row for an item inside a `ToolsMenu` panel -- same left-aligned,
 * block-level shape regardless of whether the item is a plain nav button, a
 * toggle, or (Export/Duplicate) something with its own nested state. */
export const toolsMenuItem =
  "w-full border-b border-line-soft px-3 py-1.5 text-left text-sm transition-colors last:border-b-0 hover:bg-paper hover:text-ink disabled:opacity-40";

/**
 * Collects secondary/occasional toolbar actions -- history, lineage,
 * export, duplicate, and the like -- behind one trigger instead of each
 * rendering directly in the page toolbar. A row of five-plus buttons of
 * mixed size read as clutter and buried the controls people actually
 * reach for on every visit (view mode, edit); this keeps those in the
 * toolbar and tucks the rest one click away, all at the same trigger
 * height as the primary controls beside it.
 *
 * `children` may be a render prop `({ close }) => …` so an item (History,
 * Lineage) can close the menu after acting; a plain node works too for
 * items (Duplicate) that manage their own open state and shouldn't be
 * dismissed by their own click.
 */
export default function ToolsMenu({ label = "Tools", children }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    function handlePointerDown(event) {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    }
    function handleKeyDown(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <div className="relative inline-block text-left" ref={ref}>
      <button
        type="button"
        className={btn}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
      >
        {label} <span className="ml-1 text-xs">&#9662;</span>
      </button>
      {open && (
        <div
          className="absolute right-0 z-50 mt-1 flex w-56 flex-col border border-line bg-ink"
          role="menu"
        >
          {typeof children === "function" ? children({ close }) : children}
        </div>
      )}
    </div>
  );
}
