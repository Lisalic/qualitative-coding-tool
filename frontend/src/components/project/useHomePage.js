import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, describeApiError } from "../../api";

export default function useHomePage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState("");
  const [messageIsError, setMessageIsError] = useState(false);
  const [creating, setCreating] = useState(false);
  // Only the newest load may write: the refresh after creating a project
  // can overlap the initial load, and the older response must not win.
  const latestRequest = useRef(0);

  const fetchProjects = useCallback(async () => {
    const requestId = ++latestRequest.current;
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch("/api/projects/");
      if (requestId !== latestRequest.current) return;
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        if (requestId !== latestRequest.current) return;
        setError(describeApiError(data, `HTTP ${resp.status}`));
        setLoading(false);
        return;
      }
      const data = await resp.json();
      if (requestId !== latestRequest.current) return;
      const list = Array.isArray(data.projects) ? data.projects : [];
      list.sort((a, b) => {
        const ta = a && a.created_at ? Date.parse(a.created_at) : 0;
        const tb = b && b.created_at ? Date.parse(b.created_at) : 0;
        return ta - tb;
      });
      setProjects(list);
      setLoading(false);
    } catch (err) {
      if (requestId !== latestRequest.current) return;
      setError(String(err));
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleCreateClick = useCallback(() => {
    setShowForm(true);
  }, []);

  const handleCancel = useCallback(() => {
    setShowForm(false);
    setName("");
    setDescription("");
    setMessage("");
  }, []);

  const handleCreateProject = useCallback(
    async (event) => {
      event.preventDefault();
      if (creating) return; // a second click while the first is in flight
      setMessage("");
      if (!name || !name.trim()) {
        setMessage("Name is required");
        setMessageIsError(true);
        return;
      }

      setCreating(true);
      try {
        const form = new FormData();
        form.append("name", name.trim());
        if (description) form.append("description", description);

        const resp = await apiFetch("/api/create-project/", {
          method: "POST",
          body: form,
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(describeApiError(data, `HTTP ${resp.status}`));
        }

        const data = await resp.json();
        setMessage(`Project "${data.project.projectname}" created`);
        setMessageIsError(false);
        setShowForm(false);
        setName("");
        setDescription("");
        await fetchProjects();
      } catch (err) {
        setMessage(`Error: ${err.message}`);
        setMessageIsError(true);
      } finally {
        setCreating(false);
      }
    },
    [creating, description, fetchProjects, name],
  );

  return {
    projects,
    loading,
    error,
    showForm,
    setShowForm,
    name,
    setName,
    description,
    setDescription,
    message,
    messageIsError,
    creating,
    handleCreateClick,
    handleCancel,
    handleCreateProject,
  };
}
