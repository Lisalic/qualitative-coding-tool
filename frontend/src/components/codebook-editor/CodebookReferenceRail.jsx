import CodebookAiPanel from "./CodebookAiPanel";
import CodebookReaderPane from "./CodebookReaderPane";
import EditorRail from "../editor-shell/EditorRail";
import RailTabs from "../primitives/RailTabs";
import Panel from "../shell/Panel";

const TABS = [
  { value: "row", label: "Row" },
  { value: "ai", label: "AI Assist" },
];

/**
 * Right rail of the codebook workspace: a tabbed panel -- the active
 * row's full text ("Row", for reading themes) or the AI codebook
 * generator ("AI Assist") -- the same shape as the coding workspace's
 * rail, where AI Coding is likewise a mode of the panel rather than a
 * disclosure pinned at its foot.
 *
 * The AI tab stays mounted while hidden, so a run in flight keeps its
 * progress and the typed prompt/model survive switching back to read a
 * row.
 *
 * The tab is controlled by the editor so that picking a row (click or
 * j/k) brings the Row tab forward -- otherwise selecting a row while the
 * AI tab is open appears to do nothing.
 */
export default function CodebookReferenceRail({
  tab,
  onTabChange,
  activeRow,
  memo,
  onSaveMemo,
  database,
  existingCodes,
  onProposals,
  disabled,
}) {
  const setTab = onTabChange;

  return (
    <EditorRail scroll={false}>
      <Panel
        title={<RailTabs tabs={TABS} activeTab={tab} onChange={setTab} />}
        className="min-h-0 flex-1"
      >
        <div className={tab === "row" ? "" : "hidden"}>
          <CodebookReaderPane activeRow={activeRow} memo={memo} onSaveMemo={onSaveMemo} />
        </div>
        <div className={tab === "ai" ? "" : "hidden"}>
          <CodebookAiPanel
            database={database}
            existingCodes={existingCodes}
            onProposals={onProposals}
            disabled={disabled}
          />
        </div>
      </Panel>
    </EditorRail>
  );
}
