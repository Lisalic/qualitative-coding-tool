import SelectionList from "./SelectionList";
import ProjectFilterSelect from "../forms/ProjectFilterSelect";

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
  filterStyle,
  wrapperStyle,
}) {
  return (
    <div style={wrapperStyle}>
      {showProjectFilter ? (
        <ProjectFilterSelect
          projects={projects}
          value={selectedProject}
          onChange={onProjectChange}
          style={filterStyle}
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
    </div>
  );
}
