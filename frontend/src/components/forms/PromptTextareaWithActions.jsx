import { useState } from "react";
import PromptManager from "./PromptManager";
import { savePromptToLibrary } from "../../lib/savePromptToLibrary";
import ToastService from "../feedback/ToastService";
import AiLabel from "./AiLabel";
import { btnSm, textarea } from "../../lib/uiClasses";

const linkBtn = btnSm;

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
  // A caller may show save results itself; otherwise they go to a toast,
  // so "Save prompt" never succeeds or fails silently.
  const emitSaveFeedback = (payload) => {
    if (typeof onSaveFeedback === "function") {
      onSaveFeedback(payload);
    } else {
      ToastService.show(payload.message, payload.type);
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
      emitSaveFeedback({ type: "success", message: `Saved to your prompt library as "${savedLabel}".` });
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
      const detail = err?.response?.data?.detail || err?.response?.data?.error;
      const msg = typeof detail === "string" ? detail : "Couldn't save the prompt. Please try again.";
      emitSaveFeedback({ type: "error", message: msg });
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <AiLabel htmlFor={id} text={label} />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSave}
            className={linkBtn}
            disabled={disabled}
          >
            Save prompt
          </button>
          <button
            type="button"
            onClick={() => setIsPromptManagerOpen(true)}
            className={linkBtn}
            disabled={disabled}
          >
            Load prompt
          </button>
        </div>
      </div>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className={textarea}
        disabled={disabled}
      />
      <PromptManager
        isOpen={isPromptManagerOpen}
        onClose={() => setIsPromptManagerOpen(false)}
        onLoadPrompt={onChange}
        promptType={promptType}
        examplePrompt={exampleText}
      />
    </div>
  );
}
