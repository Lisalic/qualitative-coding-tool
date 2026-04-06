import { savePromptToLibrary } from "../../lib/savePromptToLibrary";
import "../../styles/Home.css";

export default function PromptTextareaWithActions({
  id,
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  promptType,
  exampleText,
  disabled,
  onSaveFeedback,
}) {
  const handleSave = async () => {
    if (!value || !value.trim()) {
      alert("Please enter a prompt before saving");
      return;
    }
    try {
      const { label: savedLabel } = await savePromptToLibrary(
        promptType,
        value,
      );
      onSaveFeedback({ type: "success", message: `Saved: ${savedLabel}` });
      try {
        window.dispatchEvent(new Event("promptSaved"));
      } catch {
        /* ignore */
      }
    } catch (err) {
      if (err?.message === "EMPTY_PROMPT") {
        alert("Please enter a prompt before saving");
        return;
      }
      console.error("Failed to save prompt:", err);
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to save prompt";
      onSaveFeedback({ type: "error", message: String(msg) });
    }
  };

  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      <div style={{ textAlign: "right", marginTop: "-2rem" }}>
        <button
          type="button"
          onClick={handleSave}
          className="load-prompt-btn"
          disabled={disabled}
          style={{ marginLeft: "0.5rem" }}
        >
          Save prompt
        </button>
        <button
          type="button"
          onClick={() => onChange(exampleText)}
          className="load-prompt-btn"
          disabled={disabled}
          style={{ marginLeft: "0.5rem" }}
        >
          Load example prompt
        </button>
      </div>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="form-input"
        disabled={disabled}
      />
    </div>
  );
}
