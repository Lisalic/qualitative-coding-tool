/**
 * Progress indicator for a background job that reports interim
 * `{current, total, label}` updates (see `backend/app/jobs/progress.py`
 * and `postFormAndPoll`'s `onProgress` callback in `../../api`).
 *
 * Renders nothing until there's more than one step to show progress
 * across -- a job that completes in a single LLM call has no meaningful
 * midpoint to report, so the caller's existing "Processing..." button
 * state already covers it.
 */
export default function ProgressBar({ current = 0, total = 0, label = "batches" }) {
  if (!total || total <= 1) return null;

  const clampedCurrent = Math.min(Math.max(current, 0), total);
  const percent = Math.round((clampedCurrent / total) * 100);

  return (
    <div className="mt-4" role="status">
      <div className="mb-1 flex justify-between text-xs text-paper/70">
        <span>
          {percent}% ({clampedCurrent}/{total} {label} processed)
        </span>
      </div>
      <div className="h-2 w-full border border-paper bg-white/5">
        <div
          className="h-full bg-paper transition-[width] duration-300 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
