import AiLabel from "../forms/AiLabel";

const EXAMPLE_PROMPT =
  "Please provide a comprehensive summary focusing on:\n- Key themes and patterns in the coded data\n- Most frequently applied codes and their significance\n- Relationships between different codes\n- Representative examples from the data\n- Overall insights and implications";

export default function PromptEditorSection({ value, onChange, onLoadExample }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: 6,
        }}
      >
        <AiLabel text="Prompt" style={{ marginBottom: 0 }} />
        <button
          className="project-tab"
          type="button"
          onClick={() => onLoadExample?.(EXAMPLE_PROMPT)}
          style={{
            fontSize: "12px",
            padding: "4px 8px",
            flexShrink: 0,
          }}
        >
          Load Example Prompt
        </button>
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Enter any specific instructions for the summary..."
        style={{
          width: "100%",
          minHeight: 80,
          padding: 12,
          backgroundColor: "#1a1a1a",
          color: "#fff",
          border: "1px solid #ffffff",
          borderRadius: 4,
          fontFamily: "inherit",
          resize: "vertical",
          fontSize: "14px",
        }}
      />
    </div>
  );
}
