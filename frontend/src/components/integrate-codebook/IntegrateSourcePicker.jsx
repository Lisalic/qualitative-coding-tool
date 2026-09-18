import { useMemo, useState } from "react";
import { inputSm } from "../../lib/uiClasses";

/**
 * Multi-select field for "which codebooks am I merging" -- a search box,
 * a chip strip of what's picked so far, and a grid of selectable cards
 * (name + description, whole card is the hit target) rather than a bare
 * checkbox list. `Dropdown` (the app's one select primitive) is
 * single-select only and there is no multi-select primitive elsewhere in
 * the app; this is still a bordered/inverted-fill selection idiom (the
 * style guide's pill-selector pattern), just laid out as cards instead of
 * a stacked list so a codebook's description is visible while choosing,
 * not only after.
 *
 * The chip strip exists because a card grid scrolls -- once several
 * codebooks are picked, a chip is how the researcher confirms the full
 * selection without hunting back through the grid.
 */
export default function IntegrateSourcePicker({ codebooks, selected, onToggle, loading, disabled }) {
  const [search, setSearch] = useState("");

  const nameByRef = useMemo(() => {
    const names = {};
    for (const option of codebooks) names[option.metadata?.schema || option.id] = option.name;
    return names;
  }, [codebooks]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return codebooks;
    return codebooks.filter(
      (option) =>
        option.name?.toLowerCase().includes(query) || option.description?.toLowerCase().includes(query),
    );
  }, [codebooks, search]);

  if (loading) {
    return <p className="text-sm text-paper/60">Loading codebooks...</p>;
  }
  if (codebooks.length === 0) {
    return <p className="text-sm text-paper/60">No codebooks yet -- create one first.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((ref) => (
            <span
              key={ref}
              className="inline-flex max-w-full items-center gap-1 border border-paper bg-paper px-2 py-0.5 text-xs text-ink"
            >
              <span className="max-w-[12rem] truncate">{nameByRef[ref] || ref}</span>
              <button
                type="button"
                className="shrink-0 leading-none text-ink/60 hover:text-ink"
                onClick={() => onToggle(ref)}
                disabled={disabled}
                aria-label={`Remove ${nameByRef[ref] || ref} from the selection`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {codebooks.length > 5 && (
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search codebooks…"
          className={inputSm}
          disabled={disabled}
        />
      )}

      <div className="grid max-h-72 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
        {filtered.length === 0 ? (
          <p className="col-span-full text-sm text-paper/60">No codebooks match that search.</p>
        ) : (
          filtered.map((option) => {
            const ref = option.metadata?.schema || option.id;
            const checked = selected.includes(ref);
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onToggle(ref)}
                disabled={disabled}
                aria-pressed={checked}
                className={`flex flex-col items-start gap-1 border p-2.5 text-left text-sm transition-colors ${
                  checked ? "border-paper bg-paper text-ink" : "border-line hover:bg-white/5"
                } ${disabled ? "opacity-50" : ""}`}
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <span className="min-w-0 truncate font-medium">{option.name}</span>
                  {checked && <span className="shrink-0">✓</span>}
                </div>
                {option.description ? (
                  <span className={`truncate text-xs ${checked ? "text-ink/70" : "text-paper/50"}`}>
                    {option.description}
                  </span>
                ) : null}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
