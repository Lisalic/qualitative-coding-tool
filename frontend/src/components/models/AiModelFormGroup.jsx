import { useEffect, useMemo, useState } from "react";
import { filterAiModelsByPaid } from "../../lib/aiModelCatalog";
import { AI_MODELS } from "../../lib/constants";
import PaidModelPricingNotice from "./PaidModelPricingNotice";

const SEGMENTS = [
  { mode: "all", label: "All" },
  { mode: "free", label: "Free" },
  { mode: "paid", label: "Paid" },
];

/**
 * @param {object} props
 * @param {string} props.model
 * @param {(v: string) => void} props.onModelChange
 * @param {boolean} [props.disabled]
 * @param {string} [props.id]
 * @param {string} [props.label]
 * @param {'filter' | 'dash' | 'compare'} [props.selectPlaceholder]
 * @param {string} [props.className] — root wrapper; default "form-group"
 * @param {string} [props.labelClassName]
 * @param {import('react').CSSProperties} [props.labelStyle]
 * @param {string} [props.selectClassName]
 */
export default function AiModelFormGroup({
  model,
  onModelChange,
  disabled = false,
  id = "model",
  label = "AI Model",
  selectPlaceholder = "dash",
  className = "form-group",
  labelClassName,
  labelStyle,
  selectClassName = "form-input",
}) {
  const [priceFilter, setPriceFilter] = useState("all");
  const filteredModels = useMemo(
    () => filterAiModelsByPaid(AI_MODELS, priceFilter),
    [priceFilter],
  );

  useEffect(() => {
    if (!model) return;
    const ok = filteredModels.some((m) => m.value === model);
    if (!ok) onModelChange("");
  }, [model, filteredModels, onModelChange]);

  let selectChildren;
  if (selectPlaceholder === "filter") {
    selectChildren = (
      <>
        {!model && (
          <option value="" disabled>
            Select an AI model
          </option>
        )}
        {filteredModels.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </>
    );
  } else if (selectPlaceholder === "compare") {
    selectChildren = (
      <>
        <option value="">Select a model</option>
        {filteredModels.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </>
    );
  } else {
    selectChildren = [{ value: "", label: "-- select model --" }, ...filteredModels].map(
      (opt) => (
        <option key={opt.value || "empty"} value={opt.value}>
          {opt.label}
        </option>
      ),
    );
  }

  return (
    <div className={className || undefined}>
      <div className="ai-model-form-group__label-row">
        <label htmlFor={id} className={labelClassName} style={labelStyle}>
          {label}
        </label>
        <div
          className="ai-model-price-filter"
          role="group"
          aria-label="Filter models by pricing"
        >
          {SEGMENTS.map(({ mode, label: segLabel }) => (
            <button
              key={mode}
              type="button"
              className={
                priceFilter === mode
                  ? "ai-model-price-filter__seg is-active"
                  : "ai-model-price-filter__seg"
              }
              aria-pressed={priceFilter === mode}
              disabled={disabled}
              onClick={() => setPriceFilter(mode)}
            >
              {segLabel}
            </button>
          ))}
        </div>
      </div>
      <select
        id={id}
        value={model}
        onChange={(e) => onModelChange(e.target.value)}
        className={selectClassName}
        disabled={disabled}
      >
        {selectChildren}
      </select>
      <PaidModelPricingNotice modelValue={model} />
    </div>
  );
}
