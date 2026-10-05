import { Link } from "react-router-dom";
import { btn, btnDanger } from "../../lib/uiClasses";

/**
 * A project file row's actions. View and History are real links (they
 * open in a new tab like any link); Rename and Delete act in place.
 */
export default function FileRowActions({
  file,
  viewTo,
  historyTo,
  onRename,
  onDelete,
  disabled = false,
}) {
  const name = file?.display_name || file?.filename || "file";
  return (
    <div className="flex shrink-0 flex-wrap gap-2">
      {viewTo ? (
        <Link to={viewTo} className={`${btn} hover:text-ink`} aria-label={`View ${name}`}>
          View
        </Link>
      ) : null}
      {historyTo ? (
        <Link to={historyTo} className={`${btn} hover:text-ink`} aria-label={`History of ${name}`}>
          History
        </Link>
      ) : null}
      <button
        type="button"
        className={btn}
        onClick={() => onRename?.(file)}
        disabled={disabled}
        aria-label={`Rename ${name}`}
      >
        Rename
      </button>
      <button
        type="button"
        className={btnDanger}
        onClick={() => onDelete?.(file)}
        disabled={disabled}
        aria-label={`Delete ${name}`}
      >
        Delete
      </button>
    </div>
  );
}
