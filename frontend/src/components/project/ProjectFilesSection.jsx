import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../../api";
import DialogService from "../feedback/DialogService";
import ToastService from "../feedback/ToastService";
import FileRowActions from "./FileRowActions";
import Panel from "../shell/Panel";
import { formatDate } from "../../lib/formatDate";
import ErrorDisplay from "../feedback/ErrorDisplay";
import { btn, btnActive, btnSm, input, meta } from "../../lib/uiClasses";

const tabBtn = btn;
const tabBtnSelected = btnActive;
const inputClasses = input;

const TABS = [
  ["database", "Databases"],
  ["filtered", "Filtered"],
  ["codebook", "Codebooks"],
  ["coding", "Codings"],
  ["summary", "Summaries"],
];

// Where each file type is viewed. Every view page reads `?ref=`, so a
// plain link works -- including open-in-new-tab.
const VIEW_PATH_BY_TYPE = {
  raw_data: "/data",
  filtered_data: "/filtered-data",
  codebook: "/codebook-view",
  codebook_comparison: "/codebook-comparison-view",
  coding: "/coding-view",
  coding_comparison: "/coding-comparison-view",
  summary: "/summaryview",
};

function viewPathFor(file) {
  const base = VIEW_PATH_BY_TYPE[file.file_type];
  return base && file.schema_name ? `${base}?ref=${encodeURIComponent(file.schema_name)}` : null;
}

/** One line under a tab that has no files of its kind yet. */
function EmptyTabLine({ children }) {
  return <p className="text-sm text-paper/60">{children}</p>;
}

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
  const [renameError, setRenameError] = useState("");
  const [renaming, setRenaming] = useState(false);
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
    setRenameError("");
    setRenamingFile(file.schema_name);
    setNewFileName(file.display_name || file.filename || file.schema_name);
    setNewFileDescription(file.description || "");
  };

  const cancelRenameFile = () => {
    setRenameError("");
    setRenamingFile(null);
    setNewFileName("");
    setNewFileDescription("");
  };

  const saveRenameFile = async (e) => {
    e?.preventDefault();
    if (!newFileName.trim()) {
      setRenameError("Enter a name.");
      return;
    }
    setRenaming(true);
    setRenameError("");
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
      setRenameError("Couldn't rename the file. Please try again.");
    } finally {
      setRenaming(false);
    }
  };

  // Artifacts derived from this one survive its deletion -- each owns a
  // full copy of everything it needs (a coding file carries its own
  // codebook snapshot and its own rows) -- but they permanently lose the
  // recorded link back to it. Name them in the confirmation so that
  // trade-off is a decision rather than a surprise. Best-effort: if the
  // lineage lookup fails, confirm without the list rather than blocking
  // a delete the user asked for.
  const fetchDerivedNames = async (schemaName) => {
    try {
      const response = await apiFetch(
        `/api/artifacts/${encodeURIComponent(schemaName)}/lineage`,
      );
      if (!response.ok) return [];
      const data = await response.json();
      return (data?.children || []).map(
        (child) => child.filename || child.schema_name,
      );
    } catch {
      return [];
    }
  };

  const handleDeleteFile = async (file) => {
    const label = file.display_name || file.schema_name;
    const derived = await fetchDerivedNames(file.schema_name);
    const derivedNote = derived.length
      ? ` Derived files (${derived.join(", ")}) are kept but lose their link to it.`
      : "";
    const confirmed = await DialogService.confirm(
      `Delete "${label}"? This cannot be undone.${derivedNote}`,
      { title: "Delete file", confirmLabel: "Delete", danger: true },
    );
    if (!confirmed) {
      return;
    }
    try {
      const response = await apiFetch(`/api/delete-database/${file.schema_name}`, {
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
      setMergeError("Select at least 2 databases to merge.");
      return;
    }
    if (!mergeName.trim()) {
      setMergeError("Enter a name for the merged database.");
      return;
    }
    const confirmed = await DialogService.confirm(
      `Merge ${selectedDatabases.length} databases into "${mergeName.trim()}"?`,
      { title: "Merge databases", confirmLabel: "Merge" },
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
      setMergeSuccess(`Merged into "${mergeName.trim()}".`);
      setSelectedDatabases([]);
      setMergeName("");
      await onRefreshProject?.();
    } catch (err) {
      console.error("Merge error:", err);
      setMergeError("Couldn't merge the databases. Please try again.");
    } finally {
      setMergeLoading(false);
    }
  };

  const renderFileRow = (f, allowMergeCheckbox = false) => (
    <div
      key={f.id}
      className="flex items-start gap-3 border border-line-soft p-3"
    >
      {allowMergeCheckbox && (
        <input
          type="checkbox"
          checked={selectedDatabases.includes(f.schema_name)}
          onChange={() => handleSelectDatabase(f.schema_name)}
          className="mt-1 accent-paper"
          aria-label={`Select ${f.display_name || f.schema_name} to merge`}
        />
      )}
      <div className="flex-1">
        {renamingFile === f.schema_name ? (
          <form onSubmit={saveRenameFile} className="flex flex-col gap-2">
            <input
              className={inputClasses}
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") cancelRenameFile();
              }}
              placeholder="File name"
              aria-label="File name"
              autoFocus
            />
            <textarea
              className={`${inputClasses} resize-y`}
              value={newFileDescription}
              onChange={(e) => setNewFileDescription(e.target.value)}
              placeholder="Description (optional)"
              aria-label="Description"
              rows={2}
            />
            <div className="flex gap-2">
              <button type="submit" className={tabBtn} disabled={renaming}>
                {renaming ? "Saving…" : "Save"}
              </button>
              <button type="button" className={tabBtn} onClick={cancelRenameFile}>
                Cancel
              </button>
            </div>
            <ErrorDisplay message={renameError} variant="alert" />
          </form>
        ) : (
          <>
            <div className="text-base font-semibold">{f.display_name || "Untitled file"}</div>
            {f.description && (
              <div className="mt-1 text-paper/70">{f.description}</div>
            )}
            <div className={`mt-1.5 ${meta}`}>{formatDate(f.created_at)}</div>
          </>
        )}
      </div>
      {renamingFile !== f.schema_name && (
        <FileRowActions
          file={f}
          viewTo={viewPathFor(f)}
          historyTo={`/versions?ref=${encodeURIComponent(f.schema_name)}`}
          onRename={startRenameFile}
          onDelete={handleDeleteFile}
        />
      )}
    </div>
  );

  return (
    <>
      {/* The tab strip is the region header, not a second panel above it. */}
      <Panel
        title="Project files"
        scroll={false}
        actions={TABS.map(([tab, label]) => (
          <button
            key={tab}
            type="button"
            aria-pressed={activeTab === tab}
            className={`${tabBtn} ${activeTab === tab ? tabBtnSelected : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {label}
          </button>
        ))}
      >
        {activeTab === "database" && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Databases</h2>
              <button type="button" className={tabBtn} onClick={() => navigate("/import")}>
                Import data
              </button>
            </div>
            {dbFiles.length === 0 ? (
              <EmptyTabLine>No databases yet. Import data to add one.</EmptyTabLine>
            ) : (
              <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
                {dbFiles.map((f) => renderFileRow(f, true))}
              </div>
            )}
          </>
        )}

        {activeTab === "filtered" && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Filtered databases</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/filter", { state: { projectId: project.id } })}
              >
                Filter data
              </button>
            </div>
            {filteredFiles.length === 0 ? (
              <EmptyTabLine>No filtered databases yet.</EmptyTabLine>
            ) : (
              <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
                {filteredFiles.map((f) => renderFileRow(f, true))}
              </div>
            )}
          </>
        )}

        {activeTab === "codebook" && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Codebooks</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/codebook", { state: { projectId: project.id } })}
              >
                Create codebook
              </button>
            </div>
            <div className="mb-3 flex gap-2" role="group" aria-label="Show">
              {[
                ["all", "All"],
                ["codebook", "Codebooks"],
                ["comparisons", "Comparisons"],
              ].map(([f, label]) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={codebookFilter === f}
                  className={`${btnSm} ${codebookFilter === f ? btnActive : ""}`}
                  onClick={() => setCodebookFilter(f)}
                >
                  {label}
                </button>
              ))}
            </div>
            {shownCodebooks.length === 0 ? (
              <EmptyTabLine>Nothing here yet.</EmptyTabLine>
            ) : (
              <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
                {shownCodebooks.map((f) => renderFileRow(f))}
              </div>
            )}
          </>
        )}

        {activeTab === "coding" && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Codings</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/codebook-apply", { state: { projectId: project.id } })}
              >
                Apply codebook
              </button>
            </div>
            <div className="mb-3 flex gap-2" role="group" aria-label="Show">
              {[
                ["all", "All"],
                ["coding", "Codings"],
                ["comparisons", "Comparisons"],
              ].map(([f, label]) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={codingFilter === f}
                  className={`${btnSm} ${codingFilter === f ? btnActive : ""}`}
                  onClick={() => setCodingFilter(f)}
                >
                  {label}
                </button>
              ))}
            </div>
            {shownCodings.length === 0 ? (
              <EmptyTabLine>Nothing here yet.</EmptyTabLine>
            ) : (
              <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
                {shownCodings.map((f) => renderFileRow(f))}
              </div>
            )}
          </>
        )}

        {activeTab === "summary" && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Summaries</h2>
              <button
                type="button"
                className={tabBtn}
                onClick={() => navigate("/summarize-coding", { state: { projectId: project.id } })}
              >
                Summarize coding
              </button>
            </div>
            {summaryFiles.length === 0 ? (
              <EmptyTabLine>No summaries yet.</EmptyTabLine>
            ) : (
              <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
                {summaryFiles.map((f) => renderFileRow(f))}
              </div>
            )}
          </>
        )}

        {/* Merging needs two files to pick from on this tab. */}
        {((activeTab === "database" && dbFiles.length >= 2) ||
          (activeTab === "filtered" && filteredFiles.length >= 2)) && (
            <div className="mt-5 text-center">
              <p className={`mb-2 ${meta}`}>Tick two or more databases above to merge them into a new one.</p>
              <input
                type="text"
                aria-label="Merged database name"
                placeholder="Merged database name…"
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
                    ? "Merging…"
                    : `Merge ${selectedDatabases.length} Database${selectedDatabases.length !== 1 ? "s" : ""}`}
                </button>
              </div>
              {mergeError && (
                <div role="alert" className="mt-2 text-error">
                  {mergeError}
                </div>
              )}
              {mergeSuccess && (
                <div role="status" className="mt-2 text-success">
                  {mergeSuccess}
                </div>
              )}
            </div>
          )}
      </Panel>
    </>
  );
}
