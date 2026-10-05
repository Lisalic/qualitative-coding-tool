import { useEffect, useState } from "react";
import { apiFetch } from "../api";

/** @typedef {'all' | 'free' | 'paid'} AiModelPaidFilter */

/**
 * @param {object[]} models
 * @param {AiModelPaidFilter} mode
 */
export function filterAiModelsByPaid(models, mode) {
  if (mode === "all") return models;
  if (mode === "free") return models.filter((m) => m.paid !== true);
  return models.filter((m) => m.paid === true);
}

export function getAiModelByValue(models, value) {
  if (!value) return undefined;
  return models.find((m) => m.value === value);
}

let _cachedModelsPromise = null;

/** Fetches the live OpenRouter catalog from the backend, caching the in-flight/settled promise. */
export function fetchAiModels() {
  if (!_cachedModelsPromise) {
    _cachedModelsPromise = apiFetch("/api/models")
      .then(async (res) => {
        if (!res.ok) throw new Error(`Failed to load AI models (HTTP ${res.status})`);
        return res.json();
      })
      .catch((err) => {
        _cachedModelsPromise = null; // allow retry on next call
        throw err;
      });
  }
  return _cachedModelsPromise;
}

/** @returns {{models: object[], loading: boolean, error: string | null}} */
export function useAiModels() {
  const [state, setState] = useState({ models: [], loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    fetchAiModels()
      .then((models) => {
        if (!cancelled) setState({ models, loading: false, error: null });
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn("Failed to load AI models:", err);
          setState({ models: [], loading: false, error: "Couldn't load the list of AI models." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
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

/** Compact "1.2M" / "262K" rendering of a catalog entry's context window. */
function formatContextLength(n) {
  if (typeof n !== "number" || !Number.isFinite(n) || n <= 0) return null;
  if (n >= 1_000_000) return `${Math.round(n / 100_000) / 10}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}

/**
 * One-line secondary label for a model inside the picker's option list:
 * pricing tier first, then the context window, then the raw OpenRouter
 * slug (which is what a user searching for a specific model usually
 * knows). Kept short -- it sits under the display name in a dropdown row.
 */
export function formatAiModelOptionMeta(model) {
  const parts = [];
  if (model?.paid === true) {
    const inStr = formatUsdPerMillion(model?.pricing?.inputUsdPerMillion);
    const outStr = formatUsdPerMillion(model?.pricing?.outputUsdPerMillion);
    parts.push(inStr && outStr ? `Paid · ${inStr}/${outStr} per 1M` : "Paid");
  } else {
    parts.push("Free");
  }
  const ctx = formatContextLength(model?.context_length);
  if (ctx) parts.push(`${ctx} context`);
  if (model?.value) parts.push(model.value);
  return parts.join(" · ");
}
