import { useState, useRef, useEffect } from "react";
import { apiFetch } from "../../api";
import { btn } from "../../lib/uiClasses";
import { buildExportPath, filenameFromDisposition, getExportOptions } from "./exportHelpers";

/** Opt-in coding export columns -- both off by default (de-identification). */
const CODING_PRIVACY_OPTIONS = [
  { param: "include_source_text", label: "Include source text" },
  { param: "include_author", label: "Include author" },
];

/**
 * Dropdown trigger for exporting codebooks, coding entries, memos, or summaries.
 * A black menu with hover-invert items, like every other menu in the app
 * (documentation/style-guide.md). Escape closes it and returns focus to
 * the trigger; arrow keys move between formats. While a download is being
 * prepared the trigger says so, since a large export can take a moment.
 *
 * Every artifact type offers Word/Excel first plus the interchange formats
 * (see `getExportOptions`), so the trigger always opens a menu.
 */
export default function ExportDropdown({
  fileId,
  artifactType,
  label = "Export",
  triggerClassName,
  onAction,
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const [codingFlags, setCodingFlags] = useState({});
  const [exporting, setExporting] = useState(false);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleMenuKeyDown = (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const items = [...(menuRef.current?.querySelectorAll('[role="menuitem"]') || [])];
    if (items.length === 0) return;
    event.preventDefault();
    const at = items.indexOf(document.activeElement);
    const next = event.key === "ArrowDown" ? (at + 1) % items.length : (at - 1 + items.length) % items.length;
    items[next].focus();
  };

  const handleDownload = async (targetType, format, extraParams) => {
    setError(null);
    setOpen(false);
    setExporting(true);
    const flags = targetType === "coding"
      ? Object.fromEntries(Object.entries(codingFlags).filter(([, on]) => on))
      : {};
    const path = buildExportPath(fileId, targetType, format, null, { ...extraParams, ...flags });

    try {
      const res = await apiFetch(path);
      if (!res.ok) throw new Error("Export failed");

      const filename = filenameFromDisposition(
        res.headers.get("content-disposition"),
        `${targetType}_export.${format}`,
      );

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
      // Only dismiss the parent menu (e.g. a Tools popover) once the
      // download actually succeeded -- closing it eagerly, before the
      // request even resolved, meant a failed export's error alert
      // unmounted along with everything else and was never seen.
      onAction?.();
    } catch (err) {
      console.error("Download failed:", err);
      setError(err?.message || "Export failed. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  const options = getExportOptions(artifactType);

  return (
    <div className="relative inline-block text-left" ref={menuRef} onKeyDown={handleMenuKeyDown}>
      <button
        ref={triggerRef}
        type="button"
        className={triggerClassName || btn}
        disabled={exporting}
        onClick={() => {
          setError(null);
          setOpen((prev) => !prev);
        }}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <span>{exporting ? "Exporting…" : label}</span>
        <span className="ml-1 text-xs" aria-hidden="true">
          ▼
        </span>
      </button>

      {open && (
        <div
          className="absolute right-0 z-50 mt-1 w-64 border border-line bg-ink text-paper"
          role="menu"
        >
          <div className="border-b border-line px-3 py-1.5 text-xs uppercase tracking-wider font-semibold text-paper/70 bg-ink">
            Export format
          </div>
          {artifactType === "coding" && (
            <div className="border-b border-line px-3 py-2 space-y-1">
              {CODING_PRIVACY_OPTIONS.map(({ param, label: optionLabel }) => (
                <label key={param} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    className="accent-paper"
                    checked={Boolean(codingFlags[param])}
                    onChange={(e) =>
                      setCodingFlags((prev) => ({ ...prev, [param]: e.target.checked }))
                    }
                  />
                  {optionLabel}
                </label>
              ))}
            </div>
          )}
          {options.map((opt, idx) => (
            <button
              key={opt.label}
              type="button"
              className={`w-full px-3 py-2 text-left text-sm transition-colors duration-150 hover:bg-paper hover:text-ink focus:bg-paper focus:text-ink ${
                idx > 0 ? "border-t border-line" : ""
              }`}
              role="menuitem"
              onClick={() => handleDownload(opt.target, opt.format, opt.extraParams)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="absolute right-0 mt-1 w-64 border border-line bg-paper text-ink p-2 text-xs z-50 rounded-none shadow-none flex items-center justify-between gap-2"
        >
          <span className="flex-1">{error}</span>
          <button
            type="button"
            className="text-xs font-bold px-1 hover:bg-ink hover:text-paper"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
