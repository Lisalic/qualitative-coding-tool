import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api";
import { PROJECT_BUNDLE_KINDS, buildProjectBundlePath, filenameFromDisposition, slugify } from "../export/exportHelpers";
import { btn, btnPrimary } from "../../lib/uiClasses";

/** Opt-in coding columns -- both off by default (de-identification). */
const CODING_PRIVACY_OPTIONS = [
  { param: "include_source_text", label: "Include source text" },
  { param: "include_author", label: "Include author" },
];

const checkbox = "rounded-none accent-paper";

/**
 * Download a whole project as one ZIP, choosing the file format(s) per
 * kind of artifact. Only kinds the project actually holds are shown, each
 * with a checkbox per format and Word/Excel ticked by default -- ticking
 * more than one puts the same artifact in the bundle once per format.
 */
export default function ProjectDownloadModal({ project, onClose }) {
  const kinds = useMemo(() => {
    const files = project?.files || [];
    return PROJECT_BUNDLE_KINDS.map((kind) => ({
      ...kind,
      count: files.filter((f) => kind.fileTypes.includes(f.file_type)).length,
    })).filter((kind) => kind.count > 0);
  }, [project]);

  const [selected, setSelected] = useState(() =>
    Object.fromEntries(PROJECT_BUNDLE_KINDS.map((kind) => [kind.key, [kind.formats[0].value]])),
  );
  const [flags, setFlags] = useState({});
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape" && !downloading) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, downloading]);

  const toggleFormat = (kindKey, value) => {
    setSelected((prev) => {
      const current = prev[kindKey] || [];
      const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
      return { ...prev, [kindKey]: next };
    });
  };

  const missingFormat = kinds.some((kind) => (selected[kind.key] || []).length === 0);
  const hasCodings = kinds.some((kind) => kind.key === "coding");

  const download = async () => {
    setError(null);
    setDownloading(true);
    try {
      const formats = Object.fromEntries(kinds.map((kind) => [kind.param, selected[kind.key]]));
      const res = await apiFetch(
        buildProjectBundlePath(project.id, { formats, flags: hasCodings ? flags : {} }),
      );
      if (!res.ok) throw new Error("Download failed");

      const filename = filenameFromDisposition(
        res.headers.get("content-disposition"),
        `${slugify(project.projectname, `project_${project.id}`)}_project_bundle.zip`,
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
      onClose();
    } catch (err) {
      setError(err?.message || "Download failed. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80 p-4"
      onClick={downloading ? undefined : onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-download-title"
        className="flex max-h-[90vh] w-full max-w-[480px] flex-col border-2 border-paper bg-ink text-paper shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-paper px-5 py-3.5">
          <h2 id="project-download-title" className="text-sm font-semibold uppercase tracking-wide">
            Download project
          </h2>
          <button
            type="button"
            className="flex h-7 w-7 items-center justify-center text-lg transition-colors hover:bg-white/10"
            onClick={onClose}
            disabled={downloading}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-5">
          {kinds.length === 0 && (
            <p className="text-sm text-paper/60">
              This project has no exportable files yet. The download will contain only its manifest and
              lineage.
            </p>
          )}

          {kinds.map((kind) => (
            <fieldset key={kind.key} className="flex flex-col gap-1.5">
              <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wide">
                {kind.label} <span className="font-normal text-paper/50">({kind.count})</span>
              </legend>
              {kind.formats.map((format) => (
                <label key={format.value} className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className={checkbox}
                    checked={(selected[kind.key] || []).includes(format.value)}
                    onChange={() => toggleFormat(kind.key, format.value)}
                    disabled={downloading}
                  />
                  {format.label}
                </label>
              ))}
              {(selected[kind.key] || []).length === 0 && (
                <p className="text-xs text-error">Pick at least one format.</p>
              )}
              {kind.key === "coding" && (
                <div className="mt-1 flex flex-col gap-1.5 border-t border-line pt-2">
                  {CODING_PRIVACY_OPTIONS.map(({ param, label }) => (
                    <label key={param} className="flex cursor-pointer items-center gap-2 text-xs text-paper/80">
                      <input
                        type="checkbox"
                        className={checkbox}
                        checked={Boolean(flags[param])}
                        onChange={(e) => setFlags((prev) => ({ ...prev, [param]: e.target.checked }))}
                        disabled={downloading}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              )}
            </fieldset>
          ))}

          {error && (
            <div role="alert" className="border border-error bg-error/10 px-3 py-2 text-sm text-error">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-paper px-5 py-3.5">
          <button type="button" className={btn} onClick={onClose} disabled={downloading}>
            Cancel
          </button>
          <button
            type="button"
            className={btnPrimary}
            onClick={download}
            disabled={downloading || missingFormat}
          >
            {downloading ? "Preparing download..." : "Download"}
          </button>
        </div>
      </div>
    </div>
  );
}
