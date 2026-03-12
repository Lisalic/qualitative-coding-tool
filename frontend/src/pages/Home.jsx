import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { apiFetch } from "../api";
import "../styles/Home.css";

export default function Home() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState("");

  const handleCreateClick = () => setShowForm(true);
  const handleCancel = () => {
    setShowForm(false);
    setName("");
    setDescription("");
    setMessage("");
  };

  // Fetch user's projects (includes associated files)
  const fetchProjects = async () => {
    let mounted = true;
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(`/api/projects/`);
      if (!mounted) return;
      if (!resp.ok) {
        try {
          const d = await resp.json().catch(() => ({}));
          setError(d.detail || `HTTP ${resp.status}`);
        } catch (e) {
          setError(`HTTP ${resp.status}`);
        }
        setLoading(false);
        return;
      }
      try {
        const d = await resp.json();
        const list = Array.isArray(d.projects) ? d.projects : [];
        // Sort by creation date ascending: oldest first
        list.sort((a, b) => {
          const ta = a && a.created_at ? Date.parse(a.created_at) : 0;
          const tb = b && b.created_at ? Date.parse(b.created_at) : 0;
          return ta - tb;
        });
        setProjects(list);
      } catch (e) {
        setError("Failed to parse projects response");
      }
      setLoading(false);
    } catch (e) {
      if (!mounted) return;
      setError(String(e));
      setLoading(false);
    }
    return () => (mounted = false);
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
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
      // Refresh the projects list to show the new project
      fetchProjects();
      // optionally navigate to project view
      // navigate(`/data?schema=${data.project.schema_name}`)
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    }
  };

  return (
    <div className="layout-page">
      <div className="layout-card layout-card--padded layout-card--full-width">
        {/* Header removed - page begins with projects list */}

        {/* Projects List */}
        <div>
          <h2 className="heading-md text-center">Projects</h2>

          {loading && <div className="alert alert--info text-center">Loading projects...</div>}

          {error && <div className="alert alert--error text-center">Error: {error}</div>}

          {!loading && !error && projects.length === 0 && (
            <div className="empty-state">
              No projects yet. Create your first project to get started!
            </div>
          )}

          {!loading && projects.length > 0 && (
            <div className="layout-flex-col gap-md">
              {projects.map((p) => (
                <div
                  key={p.id}
                  className="layout-card layout-card--padded"
                >
                  <div className="layout-flex-row layout-space-between gap-md">
                    <div style={{ flex: 1 }}>
                      <div>
                        <h3 className="heading-sm">{p.projectname}</h3>
                        {p.description && (
                          <div className="body-base">
                            {p.description}
                          </div>
                        )}
                        <div className="layout-flex-row gap-md body-sm">
                          {p.created_at && (
                            <div>
                              Created: {new Date(p.created_at).toLocaleString()}
                            </div>
                          )}
                          <div>
                            {Array.isArray(p.files)
                              ? `${p.files.length} file${p.files.length === 1 ? "" : "s"}`
                              : "0 files"}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="layout-center">
                      <button
                        className="btn btn-primary btn-large"
                        onClick={() => navigate(`/project/${p.id}`)}
                        aria-label={`View project ${p.projectname}`}
                      >
                        View Project
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {!showForm && (
          <div className="layout-center mt-md">
            <button
              className="btn btn-primary btn-large"
              onClick={handleCreateClick}
              aria-label="Create New Project"
            >
              Create New Project
            </button>
          </div>
        )}

        {/* Create Project Form (rendered at bottom when requested) */}
        {showForm && (
          <div className="panel mt-md layout-card--padded">
            <h2 className="heading-md">Create New Project</h2>
            <form onSubmit={handleSubmit}>
              <div className="form__group">
                <label className="form__label">
                  Project Name *
                </label>
                <input
                  className="form__input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Enter project name"
                />
              </div>
              <div className="form__group">
                <label className="form__label">
                  Description
                </label>
                <textarea
                  className="form__textarea"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Enter project description (optional)"
                />
              </div>
              <div className="form__actions">
                <button
                  type="submit"
                  className="btn btn-primary btn-large"
                >
                  Create Project
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-large"
                  onClick={handleCancel}
                >
                  Cancel
                </button>
              </div>
              {message && (
                <div
                  className={`alert ${
                    message.includes("Error")
                      ? "alert--error"
                      : "alert--success"
                  }`}
                >
                  {message}
                </div>
              )}
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
