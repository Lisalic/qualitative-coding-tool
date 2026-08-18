import { useState } from "react";
import { apiFetch } from "../../api";

const tabBtn =
  "border border-paper px-3.5 py-2 text-sm font-medium transition-colors hover:bg-paper hover:text-ink disabled:opacity-50";
const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper";

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
    <div className="mb-6 border-2 border-paper p-6">
      {!editing ? (
        <>
          <div className="mb-3 flex items-center gap-3">
            <h1 className="text-2xl font-bold">{project.projectname}</h1>
            <button type="button" className={`${tabBtn} text-xs`} onClick={startEdit}>
              Edit
            </button>
          </div>
          {project.description && (
            <p className="mb-3 text-base leading-relaxed text-paper/70">
              {project.description}
            </p>
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
    </div>
  );
}
