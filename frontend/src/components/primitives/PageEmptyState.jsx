/**
 * The standard "nothing selected yet" placeholder.
 *
 * Every view page opens in this state, so it is the first thing a user sees
 * on half the app -- it gets ONE size and ONE style regardless of the page's
 * `width`, rather than stretching to whatever column happens to contain it.
 * `w-full max-w-2xl` plus a fixed `min-h` means the box is identical on a
 * full-bleed data page and a prose-width codebook page alike.
 *
 * Copy convention, so the app names things the same way everywhere:
 * "Select a <noun> to view <what you get>" -- a database, a codebook, a
 * coding, a summary, a comparison, an artifact. Never "file", never
 * "project file", never "coded data".
 */
const DEFAULT_CLASSES =
  "mx-auto flex min-h-32 w-full max-w-2xl items-center justify-center border border-line bg-surface px-6 py-8 text-center italic text-paper/70";

export default function PageEmptyState({ message, className = DEFAULT_CLASSES, style }) {
  return (
    <div className={className} style={style}>
      {message}
    </div>
  );
}
