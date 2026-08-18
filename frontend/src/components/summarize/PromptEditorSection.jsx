import AiLabel from "../forms/AiLabel";

const EXAMPLE_PROMPT =
  "Please provide a comprehensive summary focusing on:\n- Key themes and patterns in the coded data\n- Most frequently applied codes and their significance\n- Relationships between different codes\n- Representative examples from the data\n- Overall insights and implications";

export default function PromptEditorSection({ value, onChange, onLoadExample }) {
  return (
    <div className="mb-4">
      <div className="mb-1.5 flex items-center gap-2">
        <AiLabel text="Prompt" />
        <button
          type="button"
          className="shrink-0 border border-paper px-2 py-1 text-xs transition-colors hover:bg-paper hover:text-ink"
          onClick={() => onLoadExample?.(EXAMPLE_PROMPT)}
        >
          Load Example Prompt
        </button>
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Enter any specific instructions for the summary..."
        className="min-h-[80px] w-full resize-y border border-paper bg-white/5 px-3 py-3 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper"
      />
    </div>
  );
}
