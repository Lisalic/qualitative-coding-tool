// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  filterAiModelsByPaid,
  getAiModelByValue,
  formatPaidModelPricingLine,
} from "../aiModelCatalog";

const sample = [
  { value: "free/a", paid: false },
  { value: "free/b", paid: undefined },
  { value: "paid/a", paid: true },
];

beforeEach(() => {
  // fetchAiModels caches its promise at module scope; reset between tests
  // so each test controls its own fetch mock.
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

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
    expect(getAiModelByValue(sample, "")).toBeUndefined();
    expect(getAiModelByValue(sample, null)).toBeUndefined();
    expect(getAiModelByValue(sample, undefined)).toBeUndefined();
    expect(getAiModelByValue(sample, 0)).toBeUndefined();
  });

  it("returns undefined for an unknown slug", () => {
    expect(getAiModelByValue(sample, "not/a/real-model")).toBeUndefined();
  });

  it("finds a known slug, case-sensitively", () => {
    expect(getAiModelByValue(sample, "free/a")).toEqual(sample[0]);
    expect(getAiModelByValue(sample, "FREE/A")).toBeUndefined();
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

describe("fetchAiModels", () => {
  it("GETs /api/models and resolves with the parsed catalog", async () => {
    const catalog = [{ value: "a/b", label: "A B", paid: false }];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => catalog,
    });
    vi.stubGlobal("fetch", fetchMock);

    const { fetchAiModels: freshFetch } = await import("../aiModelCatalog");
    const result = await freshFetch();

    expect(result).toEqual(catalog);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/models"),
      expect.anything(),
    );
  });

  it("caches the in-flight/settled promise across calls", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    const { fetchAiModels: freshFetch } = await import("../aiModelCatalog");
    await freshFetch();
    await freshFetch();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects on a non-ok response and allows a retry on the next call", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);

    const { fetchAiModels: freshFetch } = await import("../aiModelCatalog");
    await expect(freshFetch()).rejects.toThrow(/HTTP 500/);
    await expect(freshFetch()).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
