import { btn, btnPrimary } from "../../lib/uiClasses";

/**
 * The pinned action bar at the foot of every editor workspace: a summary
 * on the left, a secondary action (Clear/Discard) then the primary
 * action pushed right. Lifted from the coding workspace's Save/Discard
 * bar, which the filter and codebook editors' own footer strips (each
 * with their own border and spacing) now match instead of drifting.
 *
 * `emphasized` renders the coding workspace's pinned `border-t-2`,
 * centered treatment -- appropriate when the bar only appears once a
 * session is actually dirty. Filter/Codebook's bar is always visible, so
 * it keeps the plainer bordered strip instead.
 */
export default function EditorActionBar({
  summary,
  secondaryLabel,
  onSecondary,
  secondaryDisabled,
  primaryLabel,
  primaryLoadingLabel,
  onPrimary,
  primaryDisabled,
  primaryLoading,
  errorMessage,
  emphasized = false,
}) {
  const toneClasses = emphasized
    ? "justify-center border-t-2 border-paper bg-ink"
    : "border border-line bg-surface";

  const buttons = (
    <>
      {secondaryLabel ? (
        <button
          type="button"
          className={emphasized ? `${btn} text-paper/70` : btn}
          onClick={onSecondary}
          disabled={secondaryDisabled}
        >
          {secondaryLabel}
        </button>
      ) : null}
      <button
        type="button"
        className={emphasized ? `${btnPrimary} bg-paper text-ink hover:bg-ink hover:text-paper` : btnPrimary}
        onClick={onPrimary}
        disabled={primaryDisabled}
      >
        {primaryLoading ? primaryLoadingLabel : primaryLabel}
      </button>
    </>
  );

  return (
    <div className={`flex shrink-0 flex-wrap items-center gap-3 px-4 py-2 ${toneClasses}`}>
      <span className="text-sm">{summary}</span>
      {errorMessage ? <span className="text-sm text-error">{errorMessage}</span> : null}
      <div className={`flex items-center gap-2 ${emphasized ? "" : "ml-auto"}`}>{buttons}</div>
    </div>
  );
}
