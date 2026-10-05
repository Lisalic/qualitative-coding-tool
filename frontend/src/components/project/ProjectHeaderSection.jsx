import { useState } from "react";
import { apiFetch } from "../../api";
import ProjectDownloadModal from "./ProjectDownloadModal";

import Panel from "../shell/Panel";
import { btn, input } from "../../lib/uiClasses";
import { formatDate } from "../../lib/formatDate";
import ErrorDisplay from "../feedback/ErrorDisplay";

const tabBtn = btn;
const inputClasses = input;

export default function ProjectHeaderSection({ project, onRefreshProject }) {
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [downloadOpen, setDownloadOpen] = useState(false);

  const startEdit = () => {
    setEditName(project?.projectname || "");
    setEditDescription(project?.description || "");
    setSaveError("");
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditName("");
    setEditDescription("");
  };

  const saveEdit = async (e) => {
    e?.preventDefault();
    if (!project) return;
    if (!editName.trim()) {
      setSaveError("Enter a project name.");
      return;
    }
    setSaving(true);
    setSaveError("");
    try {
      const form = new FormData();
      form.append("project_id", String(project.id));
      form.append("name", editName || "");
      form.append("description", editDescription || "");
      const resp = await apiFetch("/api/update-project/", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) throw new Error("Failed to update project");
      await onRefreshProject?.();
      setEditing(false);
    } catch (err) {
      console.error("Failed to update project:", err);
      setSaveError("Couldn't save the project. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel
      title="Details"
      scroll={false}
      actions={
        !editing ? (
          <div className="flex items-center gap-2">
            <button type="button" className={tabBtn} onClick={() => setDownloadOpen(true)}>
              Download
            </button>
            <button type="button" className={tabBtn} onClick={startEdit}>
              Edit
            </button>
          </div>
        ) : null
      }
    >
      {!editing ? (
        <>
          {project.description && (
            <p className="mb-2 leading-relaxed text-paper/70">{project.description}</p>
          )}
          {project.created_at && (
            <div className="text-sm text-paper/50">
              Created: {formatDate(project.created_at)}
            </div>
          )}
        </>
      ) : (
        <form onSubmit={saveEdit} className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <input
              className={`${inputClasses} flex-1 text-lg font-semibold`}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="Project name"
              aria-label="Project name"
              autoFocus
            />
            <button type="submit" className={tabBtn} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button type="button" className={tabBtn} onClick={cancelEdit}>
              Cancel
            </button>
          </div>
          <textarea
            className={`${inputClasses} min-h-[80px] resize-y`}
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            placeholder="Project description…"
            aria-label="Project description"
          />
          <ErrorDisplay message={saveError} variant="alert" />
        </form>
      )}
      {downloadOpen && <ProjectDownloadModal project={project} onClose={() => setDownloadOpen(false)} />}
    </Panel>
  );
}
