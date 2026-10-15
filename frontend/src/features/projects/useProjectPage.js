import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../../api/client";

export default function useProjectPage(projectId) {
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Only the newest load may write: a refresh overlapping a route change
  // to another project (same mounted page) used to let the older response
  // land last and show the wrong project.
  const latestRequest = useRef(0);

  // `loading` is only the FIRST load. A refresh after a rename/delete/merge
  // keeps the page mounted -- swapping it for a loading screen used to
  // reset the open tab and wipe any message the action had just shown.
  const refreshProject = useCallback(async () => {
    const requestId = ++latestRequest.current;
    setError("");
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (requestId !== latestRequest.current) return;
      const found = (data.projects || []).find(
        (item) => String(item.id) === String(projectId),
      );
      setProject(found || null);
    } catch (err) {
      if (requestId !== latestRequest.current) return;
      console.error("Failed to load project:", err);
      setError("Couldn't load this project. Check your connection and refresh to try again.");
    } finally {
      if (requestId === latestRequest.current) setLoading(false);
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
