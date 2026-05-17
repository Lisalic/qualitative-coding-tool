import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../api";

export default function useProjectPage(projectId) {
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshProject = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiFetch("/api/projects/");
      const data = await resp.json();
      const found = (data.projects || []).find(
        (item) => String(item.id) === String(projectId),
      );
      setProject(found || null);
    } catch {
      setProject(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    refreshProject();
  }, [refreshProject]);

  return {
    project,
    loading,
    refreshProject,
  };
}
