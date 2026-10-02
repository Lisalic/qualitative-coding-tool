import { useState, useRef, useEffect } from "react";
import { apiFetch } from "../../api";
import { btn } from "../../lib/uiClasses";
import { buildExportPath, getExportOptions } from "./exportHelpers";

/** Opt-in coding export columns -- both off by default (de-identification). */
const CODING_PRIVACY_OPTIONS = [
  { param: "include_source_text", label: "Include source text" },
  { param: "include_author", label: "Include author" },
];

/**
 * Dropdown trigger for exporting codebooks, coding entries, memos, or summaries.
 * Strictly adheres to black & white palette, square corners (rounded-none),
 * and hover-invert styling per documentation/style-guide.md.
 *
 * When `getExportOptions` has only one option for this artifact type
 * (summary's case: markdown only), there is nothing to choose between: the
 * trigger downloads directly instead of opening a one-item menu.
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
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleDownload = async (targetType, format, extraParams) => {
    setError(null);
    setOpen(false);
    const flags = targetType === "coding"
      ? Object.fromEntries(Object.entries(codingFlags).filter(([, on]) => on))
      : {};
    const path = buildExportPath(fileId, targetType, format, null, { ...extraParams, ...flags });

    try {
      const res = await apiFetch(path);
      if (!res.ok) throw new Error("Export failed");

      const disposition = res.headers.get("content-disposition");
      let filename = `${targetType}_export.${format}`;
      if (disposition) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) filename = match[1];
      }

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
    }
  };

  const options = getExportOptions(artifactType);
  const singleOption = options.length === 1 ? options[0] : null;

  if (singleOption) {
    return (
      <div className="relative inline-block text-left" ref={menuRef}>
        <button
          type="button"
          className={triggerClassName || `${btn} rounded-none`}
          onClick={() => handleDownload(singleOption.target, singleOption.format, singleOption.extraParams)}
        >
          {label}
        </button>
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

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      <button
        type="button"
        className={triggerClassName || `${btn} rounded-none`}
        onClick={() => {
          setError(null);
          setOpen((prev) => !prev);
        }}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <span>{label}</span>
        <span className="ml-1 text-xs">▼</span>
      </button>

      {open && (
        <div
          className="absolute right-0 mt-1 w-48 border border-line bg-paper text-ink z-50 rounded-none shadow-none"
          role="menu"
        >
          <div className="border-b border-line px-3 py-1.5 text-xs uppercase tracking-wider font-semibold text-paper/70 bg-ink">
            Export Format
          </div>
          {artifactType === "coding" && (
            <div className="border-b border-line px-3 py-2 space-y-1">
              {CODING_PRIVACY_OPTIONS.map(({ param, label: optionLabel }) => (
                <label key={param} className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    className="rounded-none accent-ink"
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
              className={`w-full text-left px-3 py-2 text-sm hover:bg-ink hover:text-paper rounded-none transition-colors duration-150 ${
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
