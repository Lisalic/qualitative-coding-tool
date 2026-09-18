import { useEffect, useState } from "react";
import { apiFetch } from "../../api";
import CodeLegend from "../coding-table/CodeLegend";
import { getCodeColor, groupCodesByFamily } from "../../lib/codingUtils";
import CodingVersionSnapshot from "./CodingVersionSnapshot";

const linkSmall = "text-xs text-paper/50 underline decoration-dotted hover:text-paper";
const noop = () => {};

// How many submissions/comments rows to show for a raw_data/filtered_data
// snapshot -- this is a historical inspection view, not the live,
// paginated data browser (DataTable.jsx), so a single capped page is
// enough to answer "what did this look like back then" without
// reimplementing search/pagination for a read-only snapshot.
const DATA_PREVIEW_LIMIT = 50;

function StatChip({ value, label }) {
  return (
    <div className="border border-paper/30 px-2.5 py-1.5">
      <div className="text-lg font-semibold leading-none">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-paper/50">{label}</div>
    </div>
  );
}

function DataRowsPreview({ rows, columns, emptyMessage }) {
  if (!rows || rows.length === 0) {
    return <p className="text-sm text-paper/50">{emptyMessage}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className="border-b-2 border-r border-paper px-2 py-1.5 text-left last:border-r-0">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={row.id ?? idx}>
              {columns.map((col) => (
                <td key={col.key} className="max-w-xs truncate border-b border-r border-paper/20 px-2 py-1.5 last:border-r-0">
                  {String(row[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function fetchCodebookContent(ref, versionNo) {
  const resp = await apiFetch(`/api/codebook?codebook_id=${encodeURIComponent(ref)}&version_no=${versionNo}`);
  if (!resp.ok) throw new Error(`Failed to load codebook (HTTP ${resp.status})`);
  const data = await resp.json();
  return { kind: "codebook", tree: groupCodesByFamily(data.codes) };
}

async function fetchCodingContent(ref, versionNo) {
  const artifactResp = await apiFetch(`/api/coding/${encodeURIComponent(ref)}?version_no=${versionNo}`);
  if (!artifactResp.ok) throw new Error(`Failed to load codebook snapshot (HTTP ${artifactResp.status})`);
  const artifact = await artifactResp.json();
  return {
    kind: "coding",
    tree: groupCodesByFamily(artifact.codes),
    totalRows: artifact.total_rows,
    totalCoded: artifact.total_coded,
  };
}

async function fetchDataContent(ref, versionNo) {
  const resp = await apiFetch(
    `/api/file-entries/?schema=${encodeURIComponent(ref)}&version_no=${versionNo}&limit=${DATA_PREVIEW_LIMIT}&offset=0`,
  );
  if (!resp.ok) throw new Error(`Failed to load data (HTTP ${resp.status})`);
  const data = await resp.json();
  return {
    kind: "data",
    submissions: data.submissions || [],
    comments: data.comments || [],
    totalSubmissions: data.total_submissions || 0,
    totalComments: data.total_comments || 0,
  };
}

const FETCHERS_BY_TYPE = {
  codebook: fetchCodebookContent,
  coding: fetchCodingContent,
  raw_data: fetchDataContent,
  filtered_data: fetchDataContent,
};

/**
 * Read-only snapshot of one artifact version's actual content --
 * "view a previous version", as opposed to `VersionHistoryPanel`'s
 * two-version diff (structural change) or "duplicate from here"
 * (fork a new artifact). Fetches through the same `version_no`-aware
 * endpoints each artifact type's live view already uses
 * (`GET /codebook`, `GET /coding/{ref}`+`/rows`, `GET /file-entries/`),
 * just pinned to a specific version instead of head/live.
 *
 * Not every file type has a content viewer here -- comparison/summary
 * artifacts are blobs with no structured "codes"/"rows" shape worth
 * building a dedicated renderer for; `useVersionHistoryPage` only wires
 * this in for the four types `FETCHERS_BY_TYPE` covers.
 */
export default function VersionContentViewer({ artifactRef, fileType, versionNo, onClose }) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    const fetcher = FETCHERS_BY_TYPE[fileType];
    if (!fetcher || !artifactRef || !versionNo) {
      setState({ status: "unsupported", data: null, error: null });
      return undefined;
    }
    setState({ status: "loading", data: null, error: null });
    fetcher(artifactRef, versionNo)
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ status: "error", data: null, error: err?.message || "Failed to load" });
      });
    return () => {
      cancelled = true;
    };
  }, [artifactRef, fileType, versionNo]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">
          Viewing v{versionNo}
        </span>
        <button type="button" className={linkSmall} onClick={onClose}>
          Close
        </button>
      </div>

      {state.status === "loading" && <p className="text-sm text-paper/60">Loading v{versionNo}...</p>}
      {state.status === "unsupported" && (
        <p className="text-sm text-paper/60">This file type has no content preview.</p>
      )}
      {state.status === "error" && (
        <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{state.error}</p>
      )}

      {state.status === "ready" && state.data.kind === "codebook" && (
        state.data.tree.length === 0 ? (
          <p className="text-sm text-paper/50">No codes in this version.</p>
        ) : (
          <CodeLegend
            codebookTree={state.data.tree}
            selectedFilterCodes={[]}
            onCodeToggle={noop}
            getCodeColor={getCodeColor}
            showDetails
          />
        )
      )}

      {state.status === "ready" && state.data.kind === "coding" && (
        <CodingVersionSnapshot
          artifactRef={artifactRef}
          versionNo={versionNo}
          codebookTree={state.data.tree}
          totalRows={state.data.totalRows}
          totalCoded={state.data.totalCoded}
        />
      )}

      {state.status === "ready" && state.data.kind === "data" && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-1.5">
            <StatChip value={state.data.totalSubmissions} label="Submissions" />
            <StatChip value={state.data.totalComments} label="Comments" />
          </div>
          <div>
            <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">
              Submissions (first {Math.min(DATA_PREVIEW_LIMIT, state.data.totalSubmissions)} of {state.data.totalSubmissions})
            </span>
            <div className="mt-1.5">
              <DataRowsPreview
                rows={state.data.submissions}
                columns={[
                  { key: "id", label: "ID" },
                  { key: "subreddit", label: "Subreddit" },
                  { key: "title", label: "Title" },
                  { key: "author", label: "Author" },
                ]}
                emptyMessage="No submissions in this version."
              />
            </div>
          </div>
          <div>
            <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">
              Comments (first {Math.min(DATA_PREVIEW_LIMIT, state.data.totalComments)} of {state.data.totalComments})
            </span>
            <div className="mt-1.5">
              <DataRowsPreview
                rows={state.data.comments}
                columns={[
                  { key: "id", label: "ID" },
                  { key: "subreddit", label: "Subreddit" },
                  { key: "body", label: "Body" },
                  { key: "author", label: "Author" },
                ]}
                emptyMessage="No comments in this version."
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
