import React from "react";
import Panel from "../shell/Panel";

/**
 * Split results table for deterministic cross-artifact comparisons (QC-002).
 * Displays stable-identity matches, directional additions/removals,
 * per-code delta counts, and applied/removed evidence without requiring LLM calls.
 */
export default function ComputedComparisonResults({ mode, data, loading, error, onSwap }) {
  if (loading) {
    return (
      <Panel title="Computed Comparison" className="w-full">
        <div className="p-4 text-xs text-paper/60 animate-pulse font-mono">
          Computing deterministic comparison…
        </div>
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel title="Computed Comparison" className="w-full">
        <div className="p-4 text-xs text-red-400 border border-line bg-surface-raised font-mono">
          {error}
        </div>
      </Panel>
    );
  }

  if (!data) {
    return null;
  }

  const isCodebook = mode === "codebook";

  return (
    <Panel
      title="Computed Comparison (Deterministic)"
      actions={
        onSwap && (
          <button
            type="button"
            className="text-xs uppercase tracking-wider text-paper/70 hover:text-paper font-semibold border border-line px-2 py-1 bg-surface-raised"
            onClick={onSwap}
          >
            Swap A ⇄ B
          </button>
        )
      }
      className="w-full"
      bodyClassName="flex flex-col gap-4 p-4 text-xs"
    >
      {/* Notice / Status Banners */}
      {data.unrelated_histories && (
        <div className="border border-line bg-surface-raised p-2 text-xs text-paper/80">
          <span className="font-semibold text-paper block mb-0.5">Unrelated Histories</span>
          These codebooks do not share stable code identities. Codes have been matched by normalized name per documented rules.
        </div>
      )}

      {data.unrelated_corpus && (
        <div className="border border-line bg-surface-raised p-2 text-xs text-paper/80">
          <span className="font-semibold text-paper block mb-0.5">Unrelated Corpora</span>
          These coding artifacts share no common row or post identifiers.
        </div>
      )}

      {data.is_empty && (
        <div className="border border-line p-3 text-center text-paper/60 font-mono">
          Artifacts are identical (no differences found).
        </div>
      )}

      {isCodebook ? (
        /* CODEBOOK DIFF VIEW */
        <div className="flex flex-col gap-4">
          {/* Summary Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Only in A (Removed)</div>
              <div className="text-base font-semibold font-mono text-paper mt-0.5">
                {(data.removed || []).length}
              </div>
            </div>
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Only in B (Added)</div>
              <div className="text-base font-semibold font-mono text-paper mt-0.5">
                {(data.added || []).length}
              </div>
            </div>
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Modified (Renamed/Redefined/Moved)</div>
              <div className="text-base font-semibold font-mono text-paper mt-0.5">
                {(data.renamed || []).length + (data.redefined || []).length + (data.moved || []).length}
              </div>
            </div>
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Unchanged</div>
              <div className="text-base font-semibold font-mono text-paper mt-0.5">
                {(data.unchanged || []).length}
              </div>
            </div>
          </div>

          {/* Split comparison tables */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Left Column: File A details */}
            <div className="border border-line p-2 flex flex-col gap-2 bg-paper/5">
              <div className="font-semibold border-b border-line pb-1 text-paper flex justify-between">
                <span>Codebook A: {data.file_a?.filename}</span>
                <span className="font-mono text-paper/50">v{data.file_a?.version_no}</span>
              </div>
              <div className="text-[11px] uppercase tracking-wider text-paper/60 font-semibold mt-1">
                Only in A ({data.removed?.length || 0})
              </div>
              {(!data.removed || data.removed.length === 0) ? (
                <div className="text-paper/40 py-1 text-xs">None</div>
              ) : (
                <ul className="divide-y divide-line/40 font-mono text-xs">
                  {data.removed.map((c) => (
                    <li key={c.code_uid} className="py-1">
                      <span className="font-semibold text-paper">{c.name}</span>{" "}
                      <span className="text-paper/40">({c.family_name || "No family"})</span>
                      {c.body && <div className="text-[11px] text-paper/60 truncate">{c.body}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Right Column: File B details */}
            <div className="border border-line p-2 flex flex-col gap-2 bg-paper/5">
              <div className="font-semibold border-b border-line pb-1 text-paper flex justify-between">
                <span>Codebook B: {data.file_b?.filename}</span>
                <span className="font-mono text-paper/50">v{data.file_b?.version_no}</span>
              </div>
              <div className="text-[11px] uppercase tracking-wider text-paper/60 font-semibold mt-1">
                Only in B ({data.added?.length || 0})
              </div>
              {(!data.added || data.added.length === 0) ? (
                <div className="text-paper/40 py-1 text-xs">None</div>
              ) : (
                <ul className="divide-y divide-line/40 font-mono text-xs">
                  {data.added.map((c) => (
                    <li key={c.code_uid} className="py-1">
                      <span className="font-semibold text-paper">{c.name}</span>{" "}
                      <span className="text-paper/40">({c.family_name || "No family"})</span>
                      {c.body && <div className="text-[11px] text-paper/60 truncate">{c.body}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Modifications Section */}
          {((data.renamed && data.renamed.length > 0) ||
            (data.redefined && data.redefined.length > 0) ||
            (data.moved && data.moved.length > 0) ||
            (data.matched_by_name && data.matched_by_name.length > 0)) && (
            <div className="border border-line p-3 flex flex-col gap-2">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-paper/80 border-b border-line pb-1">
                Substantive Differences (Matched Codes)
              </span>

              {data.renamed?.map((r) => (
                <div key={r.code_uid} className="flex justify-between items-baseline text-xs font-mono py-1 border-b border-line/30">
                  <span className="text-paper/50">Renamed:</span>
                  <span className="text-paper">
                    <span className="line-through text-paper/50">{r.from.name}</span> → <span className="font-semibold">{r.to.name}</span>
                  </span>
                </div>
              ))}

              {data.redefined?.map((r) => (
                <div key={r.code_uid} className="flex flex-col gap-0.5 text-xs font-mono py-1 border-b border-line/30">
                  <span className="font-semibold text-paper">Redefined: {r.to.name}</span>
                  <div className="text-paper/50 line-through text-[11px]">A: {r.from.body || r.from.definition}</div>
                  <div className="text-paper text-[11px]">B: {r.to.body || r.to.definition}</div>
                </div>
              ))}

              {data.moved?.map((m) => (
                <div key={m.code_uid} className="flex justify-between items-baseline text-xs font-mono py-1 border-b border-line/30">
                  <span className="text-paper/50">Moved Family: {m.to.name}</span>
                  <span className="text-paper">
                    {m.from.family_name || "None"} → <span className="font-semibold">{m.to.family_name || "None"}</span>
                  </span>
                </div>
              ))}

              {data.matched_by_name?.map((m, idx) => (
                <div key={idx} className="flex flex-col gap-0.5 text-xs font-mono py-1 border-b border-line/30">
                  <span className="font-semibold text-paper">Matched by Name: {m.name}</span>
                  <div className="text-[10px] text-paper/40">
                    A UID: {m.code_uid_from} | B UID: {m.code_uid_to}
                  </div>
                  {m.redefined && (
                    <div className="text-[11px] text-paper/60">
                      Definitions differ: &ldquo;{m.from.body || "empty"}&rdquo; vs &ldquo;{m.to.body || "empty"}&rdquo;
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* CODING DIFF VIEW */
        <div className="flex flex-col gap-4">
          {/* Summary Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono">
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Rows Recoded</div>
              <div className="text-base font-semibold text-paper mt-0.5">{data.rows_recoded}</div>
            </div>
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Identical Coded Rows</div>
              <div className="text-base font-semibold text-paper mt-0.5">{data.matching_rows}</div>
            </div>
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Newly Coded (in B)</div>
              <div className="text-base font-semibold text-paper mt-0.5">{data.rows_newly_coded}</div>
            </div>
            <div className="border border-line p-2 bg-paper/5">
              <div className="text-[10px] text-paper/50 uppercase">Newly Uncoded (in B)</div>
              <div className="text-base font-semibold text-paper mt-0.5">{data.rows_newly_uncoded}</div>
            </div>
          </div>

          {/* Per-code counts with delta */}
          <div className="border border-line p-3 flex flex-col gap-2">
            <span className="text-[11px] uppercase tracking-wider font-semibold text-paper/80 border-b border-line pb-1">
              Code Frequency Deltas
            </span>
            {(!data.code_counts || data.code_counts.length === 0) ? (
              <div className="text-paper/40 py-1 text-xs">All code frequencies are identical between A and B.</div>
            ) : (
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-line text-paper/50 text-[10px] uppercase">
                    <th className="py-1">Code</th>
                    <th className="py-1 text-right">In A</th>
                    <th className="py-1 text-right">In B</th>
                    <th className="py-1 text-right">Delta (B - A)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/30">
                  {data.code_counts.map((c) => (
                    <tr key={c.code_uid}>
                      <td className="py-1 text-paper font-semibold">{c.name}</td>
                      <td className="py-1 text-right text-paper/60">{c.from_count}</td>
                      <td className="py-1 text-right text-paper/60">{c.to_count}</td>
                      <td className="py-1 text-right font-bold">
                        {c.delta > 0 ? `+${c.delta}` : c.delta}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Split Evidence: Applied vs Removed */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="border border-line p-2 bg-paper/5 flex flex-col gap-2">
              <div className="font-semibold text-paper border-b border-line pb-1">
                Evidence Removed in B (Present only in A: {data.removed?.length || 0})
              </div>
              {(!data.removed || data.removed.length === 0) ? (
                <div className="text-paper/40 py-1 text-xs">None</div>
              ) : (
                <div className="max-h-60 overflow-y-auto divide-y divide-line/30 text-xs font-mono">
                  {data.removed.map((e, idx) => (
                    <div key={idx} className="py-1">
                      <div className="flex justify-between text-paper/70">
                        <span className="font-semibold text-paper">{e.code}</span>
                        <span className="text-[10px] text-paper/40">Row {e.post_id}</span>
                      </div>
                      <div className="text-[11px] text-paper/50 italic truncate">&ldquo;{e.quote}&rdquo;</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border border-line p-2 bg-paper/5 flex flex-col gap-2">
              <div className="font-semibold text-paper border-b border-line pb-1">
                Evidence Applied in B (New in B: {data.applied?.length || 0})
              </div>
              {(!data.applied || data.applied.length === 0) ? (
                <div className="text-paper/40 py-1 text-xs">None</div>
              ) : (
                <div className="max-h-60 overflow-y-auto divide-y divide-line/30 text-xs font-mono">
                  {data.applied.map((e, idx) => (
                    <div key={idx} className="py-1">
                      <div className="flex justify-between text-paper/70">
                        <span className="font-semibold text-paper">{e.code}</span>
                        <span className="text-[10px] text-paper/40">Row {e.post_id}</span>
                      </div>
                      <div className="text-[11px] text-paper/50 italic truncate">&ldquo;{e.quote}&rdquo;</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
