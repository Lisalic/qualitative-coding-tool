import { useParams } from "react-router-dom";
import ProjectHeaderSection from "../components/project/ProjectHeaderSection";
import ProjectFilesSection from "../components/project/ProjectFilesSection";
import PageEmptyState from "../components/primitives/PageEmptyState";
import useProjectPage from "../components/project/useProjectPage";
import PageShell from "../components/shell/PageShell";

export default function Project() {
  const { projectId } = useParams();
  const page = useProjectPage(projectId);

  if (page.loading) {
    return (
      <PageShell title="Project" width="prose">
        <PageEmptyState message="Loading project..." />
      </PageShell>
    );
  }
  if (!page.project) {
    return (
      <PageShell title="Project" width="prose">
        <PageEmptyState message="Project not found" />
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
