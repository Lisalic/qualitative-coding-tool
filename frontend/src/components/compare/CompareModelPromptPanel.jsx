import React from "react";
import { AI_MODELS } from "../../lib/constants";

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

        <div className="compare-form-group compare-model-select">
          <label className="compare-label">Model</label>
          <select
            className="form-input form-input-model"
            value={model}
            onChange={(e) => onModelChange(e.target.value)}
          >
            <option value="">Select a model</option>
            {AI_MODELS.map((modelOption) => (
              <option key={modelOption.value} value={modelOption.value}>
                {modelOption.label}
              </option>
            ))}
          </select>
        </div>

        <div className="compare-form-group">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 4,
            }}
          >
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
