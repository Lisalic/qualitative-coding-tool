import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../api";

export default function useProjectPage(projectId) {
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // `loading` is only the FIRST load. A refresh after a rename/delete/merge
  // keeps the page mounted -- swapping it for a loading screen used to
  // reset the open tab and wipe any message the action had just shown.
  const refreshProject = useCallback(async () => {
    setError("");
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const found = (data.projects || []).find(
        (item) => String(item.id) === String(projectId),
      );
      setProject(found || null);
    } catch (err) {
      console.error("Failed to load project:", err);
      setError("Couldn't load this project. Check your connection and refresh to try again.");
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
    error,
    refreshProject,
  };
}
