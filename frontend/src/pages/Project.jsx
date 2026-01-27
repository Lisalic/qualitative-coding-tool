import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import "../styles/Home.css";

export default function Project() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("database");
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiFetch("/api/projects/")
      .then((r) => r.json())
      .then((data) => {
        if (!mounted) return;
        const rows = data.projects || [];
        const found = rows.find((p) => String(p.id) === String(projectId));
        setProject(found || null);
        setLoading(false);
      })
      .catch(() => {
        if (!mounted) return;
        setProject(null);
        setLoading(false);
      });
    return () => (mounted = false);
  }, [projectId]);

  if (loading) return <div style={{ padding: 20 }}>Loading project...</div>;
  if (!project) return <div style={{ padding: 20 }}>Project not found</div>;

  // determine files for categories
  const dbFiles = (project.files || []).filter(
    (f) => f.file_type === "raw_data",
  );
  const filteredFiles = (project.files || []).filter(
    (f) => f.file_type === "filtered_data",
  );
  const codebookFiles = (project.files || []).filter(
    (f) => f.file_type === "codebook",
  );
  const codingFiles = (project.files || []).filter(
    (f) => f.file_type === "coding",
  );

  const startEdit = () => {
    setEditName(project.projectname || "");
    setEditDescription(project.description || "");
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditName("");
    setEditDescription("");
  };

  const saveEdit = async (e) => {
    e?.preventDefault();
    setSaving(true);
    try {
      const form = new FormData();
      form.append("project_id", String(project.id));
      form.append("name", editName || "");
      if (editDescription != null) form.append("description", editDescription);

      const resp = await apiFetch("/api/update-project/", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${resp.status}`);
      }
      const d = await resp.json();
      const updated = d.project;
      setProject((p) => ({
        ...p,
        projectname: updated.projectname,
        description: updated.description,
      }));
      setEditing(false);
    } catch (err) {
      console.error("Failed to update project:", err);
      // keep editing state so user can retry
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteFile = async (fileName, fileType) => {
    if (
      !confirm(
        `Are you sure you want to delete "${fileName}"? This action cannot be undone.`,
      )
    ) {
      return;
    }

    try {
      const response = await apiFetch(`/api/delete-database/${fileName}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("Failed to delete file");
      }

      // Refresh the page to update the file list
      window.location.reload();
    } catch (err) {
      console.error("Delete error:", err);
      alert("Failed to delete file. Please try again.");
    }
  };

  return (
    <div className="home-container">
      <div className="form-wrapper">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            {!editing ? (
              <>
                <h1 style={{ display: "inline-block", marginRight: 12 }}>
                  {project.projectname}
                </h1>
                <button
                  className="project-tab"
                  onClick={startEdit}
                  style={{ marginLeft: 8, padding: "8px 10px", fontSize: 14 }}
                >
                  Edit
                </button>
                <div style={{ color: "#666", marginTop: 6 }}>
                  {project.description}
                </div>
                {project.created_at && (
                  <div
                    style={{ color: "#999", marginTop: 6, fontSize: "0.9em" }}
                  >
                    Created: {new Date(project.created_at).toLocaleString()}
                  </div>
                )}
              </>
            ) : (
              <form onSubmit={saveEdit} style={{ marginTop: 6 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    className="form-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    style={{ fontSize: "1.2em" }}
                  />
                  <button
                    type="submit"
                    className="project-tab"
                    disabled={saving}
                    style={{ padding: "8px 12px", fontSize: 14 }}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="project-tab"
                    onClick={cancelEdit}
                    style={{ marginLeft: 8, padding: "8px 12px", fontSize: 14 }}
                  >
                    Cancel
                  </button>
                </div>
                <div style={{ marginTop: 8 }}>
                  <label
                    style={{ display: "block", marginBottom: 6, color: "#ccc" }}
                  >
                    Description
                  </label>
                  <textarea
                    className="form-input"
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    style={{ width: "100%", minHeight: 60 }}
                  />
                </div>
              </form>
            )}
          </div>
          <div />
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className={`project-tab ${activeTab === "database" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("database");
              }}
            >
              Database
            </button>
            <button
              type="button"
              className={`project-tab ${activeTab === "filtered" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("filtered");
              }}
            >
              Filtered Database
            </button>
            <button
              type="button"
              className={`project-tab ${activeTab === "codebook" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("codebook");
              }}
            >
              Codebook
            </button>
            <button
              type="button"
              className={`project-tab ${activeTab === "coding" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("coding");
              }}
            >
              Coding
            </button>
          </div>

          <div style={{ marginTop: 16 }}>
            {activeTab === "database" && (
              <div>
                <h2>Database</h2>
                {dbFiles.length === 0 ? (
                  <div>No database</div>
                ) : (
                  dbFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "8px 0",
                        borderBottom: "1px solid #111",
                      }}
                    >
                      <div>
                        <div>{f.display_name || f.schema_name}</div>
                        {f.description && (
                          <div style={{ color: "#888", marginTop: 6 }}>
                            {f.description}
                          </div>
                        )}
                        {f.created_at && (
                          <div
                            style={{
                              color: "#999",
                              marginTop: 6,
                              fontSize: "0.9em",
                            }}
                          >
                            Created: {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          className="project-tab"
                          onClick={() =>
                            navigate("/data", {
                              state: { selectedDatabase: f.schema_name },
                            })
                          }
                          style={{ padding: "8px 12px", fontSize: 14 }}
                        >
                          View
                        </button>
                        <button
                          className="project-tab"
                          onClick={() =>
                            handleDeleteFile(f.schema_name, "database")
                          }
                          style={{
                            padding: "8px 12px",
                            fontSize: 14,
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))
                )}
                <div style={{ marginTop: 8 }}>
                  <button
                    className="project-tab"
                    onClick={() =>
                      navigate("/import", { state: { projectId: project.id } })
                    }
                    style={{ padding: "8px 12px", fontSize: 14 }}
                  >
                    Add Database
                  </button>
                </div>
              </div>
            )}

            {activeTab === "filtered" && (
              <div>
                <h2>Filtered Database</h2>
                {filteredFiles.length === 0 ? (
                  <div>No filtered database</div>
                ) : (
                  filteredFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "8px 0",
                        borderBottom: "1px solid #111",
                      }}
                    >
                      <div>
                        <div>{f.display_name || f.schema_name}</div>
                        {f.description && (
                          <div style={{ color: "#888", marginTop: 6 }}>
                            {f.description}
                          </div>
                        )}
                        {f.created_at && (
                          <div
                            style={{
                              color: "#999",
                              marginTop: 6,
                              fontSize: "0.9em",
                            }}
                          >
                            Created: {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          className="project-tab"
                          onClick={() =>
                            navigate("/filtered-data", {
                              state: { selectedDatabase: f.schema_name },
                            })
                          }
                          style={{ padding: "8px 12px", fontSize: 14 }}
                        >
                          View
                        </button>
                        <button
                          className="project-tab"
                          onClick={() =>
                            handleDeleteFile(f.schema_name, "filtered")
                          }
                          style={{
                            padding: "8px 12px",
                            fontSize: 14,
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))
                )}
                <div style={{ marginTop: 8 }}>
                  <button
                    className="project-tab"
                    onClick={() =>
                      navigate("/filter", { state: { projectId: project.id } })
                    }
                    style={{ padding: "8px 12px", fontSize: 14 }}
                  >
                    Add Filtered Database
                  </button>
                </div>
              </div>
            )}

            {activeTab === "codebook" && (
              <div>
                <h2>Codebook</h2>
                {codebookFiles.length === 0 ? (
                  <div>No codebook</div>
                ) : (
                  codebookFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "8px 0",
                        borderBottom: "1px solid #111",
                      }}
                    >
                      <div>
                        <div>{f.display_name || f.schema_name}</div>
                        {f.description && (
                          <div style={{ color: "#888", marginTop: 6 }}>
                            {f.description}
                          </div>
                        )}
                        {f.created_at && (
                          <div
                            style={{
                              color: "#999",
                              marginTop: 6,
                              fontSize: "0.9em",
                            }}
                          >
                            Created: {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          className="project-tab"
                          onClick={() =>
                            navigate(
                              `/codebook-view?selected=${encodeURIComponent(f.schema_name || f.display_name || f.id)}`,
                            )
                          }
                          style={{ padding: "8px 12px", fontSize: 14 }}
                        >
                          View
                        </button>
                        <button
                          className="project-tab"
                          onClick={() =>
                            handleDeleteFile(
                              f.schema_name || f.display_name || f.id,
                              "codebook",
                            )
                          }
                          style={{
                            padding: "8px 12px",
                            fontSize: 14,
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))
                )}
                <div style={{ marginTop: 8 }}>
                  <button
                    className="project-tab"
                    onClick={() =>
                      navigate("/codebook-generate", {
                        state: { projectId: project.id },
                      })
                    }
                    style={{ padding: "8px 12px", fontSize: 14 }}
                  >
                    Add Codebook
                  </button>
                </div>
              </div>
            )}

            {activeTab === "coding" && (
              <div>
                <h2>Coding</h2>
                {codingFiles.length === 0 ? (
                  <div>No coding</div>
                ) : (
                  codingFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "8px 0",
                        borderBottom: "1px solid #111",
                      }}
                    >
                      <div>
                        <div>{f.display_name || f.schema_name}</div>
                        {f.description && (
                          <div style={{ color: "#888", marginTop: 6 }}>
                            {f.description}
                          </div>
                        )}
                        {f.created_at && (
                          <div
                            style={{
                              color: "#999",
                              marginTop: 6,
                              fontSize: "0.9em",
                            }}
                          >
                            Created: {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          className="project-tab"
                          onClick={() =>
                            navigate("/coding-view", {
                              state: { selectedCodedData: f.schema_name },
                            })
                          }
                          style={{ padding: "8px 12px", fontSize: 14 }}
                        >
                          View
                        </button>
                        <button
                          className="project-tab"
                          onClick={() =>
                            handleDeleteFile(f.schema_name, "coding")
                          }
                          style={{
                            padding: "8px 12px",
                            fontSize: 14,
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))
                )}
                <div style={{ marginTop: 8 }}>
                  <button
                    className="project-tab"
                    onClick={() =>
                      navigate("/codebook-apply", {
                        state: { projectId: project.id },
                      })
                    }
                    style={{ padding: "8px 12px", fontSize: 14 }}
                  >
                    Add Coding
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
