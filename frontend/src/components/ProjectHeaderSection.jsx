import { useState } from "react";
import { apiFetch } from "../api";

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
    <div
      style={{
        backgroundColor: "#000000",
        border: "2px solid #ffffff",
        borderRadius: "12px",
        padding: "24px",
        marginBottom: "24px",
      }}
    >
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
            <h1 style={{ margin: 0, color: "#ffffff" }}>{project.projectname}</h1>
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
            <div style={{ color: "#888", fontSize: "0.9em" }}>
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
              style={{ fontSize: "1.2em", fontWeight: "bold" }}
              placeholder="Project name"
            />
            <button type="submit" className="project-tab" disabled={saving}>
              Save
            </button>
            <button type="button" className="project-tab" onClick={cancelEdit}>
              Cancel
            </button>
          </div>
          <textarea
            className="form-input"
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            style={{ width: "100%", minHeight: 80, resize: "vertical" }}
            placeholder="Project description..."
          />
        </form>
      )}
    </div>
  );
}
