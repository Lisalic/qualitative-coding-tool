import AiModelFormGroup from "../models/AiModelFormGroup";
import PromptEditorSection from "./PromptEditorSection";
import Panel from "../shell/Panel";
import Dropdown from "../primitives/Dropdown";
import { input, select } from "../../lib/uiClasses";
import { toProjectOptions } from "../../lib/projectOptions";

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
  errors = {},
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
        {errors.name ? <p className="text-xs text-error">{errors.name}</p> : null}
      </div>

      <div className="mb-3 flex flex-col gap-1.5">
        <label htmlFor="summarize-project" className="text-sm">
          Project
        </label>
        <Dropdown
          id="summarize-project"
          value={selectedProject}
          options={toProjectOptions(projects)}
          onChange={onProjectChange}
          placeholder="Select a project"
          triggerClassName={selectClasses}
          listLabel="Project"
          searchPlaceholder="Search projects…"
          emptyMessage="No projects match that search."
          noOptionsMessage="No projects yet. Create one from Home first."
        />
        {errors.project ? <p className="text-xs text-error">{errors.project}</p> : null}
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
      {errors.model ? <p className="-mt-2 mb-3 text-xs text-error">{errors.model}</p> : null}

      <PromptEditorSection
        value={additionalPrompt}
        onChange={onAdditionalPromptChange}
        onLoadExample={onAdditionalPromptChange}
      />
    </Panel>
  );
}
