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
        {/* Header Section */}
        <div
          style={{
            backgroundColor: "#111",
            border: "2px solid #ffffff",
            borderRadius: "12px",
            padding: "24px",
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "20px",
            }}
          >
            <h1 style={{ margin: 0, color: "#ffffff", fontSize: "2em" }}>
              My Projects
            </h1>
            {!showForm && (
              <button
                className="project-tab"
                onClick={handleCreateClick}
                aria-label="Create New Project"
                style={{
                  padding: "12px 20px",
                  fontSize: 16,
                  fontWeight: "bold",
                  textAlign: "center",
                }}
              >
                Create New Project
              </button>
            )}
          </div>
        </div>

        {/* Create Project Form */}
        {showForm && (
          <div
            style={{
              backgroundColor: "#111",
              border: "2px solid #ffffff",
              borderRadius: "12px",
              padding: "24px",
              marginBottom: "24px",
            }}
          >
            <h2 style={{ margin: "0 0 20px 0", color: "#ffffff" }}>
              Create New Project
            </h2>
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: "16px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "8px",
                    color: "#cccccc",
                    fontWeight: "bold",
                  }}
                >
                  Project Name *
                </label>
                <input
                  className="form-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Enter project name"
                  style={{
                    width: "100%",
                    padding: "12px",
                    fontSize: "16px",
                  }}
                />
              </div>
              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "8px",
                    color: "#cccccc",
                    fontWeight: "bold",
                  }}
                >
                  Description
                </label>
                <textarea
                  className="form-input"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Enter project description (optional)"
                  style={{
                    width: "100%",
                    minHeight: "80px",
                    resize: "vertical",
                    padding: "12px",
                    fontSize: "16px",
                  }}
                />
              </div>
              <div
                style={{ display: "flex", gap: "12px", alignItems: "center" }}
              >
                <button
                  type="submit"
                  className="project-tab"
                  style={{ padding: "12px 24px", fontSize: 16 }}
                >
                  Create Project
                </button>
                <button
                  type="button"
                  className="project-tab"
                  onClick={handleCancel}
                  style={{ padding: "12px 24px", fontSize: 16 }}
                >
                  Cancel
                </button>
              </div>
              {message && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "12px",
                    borderRadius: "6px",
                    backgroundColor: message.includes("Error")
                      ? "#330000"
                      : "#003300",
                    border: `1px solid ${message.includes("Error") ? "#ff6666" : "#66ff66"}`,
                    color: message.includes("Error") ? "#ffcccc" : "#ccffcc",
                  }}
                >
                  {message}
                </div>
              )}
            </form>
          </div>
        )}

        {/* Projects List */}
        <div
          style={{
            backgroundColor: "#111",
            border: "2px solid #ffffff",
            borderRadius: "12px",
            padding: "24px",
          }}
        >
          <h2 style={{ margin: "0 0 20px 0", color: "#ffffff" }}>
            Your Projects
          </h2>

          {loading && (
            <div
              style={{ textAlign: "center", color: "#cccccc", padding: "40px" }}
            >
              Loading projects...
            </div>
          )}

          {error && (
            <div
              style={{
                textAlign: "center",
                color: "#ff6666",
                padding: "20px",
                backgroundColor: "#220000",
                border: "1px solid #ff6666",
                borderRadius: "6px",
                marginBottom: "20px",
              }}
            >
              Error: {error}
            </div>
          )}

          {!loading && !error && projects.length === 0 && (
            <div
              style={{
                textAlign: "center",
                color: "#888",
                padding: "40px",
                fontSize: "1.1em",
              }}
            >
              No projects yet. Create your first project to get started!
            </div>
          )}

          {!loading && projects.length > 0 && (
            <div
              style={{ display: "flex", flexDirection: "column", gap: "16px" }}
            >
              {projects.map((p) => (
                <div
                  key={p.id}
                  style={{
                    backgroundColor: "#000",
                    border: "1px solid #ffffff",
                    borderRadius: "8px",
                    padding: "20px",
                    transition: "all 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "#cccccc";
                    e.currentTarget.style.boxShadow =
                      "0 4px 12px rgba(255, 255, 255, 0.1)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "#ffffff";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      gap: "20px",
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <h3
                        style={{
                          margin: "0 0 8px 0",
                          color: "#ffffff",
                          fontSize: "1.3em",
                        }}
                      >
                        {p.projectname}
                      </h3>
                      {p.description && (
                        <div
                          style={{
                            color: "#cccccc",
                            fontSize: "1em",
                            lineHeight: 1.4,
                            marginBottom: "12px",
                          }}
                        >
                          {p.description}
                        </div>
                      )}
                      <div
                        style={{
                          display: "flex",
                          gap: "16px",
                          alignItems: "center",
                          fontSize: "0.9em",
                          color: "#888",
                        }}
                      >
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
                    <div style={{ display: "flex", alignItems: "center" }}>
                      <button
                        className="project-tab"
                        onClick={() => navigate(`/project/${p.id}`)}
                        aria-label={`View project ${p.projectname}`}
                        style={{
                          padding: "12px 20px",
                          fontSize: 14,
                          fontWeight: "bold",
                          textAlign: "center",
                        }}
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
      </div>
    </div>
  );
}
