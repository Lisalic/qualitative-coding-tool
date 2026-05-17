import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../api";

export default function useHomePage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState("");

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data.detail || `HTTP ${resp.status}`);
        setLoading(false);
        return;
      }
      const data = await resp.json();
      const list = Array.isArray(data.projects) ? data.projects : [];
      list.sort((a, b) => {
        const ta = a && a.created_at ? Date.parse(a.created_at) : 0;
        const tb = b && b.created_at ? Date.parse(b.created_at) : 0;
        return ta - tb;
      });
      setProjects(list);
      setLoading(false);
    } catch (err) {
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
      setMessage("");
      if (!name || !name.trim()) {
        setMessage("Name is required");
        return;
      }

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
          throw new Error(data.detail || `HTTP ${resp.status}`);
        }

        const data = await resp.json();
        setMessage(`Project "${data.project.projectname}" created`);
        setShowForm(false);
        setName("");
        setDescription("");
        await fetchProjects();
      } catch (err) {
        setMessage(`Error: ${err.message}`);
      }
    },
    [description, fetchProjects, name],
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
    handleCreateClick,
    handleCancel,
    handleCreateProject,
  };
}
