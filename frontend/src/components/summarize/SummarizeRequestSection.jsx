import SummarizeCodingPanel from "./SummarizeCodingPanel";
import SummarizeModelPromptPanel from "./SummarizeModelPromptPanel";

export default function SummarizeRequestSection({
  codings,
  selectedCoding,
  onCodingChange,
  model,
  onModelChange,
  name,
  onNameChange,
  additionalPrompt,
  onAdditionalPromptChange,
  loading,
  onSubmit,
}) {
  return (
    <form onSubmit={onSubmit}>
      <div className="flex flex-col gap-6 lg:flex-row">
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
          additionalPrompt={additionalPrompt}
          onAdditionalPromptChange={onAdditionalPromptChange}
        />
      </div>

      <div className="mt-4 flex justify-center">
        <button
          type="submit"
          className="border-2 border-paper px-7 py-2.5 text-base font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-50"
          disabled={loading}
        >
          {loading ? "Summarizing..." : "Summarize"}
        </button>
      </div>
    </form>
  );
}
