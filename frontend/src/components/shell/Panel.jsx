/**
 * The one bordered region primitive.
 *
 * Codifies the pattern VersionHistoryPanel already used well: a single 1px
 * border, a header strip separated by a `border-b`, and one internal scroll
 * container. Replaces the `border-2 border-paper p-6` box that had been
 * applied uniformly at 18 sites -- whether it wrapped a two-field form or a
 * viewport-height workspace -- and which nested up to four borders deep
 * around a single codebook row.
 *
 * The one-border rule: a Panel never directly contains another Panel, and
 * content that already draws its own border (a table, CodeLegend) goes in a
 * `padded={false}` Panel rather than gaining an extra frame. `border-2` is
 * now reserved for modals and primary buttons only.
 *
 * padded={false} drops body padding so a table's own cell borders can meet
 * the region edge. scroll={false} hands scrolling to a child instead, which
 * is what a Panel containing its own split layout wants.
 */
export default function Panel({
  title,
  actions,
  children,
  padded = true,
  scroll = true,
  className = "",
  bodyClassName = "",
}) {
  const hasHeader = Boolean(title || actions);

  return (
    <section
      className={`flex min-h-0 min-w-0 flex-col border border-line bg-surface ${className}`}
    >
      {hasHeader ? (
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-3 py-2">
          {title ? (
            <h2 className="min-w-0 truncate text-sm font-semibold uppercase tracking-wide">
              {title}
            </h2>
          ) : (
            <span />
          )}
          {actions ? (
            <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
          ) : null}
        </header>
      ) : null}

      <div
        className={`min-h-0 min-w-0 flex-1 ${scroll ? "overflow-auto" : ""} ${
          padded ? "p-3" : ""
        } ${bodyClassName}`}
      >
        {children}
      </div>
    </section>
  );
}
