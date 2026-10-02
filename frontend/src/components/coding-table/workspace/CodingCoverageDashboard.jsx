import { useState, useEffect } from "react";
import { apiFetch } from "../../../api";

/**
 * Descriptive corpus coverage dashboard for qualitative coding artifacts.
 *
 * Displays:
 * 1. Descriptive disclaimer notice (does NOT imply statistical representativeness).
 * 2. Coded vs. uncoded row counts and percentages.
 * 3. Codes-per-row distribution and summary statistics.
 * 4. Code density buckets (0, 1, 2, 3-4, 5+ codes).
 * 5. Code family rollups with nested code breakdowns and per-code color badges.
 */
export default function CodingCoverageDashboard({ schema, refreshKey, getCodeColor }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!schema) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch(`/api/coding/${encodeURIComponent(schema)}/coverage`)
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || errData.error || "Failed to load coverage");
        }
        return res.json();
      })
      .then((json) => {
        if (!cancelled) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [schema, refreshKey]);

  if (loading) {
    return (
      <div className="p-3 text-xs text-paper/60 animate-pulse">
        Computing coverage metrics…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 text-xs text-red-400 border border-line bg-surface-raised font-mono">
        {error}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="flex flex-col gap-4 text-xs overflow-y-auto px-1 pb-4">
      {/* Disclaimer Notice */}
      <div className="border border-line bg-surface-raised p-2 text-[11px] leading-snug text-paper/70">
        <span className="font-semibold text-paper uppercase tracking-wider block mb-0.5">
          Descriptive Notice
        </span>
        {data.notice}
      </div>

      {/* Overview Grid */}
      <div className="grid grid-cols-2 gap-2">
        <div className="border border-line p-2 bg-paper/5 flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-paper/50">Coded Rows</span>
          <span className="text-base font-semibold text-paper mt-0.5 font-mono">
            {data.coded_rows} <span className="text-xs text-paper/60 font-normal">({data.coded_percentage}%)</span>
          </span>
          <span className="text-[10px] text-paper/40 mt-1 font-mono">of {data.total_rows} total rows</span>
        </div>

        <div className="border border-line p-2 bg-paper/5 flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-paper/50">Uncoded Rows</span>
          <span className="text-base font-semibold text-paper mt-0.5 font-mono">
            {data.uncoded_rows} <span className="text-xs text-paper/60 font-normal">({data.uncoded_percentage}%)</span>
          </span>
          <span className="text-[10px] text-paper/40 mt-1 font-mono">of {data.total_rows} total rows</span>
        </div>
      </div>

      {/* Codes Applied Summary */}
      <div className="border border-line p-2 bg-paper/5 flex justify-between items-center text-xs">
        <span className="text-paper/70">Distinct Codes Applied:</span>
        <span className="font-mono font-semibold text-paper">
          {data.distinct_codes_applied}{" "}
          <span className="text-paper/40 font-normal">/ {data.total_codebook_codes} in codebook</span>
        </span>
      </div>

      {/* Code Density Buckets */}
      <div className="flex flex-col gap-1.5">
        <span className="text-[11px] uppercase tracking-wider font-semibold text-paper/80 border-b border-line pb-1">
          Code Density Distribution
        </span>
        <div className="flex flex-col gap-1 mt-1">
          {(data.density_buckets || []).map((b) => (
            <div key={b.bucket} className="flex flex-col gap-0.5 text-xs">
              <div className="flex justify-between items-baseline">
                <span className="text-paper/80 font-mono">
                  {b.label} <span className="text-[10px] text-paper/50">({b.bucket})</span>
                </span>
                <span className="font-mono text-paper/70">
                  {b.row_count} <span className="text-paper/40">({b.percentage}%)</span>
                </span>
              </div>
              <div className="h-1.5 w-full bg-line/40 overflow-hidden">
                <div
                  className="h-full bg-paper"
                  style={{ width: `${Math.min(100, Math.max(0, b.percentage))}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Codes Per Row Summary Stats */}
      {data.codes_per_row && (
        <div className="border border-line p-2 bg-paper/5">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-paper/60 block mb-1.5">
            Codes Per Row Statistics
          </span>
          <div className="grid grid-cols-4 gap-1 text-center font-mono">
            <div>
              <div className="text-[10px] text-paper/40">Mean</div>
              <div className="text-xs font-semibold text-paper">{data.codes_per_row.mean}</div>
            </div>
            <div>
              <div className="text-[10px] text-paper/40">Median</div>
              <div className="text-xs font-semibold text-paper">{data.codes_per_row.median}</div>
            </div>
            <div>
              <div className="text-[10px] text-paper/40">Min</div>
              <div className="text-xs font-semibold text-paper">{data.codes_per_row.min}</div>
            </div>
            <div>
              <div className="text-[10px] text-paper/40">Max</div>
              <div className="text-xs font-semibold text-paper">{data.codes_per_row.max}</div>
            </div>
          </div>
        </div>
      )}

      {/* Code Family Rollups */}
      <div className="flex flex-col gap-2">
        <span className="text-[11px] uppercase tracking-wider font-semibold text-paper/80 border-b border-line pb-1">
          Code Family Rollups
        </span>
        {(!data.family_rollups || data.family_rollups.length === 0) ? (
          <div className="text-paper/40 py-2">No code families defined.</div>
        ) : (
          data.family_rollups.map((fam) => (
            <div key={fam.family_uid} className="border border-line bg-paper/5 p-2 flex flex-col gap-1.5">
              <div className="flex justify-between items-baseline border-b border-line/40 pb-1">
                <span className="font-semibold text-paper text-xs">{fam.family_name}</span>
                <span className="font-mono text-[11px] text-paper/70">
                  {fam.row_count} rows ({fam.row_percentage}%)
                </span>
              </div>
              <div className="flex flex-col gap-1 pl-1">
                {(fam.codes || []).map((code) => {
                  const badgeColor = getCodeColor ? getCodeColor(code.code_uid) : "#888";
                  return (
                    <div key={code.code_uid} className="flex justify-between items-center text-[11px]">
                      <div className="flex items-center gap-1.5 truncate pr-2">
                        <span
                          className="inline-block w-2 h-2 shrink-0 border border-line"
                          style={{ backgroundColor: badgeColor }}
                        />
                        <span className="truncate text-paper/80" title={code.name}>
                          {code.name}
                        </span>
                      </div>
                      <span className="font-mono text-paper/50 shrink-0">
                        {code.ai_entry_count > 0 && (
                          <span
                            className="mr-1.5 text-[10px]"
                            title={`${code.ai_entry_count} AI-coded, ${code.human_entry_count} human-coded segments`}
                          >
                            AI {code.ai_entry_count} &middot; H {code.human_entry_count}
                          </span>
                        )}
                        {code.row_count} <span className="text-[10px]">({code.row_percentage}%)</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
