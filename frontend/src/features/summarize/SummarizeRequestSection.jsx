import SummarizeCodingPanel from "./SummarizeCodingPanel";
import SummarizeModelPromptPanel from "./SummarizeModelPromptPanel";
import { btnPrimary, meta } from "../../lib/uiClasses";

export default function SummarizeRequestSection({
  codings,
  selectedCoding,
  onCodingChange,
  model,
  onModelChange,
  name,
  onNameChange,
  projects,
  selectedProject,
  onProjectChange,
  additionalPrompt,
  onAdditionalPromptChange,
  loading,
  onSubmit,
  errors = {},
}) {
  return (
    <form onSubmit={onSubmit}>
      <div className="flex flex-col gap-3 lg:flex-row">
        <SummarizeCodingPanel
          codings={codings}
          selectedCoding={selectedCoding}
          onCodingChange={onCodingChange}
          error={errors.coding}
        />

        <SummarizeModelPromptPanel
          model={model}
          onModelChange={onModelChange}
          name={name}
          onNameChange={onNameChange}
          projects={projects}
          selectedProject={selectedProject}
          onProjectChange={onProjectChange}
          additionalPrompt={additionalPrompt}
          onAdditionalPromptChange={onAdditionalPromptChange}
          errors={errors}
        />
      </div>

      <div className="mt-3 flex flex-col items-center gap-1.5">
        <button type="submit" className={btnPrimary} disabled={loading}>
          {loading ? "Summarizing…" : "Summarize"}
        </button>
        {loading ? (
          <p className={meta}>
            This can take a few minutes. If you leave, it keeps running and the summary will appear
            in your project.
          </p>
        ) : null}
      </div>
    </form>
  );
}
