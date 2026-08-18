import { describe, it, expect } from "vitest";
import {
  filterAiModelsByPaid,
  getAiModelByValue,
  formatPaidModelPricingLine,
} from "../aiModelCatalog";
import { AI_MODELS } from "../constants";

const sample = [
  { value: "free/a", paid: false },
  { value: "free/b", paid: undefined },
  { value: "paid/a", paid: true },
];

describe("filterAiModelsByPaid", () => {
  it("'all' returns the SAME array reference, unfiltered", () => {
    expect(filterAiModelsByPaid(sample, "all")).toBe(sample);
  });

  it("'free' includes paid:false and paid:undefined, excludes paid:true", () => {
    expect(filterAiModelsByPaid(sample, "free")).toEqual([sample[0], sample[1]]);
  });

  it("'paid' (or anything else) includes only paid:true", () => {
    expect(filterAiModelsByPaid(sample, "paid")).toEqual([sample[2]]);
  });

  it("any unrecognized mode falls into the paid branch, not free", () => {
    for (const mode of [undefined, null, "", "PAID", "Free", "nonsense"]) {
      expect(filterAiModelsByPaid(sample, mode)).toEqual([sample[2]]);
    }
  });

  it("empty array returns []", () => {
    expect(filterAiModelsByPaid([], "free")).toEqual([]);
  });

  it("null/undefined models with mode != 'all' throws", () => {
    expect(() => filterAiModelsByPaid(null, "free")).toThrow();
  });
});

describe("getAiModelByValue", () => {
  it("returns undefined for falsy value", () => {
    expect(getAiModelByValue("")).toBeUndefined();
    expect(getAiModelByValue(null)).toBeUndefined();
    expect(getAiModelByValue(undefined)).toBeUndefined();
    expect(getAiModelByValue(0)).toBeUndefined();
  });

  it("returns undefined for an unknown slug", () => {
    expect(getAiModelByValue("not/a/real-model")).toBeUndefined();
  });

  it("finds a known slug from the real catalog, case-sensitively", () => {
    const known = AI_MODELS[0];
    expect(getAiModelByValue(known.value)).toEqual(known);
    expect(getAiModelByValue(known.value.toUpperCase())).toBeUndefined();
  });
});

describe("AI_MODELS catalog invariants", () => {
  it("is a non-empty array", () => {
    expect(Array.isArray(AI_MODELS)).toBe(true);
    expect(AI_MODELS.length).toBeGreaterThan(0);
  });

  it("every entry has a unique `value`", () => {
    const values = AI_MODELS.map((m) => m.value);
    expect(new Set(values).size).toBe(values.length);
  });

  it("every entry declares `paid`", () => {
    for (const m of AI_MODELS) {
      expect(typeof m.paid).toBe("boolean");
    }
  });

  it("every paid entry carries numeric pricing", () => {
    const paid = AI_MODELS.filter((m) => m.paid === true);
    expect(paid.length).toBeGreaterThan(0);
    for (const m of paid) {
      expect(typeof m.pricing?.inputUsdPerMillion).toBe("number");
      expect(typeof m.pricing?.outputUsdPerMillion).toBe("number");
    }
  });
});

describe("formatPaidModelPricingLine", () => {
  it("formats a valid pricing object", () => {
    const model = { pricing: { inputUsdPerMillion: 3, outputUsdPerMillion: 15 } };
    expect(formatPaidModelPricingLine(model)).toBe(
      "Paid model: $3 / $15 per 1M tokens (input / output).",
    );
  });

  it("formats fractional pricing with up to 6 decimal places, no trailing zeros", () => {
    const model = { pricing: { inputUsdPerMillion: 0.7448, outputUsdPerMillion: 4.655 } };
    expect(formatPaidModelPricingLine(model)).toBe(
      "Paid model: $0.7448 / $4.655 per 1M tokens (input / output).",
    );
  });

  it("0 is a valid finite number and formats as $0, not the fallback", () => {
    const model = { pricing: { inputUsdPerMillion: 0, outputUsdPerMillion: 5 } };
    expect(formatPaidModelPricingLine(model)).toBe(
      "Paid model: $0 / $5 per 1M tokens (input / output).",
    );
  });

  it("falls back to the em-dash message for null/undefined model", () => {
    expect(formatPaidModelPricingLine(null)).toBe("Paid model — pricing not listed");
    expect(formatPaidModelPricingLine(undefined)).toBe("Paid model — pricing not listed");
  });

  it("falls back when pricing is missing entirely", () => {
    expect(formatPaidModelPricingLine({})).toBe("Paid model — pricing not listed");
  });

  it("falls back when only one side of pricing is present", () => {
    const model = { pricing: { inputUsdPerMillion: 3 } };
    expect(formatPaidModelPricingLine(model)).toBe("Paid model — pricing not listed");
  });

  it("falls back for a numeric-STRING price (typeof check, not coercion)", () => {
    const model = { pricing: { inputUsdPerMillion: "3", outputUsdPerMillion: 15 } };
    expect(formatPaidModelPricingLine(model)).toBe("Paid model — pricing not listed");
  });

  it("falls back for NaN/Infinity", () => {
    expect(
      formatPaidModelPricingLine({
        pricing: { inputUsdPerMillion: NaN, outputUsdPerMillion: 1 },
      }),
    ).toBe("Paid model — pricing not listed");
    expect(
      formatPaidModelPricingLine({
        pricing: { inputUsdPerMillion: Infinity, outputUsdPerMillion: 1 },
      }),
    ).toBe("Paid model — pricing not listed");
  });
});
