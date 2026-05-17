import ProjectCard from "./ProjectCard";
import PageEmptyState from "../primitives/PageEmptyState";

export default function ProjectsListSection({
  projects,
  loading,
  error,
  onViewProject,
}) {
  return (
    <div>
      <h2 className="heading-md text-center">Projects</h2>

      {loading && <div className="alert alert--info text-center">Loading projects...</div>}
      {error && <div className="alert alert--error text-center">Error: {error}</div>}

      {!loading && !error && projects.length === 0 && (
        <PageEmptyState message="No projects yet. Create your first project to get started!" />
      )}

      {!loading && projects.length > 0 && (
        <div className="layout-flex-col gap-md">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} onViewProject={onViewProject} />
          ))}
        </div>
      )}
    </div>
  );
}
