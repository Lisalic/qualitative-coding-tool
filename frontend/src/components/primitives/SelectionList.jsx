import { useMemo, useState } from "react";
import { input, select } from "../../lib/uiClasses";

const inputClasses = `min-w-0 ${input}`;

const projectSelectClasses = `${select} sm:w-56 sm:flex-none`;

function itemLabel(item) {
  return String(item.display_name ?? item.name ?? item.id ?? "");
}

function projectLabel(project) {
  return project.projectname || project.display_name || project.schema_name || project.id;
}

/**
 * Document picker body: an alphabetized, scrollable grid with an
 * always-visible name filter, so this doesn't degrade once a user
 * accumulates dozens of codebooks/comparisons/summaries.
 *
 * This renders no chrome of its own -- it lives inside ArtifactPicker's
 * toolbar popover. It used to be the page-level `border-2 border-paper p-4`
 * box every view page opened with, which cost ~200px above content that
 * often wanted the full viewport.
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
  className = "",
  listClassName = "mt-2 grid max-h-[50vh] grid-cols-1 content-start gap-1 overflow-y-auto sm:grid-cols-2",
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
        <p className="text-sm text-paper/70">{emptyMessage}</p>
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
            <p className="px-1 py-2 text-sm text-paper/70 sm:col-span-2">
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
        <p className="mt-2 text-sm text-paper/70">{emptyMessage}</p>
      )}
    </div>
  );
}
