import { useState } from "react";

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";
const btnSmall =
  "border border-paper px-3 py-2 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";
const btnPrimary =
  "border-2 border-paper px-3 py-2 text-sm font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

/**
 * Forks a whole coding artifact -- its codebook snapshot, its own rows,
 * and their coding (see `coding_service.duplicate_coding`) -- into a
 * brand-new file under a new name. Unlike the old blob-backed "Save and
 * Duplicate", this always duplicates the artifact as currently saved
 * (not an in-progress edit draft): the copy is a full server-side clone
 * of everything the artifact owns, not a small JSON payload of edits.
 */
export default function CodingDuplicateControl({ defaultName, onDuplicate, disabled }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [status, setStatus] = useState({ state: "idle", message: "" });

  const startOpen = () => {
    setName(defaultName ? `${defaultName} (copy)` : "");
    setStatus({ state: "idle", message: "" });
    setOpen(true);
  };

  const cancel = () => {
    setOpen(false);
    setStatus({ state: "idle", message: "" });
  };

  const confirm = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setStatus({ state: "error", message: "Name is required." });
      return;
    }
    setStatus({ state: "saving", message: "" });
    const result = await onDuplicate(trimmed);
    if (!result?.ok) {
      setStatus({ state: "error", message: result?.error || "Failed to duplicate." });
      return;
    }
    setOpen(false);
    setStatus({ state: "idle", message: "" });
  };

  if (!open) {
    return (
      <button type="button" className={btnSmall} onClick={startOpen} disabled={disabled}>
        Duplicate
      </button>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="text"
        className={inputClasses}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="New coding name"
        disabled={status.state === "saving"}
      />
      <button
        type="button"
        className={btnPrimary}
        onClick={confirm}
        disabled={status.state === "saving"}
      >
        {status.state === "saving" ? "Duplicating..." : "Confirm"}
      </button>
      <button type="button" className={btnSmall} onClick={cancel} disabled={status.state === "saving"}>
        Cancel
      </button>
      {status.state === "error" && status.message && (
        <span className="text-sm text-error">{status.message}</span>
      )}
    </div>
  );
}
