import { Link } from "react-router-dom";
import MarkdownDisplay from "../primitives/MarkdownDisplay";
import { select } from "../../lib/uiClasses";
import { useComparisonContent } from "./useSourceComparisons";

/**
 * Integrate rail's "Comparison" tab: read a Compare Codebook report of
 * the codebooks being merged, right beside the draft, and choose whether
 * the AI merge assistant should follow it. Rendered inside the rail's
 * tabbed `Panel`, so it draws no border of its own.
 *
 * `comparisons` comes from `useSourceComparisons` -- only reports made
 * from at least one of the selected codebooks are offered.
 */
export default function IntegrateComparisonPanel({
  comparisons,
  loading,
  selected,
  onSelect,
  useInAi,
  onUseInAiChange,
  firstSourceRef,
  disabled,
}) {
  const { content, loading: contentLoading, error } = useComparisonContent(selected);

  if (loading) {
    return <p className="text-sm text-paper/60">Looking for comparisons of these codebooks...</p>;
  }

  if (comparisons.length === 0) {
    return (
      <div className="flex flex-col gap-2 text-sm">
        <p className="italic text-paper/60">No comparisons of these codebooks yet.</p>
        <p className="text-paper/60">
          Compare two of them first to get a report of overlaps, conflicts and suggested merges you can
          read here -- and hand to the AI merge assistant.
        </p>
        <Link
          to="/compare-codebook"
          state={firstSourceRef ? { codebookA: firstSourceRef } : undefined}
          className="self-start text-sm underline"
        >
          Open Compare Codebook
        </Link>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="flex shrink-0 flex-col gap-2">
        <label htmlFor="integrateComparison" className="sr-only">
          Comparison report
        </label>
        <select
          id="integrateComparison"
          className={select}
          value={selected || ""}
          onChange={(e) => onSelect(e.target.value || null)}
          disabled={disabled}
        >
          <option value="">Select a comparison…</option>
          {comparisons.map((cmp) => (
            <option key={cmp.ref} value={cmp.ref}>
              {cmp.name}
              {cmp.coversSelection ? "" : " (covers one source)"}
            </option>
          ))}
        </select>

        {selected && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={useInAi}
              onChange={(e) => onUseInAiChange(e.target.checked)}
              disabled={disabled}
            />
            Use this comparison to guide the AI merge
          </label>
        )}
      </div>

      {selected ? (
        contentLoading ? (
          <p className="text-sm text-paper/60">Loading comparison...</p>
        ) : error ? (
          <p className="text-sm text-error">{error}</p>
        ) : content ? (
          <MarkdownDisplay content={content} className="text-sm text-paper" />
        ) : (
          <p className="italic text-paper/60">This comparison is empty.</p>
        )
      ) : (
        <p className="italic text-paper/60">Pick a comparison to read it alongside your draft.</p>
      )}
    </div>
  );
}
