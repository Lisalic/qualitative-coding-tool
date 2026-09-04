/**
 * The one page frame. Every route renders exactly one of these.
 *
 * Replaces the old ToolPage/ToolPageShell/ToolPageBody/ToolPanelHost/
 * ViewPageShell quartet-plus-one, which stacked a centered max-width
 * container inside App's padding inside a `border-2` panel -- three frames
 * before any content, and two competing max-widths (4xl vs 6xl) split
 * arbitrarily between pages.
 *
 * Structure is a fixed-height flex column: a toolbar row that never scrolls,
 * above a body that does. Because App.jsx now constrains the viewport, this
 * needs no `sticky` and no `calc()` -- a `scroll="fill"` child can simply ask
 * for `h-full` and get the real remaining height.
 *
 * The toolbar holds the page's ONLY title. Workspace sections used to render
 * a second centered heading directly beneath the shell's own, which together
 * with the artifact picker box cost ~200px before content began.
 *
 * width:
 *   "full"  -- no cap. Dense pages: coding workspace, data tables, editors.
 *   "wide"  -- capped at 1600px. Reading-plus-structure pages.
 *   "prose" -- capped at 3xl. Forms and long-form text, where a readable
 *              measure matters more than filling the screen.
 * scroll:
 *   "page"  -- the body scrolls as one column. The common case.
 *   "fill"  -- the body is a fixed-height box and the CHILD owns scrolling.
 *              Use with width="full" for viewport-height workspaces.
 */

const WIDTHS = {
  full: "w-full",
  wide: "mx-auto w-full max-w-[1600px]",
  prose: "mx-auto w-full max-w-3xl",
};

export default function PageShell({
  title,
  subtitle,
  actions,
  children,
  width = "full",
  scroll = "page",
  bodyClassName = "",
}) {
  const isFill = scroll === "fill";
  const widthClass = WIDTHS[width] || WIDTHS.full;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {title || actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-2">
          {title ? (
            <div className="flex min-w-0 items-baseline gap-2">
              <h1 className="truncate text-base font-semibold">{title}</h1>
              {subtitle ? (
                <span className="truncate text-sm text-paper/60">{subtitle}</span>
              ) : null}
            </div>
          ) : null}
          {actions ? (
            <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>
          ) : null}
        </div>
      ) : null}

      <div
        className={
          isFill
            ? "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-3"
            : // `overflow-auto`, not just -y: the document itself cannot
              // scroll, so content that refuses to shrink below the viewport
              // has to be reachable here or it is simply lost.
              "min-h-0 min-w-0 flex-1 overflow-auto px-4 py-4"
        }
      >
        <div
          className={`${widthClass} ${
            isFill ? "flex min-h-0 min-w-0 flex-1 flex-col" : ""
          } ${bodyClassName}`}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
