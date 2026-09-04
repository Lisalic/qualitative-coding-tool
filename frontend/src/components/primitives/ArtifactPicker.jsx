import { useEffect, useRef, useState } from "react";
import SelectionList from "./SelectionList";
import { btn } from "../../lib/uiClasses";

/**
 * Compact artifact picker for a PageShell toolbar.
 *
 * Every view page used to open with a `border-2` box wrapping a `max-h-32`
 * two-column grid -- a picker with its own scrollbar, sitting above content
 * that often needed the whole viewport. Collapsing it into the toolbar
 * recovers that space; the list itself is unchanged, just relocated into a
 * popover where it can afford to be taller than 128px.
 *
 * SelectionList still owns the filtering and alphabetical sort; this only
 * supplies the trigger, the popover chrome, and dismissal.
 */
export default function ArtifactPicker({
  items = [],
  selectedId,
  onSelect,
  projects = [],
  selectedProject,
  onProjectChange,
  showProjectFilter = false,
  emptyMessage = "No items available",
  placeholder = "Select…",
  searchPlaceholder = "Search by name…",
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const handlePointerDown = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false);
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const selected = items.find((item) => String(item.id) === String(selectedId));
  const selectedLabel = selected
    ? String(selected.display_name ?? selected.name ?? selected.id)
    : placeholder;

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className={`${btn} flex max-w-[18rem] items-center gap-2`}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="truncate">{selectedLabel}</span>
        <span aria-hidden="true" className="shrink-0 text-paper/60">
          &#9662;
        </span>
      </button>

      {open ? (
        <div className="absolute right-0 top-full z-40 mt-1 w-[min(32rem,calc(100vw-2rem))] border border-paper bg-ink p-2">
          <SelectionList
            items={items}
            selectedId={selectedId}
            onSelect={(id) => {
              onSelect?.(id);
              setOpen(false);
            }}
            className=""
            listClassName="mt-2 grid max-h-[50vh] grid-cols-1 content-start gap-1 overflow-y-auto sm:grid-cols-2"
            emptyMessage={emptyMessage}
            searchPlaceholder={searchPlaceholder}
            showProjectFilter={showProjectFilter}
            projects={projects}
            selectedProject={selectedProject}
            onProjectChange={onProjectChange}
          />
        </div>
      ) : null}
    </div>
  );
}
