import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../../api";
import ToastService from "../feedback/ToastService";
import FileRowActions from "./FileRowActions";

const tabBtn =
  "border border-paper px-3.5 py-2 text-sm font-medium transition-colors hover:bg-paper hover:text-ink";
const tabBtnSelected = "bg-paper text-ink";
const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper";

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
    const confirmed = await ToastService.confirm(
      `Are you sure you want to delete "${schemaName}"? This action cannot be undone.`,
    );
    if (!confirmed) {
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
      ToastService.show("Failed to delete file. Please try again.", "error");
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
    const confirmed = await ToastService.confirm(
      `Merge ${selectedDatabases.length} databases into "${mergeName.trim()}"?`,
    );
    if (!confirmed) return;
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
      className="flex items-start gap-3 border border-paper/20 p-4"
    >
      {allowMergeCheckbox && (
        <input
          type="checkbox"
          checked={selectedDatabases.includes(f.schema_name)}
          onChange={() => handleSelectDatabase(f.schema_name)}
          className="mt-1 accent-paper"
        />
      )}
      <div className="flex-1">
        {renamingFile === f.schema_name ? (
          <form onSubmit={saveRenameFile} className="flex flex-col gap-2">
            <input
              className={inputClasses}
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              placeholder="File name"
            />
            <textarea
              className={`${inputClasses} resize-y`}
              value={newFileDescription}
              onChange={(e) => setNewFileDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
            />
            <div className="flex gap-2">
              <button type="submit" className={tabBtn}>
                Save
              </button>
              <button type="button" className={tabBtn} onClick={cancelRenameFile}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <>
            <div className="text-base font-semibold">
              {f.display_name || f.schema_name}
            </div>
            {f.description && (
              <div className="mt-1 text-paper/70">{f.description}</div>
            )}
            <div className="mt-1.5 text-xs text-paper/50">
              {f.created_at ? new Date(f.created_at).toLocaleString() : ""}
            </div>
          </>
        )}
      </div>
      {renamingFile !== f.schema_name && (
        <FileRowActions
          file={f}
          onView={onView}
          onRename={startRenameFile}
          onDelete={(file) => handleDeleteFile(file.schema_name)}
        />
      )}
    </div>
  );

  return (
    <>
      <div className="mb-6 border-2 border-paper p-5">
        <h2 className="mb-4 text-lg font-semibold">Project Files</h2>
        <div className="flex flex-wrap gap-3">
          {["database", "filtered", "codebook", "coding", "summary"].map((tab) => (
            <button
              key={tab}
              type="button"
              className={`${tabBtn} ${activeTab === tab ? tabBtnSelected : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="border-2 border-paper p-6">
        {activeTab === "database" && (
          <>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Database Files</h2>
              <button type="button" className={tabBtn} onClick={() => navigate("/import")}>
                Add Database
              </button>
            </div>
            <div className="flex flex-col gap-3">
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
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Filtered Files</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/filter", { state: { projectId: project.id } })}
              >
                Add Filtered
              </button>
            </div>
            <div className="flex flex-col gap-3">
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
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Codebook Files</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/codebook-generate", { state: { projectId: project.id } })}
              >
                Add Codebook
              </button>
            </div>
            <div className="mb-3 flex gap-2">
              {["codebook", "comparisons", "all"].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`${tabBtn} ${codebookFilter === f ? tabBtnSelected : ""}`}
                  onClick={() => setCodebookFilter(f)}
                >
                  {f === "all" ? "Show All" : `Show ${f}`}
                </button>
              ))}
            </div>
            <div className="flex flex-col gap-3">
              {shownCodebooks.map((f) =>
                renderFileRow(f, () =>
                  f.file_type === "codebook_comparison"
                    ? navigate("/codebook-comparison-view", {
                        state: { selected: f.schema_name },
                      })
                    : navigate("/codebook-view", { state: { selected: String(f.id) } }),
                ),
              )}
            </div>
          </>
        )}

        {activeTab === "coding" && (
          <>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Coding Files</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/codebook-apply", { state: { projectId: project.id } })}
              >
                Add Coding
              </button>
            </div>
            <div className="mb-3 flex gap-2">
              {["coding", "comparisons", "all"].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`${tabBtn} ${codingFilter === f ? tabBtnSelected : ""}`}
                  onClick={() => setCodingFilter(f)}
                >
                  {f === "all" ? "Show All" : `Show ${f}`}
                </button>
              ))}
            </div>
            <div className="flex flex-col gap-3">
              {shownCodings.map((f) =>
                renderFileRow(f, () =>
                  navigate(
                    f.file_type === "coding_comparison"
                      ? "/coding-comparison-view"
                      : "/coding-view",
                    { state: { selectedCodedData: f.schema_name } },
                  ),
                ),
              )}
            </div>
          </>
        )}

        {activeTab === "summary" && (
          <>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Summary Files</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/summarize-coding")}
              >
                Add Summary
              </button>
            </div>
            <div className="flex flex-col gap-3">
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
            <div className="mt-5 text-center">
              <input
                type="text"
                placeholder="Enter merged database name..."
                value={mergeName}
                onChange={(e) => setMergeName(e.target.value)}
                disabled={mergeLoading}
                className={`${inputClasses} max-w-xs`}
              />
              <div className="mt-2.5">
                <button
                  type="button"
                  className={tabBtn}
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
              {mergeError && <div className="mt-2 text-error">{mergeError}</div>}
              {mergeSuccess && <div className="mt-2 text-success">{mergeSuccess}</div>}
            </div>
          )}
      </div>
    </>
  );
}
