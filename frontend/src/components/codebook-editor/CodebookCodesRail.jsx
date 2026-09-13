import CodeLegend from "../coding-table/CodeLegend";
import CodebookAiPanel from "./CodebookAiPanel";
import CodebookProposalTray from "./CodebookProposalTray";
import Panel from "../shell/Panel";
import { getCodeColor } from "../../lib/codingUtils";
import { input, select } from "../../lib/uiClasses";

const noop = () => {};

/**
 * Right rail: the fields that will name the artifact, the draft codebook
 * itself, proposals awaiting review, and the AI assist tool -- in the
 * order they matter while working (name once, codes constantly, a
 * proposal or an AI run occasionally).
 */
export default function CodebookCodesRail({
  mode,
  name,
  onNameChange,
  description,
  onDescriptionChange,
  selectedProject,
  onProjectChange,
  projectOptions,
  editor,
  database,
  disabled,
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto">
      {mode === "new" && (
        <Panel title="Output" scroll={false} className="shrink-0" bodyClassName="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="codebookEditorName" className="text-sm">
              Codebook name
            </label>
            <input
              id="codebookEditorName"
              type="text"
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="my-codebook"
              className={input}
              disabled={disabled}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="codebookEditorDescription" className="text-sm">
              Description (optional)
            </label>
            <textarea
              id="codebookEditorDescription"
              value={description}
              onChange={(e) => onDescriptionChange(e.target.value)}
              placeholder="Optional description"
              rows={2}
              className={`${input} w-full resize-y`}
              disabled={disabled}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="codebookEditorProject" className="text-sm">
              Project (optional)
            </label>
            <select
              id="codebookEditorProject"
              value={selectedProject || ""}
              onChange={(e) => onProjectChange(e.target.value)}
              className={select}
              disabled={disabled}
            >
              <option value="">No project</option>
              {(projectOptions || []).map((project) => (
                <option key={project.id} value={String(project.id)}>
                  {project.projectname}
                </option>
              ))}
            </select>
          </div>
        </Panel>
      )}

      <Panel title={`Draft codes (${editor.counts.draft})`} padded={false} className="min-h-[200px] flex-1">
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
        />
      </Panel>

      {editor.proposals.length > 0 && (
        <div className="shrink-0">
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

      <div className="shrink-0">
        <CodebookAiPanel
          database={database}
          existingCodes={editor.existingCodes}
          onProposals={editor.receiveProposals}
          disabled={disabled}
        />
      </div>
    </div>
  );
}
