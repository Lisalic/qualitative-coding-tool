import SelectionList from "./SelectionList";

// Project scope (when shown) lives inside SelectionList's own toolbar, next
// to the search box, rather than as a separate control rendered here.
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
    <SelectionList
      items={items}
      selectedId={selectedId}
      onSelect={onSelect}
      className={listClassName}
      buttonClass={buttonClassName}
      emptyMessage={emptyMessage}
      showProjectFilter={showProjectFilter}
      projects={projects}
      selectedProject={selectedProject}
      onProjectChange={onProjectChange}
    />
  );
}
