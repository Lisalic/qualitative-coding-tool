import { useNavigate } from "react-router-dom";
import { useState } from "react";
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
  useState(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    apiFetch(`/api/projects/`)
      .then(async (resp) => {
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
      })
      .catch((e) => {
        if (!mounted) return;
        setError(String(e));
        setLoading(false);
      });
    return () => (mounted = false);
  });

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
      // optionally navigate to project view
      // navigate(`/data?schema=${data.project.schema_name}`)
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    }
  };

  return (
    <div className="home-container">
      <div className="form-wrapper">
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "12px",
            flexDirection: "column",
          }}
        >
          <h1>Projects</h1>

          {loading && <div>Loading projects...</div>}
          {error && <div style={{ color: "red" }}>Error: {error}</div>}

          {!loading && !error && projects.length === 0 && (
            <div>No projects yet.</div>
          )}

          {!loading && projects.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {projects.map((p) => (
                <li
                  key={p.id}
                  style={{ padding: "6px 0", borderBottom: "1px solid #eee" }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                    }}
                  >
                    <div>
                      <strong>{p.projectname}</strong>
                      <div style={{ fontSize: "0.9em", color: "#666" }}>
                        {p.description}
                      </div>
                      {p.created_at && (
                        <div
                          style={{
                            fontSize: "0.8em",
                            color: "#999",
                            marginTop: 6,
                          }}
                        >
                          Created: {new Date(p.created_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* show count of files and a View Project button */}
                  <div
                    style={{
                      marginTop: "8px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div style={{ color: "#666" }}>
                      {Array.isArray(p.files)
                        ? `${p.files.length} file${p.files.length === 1 ? "" : "s"}`
                        : "0 files"}
                    </div>
                    <div>
                      <button
                        className="project-tab"
                        onClick={() => navigate(`/project/${p.id}`)}
                        aria-label={`View project ${p.projectname}`}
                        style={{ padding: "6px 10px", fontSize: 14 }}
                      >
                        View Project
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {!showForm && (
            <button
              className="project-tab"
              onClick={handleCreateClick}
              aria-label="Create New Project"
              style={{ padding: "10px 16px", fontSize: 16 }}
            >
              + Create New Project
            </button>
          )}
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} style={{ marginTop: "12px" }}>
            <div>
              <label style={{ display: "block", marginBottom: "6px" }}>
                Name
              </label>
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div style={{ marginTop: "8px" }}>
              <label style={{ display: "block", marginBottom: "6px" }}>
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div style={{ marginTop: "8px" }}>
              <button type="submit" className="main-button">
                Save
              </button>
              <button
                type="button"
                onClick={handleCancel}
                style={{ marginLeft: "8px" }}
              >
                Cancel
              </button>
            </div>
            {message && <div style={{ marginTop: "8px" }}>{message}</div>}
          </form>
        )}
      </div>
    </div>
  );
}
