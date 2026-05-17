export default function CodingEditActionsBar({
  selectedCodedData,
  viewMode,
  isTableEditMode,
  onBeginEdit,
  onCancelEdit,
  saveStatus,
}) {
  if (!selectedCodedData || viewMode !== "table") return null;

  return (
    <div
      style={{
        marginBottom: "16px",
        display: "flex",
        justifyContent: "flex-end",
        gap: "8px",
      }}
    >
      {isTableEditMode ? (
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onCancelEdit}
          disabled={saveStatus === "saving"}
        >
          Cancel Edit
        </button>
      ) : (
        <button type="button" className="btn btn-primary" onClick={onBeginEdit}>
          Edit
        </button>
      )}
    </div>
  );
}
