export default function FileRowActions({
  file,
  onView,
  onRename,
  onDelete,
  disabled = false,
}) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <button className="project-tab" onClick={() => onView?.(file)} disabled={disabled}>
        View
      </button>
      <button className="project-tab" onClick={() => onRename?.(file)} disabled={disabled}>
        Edit
      </button>
      <button className="project-tab" onClick={() => onDelete?.(file)} disabled={disabled}>
        Delete
      </button>
    </div>
  );
}
