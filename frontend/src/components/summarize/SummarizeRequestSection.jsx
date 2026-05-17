import PromptEditorSection from "./PromptEditorSection";
import SummarizeFormSection from "./SummarizeFormSection";

export default function SummarizeRequestSection({
  codings,
  selectedCoding,
  onCodingChange,
  model,
  onModelChange,
  additionalPrompt,
  onAdditionalPromptChange,
  loading,
  onSubmit,
}) {
  return (
    <form onSubmit={onSubmit}>
      <div className="compare-panel">
        <SummarizeFormSection
          codings={codings}
          selectedCoding={selectedCoding}
          onCodingChange={onCodingChange}
          model={model}
          onModelChange={onModelChange}
        />
        <PromptEditorSection
          value={additionalPrompt}
          onChange={onAdditionalPromptChange}
          onLoadExample={onAdditionalPromptChange}
        />

        <div className="compare-actions" style={{ justifyContent: "center" }}>
          <button className="project-tab" type="submit" disabled={loading}>
            {loading ? "Summarizing..." : "Summarize"}
          </button>
        </div>
      </div>
    </form>
  );
}
