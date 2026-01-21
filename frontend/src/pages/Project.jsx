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
  const dbFile =
    (project.files || []).find((f) => f.file_type === "raw_data") || null;
  const filteredFile =
    (project.files || []).find((f) => f.file_type === "filtered_data") || null;
  const codebookFile =
    (project.files || []).find((f) => f.file_type === "codebook") || null;
  const codingFile =
    (project.files || []).find((f) => f.file_type === "coding") || null;

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
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div>
                      {dbFile
                        ? dbFile.display_name || dbFile.schema_name
                        : "No database"}
                    </div>
                    {dbFile && dbFile.description && (
                      <div style={{ color: "#888", marginTop: 6 }}>
                        {dbFile.description}
                      </div>
                    )}
                  </div>
                  {dbFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate("/data", {
                          state: { selectedDatabase: dbFile.schema_name },
                        })
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}

            {activeTab === "filtered" && (
              <div>
                <h2>Filtered Database</h2>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div>
                      {filteredFile
                        ? filteredFile.display_name || filteredFile.schema_name
                        : "No filtered database"}
                    </div>
                    {filteredFile && filteredFile.description && (
                      <div style={{ color: "#888", marginTop: 6 }}>
                        {filteredFile.description}
                      </div>
                    )}
                  </div>
                  {filteredFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate("/filtered-data", {
                          state: { selectedDatabase: filteredFile.schema_name },
                        })
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}

            {activeTab === "codebook" && (
              <div>
                <h2>Codebook</h2>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div>
                      {codebookFile
                        ? codebookFile.display_name || codebookFile.schema_name
                        : "No codebook"}
                    </div>
                    {codebookFile && codebookFile.description && (
                      <div style={{ color: "#888", marginTop: 6 }}>
                        {codebookFile.description}
                      </div>
                    )}
                  </div>
                  {codebookFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate(
                          `/codebook-view?selected=${encodeURIComponent(codebookFile.schema_name || codebookFile.display_name || codebookFile.id)}`,
                        )
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}

            {activeTab === "coding" && (
              <div>
                <h2>Coding</h2>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div>
                      {codingFile
                        ? codingFile.display_name || codingFile.schema_name
                        : "No coding"}
                    </div>
                    {codingFile && codingFile.description && (
                      <div style={{ color: "#888", marginTop: 6 }}>
                        {codingFile.description}
                      </div>
                    )}
                  </div>
                  {codingFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate("/coding-view", {
                          state: { selectedCodedData: codingFile.schema_name },
                        })
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
