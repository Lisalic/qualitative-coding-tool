import React from "react";
import AiModelFormGroup from "../models/AiModelFormGroup";
import AiLabel from "../forms/AiLabel";
import Panel from "../shell/Panel";
import Dropdown from "../primitives/Dropdown";
import { btnSm, input, select, textarea } from "../../lib/uiClasses";
import { toProjectOptions } from "../../lib/projectOptions";

const inputClasses = input;

export default function CompareModelPromptPanel({
  model,
  onModelChange,
  name,
  onNameChange,
  projects,
  selectedProject,
  onProjectChange,
  additionalPrompt,
  onAdditionalPromptChange,
  examplePromptText,
}) {
  return (
    <Panel title="Model & instructions" className="flex-1" scroll={false}>
      <div className="mb-3 flex flex-col gap-1.5">
        <label htmlFor="compare-name" className="text-sm">
          Name
        </label>
        <input
          id="compare-name"
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Enter a name for the comparison"
          className={inputClasses}
        />
      </div>

      <div className="mb-3 flex flex-col gap-1.5">
        <label htmlFor="compare-project" className="text-sm">
          Project
        </label>
        <Dropdown
          id="compare-project"
          value={selectedProject}
          options={toProjectOptions(projects)}
          onChange={onProjectChange}
          placeholder="Select a project"
          triggerClassName={`w-full ${select}`}
          listLabel="Project"
          searchPlaceholder="Search projects…"
          emptyMessage="No projects match that search."
        />
      </div>

      <AiModelFormGroup
        className="mb-3 flex flex-col gap-1.5"
        labelClassName="mb-1 block text-sm"
        label="Model"
        model={model}
        onModelChange={onModelChange}
        selectPlaceholder="compare"
        selectClassName={`w-full ${select}`}
      />

      <div className="mb-3">
        <div className="mb-1 flex items-center justify-between">
          <AiLabel text="Prompt (optional)" />
          <button
            className={btnSm}
            type="button"
            onClick={() => onAdditionalPromptChange(examplePromptText)}
          >
            Load Example Prompt
          </button>
        </div>
        <textarea
          value={additionalPrompt}
          onChange={(e) => onAdditionalPromptChange(e.target.value)}
          placeholder="Enter any specific instructions for the comparison..."
          className={`${textarea} min-h-[96px]`}
        />
      </div>
    </Panel>
  );
}
