import SelectionList from "./SelectionList";
import ProjectFilterSelect from "../forms/ProjectFilterSelect";

// Renders as a fragment (not a wrapping div) so the project filter and the
// item list become direct siblings of whatever flex/gap container hosts
// this component — matching the spacing produced by DatabaseSelectionSection
// and CodingProjectScopeBar+ArtifactSelector, which do the same. Wrapping
// them in a div here would make them count as a single flex child and lose
// the parent's `gap` spacing between the filter and the list.
export default function ArtifactSelector({
  items,
  selectedId,
  onSelect,
  listClassName,
  buttonClassName,
  emptyMessage,
  showProjectFilter,
  projects,
  selectedProject,
  onProjectChange,
}) {
  return (
    <>
      {showProjectFilter ? (
        <ProjectFilterSelect
          projects={projects}
          value={selectedProject}
          onChange={onProjectChange}
        />
      ) : null}
      <SelectionList
        items={items}
        selectedId={selectedId}
        onSelect={onSelect}
        className={listClassName}
        buttonClass={buttonClassName}
        emptyMessage={emptyMessage}
      />
    </>
  );
}
