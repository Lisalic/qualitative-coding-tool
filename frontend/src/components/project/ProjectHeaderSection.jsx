import { useState } from "react";
import { apiFetch } from "../../api";

import Panel from "../shell/Panel";
import { btn, input } from "../../lib/uiClasses";

const tabBtn = btn;
const inputClasses = input;

export default function ProjectHeaderSection({ project, onRefreshProject }) {
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const startEdit = () => {
    setEditName(project?.projectname || "");
    setEditDescription(project?.description || "");
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
    setSaving(true);
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
          <button type="button" className={tabBtn} onClick={startEdit}>
            Edit
          </button>
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
              Created: {new Date(project.created_at).toLocaleString()}
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
            />
            <button type="submit" className={tabBtn} disabled={saving}>
              Save
            </button>
            <button type="button" className={tabBtn} onClick={cancelEdit}>
              Cancel
            </button>
          </div>
          <textarea
            className={`${inputClasses} min-h-[80px] resize-y`}
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            placeholder="Project description..."
          />
        </form>
      )}
    </Panel>
  );
}
