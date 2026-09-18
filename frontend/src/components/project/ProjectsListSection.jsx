import ProjectCard from "./ProjectCard";
import PageEmptyState from "../primitives/PageEmptyState";

export default function ProjectsListSection({
  projects,
  loading,
  error,
  onViewProject,
}) {
  return (
    <div className="flex flex-col gap-3">
      {loading && (
        <div className="border border-line bg-surface-raised px-3 py-2 text-center text-sm text-paper/70">
          Loading projects...
        </div>
      )}
      {error && (
        <div className="border border-error bg-error/10 px-3 py-2 text-center text-sm text-error">
          Error: {error}
        </div>
      )}

      {!loading && !error && projects.length === 0 && (
        <PageEmptyState message="No projects yet. Create your first project to get started!" />
      )}

      {!loading && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} onViewProject={onViewProject} />
          ))}
        </div>
      )}
    </div>
  );
}
