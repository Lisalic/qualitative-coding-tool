import { useState } from "react";
import { btn, btnPrimary } from "../../lib/uiClasses";
import IntegrateSourcePicker from "./IntegrateSourcePicker";

/**
 * Lets the researcher change which codebooks are being merged without
 * leaving the workspace; the caller moves the draft to the new selection's
 * `integrateDraftStorageKey`. This edits a local copy of the selection so
 * Cancel is a true no-op, and only calls `onChange` on Save.
 */
export default function IntegrateChangeSourcesModal({ codebooks, selected, onChange, onClose }) {
  const [pending, setPending] = useState(selected);

  const togglePending = (ref) => {
    setPending((prev) => (prev.includes(ref) ? prev.filter((r) => r !== ref) : [...prev, ref]));
  };

  const canSave = pending.length >= 2;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80 p-4" onClick={onClose}>
      <div
        className="flex max-h-[90vh] w-full max-w-[560px] flex-col border-2 border-paper bg-ink text-paper shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-paper px-5 py-3.5">
          <h2 className="text-sm font-semibold uppercase tracking-wide">Change source codebooks</h2>
          <button
            type="button"
            className="flex h-7 w-7 items-center justify-center text-lg transition-colors hover:bg-white/10"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <IntegrateSourcePicker codebooks={codebooks} selected={pending} onToggle={togglePending} loading={false} />
          {pending.length < 2 && (
            <p className="mt-2 text-sm text-paper/50">Select 2 or more codebooks to continue.</p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-paper px-5 py-3.5">
          <button type="button" className={btn} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={btnPrimary}
            disabled={!canSave}
            onClick={() => onChange(pending)}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
