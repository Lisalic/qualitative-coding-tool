import { useParams } from "react-router-dom";
import ProjectHeaderSection from "../components/project/ProjectHeaderSection";
import ProjectFilesSection from "../components/project/ProjectFilesSection";
import PageEmptyState from "../components/primitives/PageEmptyState";
import useProjectPage from "../components/project/useProjectPage";

export default function Project() {
  const { projectId } = useParams();
  const page = useProjectPage(projectId);

  if (page.loading) {
    return (
      <div className="layout-page">
        <PageEmptyState message="Loading project..." style={{ padding: 20 }} />
      </div>
    );
  }
  if (!page.project) {
    return (
      <div className="layout-page">
        <PageEmptyState message="Project not found" style={{ padding: 20 }} />
      </div>
    );
  }

  return (
    <div className="layout-page">
      <div className="layout-card layout-card--padded layout-card--full-width">
        <ProjectHeaderSection project={page.project} onRefreshProject={page.refreshProject} />
        <ProjectFilesSection
          project={page.project}
          onRefreshProject={page.refreshProject}
        />
      </div>
    </div>
  );
}
