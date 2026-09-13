import CodeLegend from "../coding-table/CodeLegend";
import IntegrateProposalTray from "./IntegrateProposalTray";
import Panel from "../shell/Panel";
import EditorRail from "../editor-shell/EditorRail";
import { getCodeColor } from "../../lib/codingUtils";

const noop = () => {};

/**
 * Center pane of the integrate workspace -- the merged codebook actually
 * being built. Same shape as `CodebookBuilderPane`: any proposals
 * awaiting review sit above the draft, capped at 40% height, and the
 * draft itself is edited through `CodeLegend` -- the one code editor
 * this app has, not a second one built for merges.
 */
export default function IntegrateBuilderPane({ editor, codebookNames, disabled }) {
  return (
    <EditorRail scroll={false}>
      {editor.proposals.length > 0 && (
        <div className="flex max-h-[40%] min-h-0 shrink-0 flex-col">
          <IntegrateProposalTray
            proposals={editor.proposals}
            codebookNames={codebookNames}
            onAccept={editor.accept}
            onDismiss={editor.dismiss}
            onAcceptAll={editor.acceptEvery}
            onDismissAll={editor.dismissEvery}
            disabled={disabled}
          />
        </div>
      )}

      <Panel title={`Integrated codes (${editor.counts.draft})`} padded={false} className="min-h-0 flex-1">
        <CodeLegend
          codebookTree={editor.draft}
          isEditMode
          draftTree={editor.draft}
          onDraftTreeChange={editor.updateDraft}
          disabled={disabled}
          selectedFilterCodes={[]}
          onCodeToggle={noop}
          getCodeColor={getCodeColor}
          showDetails
          isAiAccepted={editor.isAiAccepted}
        />
      </Panel>
    </EditorRail>
  );
}
