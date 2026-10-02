import IntegrateAiPanel from "./IntegrateAiPanel";
import IntegrateComparisonPanel from "./IntegrateComparisonPanel";
import IntegrateSourceDetail from "./IntegrateSourceDetail";
import EditorRail from "../editor-shell/EditorRail";
import RailTabs from "../primitives/RailTabs";
import Panel from "../shell/Panel";

/**
 * Right rail of the integrate workspace: a tabbed reference panel -- the
 * active source code's full text ("Code") or a Compare Codebook report of
 * the sources ("Comparison") -- with the AI merge assistant pinned at the
 * foot, same shape as `CodebookReferenceRail`. Compare-then-integrate is
 * the intended workflow, so the comparison sits beside the draft rather
 * than on another page, and can be handed to the assistant as guidance.
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
        ) : (
          <IntegrateSourceDetail active={active} codebookName={codebookName} />
        )}
      </Panel>

      <div className="shrink-0">
        <IntegrateAiPanel
          codebooks={codebooks}
          existingCodes={existingCodes}
          onProposals={onProposals}
          comparison={useComparisonInAi ? comparisons.find((c) => c.ref === selectedComparison) || null : null}
          disabled={disabled}
        />
      </div>
    </EditorRail>
  );
}
