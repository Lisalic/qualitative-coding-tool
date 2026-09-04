import { useEffect, useState } from "react";
import VersionContentViewer from "./VersionContentViewer";

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

/** A single "N label" stat -- the coding/data diff's headline numbers
 * (rows recoded, newly coded/uncoded, rows added/removed). Zero-value
 * stats are omitted by the caller so a diff between two untouched
 * versions doesn't show a wall of zeroes.
 */
function StatChip({ value, label }) {
  return (
    <div className="border border-line px-2.5 py-1.5">
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

function CodingChangeList({ title, entries }) {
  if (!entries?.length) return null;

  return (
    <section className="min-w-0 border border-line bg-white/[0.02]">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <h4 className="text-sm font-semibold">{title}</h4>
        <span className="border border-line px-2 py-0.5 text-xs text-paper/60">
          {entries.length}
        </span>
      </div>
      <div className="hidden grid-cols-[minmax(0,2fr)_minmax(240px,1fr)] border-b border-line-soft text-[11px] uppercase tracking-wide text-paper/50 sm:grid">
        <span className="px-4 py-2">Coded text</span>
        <span className="border-l border-line-soft px-4 py-2">Code</span>
      </div>
      <div className="max-h-[60vh] overflow-y-auto">
        {entries.map((entry, index) => (
          <div
            key={`${entry.row_type}:${entry.post_id}:${entry.code_uid}:${entry.text}:${index}`}
            className="grid min-w-0 gap-3 border-b border-line-soft px-4 py-3 transition-colors last:border-b-0 hover:bg-white/[0.03] sm:grid-cols-[minmax(0,2fr)_minmax(240px,1fr)] sm:gap-0 sm:px-0 sm:py-0"
          >
            <div className="min-w-0 sm:px-4 sm:py-3">
              <span className="mb-0.5 block text-[11px] uppercase tracking-wide text-paper/50 sm:hidden">
                Coded text
              </span>
              <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-paper/85">
                {entry.text}
              </p>
            </div>
            <div className="min-w-0 sm:border-l sm:border-line-soft sm:px-4 sm:py-3">
              <span className="mb-0.5 block text-[11px] uppercase tracking-wide text-paper/50 sm:hidden">
                Code
              </span>
              <span className="inline-block max-w-full border border-paper/25 px-2 py-1 text-sm font-medium leading-snug">
                {entry.code}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
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

  if (
    stats.length === 0 &&
    coding.code_counts.length === 0 &&
    !coding.applied?.length &&
    !coding.removed?.length
  ) {
    return null;
  }

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
        <div className="flex flex-col gap-1 border-t border-line-soft pt-1.5">
          {coding.code_counts.map((entry) => (
            <CodeCountRow key={entry.code_uid} entry={entry} />
          ))}
        </div>
      )}
      {(coding.applied?.length > 0 || coding.removed?.length > 0) && (
        <div className="flex min-w-0 flex-col gap-3 border-t border-line-soft pt-3">
          <CodingChangeList title="Applied coding" entries={coding.applied} />
          <CodingChangeList title="Removed coding" entries={coding.removed} />
        </div>
      )}
    </div>
  );
}

/** Row content changed between two versions of a raw_data/filtered_data
 * artifact -- submissions/comments added/removed -- the data-file
 * counterpart of `CodingDiffSummary` above (see
 * `backend/app/core/data_diff.py`).
 */
function DataDiffSummary({ data }) {
  const stats = [
    { value: data.submissions_added, label: "Submissions added" },
    { value: data.submissions_removed, label: "Submissions removed" },
    { value: data.comments_added, label: "Comments added" },
    { value: data.comments_removed, label: "Comments removed" },
  ].filter((s) => s.value > 0);

  if (stats.length === 0) return null;

  const samples = [
    { label: "Submissions added", ids: data.sample_submissions_added },
    { label: "Submissions removed", ids: data.sample_submissions_removed },
    { label: "Comments added", ids: data.sample_comments_added },
    { label: "Comments removed", ids: data.sample_comments_removed },
  ].filter((s) => (s.ids || []).length > 0);

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">Data</span>
      <div className="flex flex-wrap gap-1.5">
        {stats.map((s) => (
          <StatChip key={s.label} value={s.value} label={s.label} />
        ))}
        <StatChip
          value={`${data.from_submissions}→${data.to_submissions}`}
          label="Submissions total"
        />
        <StatChip value={`${data.from_comments}→${data.to_comments}`} label="Comments total" />
      </div>
      {samples.length > 0 && (
        <div className="flex flex-col gap-1.5 border-t border-line-soft pt-1.5">
          {samples.map((s) => (
            <div key={s.label} className="text-xs">
              <span className="text-paper/50">{s.label}: </span>
              <span className="break-all text-paper/80">{s.ids.join(", ")}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Version history + diff for any artifact type: a version list with
 * per-version "duplicate from here" (this app's non-destructive
 * replacement for revert -- history is append-only, see
 * `version_service.py`'s module docstring) on the left, and the diff
 * between any two selected versions on the right. Selecting exactly two
 * versions runs the diff automatically -- no separate "Diff" button.
 *
 * This is the ONE consumer of `useVersionHistory` in the app -- it used
 * to be embedded as a sidebar column inside the codebook and coding
 * workspaces; both now redirect their "History" button here instead
 * (`/versions?ref=...`) so history has one page, reachable from every
 * artifact type including raw/filtered data, not just two workspaces.
 *
 * `onDuplicateFrom(versionNo, displayName) -> {ok, error?}` is optional
 * -- omit it (as `useVersionHistoryPage` does for a file type with no
 * duplicate endpoint, e.g. a comparison/summary artifact) to hide the
 * action entirely rather than showing a control that would just error.
 *
 * Each version row also gets a "View" action -- shows that version's
 * actual content (codebook tree / visual coding reader / data rows, via
 * `VersionContentViewer`) in place of the diff panel, for artifact types
 * `VersionContentViewer` supports (`fileType`, passed through from the
 * page's selected artifact). "View" and the two-checkbox diff selection
 * are mutually exclusive in the right-hand panel -- picking one clears
 * the other, so there's never an ambiguous "which am I looking at".
 */
export default function VersionHistoryPanel({ history, fileType, onDuplicateFrom }) {
  const { versions, loading, error, diff, diffLoading, fetchVersions, fetchDiff, clearDiff } = history;
  const [selected, setSelected] = useState([]);
  const [viewingVersion, setViewingVersion] = useState(null);
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

  // Re-fetch (and drop any stale selection/diff/viewed-version) whenever
  // the page's artifact picker points this panel at a different ref.
  useEffect(() => {
    setSelected([]);
    clearDiff();
    setViewingVersion(null);
    fetchVersions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history.ref]);

  // Run the diff the instant a second version is picked -- no extra
  // click needed for the one thing this panel is mostly used for.
  useEffect(() => {
    if (selected.length === 2) {
      fetchDiff(Math.min(...selected), Math.max(...selected));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const toggleSelect = (versionNo) => {
    setViewingVersion(null);
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

  const viewVersion = (versionNo) => {
    setSelected([]);
    clearDiff();
    setViewingVersion(versionNo);
  };

  const codebookDiff = diff?.codebook;
  const codebookHasChanges =
    !!codebookDiff && CODEBOOK_DIFF_SECTIONS.some((s) => (codebookDiff[s.key] || []).length > 0);
  const codingHasChanges =
    !!diff?.coding &&
    (diff.coding.rows_recoded > 0 ||
      diff.coding.code_counts.length > 0 ||
      diff.coding.applied?.length > 0 ||
      diff.coding.removed?.length > 0);
  const dataHasChanges =
    !!diff?.data &&
    (diff.data.submissions_added > 0 ||
      diff.data.submissions_removed > 0 ||
      diff.data.comments_added > 0 ||
      diff.data.comments_removed > 0);
  const hasAnyChanges = codebookHasChanges || codingHasChanges || dataHasChanges;

  return (
    <div className={`grid grid-cols-1 gap-4 ${viewingVersion == null ? "lg:grid-cols-[360px_minmax(0,1fr)]" : ""}`}>
      {viewingVersion == null && (
        <div className="flex flex-col gap-2.5 border border-line bg-surface p-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Versions</h3>
          <button type="button" className={btnSmall} onClick={fetchVersions}>
            Refresh
          </button>
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
            <div className="flex max-h-[70vh] flex-col overflow-y-auto">
              {versions.map((v) => (
                <div
                  key={v.version_no}
                  className={`flex flex-col gap-1 border-b border-line-soft py-1.5 text-sm ${
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
                    <div className="flex shrink-0 items-center gap-2.5">
                      {fileType && (
                        <button
                          type="button"
                          className={linkSmall}
                          onClick={() => viewVersion(v.version_no)}
                          title={`View v${v.version_no}`}
                        >
                          View
                        </button>
                      )}
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
          </div>
        )}
        </div>
      )}

      <div className="flex flex-col gap-3 border border-line bg-surface p-3">
        {viewingVersion != null && (
          <VersionContentViewer
            artifactRef={history.ref}
            fileType={fileType}
            versionNo={viewingVersion}
            onClose={() => setViewingVersion(null)}
          />
        )}

        {viewingVersion == null && selected.length < 2 && !diff && (
          <p className="text-sm text-paper/60">
            Select two versions on the left to see what changed, or click &ldquo;View&rdquo; on one to see its content.
          </p>
        )}

        {viewingVersion == null && diffLoading && <p className="text-sm text-paper/60">Computing diff...</p>}

        {viewingVersion == null && diff && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">
                Diff &middot; v{Math.min(...selected)} &rarr; v{Math.max(...selected)}
              </span>
              <button type="button" className={linkSmall} onClick={clearSelection}>
                Clear
              </button>
            </div>

            {diff.data && <DataDiffSummary data={diff.data} />}
            {diff.coding && <CodingDiffSummary coding={diff.coding} />}

            {codebookHasChanges && (
              <div className="flex flex-col gap-2 border-t border-line-soft pt-2">
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

            {!hasAnyChanges && <p className="text-sm text-paper/60">No changes between these versions.</p>}
          </div>
        )}
      </div>
    </div>
  );
}
