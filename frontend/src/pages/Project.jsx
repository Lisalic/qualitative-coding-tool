import { useParams } from "react-router-dom";
import ProjectHeaderSection from "../components/project/ProjectHeaderSection";
import ProjectFilesSection from "../components/project/ProjectFilesSection";
import PageEmptyState from "../components/primitives/PageEmptyState";
import useProjectPage from "../components/project/useProjectPage";
import PageShell from "../components/shell/PageShell";
import ErrorDisplay from "../components/feedback/ErrorDisplay";

export default function Project() {
  const { projectId } = useParams();
  const page = useProjectPage(projectId);

  if (page.loading) {
    return (
      <PageShell title="Project" width="wide">
        <p role="status" className="text-sm text-paper/70">
          Loading project…
        </p>
      </PageShell>
    );
  }
  if (!page.project) {
    return (
      <PageShell title="Project" width="prose">
        {page.error ? (
          <ErrorDisplay message={page.error} variant="alert" />
        ) : (
          <PageEmptyState message="This project doesn't exist, or you don't have access to it." />
        )}
      </PageShell>
    );
  }

  return (
    <PageShell
      title={page.project.projectname || "Project"}
      width="wide"
      bodyClassName="flex flex-col gap-3"
    >
      <ProjectHeaderSection project={page.project} onRefreshProject={page.refreshProject} />
      <ProjectFilesSection project={page.project} onRefreshProject={page.refreshProject} />
    </PageShell>
  );
}
