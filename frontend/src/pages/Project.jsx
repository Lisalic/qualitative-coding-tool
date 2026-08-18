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
      <div className="mx-auto w-full max-w-4xl px-4 py-10">
        <PageEmptyState message="Loading project..." />
      </div>
    );
  }
  if (!page.project) {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-10">
        <PageEmptyState message="Project not found" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <ProjectHeaderSection project={page.project} onRefreshProject={page.refreshProject} />
      <ProjectFilesSection project={page.project} onRefreshProject={page.refreshProject} />
    </div>
  );
}
