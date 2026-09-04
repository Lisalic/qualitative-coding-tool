/**
 * Shared control class strings.
 *
 * These are deliberately plain constants rather than <Button>/<Input>
 * components: every call site already declared a local
 * `const btnClasses = "..."`, so adopting these is a one-for-one swap that
 * adds no wrapper layer (see CLAUDE.md's YAGNI rule). They exist because the
 * same button string had drifted into ~35 near-identical variants across ~26
 * files, which made any density change a 40-literal edit.
 *
 * The density baseline encoded here is tighter than the old one -- controls
 * sit at `py-1.5` rather than `py-2`/`py-3` -- so more content fits on the
 * dense pages this app has grown. Palette and hover-invert behaviour are
 * unchanged; see documentation/style-guide.md.
 */

/** Secondary action: 1px border, transparent, hover-invert. The default. */
export const btn =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

/** Primary action: 2px border + bold. One of the two remaining `border-2` uses. */
export const btnPrimary =
  "border-2 border-paper px-4 py-1.5 text-sm font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

/** Compact action, for toolbars and dense per-row controls. */
export const btnSm =
  "border border-paper px-2 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

/** Destructive action. Darkens rather than inverting, per the style guide. */
export const btnDanger =
  "border border-error bg-error/10 px-3 py-1.5 text-sm text-error transition-colors hover:bg-error hover:text-paper disabled:opacity-40";

/** Selected/active state for a bordered pill or tab. Append to `btn`/`btnSm`. */
export const btnActive = "bg-paper font-semibold text-ink";

export const input =
  "border border-paper bg-surface-raised px-2.5 py-1.5 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

export const inputSm =
  "border border-paper bg-surface-raised px-2 py-1 text-xs text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

/** Native <select>. Same box as `input`; kept separate so it can diverge. */
export const select = input;

export const textarea = `${input} w-full resize-y`;

/** Section label inside a Panel header, or a sub-heading within a Panel body. */
export const panelHeader = "text-sm font-semibold uppercase tracking-wide";

/** Small muted caption: timestamps, counts, helper text. */
export const meta = "text-xs text-paper/50";
