import FilterAiPanel from "./FilterAiPanel";
import EditorRail from "../editor-shell/EditorRail";
import Panel from "../shell/Panel";

/**
 * Right rail of the filter workspace: the AI assist tool. It is the
 * rail's only mode, so the Panel takes a plain title rather than a
 * one-tab tab strip (a tablist with a single, inert tab). Naming the artifact this session will become
 * happens up front, in the setup step (`FilterSetupStep`) -- not here,
 * matching Apply Codebook's shape, where the artifact's name is likewise
 * settled before its workspace ever opens.
 */
export default function FilterDecisionsRail({ database, included, excluded, onAcceptAi, disabled }) {
  return (
    <EditorRail scroll={false}>
      <Panel
        title="AI Assist"
        className="min-h-0 flex-1"
      >
        <FilterAiPanel
          database={database}
          included={included}
          excluded={excluded}
          onAccept={onAcceptAi}
          disabled={disabled}
        />
      </Panel>
    </EditorRail>
  );
}
