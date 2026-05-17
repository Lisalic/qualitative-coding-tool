export default function ProjectCard({ project, onViewProject }) {
  return (
    <div className="layout-card layout-card--padded">
      <div className="layout-flex-row layout-space-between gap-md">
        <div style={{ flex: 1 }}>
          <div>
            <h3 className="heading-sm">{project.projectname}</h3>
            {project.description && <div className="body-base">{project.description}</div>}
            <div className="layout-flex-row gap-md body-sm">
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
        </div>
        <div className="layout-center">
          <button
            className="btn btn-primary btn-large"
            onClick={() => onViewProject(project.id)}
            aria-label={`View project ${project.projectname}`}
          >
            View Project
          </button>
        </div>
      </div>
    </div>
  );
}
