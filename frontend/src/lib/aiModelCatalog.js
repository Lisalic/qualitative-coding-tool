import { AI_MODELS } from "./constants";

/** @typedef {'all' | 'free' | 'paid'} AiModelPaidFilter */

/**
 * @param {typeof AI_MODELS} models
 * @param {AiModelPaidFilter} mode
 */
export function filterAiModelsByPaid(models, mode) {
  if (mode === "all") return models;
  if (mode === "free") return models.filter((m) => m.paid !== true);
  return models.filter((m) => m.paid === true);
}

export function getAiModelByValue(value) {
  if (!value) return undefined;
  return AI_MODELS.find((m) => m.value === value);
}

function formatUsdPerMillion(n) {
  if (typeof n !== "number" || !Number.isFinite(n)) return null;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 6,
  }).format(n);
}

/** Full line for a paid catalog entry; caller should only use when `model.paid` is true. */
export function formatPaidModelPricingLine(model) {
  const p = model?.pricing;
  const inStr = formatUsdPerMillion(p?.inputUsdPerMillion);
  const outStr = formatUsdPerMillion(p?.outputUsdPerMillion);
  if (!inStr || !outStr) {
    return "Paid model — pricing not listed";
  }
  return `Paid model: ${inStr} / ${outStr} per 1M tokens (input / output).`;
}
