import SummarizeCodingPanel from "./SummarizeCodingPanel";
import SummarizeModelPromptPanel from "./SummarizeModelPromptPanel";
import { btnPrimary } from "../../lib/uiClasses";

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
}) {
  return (
    <form onSubmit={onSubmit}>
      <div className="flex flex-col gap-3 lg:flex-row">
        <SummarizeCodingPanel
          codings={codings}
          selectedCoding={selectedCoding}
          onCodingChange={onCodingChange}
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
        />
      </div>

      <div className="mt-3 flex justify-center">
        <button type="submit" className={btnPrimary} disabled={loading}>
          {loading ? "Summarizing..." : "Summarize"}
        </button>
      </div>
    </form>
  );
}
