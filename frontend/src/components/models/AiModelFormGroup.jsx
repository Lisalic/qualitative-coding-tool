import { useEffect, useMemo, useState } from "react";
import {
  filterAiModelsByPaid,
  formatAiModelOptionMeta,
  formatPaidModelPricingLine,
  getAiModelByValue,
  useAiModels,
} from "../../lib/aiModelCatalog";
import AiLabel from "../forms/AiLabel";
import Dropdown from "../primitives/Dropdown";
import { btnActive, btnSm, select } from "../../lib/uiClasses";

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
 * @param {string} [props.className] — root wrapper; default "flex flex-col gap-1.5"
 * @param {string} [props.labelClassName]
 * @param {import('react').CSSProperties} [props.labelStyle]
 * @param {string} [props.selectClassName] — box classes for the picker's trigger
 */
export default function AiModelFormGroup({
  model,
  onModelChange,
  disabled = false,
  id = "model",
  label = "AI model",
  selectPlaceholder = "dash",
  className = "flex flex-col gap-1.5",
  labelClassName,
  labelStyle,
  selectClassName = select,
}) {
  const [priceFilter, setPriceFilter] = useState("all");
  const { models, loading: modelsLoading, error: modelsError } = useAiModels();
  const selectedModel = getAiModelByValue(models, model);
  // The Free/Paid filter narrows what's offered, but never silently drops
  // the model already chosen -- it stays listed (and selected) until the
  // user picks another one.
  const filteredModels = useMemo(() => {
    const list = filterAiModelsByPaid(models, priceFilter);
    if (selectedModel && !list.some((m) => m.value === selectedModel.value)) {
      return [selectedModel, ...list];
    }
    return list;
  }, [models, priceFilter, selectedModel]);

  // A model that has left the catalog altogether can't be run.
  useEffect(() => {
    if (!model || modelsLoading || models.length === 0) return;
    if (!models.some((m) => m.value === model)) onModelChange("");
  }, [model, models, modelsLoading, onModelChange]);

  const isDisabled = disabled || modelsLoading;

  return (
    <div className={className || undefined}>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <AiLabel
          htmlFor={id}
          text={label}
          className={labelClassName}
          style={labelStyle}
        />
        <div
          className="inline-flex shrink-0 items-center gap-1"
          role="group"
          aria-label="Filter models by pricing"
        >
          {SEGMENTS.map(({ mode, label: segLabel }) => (
            <button
              key={mode}
              type="button"
              className={`${btnSm} py-0.5 ${priceFilter === mode ? btnActive : ""}`}
              aria-pressed={priceFilter === mode}
              disabled={isDisabled}
              onClick={() => setPriceFilter(mode)}
            >
              {segLabel}
            </button>
          ))}
        </div>
      </div>
      <Dropdown
        id={id}
        value={model}
        options={filteredModels}
        onChange={onModelChange}
        disabled={isDisabled}
        loadingLabel={modelsLoading ? "Loading models…" : undefined}
        placeholder={selectPlaceholder === "filter" ? "Select an AI model" : "Select a model"}
        triggerClassName={`w-full ${selectClassName}`}
        searchPlaceholder="Search models…"
        emptyMessage="No models match that search."
        noOptionsMessage={priceFilter === "all" ? "No models available." : `No ${priceFilter} models available.`}
        listLabel="AI models"
        renderOptionMeta={formatAiModelOptionMeta}
      />
      {modelsError ? (
        <p role="alert" className="mt-1.5 text-sm leading-snug text-error">
          {modelsError} Refresh the page to try again.
        </p>
      ) : selectedModel?.paid ? (
        <p className="mt-1.5 text-sm leading-snug text-paper/70">
          {formatPaidModelPricingLine(selectedModel)}
        </p>
      ) : null}
    </div>
  );
}
