export default function CodingSavePanel({
  isTableEditMode,
  tableEditName,
  onTableEditNameChange,
  onSaveDuplicate,
  onSaveOverwrite,
  saveStatus,
}) {
  if (!isTableEditMode) return null;

  return (
    <div
      style={{
        marginTop: "16px",
        border: "1px solid rgba(255, 255, 255, 0.3)",
        borderRadius: "8px",
        padding: "12px",
      }}
    >
      <div className="form__group" style={{ marginBottom: "12px" }}>
        <label className="form__label">Name</label>
        <input
          type="text"
          className="form__input"
          value={tableEditName}
          onChange={(event) => onTableEditNameChange(event.target.value)}
          disabled={saveStatus === "saving"}
        />
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: "8px",
        }}
      >
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onSaveDuplicate}
          disabled={saveStatus === "saving"}
        >
          Save and Duplicate
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onSaveOverwrite}
          disabled={saveStatus === "saving"}
        >
          Save and Overwrite
        </button>
      </div>
    </div>
  );
}
