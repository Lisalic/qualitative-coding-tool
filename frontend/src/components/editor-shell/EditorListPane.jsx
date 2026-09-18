import Panel from "../shell/Panel";

/**
 * Left pane of every editor workspace, as a real `Panel` instead of the
 * near-identical `border border-line bg-surface` chrome `FilterRowList`,
 * `CodebookSourceReader` and `CodingDocumentList` each hand-rolled
 * separately (three copies of the same literal, one of them drifted onto
 * different border tokens along the way).
 *
 * `header` renders plain content above the scrolling list -- filter
 * controls, counts, a search box -- rather than Panel's own uppercase
 * title treatment, since these aren't a section label. `footer` goes
 * through Panel's own footer slot, since Prev/Page N/Next is identical
 * in shape across all three editors.
 */
export default function EditorListPane({
  header,
  footer,
  loading,
  loadingMessage = "Loading rows...",
  isEmpty,
  emptyMessage = "No rows match.",
  children,
}) {
  return (
    <Panel className="h-full" scroll={false} padded={false} bodyClassName="flex min-h-0 flex-1 flex-col" footer={footer}>
      {header ? (
        <div className="flex shrink-0 flex-col gap-2 border-b border-line p-2.5">{header}</div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-3 text-sm text-paper/60">{loadingMessage}</div>
        ) : isEmpty ? (
          <div className="p-3 text-sm text-paper/60">{emptyMessage}</div>
        ) : (
          children
        )}
      </div>
    </Panel>
  );
}
