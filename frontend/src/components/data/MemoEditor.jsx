import { useEffect, useState } from "react";

const btn =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

/**
 * The memo on one row: a free-text analytic note the researcher writes
 * while reading, distinct from `CodingEntry.notes`, which annotates a
 * single coded quote and only exists once a codebook has been applied.
 *
 * Explicit Save rather than autosave-on-blur: a memo is a considered
 * sentence, not a form field, and a half-typed thought silently persisting
 * when the modal is dismissed is worse than losing it. Clearing the text
 * and saving deletes the memo -- the same idempotent `PUT /api/memos/`
 * call, since there is exactly one memo per row.
 *
 * Remounted per row by the caller's `key`, so `draft` always starts from
 * the row actually on screen.
 *
 * `compact` drops the section heading and the rule above it, for the filter
 * editor's inline expander -- there the surrounding row already says which
 * item the note belongs to, so a "Memo" header would be pure repetition.
 */
export default function MemoEditor({ memo, onSave, compact = false }) {
  const [draft, setDraft] = useState(memo?.body || "");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    setDraft(memo?.body || "");
  }, [memo]);

  const dirty = draft.trim() !== (memo?.body || "").trim();

  const handleSave = async () => {
    setSaving(true);
    setStatus("");
    const result = await onSave(draft);
    setSaving(false);
    setStatus(
      result?.ok
        ? draft.trim()
          ? "Memo saved."
          : "Memo cleared."
        : `Error: ${result?.error || "Failed to save memo"}`,
    );
  };

  return (
    <div className={compact ? "pt-2" : "mt-6 border-t border-paper/20 pt-4"}>
      {!compact && <h3 className="mb-2 text-lg font-medium">Memo</h3>}
      <p className="mb-2 text-sm text-paper/60">
        Your notes on this row. Memos follow the row into any database filtered
        or coded from this one.
      </p>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="What did you notice about this row?"
        rows={4}
        className="w-full resize-y border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50"
        disabled={saving}
      />
      <div className="mt-2 flex items-center gap-2">
        <button type="button" className={btn} onClick={handleSave} disabled={saving || !dirty}>
          {saving ? "Saving..." : "Save Memo"}
        </button>
        {memo && (
          <button
            type="button"
            className={btn}
            onClick={() => setDraft("")}
            disabled={saving || draft === ""}
          >
            Clear
          </button>
        )}
        {memo?.updated_at && !dirty && (
          <span className="text-xs text-paper/50">
            Last edited {new Date(memo.updated_at).toLocaleString()}
          </span>
        )}
        {status && <span className="text-xs text-paper/70">{status}</span>}
      </div>
    </div>
  );
}
