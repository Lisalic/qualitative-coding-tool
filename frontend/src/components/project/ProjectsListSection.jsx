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
      <h2 className="mb-6 text-center text-3xl font-bold">Projects</h2>

      {loading && (
        <div className="border border-paper/20 bg-white/5 px-4 py-3 text-center text-sm text-paper/70">
          Loading projects...
        </div>
      )}
      {error && (
        <div className="border border-error bg-error/10 px-4 py-3 text-center text-sm text-error">
          Error: {error}
        </div>
      )}

      {!loading && !error && projects.length === 0 && (
        <PageEmptyState message="No projects yet. Create your first project to get started!" />
      )}

      {!loading && projects.length > 0 && (
        <div className="flex flex-col gap-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} onViewProject={onViewProject} />
          ))}
        </div>
      )}
    </div>
  );
}
