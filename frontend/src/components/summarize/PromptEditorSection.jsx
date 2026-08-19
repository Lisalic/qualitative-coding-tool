import AiLabel from "../forms/AiLabel";

const EXAMPLE_PROMPT =
  "Please provide a comprehensive summary focusing on:\n- Key themes and patterns in the coded data\n- Most frequently applied codes and their significance\n- Relationships between different codes\n- Representative examples from the data\n- Overall insights and implications";

export default function PromptEditorSection({ value, onChange, onLoadExample }) {
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between">
        <AiLabel text="Prompt (optional)" />
        <button
          type="button"
          className="border border-paper px-2 py-1 text-xs transition-colors hover:bg-paper hover:text-ink"
          onClick={() => onLoadExample?.(EXAMPLE_PROMPT)}
        >
          Load Example Prompt
        </button>
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Enter any specific instructions for the summary..."
        className="min-h-[96px] w-full resize-y border border-paper bg-white/5 px-2 py-2 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper"
      />
    </div>
  );
}
