import { useState } from "react";
import PromptManager from "./PromptManager";
import { savePromptToLibrary } from "../../lib/savePromptToLibrary";
import ToastService from "../feedback/ToastService";
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
  const [isPromptManagerOpen, setIsPromptManagerOpen] = useState(false);
  const emitSaveFeedback = (payload) => {
    if (typeof onSaveFeedback === "function") {
      onSaveFeedback(payload);
    }
  };

  const handleSave = async () => {
    if (!value || !value.trim()) {
      ToastService.show("Please enter a prompt before saving", "info");
      return;
    }
    try {
      const { label: savedLabel } = await savePromptToLibrary(
        promptType,
        value,
      );
      emitSaveFeedback({ type: "success", message: `Saved: ${savedLabel}` });
      try {
        window.dispatchEvent(new Event("promptSaved"));
      } catch {
        /* ignore */
      }
    } catch (err) {
      if (err?.message === "EMPTY_PROMPT") {
        ToastService.show("Please enter a prompt before saving", "info");
        return;
      }
      console.error("Failed to save prompt:", err);
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to save prompt";
      emitSaveFeedback({ type: "error", message: String(msg) });
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
          onClick={() => setIsPromptManagerOpen(true)}
          className="load-prompt-btn"
          disabled={disabled}
          style={{ marginLeft: "0.5rem" }}
        >
          Load prompt
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
      <PromptManager
        isOpen={isPromptManagerOpen}
        onClose={() => setIsPromptManagerOpen(false)}
        onLoadPrompt={onChange}
        currentPrompt={value}
        promptType={promptType}
        examplePrompt={exampleText}
      />
    </div>
  );
}
