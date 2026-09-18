import React from "react";

/**
 * A standalone "(?)" hover affordance -- for explaining a control's
 * behavior (e.g. what "Autofill with AI" does) rather than flagging
 * AI involvement, which is what `AiLabel`'s sparkle icon is for.
 *
 * Same CSS-only `group`/`group-hover` tooltip mechanics as `AiLabel`,
 * but `w-64 whitespace-normal` instead of `whitespace-nowrap` -- a help
 * sentence is longer than "AI-use involved" and would run off-screen
 * without wrapping.
 */
export default function HelpTip({ text, className = "" }) {
  return (
    <span className={`group relative inline-flex cursor-help items-center ${className}`}>
      <span
        aria-hidden="true"
        className="flex h-3.5 w-3.5 items-center justify-center rounded-full border border-current text-[10px] leading-none text-paper/70"
      >
        ?
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 translate-y-1 whitespace-normal border border-paper bg-ink px-2 py-1.5 text-xs text-paper opacity-0 transition-all group-hover:translate-y-0 group-hover:opacity-100"
      >
        {text}
      </span>
      <span className="sr-only">{text}</span>
    </span>
  );
}
