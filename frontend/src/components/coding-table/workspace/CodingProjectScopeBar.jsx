import ProjectFilterSelect from "../../forms/ProjectFilterSelect";

export default function CodingProjectScopeBar({ page }) {
  return (
    <ProjectFilterSelect
      projects={page.projectsList || []}
      value={page.selectedProject}
      onChange={page.setSelectedProject}
      style={{ marginBottom: 12 }}
    />
  );
}
