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
  const [renamingFile, setRenamingFile] = useState(null);
  const [newFileName, setNewFileName] = useState("");
  const [newFileDescription, setNewFileDescription] = useState("");

  // Database merge state
  const [selectedDatabases, setSelectedDatabases] = useState([]);
  const [mergeName, setMergeName] = useState("");
  const [mergeLoading, setMergeLoading] = useState(false);
  const [mergeError, setMergeError] = useState("");
  const [mergeSuccess, setMergeSuccess] = useState("");

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

  // Clear selected databases when switching tabs
  useEffect(() => {
    setSelectedDatabases([]);
    setMergeName("");
  }, [activeTab]);

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
    (f) => f.file_type === "codebook" || f.file_type === "codebook_comparison",
  );
  const codingFiles = (project.files || []).filter(
    (f) => f.file_type === "coding" || f.file_type === "coding_comparison",
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

  const startRenameFile = (file) => {
    setRenamingFile(file.schema_name);
    setNewFileName(file.display_name || file.filename || file.schema_name);
    setNewFileDescription(file.description || "");
  };

  const cancelRenameFile = () => {
    setRenamingFile(null);
    setNewFileName("");
    setNewFileDescription("");
  };

  const saveRenameFile = async (e) => {
    e?.preventDefault();
    if (!newFileName.trim()) {
      alert("File name cannot be empty");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("schema_name", renamingFile);
      formData.append("display_name", newFileName.trim());
      formData.append("description", newFileDescription || "");

      const response = await apiFetch("/api/rename-file/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to rename file");
      }

      const data = await response.json();
      console.log("File renamed:", data);

      // Refresh the project data
      const resp = await apiFetch("/api/projects/");
      const projectData = await resp.json();
      const rows = projectData.projects || [];
      const found = rows.find((p) => String(p.id) === String(projectId));
      setProject(found || null);

      setRenamingFile(null);
      setNewFileName("");
      setNewFileDescription("");
    } catch (err) {
      console.error("Rename error:", err);
      alert(`Error renaming file: ${err.message}`);
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

  // Database merge functions
  const handleSelectDatabase = (dbName) => {
    setSelectedDatabases((prev) =>
      prev.includes(dbName)
        ? prev.filter((db) => db !== dbName)
        : [...prev, dbName],
    );
  };

  const handleMergeDatabases = async () => {
    if (selectedDatabases.length < 2) {
      setMergeError("Please select at least 2 databases to merge");
      return;
    }

    if (!mergeName.trim()) {
      setMergeError("Please enter a name for the merged database");
      return;
    }

    setMergeLoading(true);
    setMergeSuccess("");
    setMergeError("");

    try {
      const formData = new FormData();
      formData.append("databases", JSON.stringify(selectedDatabases));
      formData.append("name", mergeName.trim());
      formData.append("project_id", String(project.id));

      const response = await apiFetch("/api/merge-databases/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let errorMsg = "Failed to merge databases";
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch (e) {
          // If we can't parse JSON, use the generic message
        }
        throw new Error(errorMsg);
      }

      const data = await response.json();
      console.log("Databases merged:", data);
      setMergeSuccess("Databases merged successfully!");
      setSelectedDatabases([]);
      setMergeName("");

      // Refresh the page to show the new merged database
      window.location.reload();
    } catch (err) {
      console.error("Merge error:", err);
      setMergeError(err.message || "Failed to merge databases");
    } finally {
      setMergeLoading(false);
    }
  };

  return (
    <div className="home-container">
      <div className="form-wrapper">
        {/* Project Header */}
        <div
          style={{
            backgroundColor: "#000000",
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
              alignItems: "flex-start",
              gap: "20px",
            }}
          >
            <div style={{ flex: 1 }}>
              {!editing ? (
                <>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      marginBottom: "12px",
                    }}
                  >
                    <h1 style={{ margin: 0, color: "#ffffff" }}>
                      {project.projectname}
                    </h1>
                    <button
                      className="project-tab"
                      onClick={startEdit}
                      style={{ padding: "6px 12px", fontSize: 13 }}
                    >
                      Edit
                    </button>
                  </div>
                  {project.description && (
                    <div
                      style={{
                        color: "#cccccc",
                        fontSize: "1.1em",
                        lineHeight: 1.4,
                        marginBottom: "12px",
                      }}
                    >
                      {project.description}
                    </div>
                  )}
                  {project.created_at && (
                    <div
                      style={{
                        color: "#888",
                        fontSize: "0.9em",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      Created: {new Date(project.created_at).toLocaleString()}
                    </div>
                  )}
                </>
              ) : (
                <form onSubmit={saveEdit}>
                  <div
                    style={{
                      display: "flex",
                      gap: 12,
                      alignItems: "center",
                      marginBottom: "16px",
                    }}
                  >
                    <input
                      className="form-input"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      style={{
                        fontSize: "1.4em",
                        fontWeight: "bold",
                        padding: "8px 12px",
                      }}
                      placeholder="Project name"
                    />
                    <button
                      type="submit"
                      className="project-tab"
                      disabled={saving}
                      style={{ padding: "8px 16px", fontSize: 14 }}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="project-tab"
                      onClick={cancelEdit}
                      style={{ padding: "8px 16px", fontSize: 14 }}
                    >
                      Cancel
                    </button>
                  </div>
                  <div>
                    <label
                      style={{
                        display: "block",
                        marginBottom: 8,
                        color: "#cccccc",
                        fontWeight: "bold",
                      }}
                    >
                      Description
                    </label>
                    <textarea
                      className="form-input"
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      style={{
                        width: "100%",
                        minHeight: 80,
                        resize: "vertical",
                      }}
                      placeholder="Project description..."
                    />
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            backgroundColor: "#000000",
            border: "2px solid #ffffff",
            borderRadius: "12px",
            padding: "20px",
            marginBottom: "24px",
          }}
        >
          <h2
            style={{
              margin: "0 0 16px 0",
              color: "#ffffff",
              fontSize: "1.2em",
            }}
          >
            Project Files
          </h2>
          <div
            style={{
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <button
              type="button"
              className={`project-tab ${activeTab === "database" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("database");
              }}
              style={{
                padding: "12px 20px",
                fontSize: 15,
                fontWeight: "bold",
                minWidth: "140px",
                justifyContent: "center",
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
              style={{
                padding: "12px 20px",
                fontSize: 15,
                fontWeight: "bold",
                minWidth: "140px",
                justifyContent: "center",
              }}
            >
              Filtered
            </button>
            <button
              type="button"
              className={`project-tab ${activeTab === "codebook" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("codebook");
              }}
              style={{
                padding: "12px 20px",
                fontSize: 15,
                fontWeight: "bold",
                minWidth: "140px",
                justifyContent: "center",
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
              style={{
                padding: "12px 20px",
                fontSize: 15,
                fontWeight: "bold",
                minWidth: "140px",
                justifyContent: "center",
              }}
            >
              Coding
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div>
          {activeTab === "database" && (
            <div
              style={{
                backgroundColor: "#000000",
                border: "2px solid #ffffff",
                borderRadius: "12px",
                padding: "24px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "20px",
                }}
              >
                <h2 style={{ margin: 0, color: "#ffffff", fontSize: "1.3em" }}>
                  Database Files
                </h2>
                <button
                  className="project-tab"
                  onClick={() =>
                    navigate("/import", { state: { projectId: project.id } })
                  }
                  style={{
                    padding: "10px 16px",
                    fontSize: 14,
                    fontWeight: "bold",
                  }}
                >
                  Add Database
                </button>
              </div>

              {dbFiles.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    color: "#888",
                    padding: "40px",
                    fontSize: "1.1em",
                  }}
                >
                  No database files yet
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  {dbFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        backgroundColor: "#000000",
                        border: "1px solid #333",
                        borderRadius: "8px",
                        padding: "16px",
                        display: "flex",
                        alignItems: "flex-start",
                        transition: "border-color 0.2s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "#ffffff";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "#333";
                      }}
                    >
                      <div style={{ marginRight: "12px", marginTop: "4px" }}>
                        <input
                          type="checkbox"
                          checked={selectedDatabases.includes(f.schema_name)}
                          onChange={() => handleSelectDatabase(f.schema_name)}
                          style={{
                            width: "16px",
                            height: "16px",
                          }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        {renamingFile === f.schema_name ? (
                          <form onSubmit={saveRenameFile}>
                            <div style={{ marginBottom: "8px" }}>
                              <input
                                type="text"
                                value={newFileName}
                                onChange={(e) => setNewFileName(e.target.value)}
                                placeholder="File name"
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                }}
                              />
                            </div>
                            <div style={{ marginBottom: "8px" }}>
                              <textarea
                                value={newFileDescription}
                                onChange={(e) =>
                                  setNewFileDescription(e.target.value)
                                }
                                placeholder="Description (optional)"
                                rows={2}
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                  resize: "vertical",
                                }}
                              />
                            </div>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                type="submit"
                                className="project-tab"
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="project-tab"
                                onClick={cancelRenameFile}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </form>
                        ) : (
                          <>
                            <div
                              style={{
                                fontSize: "1.1em",
                                fontWeight: "bold",
                                color: "#ffffff",
                                marginBottom: "4px",
                              }}
                            >
                              {f.display_name || f.schema_name}
                            </div>
                            {f.description && (
                              <div
                                style={{
                                  color: "#cccccc",
                                  marginBottom: "8px",
                                  fontSize: "0.95em",
                                }}
                              >
                                {f.description}
                              </div>
                            )}
                            <div
                              style={{
                                color: "#aaa",
                                fontSize: "0.9em",
                                marginBottom: "4px",
                              }}
                            >
                              Parents:{" "}
                              {f.parent_files && f.parent_files.length > 0
                                ? f.parent_files.map((p) => p.name).join(", ")
                                : "null"}
                            </div>
                          </>
                        )}
                        {f.created_at && renamingFile !== f.schema_name && (
                          <div
                            style={{
                              color: "#888",
                              fontSize: "0.85em",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      {renamingFile !== f.schema_name && (
                        <div
                          style={{
                            display: "flex",
                            gap: "8px",
                            marginLeft: "12px",
                          }}
                        >
                          <button
                            className="project-tab"
                            onClick={() =>
                              navigate("/data", {
                                state: { selectedDatabase: f.schema_name },
                              })
                            }
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            View
                          </button>
                          <button
                            className="project-tab"
                            onClick={() => startRenameFile(f)}
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="project-tab"
                            onClick={() =>
                              handleDeleteFile(f.schema_name, "database")
                            }
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Merge Controls */}
              {dbFiles.length > 0 && (
                <div style={{ marginTop: "20px", textAlign: "center" }}>
                  <div style={{ marginBottom: "12px" }}>
                    <input
                      type="text"
                      placeholder="Enter merged database name..."
                      value={mergeName}
                      onChange={(e) => setMergeName(e.target.value)}
                      disabled={mergeLoading}
                      style={{
                        width: "300px",
                        padding: "8px 12px",
                        backgroundColor: "#000",
                        color: "#fff",
                        border: "1px solid #555",
                        borderRadius: "4px",
                        fontSize: "14px",
                      }}
                    />
                  </div>

                  <button
                    className="project-tab"
                    onClick={handleMergeDatabases}
                    disabled={
                      selectedDatabases.length < 2 ||
                      mergeLoading ||
                      !mergeName.trim()
                    }
                    style={{
                      padding: "12px 24px",
                      fontSize: "14px",
                      fontWeight: "bold",
                      opacity:
                        selectedDatabases.length < 2 ||
                        mergeLoading ||
                        !mergeName.trim()
                          ? 0.6
                          : 1,
                      cursor:
                        selectedDatabases.length < 2 ||
                        mergeLoading ||
                        !mergeName.trim()
                          ? "not-allowed"
                          : "pointer",
                    }}
                  >
                    {mergeLoading
                      ? "Merging..."
                      : `Merge ${selectedDatabases.length} Database${selectedDatabases.length !== 1 ? "s" : ""}`}
                  </button>

                  {mergeError && (
                    <div
                      style={{
                        color: "#ff6b6b",
                        fontSize: "14px",
                        marginTop: "8px",
                      }}
                    >
                      {mergeError}
                    </div>
                  )}

                  {mergeSuccess && (
                    <div
                      style={{
                        color: "#4CAF50",
                        fontSize: "14px",
                        marginTop: "8px",
                      }}
                    >
                      {mergeSuccess}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "filtered" && (
            <div
              style={{
                backgroundColor: "#000000",
                border: "2px solid #ffffff",
                borderRadius: "12px",
                padding: "24px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "20px",
                }}
              >
                <h2 style={{ margin: 0, color: "#ffffff", fontSize: "1.3em" }}>
                  Filtered Database Files
                </h2>
                <button
                  className="project-tab"
                  onClick={() =>
                    navigate("/filter", { state: { projectId: project.id } })
                  }
                  style={{
                    padding: "10px 16px",
                    fontSize: 14,
                    fontWeight: "bold",
                  }}
                >
                  Add Filtered
                </button>
              </div>

              {filteredFiles.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    color: "#888",
                    padding: "40px",
                    fontSize: "1.1em",
                  }}
                >
                  No filtered database files yet
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  {filteredFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        backgroundColor: "#000000",
                        border: "1px solid #333",
                        borderRadius: "8px",
                        padding: "16px",
                        display: "flex",
                        alignItems: "flex-start",
                        transition: "border-color 0.2s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "#ffffff";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "#333";
                      }}
                    >
                      <div style={{ marginRight: "12px", marginTop: "4px" }}>
                        <input
                          type="checkbox"
                          checked={selectedDatabases.includes(f.schema_name)}
                          onChange={() => handleSelectDatabase(f.schema_name)}
                          style={{
                            width: "16px",
                            height: "16px",
                          }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        {renamingFile === f.schema_name ? (
                          <form onSubmit={saveRenameFile}>
                            <div style={{ marginBottom: "8px" }}>
                              <input
                                type="text"
                                value={newFileName}
                                onChange={(e) => setNewFileName(e.target.value)}
                                placeholder="File name"
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                }}
                              />
                            </div>
                            <div style={{ marginBottom: "8px" }}>
                              <textarea
                                value={newFileDescription}
                                onChange={(e) =>
                                  setNewFileDescription(e.target.value)
                                }
                                placeholder="Description (optional)"
                                rows={2}
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                  resize: "vertical",
                                }}
                              />
                            </div>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                type="submit"
                                className="project-tab"
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="project-tab"
                                onClick={cancelRenameFile}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </form>
                        ) : (
                          <>
                            <div
                              style={{
                                fontSize: "1.1em",
                                fontWeight: "bold",
                                color: "#ffffff",
                                marginBottom: "4px",
                              }}
                            >
                              {f.display_name || f.schema_name}
                            </div>
                            {f.description && (
                              <div
                                style={{
                                  color: "#cccccc",
                                  marginBottom: "8px",
                                  fontSize: "0.95em",
                                }}
                              >
                                {f.description}
                              </div>
                            )}
                            <div
                              style={{
                                color: "#aaa",
                                fontSize: "0.9em",
                                marginBottom: "4px",
                              }}
                            >
                              Parents:{" "}
                              {f.parent_files && f.parent_files.length > 0
                                ? f.parent_files.map((p) => p.name).join(", ")
                                : "null"}
                            </div>
                          </>
                        )}
                        {f.created_at && renamingFile !== f.schema_name && (
                          <div
                            style={{
                              color: "#888",
                              fontSize: "0.85em",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      {renamingFile !== f.schema_name && (
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="project-tab"
                            onClick={() =>
                              navigate("/filtered-data", {
                                state: { selectedDatabase: f.schema_name },
                              })
                            }
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            View
                          </button>
                          <button
                            className="project-tab"
                            onClick={() => startRenameFile(f)}
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="project-tab"
                            onClick={() =>
                              handleDeleteFile(f.schema_name, "filtered")
                            }
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Filtered Database Merge Controls */}
              {filteredFiles.length > 0 && (
                <div style={{ marginTop: "20px", textAlign: "center" }}>
                  <div style={{ marginBottom: "12px" }}>
                    <input
                      type="text"
                      placeholder="Enter merged filtered database name..."
                      value={mergeName}
                      onChange={(e) => setMergeName(e.target.value)}
                      disabled={mergeLoading}
                      style={{
                        width: "300px",
                        padding: "8px 12px",
                        backgroundColor: "#000",
                        color: "#fff",
                        border: "1px solid #555",
                        borderRadius: "4px",
                        fontSize: "14px",
                      }}
                    />
                  </div>

                  <button
                    className="project-tab"
                    onClick={handleMergeDatabases}
                    disabled={
                      selectedDatabases.length < 2 ||
                      mergeLoading ||
                      !mergeName.trim()
                    }
                    style={{
                      padding: "12px 24px",
                      fontSize: "14px",
                      fontWeight: "bold",
                      opacity:
                        selectedDatabases.length < 2 ||
                        mergeLoading ||
                        !mergeName.trim()
                          ? 0.6
                          : 1,
                      cursor:
                        selectedDatabases.length < 2 ||
                        mergeLoading ||
                        !mergeName.trim()
                          ? "not-allowed"
                          : "pointer",
                    }}
                  >
                    {mergeLoading
                      ? "Merging..."
                      : `Merge ${selectedDatabases.length} Filtered Database${selectedDatabases.length !== 1 ? "s" : ""}`}
                  </button>

                  {mergeError && (
                    <div
                      style={{
                        color: "#ff6b6b",
                        fontSize: "14px",
                        marginTop: "8px",
                      }}
                    >
                      {mergeError}
                    </div>
                  )}

                  {mergeSuccess && (
                    <div
                      style={{
                        color: "#4CAF50",
                        fontSize: "14px",
                        marginTop: "8px",
                      }}
                    >
                      {mergeSuccess}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "codebook" && (
            <div
              style={{
                backgroundColor: "#000000",
                border: "2px solid #ffffff",
                borderRadius: "12px",
                padding: "24px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "20px",
                }}
              >
                <h2 style={{ margin: 0, color: "#ffffff", fontSize: "1.3em" }}>
                  Codebook Files
                </h2>
                <button
                  className="project-tab"
                  onClick={() =>
                    navigate("/codebook-generate", {
                      state: { projectId: project.id },
                    })
                  }
                  style={{
                    padding: "10px 16px",
                    fontSize: 14,
                    fontWeight: "bold",
                  }}
                >
                  Add Codebook
                </button>
              </div>
              {codebookFiles.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    color: "#888",
                    padding: "40px",
                    fontSize: "1.1em",
                  }}
                >
                  No codebook files yet
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  {codebookFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        backgroundColor: "#000000",
                        border: "1px solid #333",
                        borderRadius: "8px",
                        padding: "16px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "border-color 0.2s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "#ffffff";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "#333";
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        {renamingFile === f.schema_name ? (
                          <form onSubmit={saveRenameFile}>
                            <div style={{ marginBottom: "8px" }}>
                              <input
                                type="text"
                                value={newFileName}
                                onChange={(e) => setNewFileName(e.target.value)}
                                placeholder="File name"
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                }}
                              />
                            </div>
                            <div style={{ marginBottom: "8px" }}>
                              <textarea
                                value={newFileDescription}
                                onChange={(e) =>
                                  setNewFileDescription(e.target.value)
                                }
                                placeholder="Description (optional)"
                                rows={2}
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                  resize: "vertical",
                                }}
                              />
                            </div>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                type="submit"
                                className="project-tab"
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="project-tab"
                                onClick={cancelRenameFile}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </form>
                        ) : (
                          <>
                            <div
                              style={{
                                fontSize: "1.1em",
                                fontWeight: "bold",
                                color: "#ffffff",
                                marginBottom: "4px",
                              }}
                            >
                              {f.display_name || f.schema_name}
                            </div>
                            {f.description && (
                              <div
                                style={{
                                  color: "#cccccc",
                                  marginBottom: "8px",
                                  fontSize: "0.95em",
                                }}
                              >
                                {f.description}
                              </div>
                            )}
                            <div
                              style={{
                                color: "#aaa",
                                fontSize: "0.9em",
                                marginBottom: "4px",
                              }}
                            >
                              Parents:{" "}
                              {f.parent_files && f.parent_files.length > 0
                                ? f.parent_files.map((p) => p.name).join(", ")
                                : "null"}
                            </div>
                          </>
                        )}
                        {f.created_at && renamingFile !== f.schema_name && (
                          <div
                            style={{
                              color: "#888",
                              fontSize: "0.85em",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      {renamingFile !== f.schema_name && (
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="project-tab"
                            onClick={() =>
                              navigate("/codebook-view", {
                                state: { selected: String(f.id) },
                              })
                            }
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            View
                          </button>
                          <button
                            className="project-tab"
                            onClick={() => startRenameFile(f)}
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Edit
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
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === "coding" && (
            <div
              style={{
                backgroundColor: "#000000",
                border: "2px solid #ffffff",
                borderRadius: "12px",
                padding: "24px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "20px",
                }}
              >
                <h2 style={{ margin: 0, color: "#ffffff", fontSize: "1.3em" }}>
                  Coding Files
                </h2>
                <button
                  className="project-tab"
                  onClick={() =>
                    navigate("/codebook-apply", {
                      state: { projectId: project.id },
                    })
                  }
                  style={{
                    padding: "10px 16px",
                    fontSize: 14,
                    fontWeight: "bold",
                  }}
                >
                  Add Coding
                </button>
              </div>
              {codingFiles.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    color: "#888",
                    padding: "40px",
                    fontSize: "1.1em",
                  }}
                >
                  No coding files yet
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  {codingFiles.map((f) => (
                    <div
                      key={f.id}
                      style={{
                        backgroundColor: "#000000",
                        border: "1px solid #333",
                        borderRadius: "8px",
                        padding: "16px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "border-color 0.2s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "#ffffff";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "#333";
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        {renamingFile === f.schema_name ? (
                          <form onSubmit={saveRenameFile}>
                            <div style={{ marginBottom: "8px" }}>
                              <input
                                type="text"
                                value={newFileName}
                                onChange={(e) => setNewFileName(e.target.value)}
                                placeholder="File name"
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                }}
                              />
                            </div>
                            <div style={{ marginBottom: "8px" }}>
                              <textarea
                                value={newFileDescription}
                                onChange={(e) =>
                                  setNewFileDescription(e.target.value)
                                }
                                placeholder="Description (optional)"
                                rows={2}
                                style={{
                                  width: "100%",
                                  padding: "4px 8px",
                                  backgroundColor: "#333",
                                  color: "#ffffff",
                                  border: "1px solid #555",
                                  borderRadius: "4px",
                                  resize: "vertical",
                                }}
                              />
                            </div>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                type="submit"
                                className="project-tab"
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="project-tab"
                                onClick={cancelRenameFile}
                                style={{
                                  padding: "4px 8px",
                                  fontSize: 12,
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </form>
                        ) : (
                          <>
                            <div
                              style={{
                                fontSize: "1.1em",
                                fontWeight: "bold",
                                color: "#ffffff",
                                marginBottom: "4px",
                              }}
                            >
                              {f.display_name || f.schema_name}
                            </div>
                            {f.description && (
                              <div
                                style={{
                                  color: "#cccccc",
                                  marginBottom: "8px",
                                  fontSize: "0.95em",
                                }}
                              >
                                {f.description}
                              </div>
                            )}
                            <div
                              style={{
                                color: "#aaa",
                                fontSize: "0.9em",
                                marginBottom: "4px",
                              }}
                            >
                              Parents:{" "}
                              {f.parent_files && f.parent_files.length > 0
                                ? f.parent_files.map((p) => p.name).join(", ")
                                : "null"}
                            </div>
                          </>
                        )}
                        {f.created_at && renamingFile !== f.schema_name && (
                          <div
                            style={{
                              color: "#888",
                              fontSize: "0.85em",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            {new Date(f.created_at).toLocaleString()}
                          </div>
                        )}
                      </div>
                      {renamingFile !== f.schema_name && (
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="project-tab"
                            onClick={() =>
                              navigate("/coding-view", {
                                state: { selectedCodedData: f.schema_name },
                              })
                            }
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            View
                          </button>
                          <button
                            className="project-tab"
                            onClick={() => startRenameFile(f)}
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="project-tab"
                            onClick={() =>
                              handleDeleteFile(f.schema_name, "coding")
                            }
                            style={{
                              padding: "8px 14px",
                              fontSize: 13,
                              fontWeight: "bold",
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
