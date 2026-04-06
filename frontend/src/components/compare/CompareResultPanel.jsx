import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { apiFetch } from "../../api";

export default function CompareResultPanel({
  comparison,
  fileType,
  valueA,
  valueB,
  options,
  projects,
}) {
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [selectedProject, setSelectedProject] = useState("");

  const labelFor = (value) =>
    (options.find((it) => it.value === value) || {}).label || value;

  const handleSave = async () => {
    setSaveMessage("");
    const labelA = labelFor(valueA);
    const labelB = labelFor(valueB);
    const title = `Comparison: ${labelA} vs ${labelB}`;
    const description = `Compared ${labelA} and ${labelB}`;
    const form = new FormData();
    form.append("content", comparison);
    form.append("title", title);
    form.append("description", description);
    form.append("file_type", fileType);
    if (selectedProject) form.append("project_id", String(selectedProject));
    try {
      setSaving(true);
      const resp = await apiFetch("/api/save-comparison/", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${resp.status}`);
      }
      const d = await resp.json();
      setSaveMessage(d.message || "Saved");
    } catch (err) {
      setSaveMessage(String(err));
    } finally {
      setSaving(false);
    }
  };

  if (comparison === "") return null;

  return (
    <div className="compare-layout-column compare-layout-column--results">
      <div className="compare-panel-card">
        <div className="compare-result-header">
          <h2 className="compare-panel-title">Comparison result</h2>
          <div className="compare-result-actions">
            <button
              type="button"
              className="project-tab"
              onClick={() => {
                if (navigator.clipboard && comparison) {
                  navigator.clipboard.writeText(comparison).catch(() => {});
                }
              }}
            >
              Copy
            </button>
            <button
              type="button"
              className="project-tab"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>

        {projects.length > 0 && (
          <div className="compare-save-project-row">
            <label className="compare-save-project-label">
              Save to project:
            </label>
            <select
              className="form-input"
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
            >
              <option value="">Select a project</option>
              {projects.map((pr) => (
                <option key={pr.id} value={pr.id}>
                  {pr.projectname}
                </option>
              ))}
            </select>
          </div>
        )}
        {saveMessage && (
          <div className="compare-save-message">{saveMessage}</div>
        )}
        <div className="comparison-output">
          <ReactMarkdown>{comparison}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
