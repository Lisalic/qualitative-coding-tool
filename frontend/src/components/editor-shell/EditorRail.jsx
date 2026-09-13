/**
 * Right rail of every editor workspace: a flex column filling the grid
 * cell's full height.
 *
 * `scroll={false}` for a rail that contains its own `flex-1` `Panel`
 * (the draft codebook list, the coding sidebar) -- that Panel needs a
 * non-scrolling ancestor to compute a real bounded height and let ITS
 * OWN body scroll instead. `CodebookCodesRail` used to be an
 * `overflow-y-auto` column holding a `flex-1` scrolling `Panel`, which
 * left the child's height unbounded (a `flex-1` child never shrinks
 * below its content inside a scrolling flex parent) and forced a
 * `min-h-[200px]` floor to compensate -- the rail scrolled as a whole
 * instead of just the list inside it. The default (`scroll=true`) suits
 * a rail with no such child -- content-sized blocks stacked top to
 * bottom, like the filter editor's output fields plus AI assist panel --
 * where the rail itself is the only thing that could ever need to
 * scroll.
 */
export default function EditorRail({ children, scroll = true, className = "" }) {
  return (
    <div className={`flex h-full min-h-0 flex-col gap-3 ${scroll ? "overflow-y-auto" : ""} ${className}`}>
      {children}
    </div>
  );
}
