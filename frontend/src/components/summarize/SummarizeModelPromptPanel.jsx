import AiModelFormGroup from "../models/AiModelFormGroup";
import PromptEditorSection from "./PromptEditorSection";
import Panel from "../shell/Panel";
import { input, select } from "../../lib/uiClasses";

const selectClasses = `w-full ${select}`;
const inputClasses = input;

export default function SummarizeModelPromptPanel({
  model,
  onModelChange,
  name,
  onNameChange,
  projects,
  selectedProject,
  onProjectChange,
  additionalPrompt,
  onAdditionalPromptChange,
}) {
  return (
    <Panel title="Model & instructions" className="flex-1" scroll={false}>
      <div className="mb-3 flex flex-col gap-1.5">
        <label htmlFor="summarize-name" className="text-sm">
          Name
        </label>
        <input
          id="summarize-name"
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Enter a name for the summary"
          className={inputClasses}
        />
      </div>

      <div className="mb-3 flex flex-col gap-1.5">
        <label htmlFor="summarize-project" className="text-sm">
          Project
        </label>
        <select
          id="summarize-project"
          value={selectedProject}
          onChange={(e) => onProjectChange(e.target.value)}
          className={selectClasses}
        >
          {!selectedProject && (
            <option value="" disabled>
              Select a project
            </option>
          )}
          {(projects || []).map((project) => (
            <option key={project.id} value={String(project.id)}>
              {project.projectname}
            </option>
          ))}
        </select>
      </div>

      <AiModelFormGroup
        className="mb-3 flex flex-col gap-1.5"
        label="Model"
        labelClassName="mb-1 block text-sm"
        model={model}
        onModelChange={onModelChange}
        selectPlaceholder="compare"
        selectClassName={selectClasses}
      />

      <PromptEditorSection
        value={additionalPrompt}
        onChange={onAdditionalPromptChange}
        onLoadExample={onAdditionalPromptChange}
      />
    </Panel>
  );
}
