import FilterAiPanel from "./FilterAiPanel";
import EditorRail from "../editor-shell/EditorRail";

/**
 * Right rail of the filter workspace: the AI assist tool. Naming the
 * artifact this session will become happens up front, in the setup step
 * (`FilterSetupStep`) -- not here, matching Apply Codebook's shape,
 * where the artifact's name is likewise settled before its workspace
 * ever opens.
 */
export default function FilterDecisionsRail({ database, included, excluded, onAcceptAi, disabled }) {
  return (
    <EditorRail>
      <div className="shrink-0">
        <FilterAiPanel
          database={database}
          included={included}
          excluded={excluded}
          onAccept={onAcceptAi}
          disabled={disabled}
        />
      </div>
    </EditorRail>
  );
}
