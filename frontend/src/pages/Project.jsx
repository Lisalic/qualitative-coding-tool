import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import ProjectHeaderSection from "../components/ProjectHeaderSection";
import ProjectFilesSection from "../components/ProjectFilesSection";

export default function Project() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshProject = async () => {
    setLoading(true);
    try {
      const resp = await apiFetch("/api/projects/");
      const data = await resp.json();
      const found = (data.projects || []).find(
        (p) => String(p.id) === String(projectId),
      );
      setProject(found || null);
    } catch {
      setProject(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshProject();
  }, [projectId]);

  if (loading) return <div style={{ padding: 20 }}>Loading project...</div>;
  if (!project) return <div style={{ padding: 20 }}>Project not found</div>;

  return (
    <div className="layout-page">
      <div className="layout-card layout-card--padded layout-card--full-width">
        <ProjectHeaderSection project={project} onRefreshProject={refreshProject} />
        <ProjectFilesSection
          project={project}
          onRefreshProject={refreshProject}
        />
      </div>
    </div>
  );
}
