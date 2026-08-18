import React from "react";
import AiModelFormGroup from "../models/AiModelFormGroup";
import AiLabel from "../forms/AiLabel";

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

export default function CompareModelPromptPanel({
  model,
  onModelChange,
  name,
  onNameChange,
  additionalPrompt,
  onAdditionalPromptChange,
  examplePromptText,
}) {
  return (
    <div className="flex flex-1">
      <div className="w-full border-2 border-paper p-5">
        <div className="mb-3">
          <h2 className="text-lg font-semibold">Model &amp; instructions</h2>
        </div>

        <div className="mb-3 flex flex-col gap-1.5">
          <label htmlFor="compare-name" className="text-sm">
            Name
          </label>
          <input
            id="compare-name"
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Enter a name for the comparison"
            className={`${inputClasses} max-w-[220px]`}
          />
        </div>

        <AiModelFormGroup
          className="mb-3 flex max-w-[220px] flex-col gap-1.5"
          labelClassName="mb-1 block text-sm"
          label="Model"
          model={model}
          onModelChange={onModelChange}
          selectPlaceholder="compare"
          selectClassName="w-[220px] max-w-[220px] border border-paper bg-white/5 px-3 py-2 text-paper focus:outline-none focus:ring-2 focus:ring-paper"
        />

        <div className="mb-3">
          <div className="mb-1 flex items-center justify-between">
            <AiLabel text="Prompt (optional)" />
            <button
              className="border border-paper px-2 py-1 text-xs transition-colors hover:bg-paper hover:text-ink"
              type="button"
              onClick={() => onAdditionalPromptChange(examplePromptText)}
            >
              Load Example Prompt
            </button>
          </div>
          <textarea
            value={additionalPrompt}
            onChange={(e) => onAdditionalPromptChange(e.target.value)}
            placeholder="Enter any specific instructions for the comparison..."
            className="min-h-[96px] w-full resize-y border border-paper bg-white/5 px-2 py-2 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper"
          />
        </div>
      </div>
    </div>
  );
}
