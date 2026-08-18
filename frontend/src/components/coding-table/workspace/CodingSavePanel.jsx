const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

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
    <div className="mt-4 border border-paper/30 p-3">
      <div className="mb-3 flex flex-col gap-1.5">
        <label className="text-sm">Name</label>
        <input
          type="text"
          className={inputClasses}
          value={tableEditName}
          onChange={(event) => onTableEditNameChange(event.target.value)}
          disabled={saveStatus === "saving"}
        />
      </div>

      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
          onClick={onSaveDuplicate}
          disabled={saveStatus === "saving"}
        >
          Save and Duplicate
        </button>
        <button
          type="button"
          className="border-2 border-paper px-4 py-2 text-sm font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
          onClick={onSaveOverwrite}
          disabled={saveStatus === "saving"}
        >
          Save and Overwrite
        </button>
      </div>
    </div>
  );
}
