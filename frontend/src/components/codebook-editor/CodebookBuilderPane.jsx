import CodeLegend from "../coding-table/CodeLegend";
import CodebookProposalTray from "./CodebookProposalTray";
import Panel from "../shell/Panel";
import EditorRail from "../editor-shell/EditorRail";
import { getCodeColor } from "../../lib/codingUtils";

const noop = () => {};

/**
 * Center pane of the codebook workspace -- the artifact actually being
 * built. Any proposals awaiting review sit above the draft (accepting one
 * mutates the draft directly, so the decision and its result stay on the
 * same axis), capped at 40% height so a long run of proposals scrolls
 * inside its own tray rather than pushing the draft list off screen.
 */
export default function CodebookBuilderPane({ editor, disabled }) {
  return (
    <EditorRail scroll={false}>
      {editor.proposals.length > 0 && (
        <div className="flex max-h-[40%] min-h-0 shrink-0 flex-col">
          <CodebookProposalTray
            proposals={editor.proposals}
            onAccept={editor.accept}
            onDismiss={editor.dismiss}
            onAcceptAll={editor.acceptEvery}
            onDismissAll={editor.dismissEvery}
            disabled={disabled}
          />
        </div>
      )}

      <Panel title={`Draft codes (${editor.counts.draft})`} padded={false} className="min-h-0 flex-1">
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
