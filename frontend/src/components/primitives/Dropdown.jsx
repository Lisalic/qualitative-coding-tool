import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { select } from "../../lib/uiClasses";

const PANEL_MAX_HEIGHT = 320;
const MIN_PANEL_WIDTH = 288;

/** Below this many options a search box is noise, so it is hidden. */
const SEARCH_THRESHOLD = 8;

/**
 * The app's one dropdown. Every selection control that used to be a native
 * `<select>` — and the artifact/file picker on the view pages — renders
 * through this.
 *
 * It exists because a native dropdown's popup is drawn by the OS: on this
 * app's black page the options came out unreadable, and no Tailwind class on
 * the `<select>` could reach inside that popup. Rebuilding the popup in the
 * page is the only way to theme it.
 *
 * The popup is portalled to `document.body` and positioned `fixed` rather
 * than being an in-flow `absolute` popover, because these pickers live inside
 * the editors' scrollable rails and inside `Panel` bodies, both of which
 * would clip an in-flow popover with `overflow-y-auto`.
 *
 * Values are passed through untouched — `commit` hands back `option.value`
 * exactly as given, so a caller whose options carry numbers (the
 * rows-per-page pickers) gets a number back, not `"25"`.
 *
 * Nesting works: `ArtifactPicker` renders a Dropdown (its project filter)
 * inside another Dropdown's popover. `data-dropdown-panel` is what makes that
 * safe — see `handlePointerDown` below.
 */
export default function Dropdown({
  id,
  value,
  options = [],
  onChange,
  disabled = false,
  placeholder = "Select…",
  loadingLabel,
  // Replaced wholesale, not appended to -- compact call sites pass their own
  // `w-auto ... text-xs` box and must not inherit this `w-full`.
  triggerClassName = `w-full ${select}`,
  searchPlaceholder = "Search…",
  emptyMessage = "No matches.",
  renderOptionMeta,
  header,
  searchable,
  listLabel,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const listRef = useRef(null);
  // A commit moves focus from the clicked option back to the trigger, which
  // is itself the search box now -- that refocus is a genuine focus event,
  // and without this guard the trigger's onFocus reopens what commit just
  // closed.
  const suppressFocusOpenRef = useRef(false);

  const reactId = useId();
  const baseId = id || `dropdown-${reactId}`;
  const listboxId = `${baseId}-listbox`;
  const optionId = (index) => `${baseId}-option-${index}`;

  const selected = options.find((opt) => Object.is(opt.value, value));
  const showSearch = searchable ?? options.length >= SEARCH_THRESHOLD;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    // Match the raw value too, not just the label: a model picker gets
    // pasted OpenRouter slugs, and a database picker gets pasted schema
    // names, neither of which appear in the display label.
    return options.filter((opt) => {
      const label = String(opt.label ?? "").toLowerCase();
      const raw = String(opt.value ?? "").toLowerCase();
      return label.includes(q) || raw.includes(q);
    });
  }, [options, query]);

  const reposition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const box = trigger.getBoundingClientRect();
    const below = window.innerHeight - box.bottom;
    // Flip above the trigger when the panel wouldn't fit under it -- these
    // pickers often sit near the foot of a rail.
    const dropUp = below < PANEL_MAX_HEIGHT && box.top > below;
    const width = Math.min(
      Math.max(box.width, MIN_PANEL_WIDTH),
      window.innerWidth - 16,
    );
    setRect({
      left: Math.max(8, Math.min(box.left, window.innerWidth - width - 8)),
      top: dropUp ? undefined : box.bottom + 4,
      bottom: dropUp ? window.innerHeight - box.top + 4 : undefined,
      width,
      maxHeight: Math.max(160, (dropUp ? box.top : below) - 12),
    });
  }, []);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return undefined;
    }

    reposition();
    // Index against `options`, which is what `filtered` equals while the
    // query is empty -- and it always is at open time.
    const at = options.findIndex((opt) => Object.is(opt.value, value));
    setActiveIndex(at >= 0 ? at : 0);

    const handlePointerDown = (event) => {
      if (triggerRef.current?.contains(event.target)) return;
      if (panelRef.current?.contains(event.target)) return;
      // A click inside SOME OTHER dropdown's panel is a click inside a
      // dropdown this one opened (the project filter nested in
      // ArtifactPicker's popover). Closing here would tear the nested one
      // out from under the pointer.
      if (event.target instanceof Element && event.target.closest("[data-dropdown-panel]")) return;
      setOpen(false);
    };
    // `capture` so a scroll inside any ancestor rail repositions the panel,
    // not just a scroll of the document.
    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, reposition]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useLayoutEffect(() => {
    if (!open) return;
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
  }, [open, activeIndex]);

  const commit = (option) => {
    if (option.disabled) return;
    onChange(option.value);
    setOpen(false);
    suppressFocusOpenRef.current = true;
    triggerRef.current?.focus();
  };

  const step = (delta) =>
    setActiveIndex((i) => (filtered.length === 0 ? 0 : (i + delta + filtered.length) % filtered.length));

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      if (open) {
        event.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      }
      return;
    }
    if (!open) {
      if (event.key === "ArrowDown" || event.key === "Enter") {
        event.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      step(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      step(-1);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const option = filtered[activeIndex];
      if (option) commit(option);
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  };

  const triggerLabel = loadingLabel || selected?.label || placeholder;
  // Closed, the merged trigger/search box reads like any other picker
  // (selected label, or nothing so the placeholder shows through). Open, it
  // reads as a search box: the label gives way to whatever's been typed.
  const mergedValue = open ? query : loadingLabel || selected?.label || "";
  const mergedPlaceholder = open ? searchPlaceholder : placeholder;

  const panel =
    open && rect ? (
      <div
        ref={panelRef}
        data-dropdown-panel=""
        className="fixed z-50 flex flex-col border border-paper bg-ink p-2"
        style={{
          left: rect.left,
          top: rect.top,
          bottom: rect.bottom,
          width: rect.width,
          maxHeight: rect.maxHeight,
        }}
        onKeyDown={handleKeyDown}
      >
        {header ? <div className="mb-1.5 shrink-0">{header}</div> : null}
        <div
          ref={listRef}
          id={listboxId}
          role="listbox"
          aria-label={listLabel}
          aria-activedescendant={filtered.length ? optionId(activeIndex) : undefined}
          className={`flex min-h-0 flex-col overflow-y-auto ${header ? "mt-1.5" : ""}`}
        >
          {filtered.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-paper/50">{emptyMessage}</p>
          ) : (
            filtered.map((opt, index) => {
              const isSelected = Object.is(opt.value, value);
              const isActive = index === activeIndex;
              return (
                <button
                  key={String(opt.value)}
                  id={optionId(index)}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  disabled={opt.disabled}
                  data-active={isActive || undefined}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => commit(opt)}
                  className={`flex w-full shrink-0 flex-col items-start gap-0.5 border-b border-line-soft px-2 py-1.5 text-left last:border-b-0 disabled:opacity-40 ${
                    isSelected ? "bg-paper text-ink" : isActive ? "bg-white/10" : ""
                  }`}
                >
                  <span className="w-full truncate text-sm">{opt.label}</span>
                  {renderOptionMeta ? (
                    <span
                      className={`w-full truncate text-[11px] ${
                        isSelected ? "text-ink/60" : "text-paper/50"
                      }`}
                    >
                      {renderOptionMeta(opt)}
                    </span>
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      </div>
    ) : null;

  const trigger = showSearch ? (
    <div className="relative">
      <input
        id={baseId}
        ref={triggerRef}
        type="text"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-autocomplete="list"
        disabled={disabled}
        value={mergedValue}
        placeholder={mergedPlaceholder}
        onFocus={() => {
          if (suppressFocusOpenRef.current) {
            suppressFocusOpenRef.current = false;
            return;
          }
          setOpen(true);
        }}
        // `onFocus` alone misses a click when the input is already focused
        // (e.g. right after a commit refocuses it) -- a focus event only
        // fires on an actual focus change, but the panel is closed and
        // should reopen.
        onClick={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onKeyDown={handleKeyDown}
        className={`truncate pr-6 ${triggerClassName}`}
      />
      <span aria-hidden="true" className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-paper/60">
        &#9662;
      </span>
    </div>
  ) : (
    <button
      id={baseId}
      ref={triggerRef}
      type="button"
      role="combobox"
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={open ? listboxId : undefined}
      disabled={disabled}
      onClick={() => setOpen((v) => !v)}
      onKeyDown={handleKeyDown}
      className={`flex items-center justify-between gap-2 text-left ${triggerClassName}`}
    >
      <span className={`truncate ${selected || loadingLabel ? "" : "text-paper/40"}`}>
        {triggerLabel}
      </span>
      <span aria-hidden="true" className="shrink-0 text-paper/60">
        &#9662;
      </span>
    </button>
  );

  return (
    <>
      {trigger}
      {panel ? createPortal(panel, document.body) : null}
    </>
  );
}
