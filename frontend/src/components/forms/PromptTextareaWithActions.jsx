import { useState } from "react";
import PromptManager from "./PromptManager";
import { savePromptToLibrary } from "../../lib/savePromptToLibrary";
import ToastService from "../feedback/ToastService";
import AiLabel from "./AiLabel";

const linkBtn =
  "border border-paper px-3 py-1.5 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

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
        className="border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50"
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
