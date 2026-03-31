import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";

export default function ProjectFilesSection({ project, onRefreshProject }) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("database");
  const [renamingFile, setRenamingFile] = useState(null);
  const [newFileName, setNewFileName] = useState("");
  const [newFileDescription, setNewFileDescription] = useState("");
  const [selectedDatabases, setSelectedDatabases] = useState([]);
  const [mergeName, setMergeName] = useState("");
  const [mergeLoading, setMergeLoading] = useState(false);
  const [mergeError, setMergeError] = useState("");
  const [mergeSuccess, setMergeSuccess] = useState("");
  const [codebookFilter, setCodebookFilter] = useState("all");
  const [codingFilter, setCodingFilter] = useState("all");

  useEffect(() => {
    setSelectedDatabases([]);
    setMergeName("");
  }, [activeTab]);

  const dbFiles = useMemo(
    () => (project?.files || []).filter((f) => f.file_type === "raw_data"),
    [project],
  );
  const filteredFiles = useMemo(
    () => (project?.files || []).filter((f) => f.file_type === "filtered_data"),
    [project],
  );
  const codebookFiles = useMemo(
    () =>
      (project?.files || []).filter(
        (f) => f.file_type === "codebook" || f.file_type === "codebook_comparison",
      ),
    [project],
  );
  const codingFiles = useMemo(
    () =>
      (project?.files || []).filter(
        (f) => f.file_type === "coding" || f.file_type === "coding_comparison",
      ),
    [project],
  );
  const summaryFiles = useMemo(
    () => (project?.files || []).filter((f) => f.file_type === "summary"),
    [project],
  );

  const shownCodebooks = useMemo(() => {
    if (codebookFilter === "all") return codebookFiles;
    if (codebookFilter === "codebook")
      return codebookFiles.filter((f) => f.file_type === "codebook");
    return codebookFiles.filter((f) => f.file_type === "codebook_comparison");
  }, [codebookFilter, codebookFiles]);

  const shownCodings = useMemo(() => {
    if (codingFilter === "all") return codingFiles;
    if (codingFilter === "coding")
      return codingFiles.filter((f) => f.file_type === "coding");
    return codingFiles.filter((f) => f.file_type === "coding_comparison");
  }, [codingFilter, codingFiles]);

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
    if (!newFileName.trim()) return;
    try {
      const form = new FormData();
      form.append("schema_name", renamingFile);
      form.append("display_name", newFileName.trim());
      form.append("description", newFileDescription || "");
      const response = await apiFetch("/api/rename-file/", {
        method: "POST",
        body: form,
      });
      if (!response.ok) throw new Error("Failed to rename file");
      await onRefreshProject?.();
      cancelRenameFile();
    } catch (err) {
      console.error("Rename error:", err);
    }
  };

  const handleDeleteFile = async (schemaName) => {
    if (
      !confirm(
        `Are you sure you want to delete "${schemaName}"? This action cannot be undone.`,
      )
    ) {
      return;
    }
    try {
      const response = await apiFetch(`/api/delete-database/${schemaName}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Failed to delete file");
      await onRefreshProject?.();
    } catch (err) {
      console.error("Delete error:", err);
      alert("Failed to delete file. Please try again.");
    }
  };

  const handleSelectDatabase = (schemaName) => {
    setSelectedDatabases((prev) =>
      prev.includes(schemaName)
        ? prev.filter((db) => db !== schemaName)
        : [...prev, schemaName],
    );
  };

  const handleMergeDatabases = async () => {
    if (!project) return;
    if (selectedDatabases.length < 2) {
      setMergeError("Please select at least 2 databases to merge");
      return;
    }
    if (!mergeName.trim()) {
      setMergeError("Please enter a name for the merged database");
      return;
    }
    setMergeLoading(true);
    setMergeError("");
    setMergeSuccess("");
    try {
      const formData = new FormData();
      formData.append("databases", JSON.stringify(selectedDatabases));
      formData.append("name", mergeName.trim());
      formData.append("project_id", String(project.id));
      const response = await apiFetch("/api/merge-databases/", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error("Failed to merge databases");
      setMergeSuccess("Databases merged successfully!");
      setSelectedDatabases([]);
      setMergeName("");
      await onRefreshProject?.();
    } catch (err) {
      setMergeError(err.message || "Failed to merge databases");
    } finally {
      setMergeLoading(false);
    }
  };

  const renderFileRow = (f, onView, allowMergeCheckbox = false) => (
    <div
      key={f.id}
      style={{
        backgroundColor: "#000000",
        border: "1px solid #333",
        borderRadius: "8px",
        padding: "16px",
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
      }}
    >
      {allowMergeCheckbox && (
        <input
          type="checkbox"
          checked={selectedDatabases.includes(f.schema_name)}
          onChange={() => handleSelectDatabase(f.schema_name)}
          style={{ marginTop: "4px" }}
        />
      )}
      <div style={{ flex: 1 }}>
        {renamingFile === f.schema_name ? (
          <form onSubmit={saveRenameFile}>
            <input
              className="form-input"
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              placeholder="File name"
            />
            <textarea
              className="form-input"
              value={newFileDescription}
              onChange={(e) => setNewFileDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
              style={{ marginTop: 8, resize: "vertical" }}
            />
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button type="submit" className="project-tab">
                Save
              </button>
              <button type="button" className="project-tab" onClick={cancelRenameFile}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <>
            <div style={{ fontSize: "1.1em", fontWeight: "bold", color: "#fff" }}>
              {f.display_name || f.schema_name}
            </div>
            {f.description && <div style={{ color: "#ccc", marginTop: 4 }}>{f.description}</div>}
            <div style={{ color: "#888", fontSize: 12, marginTop: 6 }}>
              {f.created_at ? new Date(f.created_at).toLocaleString() : ""}
            </div>
          </>
        )}
      </div>
      {renamingFile !== f.schema_name && (
        <div style={{ display: "flex", gap: 8 }}>
          <button className="project-tab" onClick={onView}>
            View
          </button>
          <button className="project-tab" onClick={() => startRenameFile(f)}>
            Edit
          </button>
          <button className="project-tab" onClick={() => handleDeleteFile(f.schema_name)}>
            Delete
          </button>
        </div>
      )}
    </div>
  );

  return (
    <>
      <div
        style={{
          backgroundColor: "#000000",
          border: "2px solid #ffffff",
          borderRadius: "12px",
          padding: "20px",
          marginBottom: "24px",
        }}
      >
        <h2 style={{ margin: "0 0 16px 0", color: "#ffffff", fontSize: "1.2em" }}>
          Project Files
        </h2>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {["database", "filtered", "codebook", "coding", "summary"].map((tab) => (
            <button
              key={tab}
              type="button"
              className={`project-tab ${activeTab === tab ? "selected" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div
        style={{
          backgroundColor: "#000000",
          border: "2px solid #ffffff",
          borderRadius: "12px",
          padding: "24px",
        }}
      >
        {activeTab === "database" && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h2 style={{ margin: 0, color: "#fff" }}>Database Files</h2>
              <button className="project-tab" onClick={() => navigate("/import")}>
                Add Database
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {dbFiles.map((f) =>
                renderFileRow(
                  f,
                  () => navigate("/data", { state: { selectedDatabase: f.schema_name } }),
                  true,
                ),
              )}
            </div>
          </>
        )}

        {activeTab === "filtered" && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h2 style={{ margin: 0, color: "#fff" }}>Filtered Files</h2>
              <button
                className="project-tab"
                onClick={() => navigate("/filter", { state: { projectId: project.id } })}
              >
                Add Filtered
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {filteredFiles.map((f) =>
                renderFileRow(
                  f,
                  () =>
                    navigate("/filtered-data", {
                      state: { selectedDatabase: f.schema_name },
                    }),
                  true,
                ),
              )}
            </div>
          </>
        )}

        {activeTab === "codebook" && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h2 style={{ margin: 0, color: "#fff" }}>Codebook Files</h2>
              <button
                className="project-tab"
                onClick={() => navigate("/codebook-generate", { state: { projectId: project.id } })}
              >
                Add Codebook
              </button>
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              {["codebook", "comparisons", "all"].map((f) => (
                <button
                  key={f}
                  className={`project-tab ${codebookFilter === f ? "selected" : ""}`}
                  onClick={() => setCodebookFilter(f)}
                >
                  {f === "all" ? "Show All" : `Show ${f}`}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {shownCodebooks.map((f) =>
                renderFileRow(f, () =>
                  navigate("/codebook-view", { state: { selected: String(f.id) } }),
                ),
              )}
            </div>
          </>
        )}

        {activeTab === "coding" && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h2 style={{ margin: 0, color: "#fff" }}>Coding Files</h2>
              <button
                className="project-tab"
                onClick={() => navigate("/codebook-apply", { state: { projectId: project.id } })}
              >
                Add Coding
              </button>
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              {["coding", "comparisons", "all"].map((f) => (
                <button
                  key={f}
                  className={`project-tab ${codingFilter === f ? "selected" : ""}`}
                  onClick={() => setCodingFilter(f)}
                >
                  {f === "all" ? "Show All" : `Show ${f}`}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {shownCodings.map((f) =>
                renderFileRow(f, () =>
                  navigate("/coding-view", {
                    state: { selectedCodedData: f.schema_name },
                  }),
                ),
              )}
            </div>
          </>
        )}

        {activeTab === "summary" && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h2 style={{ margin: 0, color: "#fff" }}>Summary Files</h2>
              <button
                className="project-tab"
                onClick={() => navigate("/summarize-coding", { state: { projectId: project.id } })}
              >
                Add Summary
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {summaryFiles.map((f) =>
                renderFileRow(f, () =>
                  navigate("/summaryview", {
                    state: { selectedSummary: f.schema_name || f.display_name || f.id },
                  }),
                ),
              )}
            </div>
          </>
        )}

        {(activeTab === "database" || activeTab === "filtered") &&
          (dbFiles.length > 0 || filteredFiles.length > 0) && (
            <div style={{ marginTop: 20, textAlign: "center" }}>
              <input
                type="text"
                placeholder="Enter merged database name..."
                value={mergeName}
                onChange={(e) => setMergeName(e.target.value)}
                disabled={mergeLoading}
                className="form-input"
                style={{ maxWidth: 320 }}
              />
              <div style={{ marginTop: 10 }}>
                <button
                  className="project-tab"
                  onClick={handleMergeDatabases}
                  disabled={
                    selectedDatabases.length < 2 || mergeLoading || !mergeName.trim()
                  }
                >
                  {mergeLoading
                    ? "Merging..."
                    : `Merge ${selectedDatabases.length} Database${selectedDatabases.length !== 1 ? "s" : ""}`}
                </button>
              </div>
              {mergeError && <div style={{ color: "#ff6b6b", marginTop: 8 }}>{mergeError}</div>}
              {mergeSuccess && <div style={{ color: "#4CAF50", marginTop: 8 }}>{mergeSuccess}</div>}
            </div>
          )}
      </div>
    </>
  );
}
