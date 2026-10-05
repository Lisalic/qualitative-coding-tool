import AiLabel from "../forms/AiLabel";
import { btnSm, textarea } from "../../lib/uiClasses";

const EXAMPLE_PROMPT =
  "Please provide a comprehensive summary focusing on:\n- Key themes and patterns in the coded data\n- Most frequently applied codes and their significance\n- Relationships between different codes\n- Representative examples from the data\n- Overall insights and implications";

export default function PromptEditorSection({
  value,
  onChange,
  onLoadExample,
}) {
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between">
        <AiLabel htmlFor="summarize-prompt" text="Prompt (optional)" />
        <button
          type="button"
          className={btnSm}
          onClick={() => onLoadExample?.(EXAMPLE_PROMPT)}
        >
          Load example prompt
        </button>
      </div>
      <textarea
        id="summarize-prompt"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Enter any specific instructions for the summary…"
        className={`${textarea} min-h-[96px]`}
      />
    </div>
  );
}
