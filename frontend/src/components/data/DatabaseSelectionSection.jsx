import SelectionList from "../primitives/SelectionList";

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

  const { listClassName, buttonClassName, noProjectFilesMessage, noDatabaseMessage } =
    selectionProps;

  return (
    <SelectionList
      items={useProjectFileList ? projectFiles : fallbackItems}
      selectedId={selectedDatabase}
      onSelect={setSelectedDatabase}
      listClassName={listClassName}
      buttonClass={buttonClassName}
      showProjectFilter={true}
      projects={projects}
      selectedProject={selectedProject}
      onProjectChange={setSelectedProject}
      emptyMessage={
        useProjectFileList
          ? noProjectFilesMessage || "No files in project"
          : noDatabaseMessage || "No databases available"
      }
    />
  );
}
