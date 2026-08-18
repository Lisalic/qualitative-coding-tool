const tabBtn =
  "border border-paper px-3.5 py-2 text-sm font-medium transition-colors hover:bg-paper hover:text-ink disabled:opacity-50";

export default function FileRowActions({
  file,
  onView,
  onRename,
  onDelete,
  disabled = false,
}) {
  return (
    <div className="flex shrink-0 gap-2">
      <button type="button" className={tabBtn} onClick={() => onView?.(file)} disabled={disabled}>
        View
      </button>
      <button type="button" className={tabBtn} onClick={() => onRename?.(file)} disabled={disabled}>
        Edit
      </button>
      <button type="button" className={tabBtn} onClick={() => onDelete?.(file)} disabled={disabled}>
        Delete
      </button>
    </div>
  );
}
