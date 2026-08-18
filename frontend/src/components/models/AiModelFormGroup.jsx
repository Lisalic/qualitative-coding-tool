import { useEffect, useMemo, useState } from "react";
import {
  filterAiModelsByPaid,
  formatPaidModelPricingLine,
  getAiModelByValue,
  useAiModels,
} from "../../lib/aiModelCatalog";
import AiLabel from "../forms/AiLabel";

const SEGMENTS = [
  { mode: "all", label: "All" },
  { mode: "free", label: "Free" },
  { mode: "paid", label: "Paid" },
];

const DEFAULT_SELECT_CLASSES =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

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
 * @param {string} [props.selectClassName]
 */
export default function AiModelFormGroup({
  model,
  onModelChange,
  disabled = false,
  id = "model",
  label = "AI Model",
  selectPlaceholder = "dash",
  className = "flex flex-col gap-1.5",
  labelClassName,
  labelStyle,
  selectClassName = DEFAULT_SELECT_CLASSES,
}) {
  const [priceFilter, setPriceFilter] = useState("all");
  const { models, loading: modelsLoading, error: modelsError } = useAiModels();
  const selectedModel = getAiModelByValue(models, model);
  const filteredModels = useMemo(
    () => filterAiModelsByPaid(models, priceFilter),
    [models, priceFilter],
  );

  useEffect(() => {
    if (!model || modelsLoading) return;
    const ok = filteredModels.some((m) => m.value === model);
    if (!ok) onModelChange("");
  }, [model, filteredModels, modelsLoading, onModelChange]);

  const isDisabled = disabled || modelsLoading;

  let selectChildren;
  if (modelsLoading) {
    selectChildren = (
      <option value="" disabled>
        Loading models…
      </option>
    );
  } else if (selectPlaceholder === "filter") {
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
              className={`border px-2 py-0.5 text-xs transition-colors ${
                priceFilter === mode
                  ? "border-paper bg-paper text-ink"
                  : "border-paper/30 text-paper/70 hover:border-paper hover:text-paper"
              }`}
              aria-pressed={priceFilter === mode}
              disabled={isDisabled}
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
        disabled={isDisabled}
      >
        {selectChildren}
      </select>
      {modelsError ? (
        <p className="mt-1.5 text-sm leading-snug text-error">{modelsError}</p>
      ) : selectedModel?.paid ? (
        <p className="mt-1.5 text-sm leading-snug text-paper/70">
          {formatPaidModelPricingLine(selectedModel)}
        </p>
      ) : null}
    </div>
  );
}
