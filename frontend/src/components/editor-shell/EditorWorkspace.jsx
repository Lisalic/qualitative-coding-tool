import PageShell from "../shell/PageShell";

/**
 * Step 2 of every editor: the 3-pane workspace frame. Lifted from
 * `CodingWorkspaceSection.jsx`, the shape `documentation/style-guide.md`
 * already named as the reference the filter and codebook editors were
 * meant to match -- now they actually do, down to the grid's column
 * widths (previously three different `minmax()` ranges with no stated
 * reason). `EDITOR_GRID_CLASSES` is exported so the coding workspace,
 * which branches into a Text View that isn't a 3-pane grid at all, can
 * still share the exact same grid string rather than drifting again.
 *
 * `overflow-y-auto lg:overflow-hidden`: below `lg` the three panes stack
 * to one column inside `PageShell`'s `scroll="fill"` body, which
 * otherwise clips panes two and three off the bottom of a narrow
 * viewport with no way to reach them.
 *
 * `emphasis` picks which column gets the flexible `1fr` share. Filter and
 * Apply Codebook both decide something per row *in the center pane*, so
 * `"reader"` (the default) keeps it wide and pins both side columns to a
 * narrow fixed range. The codebook editor's center pane is read-only
 * reference text -- the artifact actually being built (the draft code
 * tree) lives in the rail -- so `"builder"` swaps which column is `1fr`
 * instead, without touching `EDITOR_GRID_CLASSES` itself: that constant
 * stays the single source of truth for the two editors that share it.
 */
const EDITOR_GRID_BASE =
  "grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto lg:overflow-hidden lg:grid-rows-1";
const EDITOR_GRID_COLUMNS = {
  reader: "lg:grid-cols-[minmax(220px,280px)_minmax(0,1fr)_minmax(240px,300px)]",
  builder: "lg:grid-cols-[minmax(200px,240px)_minmax(0,1fr)_minmax(320px,400px)]",
};

export const EDITOR_GRID_CLASSES = `${EDITOR_GRID_BASE} ${EDITOR_GRID_COLUMNS.reader}`;

export default function EditorWorkspace({
  title,
  subtitle,
  actions,
  banners,
  list,
  reader,
  rail,
  actionBar,
  emphasis = "reader",
}) {
  const gridClasses = `${EDITOR_GRID_BASE} ${EDITOR_GRID_COLUMNS[emphasis]}`;
  return (
    <PageShell title={title} subtitle={subtitle} actions={actions} width="full" scroll="fill" bodyClassName="gap-3">
      {banners}
      <div className={gridClasses}>
        {list}
        {reader}
        {rail}
      </div>
      {actionBar}
    </PageShell>
  );
}
