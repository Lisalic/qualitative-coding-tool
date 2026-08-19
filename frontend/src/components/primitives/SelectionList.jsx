import { useMemo, useState } from "react";

const inputClasses =
  "w-full border border-paper bg-white/5 px-3 py-1.5 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper";

function itemLabel(item) {
  return String(item.display_name ?? item.name ?? item.id ?? "");
}

/**
 * Document picker used by every "view" page (ArtifactSelector) and the
 * data browser (DatabaseSelectionSection). Renders as a scrollable,
 * alphabetized 2-column grid with an always-visible name-filter search box,
 * so this doesn't degrade once a user accumulates dozens of
 * codebooks/comparisons/summaries.
 */
export default function SelectionList({
  items = [],
  selectedId,
  onSelect = () => {},
  className = "mb-6 border-2 border-paper p-4",
  listClassName = "mt-3 grid max-h-32 grid-cols-2 content-start gap-1 overflow-y-auto",
  buttonClass = "w-full border border-paper px-3 py-1.5 text-left text-sm transition-colors hover:bg-paper hover:text-ink",
  selectedButtonClass = "bg-paper text-ink",
  emptyMessage = "No items available",
  searchPlaceholder = "Search by name…",
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matched = q
      ? items.filter((item) => itemLabel(item).toLowerCase().includes(q))
      : items;
    return [...matched].sort((a, b) =>
      itemLabel(a).localeCompare(itemLabel(b), undefined, { sensitivity: "base" }),
    );
  }, [items, query]);

  if (!items || items.length === 0) {
    return (
      <div className={className}>
        <p className="text-paper">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={className}>
      <input
        type="text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={searchPlaceholder}
        className={inputClasses}
      />
      <div className={listClassName}>
        {filtered.length === 0 ? (
          <p className="col-span-2 px-1 py-2 text-sm text-paper/70">
            No matches for &ldquo;{query}&rdquo;
          </p>
        ) : (
          filtered.map((item) => {
            const isSelected = selectedId === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`${buttonClass} ${isSelected ? selectedButtonClass : ""}`}
                onClick={() => onSelect(item.id)}
              >
                <span className="block">{itemLabel(item)}</span>
                {item.description ? (
                  <span
                    className={`block text-xs ${isSelected ? "text-ink/70" : "text-paper/60"}`}
                  >
                    {item.description}
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
