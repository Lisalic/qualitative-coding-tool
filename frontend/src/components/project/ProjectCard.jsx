export default function ProjectCard({ project, onViewProject }) {
  return (
    <div className="border border-paper p-6">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="text-xl font-semibold">{project.projectname}</h3>
          {project.description && (
            <div className="mt-1 text-paper/70">{project.description}</div>
          )}
          <div className="mt-2 flex flex-wrap gap-4 text-sm text-paper/50">
            {project.created_at && (
              <div>Created: {new Date(project.created_at).toLocaleString()}</div>
            )}
            <div>
              {Array.isArray(project.files)
                ? `${project.files.length} file${project.files.length === 1 ? "" : "s"}`
                : "0 files"}
            </div>
          </div>
        </div>
        <button
          type="button"
          className="shrink-0 border-2 border-paper px-5 py-2.5 text-sm font-semibold transition-colors hover:bg-paper hover:text-ink"
          onClick={() => onViewProject(project.id)}
          aria-label={`View project ${project.projectname}`}
        >
          View Project
        </button>
      </div>
    </div>
  );
}
