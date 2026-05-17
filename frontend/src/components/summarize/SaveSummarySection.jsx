export default function SaveSummarySection({
  projects,
  selectedProject,
  onProjectChange,
  saveName,
  onSaveNameChange,
  saveDescription,
  onSaveDescriptionChange,
  onSave,
  saving,
  saveSuccess,
  saveError,
}) {
  return (
    <div
      style={{
        marginTop: 12,
        padding: 12,
        background: "#000000",
        border: "2px solid #ffffff",
        borderRadius: 8,
        boxShadow: "0 4px 6px rgba(255, 255, 255, 0.1)",
      }}
    >
      <h4 style={{ margin: "0 0 8px 0" }}>Save Summary</h4>
      <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <label style={{ display: "block", marginBottom: 6 }}>Project</label>
          <select
            className="form-input"
            value={selectedProject}
            onChange={(event) => onProjectChange(event.target.value)}
          >
            <option value="">-- select project --</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.projectname}
              </option>
            ))}
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={{ display: "block", marginBottom: 6 }}>Name</label>
          <input
            className="form-input"
            value={saveName}
            onChange={(event) => onSaveNameChange(event.target.value)}
            placeholder="Summary name"
          />
        </div>
      </div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: "block", marginBottom: 6 }}>Description (optional)</label>
        <input
          className="form-input"
          value={saveDescription}
          onChange={(event) => onSaveDescriptionChange(event.target.value)}
          placeholder="Short description"
        />
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="project-tab" onClick={onSave} disabled={saving}>
          {saving ? "Saving..." : "Save Summary to Project"}
        </button>
        {saveSuccess && <div style={{ color: "#4CAF50", alignSelf: "center" }}>{saveSuccess}</div>}
        {saveError && <div style={{ color: "#ff6b6b", alignSelf: "center" }}>{saveError}</div>}
      </div>
    </div>
  );
}
