import { useMemo, useState } from "react";

const inputClasses =
  "min-w-0 border border-paper bg-white/5 px-3 py-1.5 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper";

const projectSelectClasses =
  "border border-paper bg-white/5 px-3 py-1.5 text-sm text-paper focus:outline-none focus:ring-2 focus:ring-paper sm:w-56 sm:flex-none";

function itemLabel(item) {
  return String(item.display_name ?? item.name ?? item.id ?? "");
}

function projectLabel(project) {
  return project.projectname || project.display_name || project.schema_name || project.id;
}

/**
 * Document picker used by every "view" page (ArtifactSelector) and the
 * data browser (DatabaseSelectionSection). Renders as a scrollable,
 * alphabetized 2-column grid with an always-visible name-filter search box,
 * so this doesn't degrade once a user accumulates dozens of
 * codebooks/comparisons/summaries.
 *
 * When showProjectFilter is set, the project scope selector sits in the
 * same toolbar row as the search box (project narrows scope, search finds
 * a name within it) rather than as a separate control stacked above —
 * one picker, not two.
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
  showProjectFilter = false,
  projects = [],
  selectedProject = "",
  onProjectChange,
  allProjectsLabel = "All Projects",
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

  const hasItems = Boolean(items && items.length > 0);

  // With no project filter, an empty list means there's nothing to search
  // or pick from, so collapse to just the message (matches prior behavior).
  // With a project filter, keep the toolbar visible even when the current
  // project has no items, so switching projects stays reachable.
  if (!hasItems && !showProjectFilter) {
    return (
      <div className={className}>
        <p className="text-paper">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={className}>
      <div className={showProjectFilter ? "flex flex-col gap-2 sm:flex-row" : undefined}>
        {showProjectFilter ? (
          <select
            value={selectedProject}
            onChange={(event) => onProjectChange?.(event.target.value)}
            aria-label="Filter by project"
            className={projectSelectClasses}
          >
            <option value="">{allProjectsLabel}</option>
            {(projects || []).map((project) => (
              <option key={project.id} value={String(project.id)}>
                {projectLabel(project)}
              </option>
            ))}
          </select>
        ) : null}
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={searchPlaceholder}
          className={showProjectFilter ? `${inputClasses} w-full sm:flex-1` : `${inputClasses} w-full`}
        />
      </div>
      {hasItems ? (
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
      ) : (
        <p className="mt-3 text-paper">{emptyMessage}</p>
      )}
    </div>
  );
}
