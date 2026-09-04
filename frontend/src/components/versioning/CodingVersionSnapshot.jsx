import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api";
import { flattenCodebookCodes, getCodeColor } from "../../lib/codingUtils";
import CodeLegend from "../coding-table/CodeLegend";
import CodingReaderPane from "../coding-table/workspace/CodingReaderPane";

const PAGE_SIZE = 25;
const btnSmall =
  "border border-paper px-2 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

function rowPreview(row) {
  if (row.title) return row.title;
  const content = String(row.content || "").trim();
  return content ? content.slice(0, 80) : "(empty)";
}

export default function CodingVersionSnapshot({
  artifactRef,
  versionNo,
  codebookTree,
  totalRows,
  totalCoded,
}) {
  const [page, setPage] = useState(0);
  const [rowsState, setRowsState] = useState({ rows: [], total: 0, loading: true, error: "" });
  const [activeItemId, setActiveItemId] = useState(null);

  useEffect(() => {
    setPage(0);
    setActiveItemId(null);
  }, [artifactRef, versionNo]);

  useEffect(() => {
    let cancelled = false;
    setRowsState((current) => ({ ...current, loading: true, error: "" }));
    const params = new URLSearchParams({
      version_no: String(versionNo),
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    apiFetch(`/api/coding/${encodeURIComponent(artifactRef)}/rows?${params}`)
      .then((response) => {
        if (!response.ok) throw new Error(`Failed to load coding rows (HTTP ${response.status})`);
        return response.json();
      })
      .then((data) => {
        if (cancelled) return;
        const rows = Array.isArray(data.rows) ? data.rows : [];
        setRowsState({ rows, total: data.total || 0, loading: false, error: "" });
        setActiveItemId((current) =>
          rows.some((row) => row.item_id === current) ? current : rows[0]?.item_id || null,
        );
      })
      .catch((error) => {
        if (!cancelled) {
          setRowsState({ rows: [], total: 0, loading: false, error: error?.message || "Failed to load coding rows" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [artifactRef, page, versionNo]);

  const activeRow = rowsState.rows.find((row) => row.item_id === activeItemId) || null;
  const availableCodes = useMemo(() => flattenCodebookCodes(codebookTree), [codebookTree]);
  const pageCount = Math.ceil(rowsState.total / PAGE_SIZE);

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 border border-paper/30 text-center text-xs uppercase tracking-wide">
        <div className="border-r border-paper/30 px-2 py-2">
          <strong className="block text-lg text-paper">{totalRows}</strong>
          <span className="text-paper/50">Total rows</span>
        </div>
        <div className="border-r border-paper/30 px-2 py-2">
          <strong className="block text-lg text-paper">{totalCoded}</strong>
          <span className="text-paper/50">Coded rows</span>
        </div>
        <div className="px-2 py-2">
          <strong className="block text-lg text-paper">{availableCodes.length}</strong>
          <span className="text-paper/50">Codes</span>
        </div>
      </div>

      {rowsState.error ? (
        <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{rowsState.error}</p>
      ) : (
        <div className="grid min-h-[560px] grid-cols-1 gap-3 xl:grid-cols-[200px_minmax(280px,1fr)_220px]">
          <div className="flex min-h-0 flex-col border border-paper">
            <div className="border-b border-paper/30 px-3 py-2">
              <h3 className="text-sm font-semibold">Documents</h3>
              <p className="text-xs text-paper/50">{totalCoded} of {totalRows} coded in v{versionNo}</p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {rowsState.loading ? (
                <p className="p-3 text-sm text-paper/60">Loading rows...</p>
              ) : rowsState.rows.length === 0 ? (
                <p className="p-3 text-sm text-paper/60">No rows in this version.</p>
              ) : (
                <ul>
                  {rowsState.rows.map((row) => {
                    const isActive = row.item_id === activeItemId;
                    const codeCount = Array.isArray(row.codes) ? row.codes.length : 0;
                    return (
                      <li key={row.item_id}>
                        <button
                          type="button"
                          onClick={() => setActiveItemId(row.item_id)}
                          className={`w-full border-b border-paper/10 px-3 py-2.5 text-left transition-colors ${
                            isActive ? "bg-paper text-ink" : "hover:bg-white/5"
                          }`}
                        >
                          <span className="block truncate text-sm font-medium">{rowPreview(row)}</span>
                          <span className={`mt-0.5 block text-xs ${isActive ? "text-ink/60" : "text-paper/50"}`}>
                            {codeCount > 0 ? `${codeCount} code${codeCount === 1 ? "" : "s"}` : "Not coded"}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
            <div className="flex items-center justify-between border-t border-paper/30 p-2">
              <button type="button" className={btnSmall} onClick={() => setPage((value) => value - 1)} disabled={rowsState.loading || page === 0}>
                Prev
              </button>
              <span className="text-xs text-paper/60">{pageCount ? `${page + 1} / ${pageCount}` : "0 / 0"}</span>
              <button type="button" className={btnSmall} onClick={() => setPage((value) => value + 1)} disabled={rowsState.loading || page >= pageCount - 1}>
                Next
              </button>
            </div>
          </div>

          <CodingReaderPane
            activeRow={activeRow}
            availableCodes={availableCodes}
            getCodeColor={getCodeColor}
            readOnly
          />

          <div className="flex min-h-0 flex-col gap-2 overflow-y-auto border border-paper p-3">
            <h3 className="text-sm font-semibold">Codebook at v{versionNo}</h3>
            {codebookTree.length === 0 ? (
              <p className="text-sm text-paper/50">No codes in this version.</p>
            ) : (
              <CodeLegend
                codebookTree={codebookTree}
                selectedFilterCodes={[]}
                getCodeColor={getCodeColor}
                disabled
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
