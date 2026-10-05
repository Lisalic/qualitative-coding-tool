import { useMemo } from "react";
import Dropdown from "./Dropdown";
import { btn, inputSm } from "../../lib/uiClasses";
import { projectLabel } from "../../lib/projectOptions";

/** Display name for a file row. The three hooks that feed this picker each
 * shape their items differently, so the coalescing chain is the seam. */
function itemLabel(item) {
  return String(item.display_name ?? item.name ?? item.id ?? "");
}

/**
 * Compact file picker for a PageShell toolbar.
 *
 * This is now a thin adapter over `Dropdown` — it supplies the trigger's
 * toolbar-button look, maps file rows onto `{value,label,meta}`, and hands
 * the project filter to `Dropdown`'s `header` slot. It used to be a second,
 * parallel dropdown implementation (its own `absolute` popover, its own
 * search box, its own dismissal, and no keyboard navigation at all), which
 * meant "the dropdown" looked and behaved differently depending on which
 * page you were on.
 *
 * Ids are compared as strings throughout, because the pages disagree about
 * the type: `ViewCodebook` passes a numeric file id while the others pass a
 * schema-name string. The old split — `String()` in the trigger, strict `===`
 * in the list — meant a numeric id showed the right trigger label but never
 * highlighted its row. `onSelect` still receives the id in its original type.
 */
export default function ArtifactPicker({
  items = [],
  selectedId,
  onSelect,
  projects = [],
  selectedProject,
  onProjectChange,
  showProjectFilter = false,
  emptyMessage = "No items available",
  loading = false,
  placeholder = "Select…",
  searchPlaceholder = "Search by name…",
}) {
  const options = useMemo(
    () =>
      [...items]
        .sort((a, b) => itemLabel(a).localeCompare(itemLabel(b), undefined, { sensitivity: "base" }))
        .map((item) => ({
          value: String(item.id),
          label: itemLabel(item),
          meta: item.description,
        })),
    [items],
  );

  const projectOptions = useMemo(
    () => [
      { value: "", label: "All projects" },
      ...projects.map((project) => ({ value: String(project.id), label: projectLabel(project) })),
    ],
    [projects],
  );

  const header = showProjectFilter ? (
    <Dropdown
      value={selectedProject ? String(selectedProject) : ""}
      options={projectOptions}
      onChange={(v) => onProjectChange?.(v)}
      placeholder="All projects"
      triggerClassName={`w-full ${inputSm}`}
      listLabel="Filter by project"
      searchPlaceholder="Search projects…"
      emptyMessage="No projects match that search."
    />
  ) : null;

  return (
    <Dropdown
      value={selectedId == null ? "" : String(selectedId)}
      options={options}
      onChange={(v) => {
        // Hand back the id in the type the page gave us, not the string the
        // option list carries.
        const item = items.find((candidate) => String(candidate.id) === v);
        onSelect?.(item ? item.id : v);
      }}
      placeholder={placeholder}
      triggerClassName={`${btn} max-w-[18rem]`}
      searchPlaceholder={searchPlaceholder}
      emptyMessage="No files match that search."
      noOptionsMessage={emptyMessage}
      loadingLabel={loading ? "Loading…" : undefined}
      listLabel="Files"
      renderOptionMeta={(opt) => opt.meta || null}
      header={header}
      // The list is always searchable here even when short: these pages are
      // reached with a file already in mind, and the box is where you type
      // its name.
      searchable
    />
  );
}
