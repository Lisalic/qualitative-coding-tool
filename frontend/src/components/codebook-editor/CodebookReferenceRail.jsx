import CodebookAiPanel from "./CodebookAiPanel";
import CodebookReaderPane from "./CodebookReaderPane";
import EditorRail from "../editor-shell/EditorRail";

/**
 * Right rail of the codebook workspace: the active row's full text (for
 * reading themes) plus the AI codebook generator pinned at the foot --
 * the same shape as the coding workspace's rail (codebook sidebar +
 * recode bar), just with the two roles swapped, since here the reader is
 * reference material rather than the artifact being built.
 */
export default function CodebookReferenceRail({ activeRow, memo, onSaveMemo, database, existingCodes, onProposals, disabled }) {
  return (
    <EditorRail scroll={false}>
      <CodebookReaderPane activeRow={activeRow} memo={memo} onSaveMemo={onSaveMemo} />

      <div className="shrink-0">
        <CodebookAiPanel
          database={database}
          existingCodes={existingCodes}
          onProposals={onProposals}
          disabled={disabled}
        />
      </div>
    </EditorRail>
  );
}
