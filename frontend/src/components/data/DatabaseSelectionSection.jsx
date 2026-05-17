import SelectionList from "../primitives/SelectionList";
import ProjectFilterSelect from "../forms/ProjectFilterSelect";

export default function DatabaseSelectionSection({ page }) {
  const {
    projects = [],
    selectedProject,
    setSelectedProject,
    selectedDatabase,
    setSelectedDatabase,
    projectFiles = [],
    fallbackItems = [],
    useProjectFileList,
    selectionProps = {},
  } = page;

  const {
    wrapperClassName = "",
    selectClassName = "",
    listClassName,
    buttonClassName,
    noProjectFilesMessage,
    noDatabaseMessage,
  } = selectionProps;

  return (
    <>
      <ProjectFilterSelect
        projects={projects}
        value={selectedProject}
        onChange={setSelectedProject}
        className={wrapperClassName}
        selectClassName={selectClassName}
      />
      <SelectionList
        items={useProjectFileList ? projectFiles : fallbackItems}
        selectedId={selectedDatabase}
        onSelect={setSelectedDatabase}
        className={listClassName}
        buttonClass={buttonClassName}
        emptyMessage={
          useProjectFileList
            ? noProjectFilesMessage || "No files in project"
            : noDatabaseMessage || "No databases available"
        }
      />
    </>
  );
}
