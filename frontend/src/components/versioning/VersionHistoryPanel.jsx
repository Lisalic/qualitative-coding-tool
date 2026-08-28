import { useEffect, useState } from "react";

const btnSmall =
  "border border-paper px-2 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";
const linkSmall = "text-xs text-paper/50 underline decoration-dotted hover:text-paper";

function originLabel(origin) {
  switch (origin) {
    case "generated":
      return "Generated";
    case "edited":
      return "Edited";
    case "imported":
      return "Imported";
    case "forked":
      return "Forked";
    default:
      return origin;
  }
}

function formatTimestamp(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const CODEBOOK_DIFF_SECTIONS = [
  { key: "renamed", label: "Renamed", tone: "text-paper" },
  { key: "redefined", label: "Redefined", tone: "text-paper" },
  { key: "moved", label: "Moved", tone: "text-paper" },
  { key: "added", label: "Added", tone: "text-success" },
  { key: "removed", label: "Removed", tone: "text-error" },
  { key: "reordered", label: "Reordered", tone: "text-paper/60" },
];

function CodebookDiffEntry({ section, entry }) {
  if (section === "added" || section === "removed") {
    return (
      <div className="text-sm">
        <span className="font-semibold">{entry.name}</span>{" "}
        <span className="text-paper/50">&middot; {entry.family_name}</span>
      </div>
    );
  }
  return (
    <div className="text-sm">
      <span className="font-semibold">{entry.from.name}</span>
      {entry.from.name !== entry.to.name && (
        <>
          <span className="text-paper/50"> &rarr; </span>
          <span className="font-semibold">{entry.to.name}</span>
        </>
      )}
      {section === "moved" && (
        <span className="text-paper/50">
          {" "}
          &middot; {entry.from.family_name} &rarr; {entry.to.family_name}
        </span>
      )}
      {section !== "moved" && (
        <span className="text-paper/50"> &middot; {entry.to.family_name}</span>
      )}
    </div>
  );
}

/** A single "N label" stat -- the coding diff's headline numbers
 * (rows recoded, newly coded/uncoded). Zero-value stats are omitted by
 * the caller so a diff between two untouched versions doesn't show a
 * wall of zeroes.
 */
function StatChip({ value, label }) {
  return (
    <div className="border border-paper/30 px-2.5 py-1.5">
      <div className="text-lg font-semibold leading-none">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-paper/50">{label}</div>
    </div>
  );
}

function CodeCountRow({ entry }) {
  const sign = entry.delta > 0 ? "+" : "";
  const tone = entry.delta > 0 ? "text-success" : "text-error";
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="min-w-0 truncate">{entry.name}</span>
      <span className="shrink-0 text-paper/50">
        {entry.from_count} &rarr; {entry.to_count}{" "}
        <span className={tone}>
          ({sign}
          {entry.delta})
        </span>
      </span>
    </div>
  );
}

/** What actually changed in a coding artifact's OWN coding between two
 * versions -- rows recoded and per-code application counts -- as
 * opposed to the codebook's structure, which usually hasn't changed at
 * all for a plain recode/manual-tagging save (a "no structural changes"
 * message there used to be the ONLY thing this panel could say, even
 * when e.g. six posts had just been recoded).
 */
function CodingDiffSummary({ coding }) {
  const entryDelta = coding.to_total_entries - coding.from_total_entries;
  const stats = [
    { value: coding.rows_recoded, label: "Rows recoded" },
    { value: coding.rows_newly_coded, label: "Newly coded" },
    { value: coding.rows_newly_uncoded, label: "Newly uncoded" },
  ].filter((s) => s.value > 0);

  if (stats.length === 0 && coding.code_counts.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">Coding</span>
      <div className="flex flex-wrap gap-1.5">
        {stats.map((s) => (
          <StatChip key={s.label} value={s.value} label={s.label} />
        ))}
        <StatChip
          value={`${coding.from_total_entries}→${coding.to_total_entries}`}
          label={`Codes applied ${entryDelta > 0 ? "(+" + entryDelta + ")" : entryDelta < 0 ? "(" + entryDelta + ")" : ""}`}
        />
      </div>
      {coding.code_counts.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-paper/20 pt-1.5">
          {coding.code_counts.map((entry) => (
            <CodeCountRow key={entry.code_uid} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Version history sidebar for any artifact: a compact version list and
 * the diff between any two selected versions. Shared by the standalone
 * codebook page and the coding workspace -- the backend routes it calls
 * (via `useVersionHistory`) are generic across file types; the diff
 * response always carries the codebook's structural diff, plus, for a
 * coding artifact, a content diff of its own coding (rows recoded, code
 * counts -- see `CodingDiffSummary` above and the route's docstring).
 *
 * Selecting exactly two versions runs the diff automatically -- there
 * is no separate "Diff selected versions" button to click first.
 *
 * `onDuplicateFrom(versionNo, displayName) -> {ok, error?}`, if given,
 * adds a per-version "Duplicate from here" action -- forking a new
 * artifact from that point in history, which is this app's replacement
 * for revert (see `version_service.py`'s module docstring: history is
 * append-only, recovering an old state never rewrites it in place).
 * Each workspace passes its own duplicate endpoint here since coding and
 * codebook duplication are genuinely different service calls.
 */
export default function VersionHistoryPanel({ history, onClose, onDuplicateFrom }) {
  const { versions, loading, error, diff, diffLoading, fetchVersions, fetchDiff, clearDiff } = history;
  const [selected, setSelected] = useState([]);
  const [duplicating, setDuplicating] = useState(null); // version_no of the open "duplicate from" form, or null
  const [duplicateName, setDuplicateName] = useState("");
  const [duplicateState, setDuplicateState] = useState({ status: "idle", message: "" });

  const startDuplicate = (versionNo) => {
    setDuplicating(versionNo);
    setDuplicateName("");
    setDuplicateState({ status: "idle", message: "" });
  };

  const cancelDuplicate = () => {
    setDuplicating(null);
    setDuplicateState({ status: "idle", message: "" });
  };

  const confirmDuplicate = async (versionNo) => {
    const trimmed = duplicateName.trim();
    if (!trimmed) {
      setDuplicateState({ status: "error", message: "Name is required." });
      return;
    }
    setDuplicateState({ status: "saving", message: "" });
    const result = await onDuplicateFrom(versionNo, trimmed);
    if (!result?.ok) {
      setDuplicateState({ status: "error", message: result?.error || "Failed to duplicate." });
      return;
    }
    setDuplicating(null);
    setDuplicateState({ status: "idle", message: "" });
  };

  useEffect(() => {
    fetchVersions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Run the diff the instant a second version is picked -- no extra
  // click needed for the one thing this panel is mostly used for.
  useEffect(() => {
    if (selected.length === 2) {
      fetchDiff(Math.min(...selected), Math.max(...selected));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const toggleSelect = (versionNo) => {
    setSelected((prev) => {
      if (prev.includes(versionNo)) {
        clearDiff();
        return prev.filter((v) => v !== versionNo);
      }
      if (prev.length >= 2) return [versionNo];
      return [...prev, versionNo];
    });
  };

  const clearSelection = () => {
    setSelected([]);
    clearDiff();
  };

  const codebookDiff = diff?.codebook;
  const codebookHasChanges =
    !!codebookDiff && CODEBOOK_DIFF_SECTIONS.some((s) => (codebookDiff[s.key] || []).length > 0);
  const codingHasChanges =
    !!diff?.coding && (diff.coding.rows_recoded > 0 || diff.coding.code_counts.length > 0);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2.5 overflow-y-auto border border-paper p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">History</h3>
        <div className="flex gap-1.5">
          <button type="button" className={btnSmall} onClick={fetchVersions}>
            Refresh
          </button>
          {onClose && (
            <button type="button" className={btnSmall} onClick={onClose}>
              Close
            </button>
          )}
        </div>
      </div>

      {error && <div className="border border-error bg-error/10 px-2 py-1.5 text-xs text-error">{error}</div>}

      {loading ? (
        <p className="text-sm text-paper/60">Loading history...</p>
      ) : versions.length === 0 ? (
        <p className="text-sm text-paper/60">No versions yet.</p>
      ) : (
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <p className="text-xs text-paper/50">Pick two versions to diff.</p>
            {selected.length > 0 && (
              <button type="button" className={linkSmall} onClick={clearSelection}>
                Clear selection
              </button>
            )}
          </div>
          {versions.map((v) => (
            <div
              key={v.version_no}
              className={`flex flex-col gap-1 border-b border-paper/10 py-1.5 text-sm ${
                selected.includes(v.version_no) ? "bg-white/10" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(v.version_no)}
                    onChange={() => toggleSelect(v.version_no)}
                  />
                  <div className="min-w-0">
                    <span className="font-semibold">v{v.version_no}</span>{" "}
                    <span className="text-xs text-paper/60">{originLabel(v.origin)}</span>{" "}
                    <span className="text-xs text-paper/40">{formatTimestamp(v.created_at)}</span>
                    {v.message && <div className="truncate text-xs text-paper/50">{v.message}</div>}
                  </div>
                </label>
                {onDuplicateFrom && duplicating !== v.version_no && (
                  <button
                    type="button"
                    className={linkSmall}
                    onClick={() => startDuplicate(v.version_no)}
                    title={`Duplicate from v${v.version_no}`}
                  >
                    Duplicate from here
                  </button>
                )}
              </div>
              {duplicating === v.version_no && (
                <div className="flex flex-wrap items-center gap-1.5 pl-6">
                  <input
                    type="text"
                    autoFocus
                    value={duplicateName}
                    onChange={(e) => setDuplicateName(e.target.value)}
                    placeholder={`New name (from v${v.version_no})`}
                    className="min-w-0 flex-1 border border-paper bg-white/5 px-2 py-1 text-xs text-paper placeholder:text-paper/40 focus:outline-none focus:ring-1 focus:ring-paper"
                    disabled={duplicateState.status === "saving"}
                  />
                  <button
                    type="button"
                    className={btnSmall}
                    onClick={() => confirmDuplicate(v.version_no)}
                    disabled={duplicateState.status === "saving"}
                  >
                    {duplicateState.status === "saving" ? "..." : "Confirm"}
                  </button>
                  <button type="button" className={btnSmall} onClick={cancelDuplicate} disabled={duplicateState.status === "saving"}>
                    Cancel
                  </button>
                  {duplicateState.status === "error" && duplicateState.message && (
                    <span className="text-xs text-error">{duplicateState.message}</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {diffLoading && <p className="text-sm text-paper/60">Computing diff...</p>}

      {diff && (
        <div className="flex flex-col gap-3 border border-paper/20 p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">
              Diff &middot; v{Math.min(...selected)} &rarr; v{Math.max(...selected)}
            </span>
            <button type="button" className={linkSmall} onClick={clearSelection}>
              Clear
            </button>
          </div>

          {diff.coding && <CodingDiffSummary coding={diff.coding} />}

          {codebookHasChanges && (
            <div className="flex flex-col gap-2 border-t border-paper/20 pt-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">Codebook</span>
              {CODEBOOK_DIFF_SECTIONS.map(({ key, label, tone }) =>
                (codebookDiff[key] || []).length > 0 ? (
                  <div key={key} className="flex flex-col gap-1">
                    <span className={`text-xs font-semibold uppercase tracking-wide ${tone}`}>
                      {label} ({codebookDiff[key].length})
                    </span>
                    {codebookDiff[key].map((entry, idx) => (
                      <CodebookDiffEntry key={idx} section={key} entry={entry} />
                    ))}
                  </div>
                ) : null,
              )}
            </div>
          )}

          {!codingHasChanges && !codebookHasChanges && (
            <p className="text-sm text-paper/60">No changes between these versions.</p>
          )}
        </div>
      )}
    </div>
  );
}
