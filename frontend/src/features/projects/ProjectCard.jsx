import { Link } from "react-router-dom";
import { btnPrimary } from "../../lib/uiClasses";
import { formatDate } from "../../lib/formatDate";

export default function ProjectCard({ project }) {
  return (
    <div className="border border-line bg-surface p-4">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold">{project.projectname}</h3>
          {project.description && (
            <div className="mt-1 text-paper/70">{project.description}</div>
          )}
          <div className="mt-2 flex flex-wrap gap-4 text-sm text-paper/50">
            {project.created_at && (
              <div>Created: {formatDate(project.created_at)}</div>
            )}
            <div>
              {Array.isArray(project.files)
                ? `${project.files.length} file${project.files.length === 1 ? "" : "s"}`
                : "0 files"}
            </div>
          </div>
        </div>
        <Link
          to={`/project/${project.id}`}
          className={`shrink-0 ${btnPrimary} hover:text-ink`}
          aria-label={`View project ${project.projectname}`}
        >
          View project
        </Link>
      </div>
    </div>
  );
}
