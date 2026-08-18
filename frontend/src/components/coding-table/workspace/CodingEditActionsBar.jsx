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
    <div className="mb-4 flex justify-end gap-2">
      {isTableEditMode ? (
        <button
          type="button"
          className="border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
          onClick={onCancelEdit}
          disabled={saveStatus === "saving"}
        >
          Cancel Edit
        </button>
      ) : (
        <button
          type="button"
          className="border-2 border-paper px-4 py-2 text-sm font-semibold transition-colors hover:bg-paper hover:text-ink"
          onClick={onBeginEdit}
        >
          Edit
        </button>
      )}
    </div>
  );
}
