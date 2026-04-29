import React from "react";
import AiModelFormGroup from "../AiModelFormGroup";

export default function CompareModelPromptPanel({
  model,
  onModelChange,
  additionalPrompt,
  onAdditionalPromptChange,
  examplePromptText,
}) {
  return (
    <div className="compare-layout-column">
      <div className="compare-panel-card">
        <div className="compare-panel-header">
          <h2 className="compare-panel-title">Model & instructions</h2>
        </div>

        <AiModelFormGroup
          className="compare-form-group compare-model-select"
          labelClassName="compare-label"
          label="Model"
          model={model}
          onModelChange={onModelChange}
          selectPlaceholder="compare"
          selectClassName="form-input form-input-model"
        />

        <div className="compare-form-group">
          <div className="compare-prompt-label-row">
            <label className="compare-label">Prompt (optional)</label>
            <button
              className="project-tab prompt-example-btn"
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
            className="compare-textarea"
          />
        </div>
      </div>
    </div>
  );
}
