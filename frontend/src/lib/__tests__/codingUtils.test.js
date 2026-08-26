import { describe, it, expect } from "vitest";
import {
  cloneCodebookTree,
  serializeCodebookTreeToText,
  flattenCodebookCodeNames,
  getCodeColor,
  getUniqueCodes,
  getFilteredCoding,
} from "../codingUtils";

describe("cloneCodebookTree", () => {
  it("returns [] for non-array input", () => {
    expect(cloneCodebookTree(null)).toEqual([]);
    expect(cloneCodebookTree(undefined)).toEqual([]);
    expect(cloneCodebookTree("x")).toEqual([]);
  });

  it("deep clones valid trees", () => {
    const tree = [
      { family_name: "F", content: "fc", codes: [{ code_name: "C", content: "cc" }] },
    ];
    const cloned = cloneCodebookTree(tree);
    expect(cloned).toEqual(tree);
    expect(cloned).not.toBe(tree);
    expect(cloned[0]).not.toBe(tree[0]);
    cloned[0].family_name = "mutated";
    expect(tree[0].family_name).toBe("F");
  });

  it("coerces null family entries and non-string fields to empty strings", () => {
    const cloned = cloneCodebookTree([null, { family_name: 5, content: {} }]);
    expect(cloned).toEqual([
      { family_name: "", content: "", codes: [] },
      { family_name: "", content: "", codes: [] },
    ]);
  });

  it("defaults missing/non-array codes to []", () => {
    expect(cloneCodebookTree([{ family_name: "F", codes: "not-array" }])[0].codes).toEqual([]);
  });

  it("drops extra keys not part of the schema", () => {
    const cloned = cloneCodebookTree([{ family_name: "F", extra: "x" }]);
    expect(cloned[0]).not.toHaveProperty("extra");
  });
});

describe("serializeCodebookTreeToText", () => {
  it("returns empty string for non-array or empty input", () => {
    expect(serializeCodebookTreeToText(null)).toBe("");
    expect(serializeCodebookTreeToText([])).toBe("");
  });

  it("serializes a family with codes", () => {
    const tree = [
      {
        family_name: "Anxiety",
        content: "Family desc",
        codes: [{ code_name: "Panic", content: "Code desc" }],
      },
    ];
    expect(serializeCodebookTreeToText(tree)).toBe(
      "### Code Family: Anxiety\nFamily desc\n#### Code Name: Panic\nCode desc",
    );
  });

  it("falls back to 'Unnamed family' for a blank family_name", () => {
    expect(serializeCodebookTreeToText([{ family_name: "  " }])).toBe(
      "### Code Family: Unnamed family",
    );
  });

  it("emits a bare '#### Code Name: ' header for a blank code_name (no fallback)", () => {
    const out = serializeCodebookTreeToText([
      { family_name: "F", codes: [{ code_name: "" }] },
    ]);
    expect(out).toBe("### Code Family: F\n#### Code Name:");
  });

  it("preserves multi-line content verbatim", () => {
    const out = serializeCodebookTreeToText([{ family_name: "F", content: "line1\nline2" }]);
    expect(out).toBe("### Code Family: F\nline1\nline2");
  });

  it("round-trips with cloneCodebookTree structurally", () => {
    const tree = cloneCodebookTree([
      { family_name: "F", content: "fc", codes: [{ code_name: "C", content: "cc" }] },
    ]);
    const text = serializeCodebookTreeToText(tree);
    expect(text).toContain("### Code Family: F");
    expect(text).toContain("#### Code Name: C");
  });
});

describe("flattenCodebookCodeNames", () => {
  it("returns [] for non-array input", () => {
    expect(flattenCodebookCodeNames(null)).toEqual([]);
  });

  it("collects code names across families, deduped and sorted", () => {
    const tree = [
      { family_name: "F1", codes: [{ code_name: "Zebra" }, { code_name: "apple" }] },
      { family_name: "F2", codes: [{ code_name: "apple" }, { code_name: "Banana" }] },
    ];
    expect(flattenCodebookCodeNames(tree)).toEqual(["apple", "Banana", "Zebra"]);
  });

  it("accepts a bare-string code entry, not just {code_name}", () => {
    expect(flattenCodebookCodeNames([{ family_name: "F", codes: ["plain-code"] }])).toEqual([
      "plain-code",
    ]);
  });

  it("skips blank code names", () => {
    expect(flattenCodebookCodeNames([{ family_name: "F", codes: [{ code_name: "  " }] }])).toEqual([]);
  });
});

describe("getCodeColor", () => {
  it("returns a deterministic hsl() string", () => {
    const a = getCodeColor("anxiety");
    const b = getCodeColor("anxiety");
    expect(a).toBe(b);
    expect(a).toMatch(/^hsl\(\d+, 85%, \d+%\)$/);
  });

  it("different inputs generally produce different colors", () => {
    expect(getCodeColor("anxiety")).not.toBe(getCodeColor("depression"));
  });

  it("empty string is deterministic (hash starts at 0)", () => {
    expect(getCodeColor("")).toBe("hsl(0, 85%, 55%)");
  });

  it("hue is always in [0, 359] and lightness in [55, 74]", () => {
    for (const code of ["a", "ab", "abc", "a very long code name here", "🎉emoji"]) {
      const match = getCodeColor(code).match(/^hsl\((\d+), 85%, (\d+)%\)$/);
      expect(match).not.toBeNull();
      const hue = Number(match[1]);
      const lightness = Number(match[2]);
      expect(hue).toBeGreaterThanOrEqual(0);
      expect(hue).toBeLessThan(360);
      expect(lightness).toBeGreaterThanOrEqual(55);
      expect(lightness).toBeLessThan(75);
    }
  });

  it("throws for non-string input (no .length guard)", () => {
    expect(() => getCodeColor(null)).toThrow();
    expect(() => getCodeColor(undefined)).toThrow();
  });
});

describe("getUniqueCodes", () => {
  it("returns [] for non-array input", () => {
    expect(getUniqueCodes(null)).toEqual([]);
  });

  it("dedupes and sorts codes", () => {
    const rows = [
      { codes: [{ code: "b" }, { code: "a" }] },
      { codes: [{ code: "a" }] },
    ];
    expect(getUniqueCodes(rows)).toEqual(["a", "b"]);
  });

  it("skips falsy code values", () => {
    const rows = [{ codes: [{ code: "" }, { code: null }, { code: "x" }] }];
    expect(getUniqueCodes(rows)).toEqual(["x"]);
  });

  it("defaults missing codes to []", () => {
    expect(getUniqueCodes([{}])).toEqual([]);
  });

  it("sort is case-sensitive (uppercase sorts before lowercase)", () => {
    const rows = [{ codes: [{ code: "apple" }, { code: "Zebra" }] }];
    expect(getUniqueCodes(rows)).toEqual(["Zebra", "apple"]);
  });
});

describe("getFilteredCoding", () => {
  const rows = [
    { item_id: "t3_1", codes: [{ code: "a" }] },
    { item_id: "t3_2", codes: [{ code: "b" }] },
  ];

  it("returns [] for non-array input", () => {
    expect(getFilteredCoding("x", [])).toEqual([]);
  });

  it("returns the SAME reference when no filter codes are selected", () => {
    expect(getFilteredCoding(rows, [])).toBe(rows);
    expect(getFilteredCoding(rows, null)).toBe(rows);
    expect(getFilteredCoding(rows, undefined)).toBe(rows);
  });

  it("filters to rows with at least one matching code", () => {
    expect(getFilteredCoding(rows, ["a"])).toEqual([rows[0]]);
  });

  it("returns [] when the filter code matches nothing", () => {
    expect(getFilteredCoding(rows, ["nonexistent"])).toEqual([]);
  });

  it("excludes rows with no codes", () => {
    expect(getFilteredCoding([{ item_id: "t3_1" }], ["a"])).toEqual([]);
  });
});
