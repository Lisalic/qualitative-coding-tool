import IntegrateAiPanel from "./IntegrateAiPanel";
import IntegrateSourceDetail from "./IntegrateSourceDetail";
import EditorRail from "../editor-shell/EditorRail";

/**
 * Right rail of the integrate workspace: the active source code's full
 * text (for reading what's being merged) plus the AI merge assistant
 * pinned at the foot -- same shape as `CodebookReferenceRail`.
 */
export default function IntegrateRail({ active, codebookName, codebooks, existingCodes, onProposals, disabled }) {
  return (
    <EditorRail scroll={false}>
      <IntegrateSourceDetail active={active} codebookName={codebookName} />

      <div className="shrink-0">
        <IntegrateAiPanel
          codebooks={codebooks}
          existingCodes={existingCodes}
          onProposals={onProposals}
          disabled={disabled}
        />
      </div>
    </EditorRail>
  );
}
