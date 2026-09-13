import FilterAiPanel from "./FilterAiPanel";
import Panel from "../shell/Panel";
import { input } from "../../lib/uiClasses";

/**
 * Right rail: the AI assist tool, and the fields that name the artifact
 * this session will become. Nothing here is decided per row -- that's
 * the list and reader panes' job -- this is what turns the accumulated
 * decisions into a file.
 */
export default function FilterDecisionsRail({
  database,
  decided,
  onAcceptAi,
  name,
  onNameChange,
  description,
  onDescriptionChange,
  selectedProject,
  onProjectChange,
  projectOptions,
  disabled,
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto">
      <Panel title="Output" scroll={false} bodyClassName="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="filterEditorName" className="text-sm">
            Filtered database name
          </label>
          <input
            id="filterEditorName"
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="my-filtered-db"
            className={input}
            disabled={disabled}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filterEditorDescription" className="text-sm">
            Description (optional)
          </label>
          <textarea
            id="filterEditorDescription"
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            placeholder="Optional description"
            rows={2}
            className={`${input} w-full resize-y`}
            disabled={disabled}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filterEditorProject" className="text-sm">
            Project (optional)
          </label>
          <select
            id="filterEditorProject"
            value={selectedProject || ""}
            onChange={(e) => onProjectChange(e.target.value)}
            className={input}
            disabled={disabled}
          >
            <option value="">No project</option>
            {(projectOptions || []).map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.projectname}
              </option>
            ))}
          </select>
        </div>
      </Panel>

      <FilterAiPanel database={database} decided={decided} onAccept={onAcceptAi} disabled={disabled} />
    </div>
  );
}
