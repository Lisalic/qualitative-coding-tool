import IntegrateAiPanel from "./IntegrateAiPanel";
import IntegrateComparisonPanel from "./IntegrateComparisonPanel";
import IntegrateSourceDetail from "./IntegrateSourceDetail";
import EditorRail from "../editor-shell/EditorRail";
import RailTabs from "../primitives/RailTabs";
import Panel from "../shell/Panel";

/**
 * Right rail of the integrate workspace: a tabbed panel -- the active
 * source code's full text ("Code"), a Compare Codebook report of the
 * sources ("Comparison"), or the AI merge assistant ("AI Assist") -- same
 * shape as `CodebookReferenceRail`. Compare-then-integrate is the
 * intended workflow, so the comparison sits beside the draft rather than
 * on another page, and can be handed to the assistant as guidance.
 *
 * The AI tab stays mounted while hidden, so a run in flight keeps its
 * progress and the typed prompt/model survive a tab switch.
 */
export default function IntegrateRail({
  tab,
  onTabChange,
  active,
  codebookName,
  codebooks,
  existingCodes,
  onProposals,
  comparisons,
  comparisonsLoading,
  selectedComparison,
  onSelectComparison,
  useComparisonInAi,
  onUseComparisonInAiChange,
  disabled,
}) {
  const comparisonCount = comparisons.length;
  const tabs = [
    { value: "code", label: "Code" },
    { value: "comparison", label: "Comparison", count: comparisonCount },
    { value: "ai", label: "AI Assist" },
  ];

  return (
    <EditorRail scroll={false}>
      <Panel
        title={<RailTabs tabs={tabs} activeTab={tab} onChange={onTabChange} />}
        className="min-h-0 flex-1"
      >
        {tab === "comparison" ? (
          <IntegrateComparisonPanel
            comparisons={comparisons}
            loading={comparisonsLoading}
            selected={selectedComparison}
            onSelect={onSelectComparison}
            useInAi={useComparisonInAi}
            onUseInAiChange={onUseComparisonInAiChange}
            firstSourceRef={codebooks[0]}
            disabled={disabled}
          />
        ) : tab === "code" ? (
          <IntegrateSourceDetail active={active} codebookName={codebookName} />
        ) : null}
        <div className={tab === "ai" ? "" : "hidden"}>
          <IntegrateAiPanel
            codebooks={codebooks}
            existingCodes={existingCodes}
            onProposals={onProposals}
            comparison={useComparisonInAi ? comparisons.find((c) => c.ref === selectedComparison) || null : null}
            disabled={disabled}
          />
        </div>
      </Panel>
    </EditorRail>
  );
}
