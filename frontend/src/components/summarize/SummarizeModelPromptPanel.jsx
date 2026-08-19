import AiModelFormGroup from "../models/AiModelFormGroup";
import PromptEditorSection from "./PromptEditorSection";

const selectClasses =
  "w-full border border-paper bg-white/5 px-3 py-2.5 text-paper focus:outline-none focus:ring-2 focus:ring-paper";
const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

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
    <div className="flex flex-1">
      <div className="w-full border-2 border-paper p-5">
        <div className="mb-3">
          <h2 className="text-lg font-semibold">Model &amp; instructions</h2>
        </div>

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
      </div>
    </div>
  );
}
