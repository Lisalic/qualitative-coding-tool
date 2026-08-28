import { describe, it, expect } from "vitest";
import {
  groupCodesByFamily,
  cloneCodebookTree,
  flattenTreeToCodes,
  flattenCodebookCodes,
  getCodeColor,
} from "../codingUtils";

describe("groupCodesByFamily", () => {
  it("returns [] for non-array input", () => {
    expect(groupCodesByFamily(null)).toEqual([]);
  });

  it("groups a flat codes list by family_uid, preserving order", () => {
    const codes = [
      { code_uid: "c1", family_uid: "f1", family_name: "F1", name: "A" },
      { code_uid: "c2", family_uid: "f2", family_name: "F2", name: "B" },
      { code_uid: "c3", family_uid: "f1", family_name: "F1", name: "C" },
    ];
    const tree = groupCodesByFamily(codes);
    expect(tree.map((f) => f.family_uid)).toEqual(["f1", "f2"]);
    expect(tree[0].codes.map((c) => c.code_uid)).toEqual(["c1", "c3"]);
    expect(tree[1].codes.map((c) => c.code_uid)).toEqual(["c2"]);
  });

  it("keeps distinct families with the same name separate (matches backend contract)", () => {
    const codes = [
      { code_uid: "c1", family_uid: "fa", family_name: "Dup", name: "A" },
      { code_uid: "c2", family_uid: "fb", family_name: "Dup", name: "B" },
    ];
    const tree = groupCodesByFamily(codes);
    expect(tree).toHaveLength(2);
  });
});

describe("cloneCodebookTree", () => {
  it("returns [] for non-array input", () => {
    expect(cloneCodebookTree(null)).toEqual([]);
    expect(cloneCodebookTree(undefined)).toEqual([]);
    expect(cloneCodebookTree("x")).toEqual([]);
  });

  it("deep clones valid trees, preserving code_uid/family_uid", () => {
    const tree = [
      {
        family_uid: "f1",
        family_name: "F",
        codes: [{ code_uid: "c1", family_uid: "f1", family_name: "F", name: "C", body: "cc" }],
      },
    ];
    const cloned = cloneCodebookTree(tree);
    expect(cloned[0].family_uid).toBe("f1");
    expect(cloned[0].codes[0].code_uid).toBe("c1");
    expect(cloned).not.toBe(tree);
    expect(cloned[0]).not.toBe(tree[0]);
    cloned[0].family_name = "mutated";
    expect(tree[0].family_name).toBe("F");
  });

  it("coerces null family entries and non-string fields to empty strings", () => {
    const cloned = cloneCodebookTree([null, { family_name: 5, codes: {} }]);
    expect(cloned).toEqual([
      { family_uid: "", family_name: "", codes: [] },
      { family_uid: "", family_name: "", codes: [] },
    ]);
  });

  it("defaults missing/non-array codes to []", () => {
    expect(cloneCodebookTree([{ family_name: "F", codes: "not-array" }])[0].codes).toEqual([]);
  });
});

describe("flattenTreeToCodes", () => {
  it("returns [] for non-array input", () => {
    expect(flattenTreeToCodes(null)).toEqual([]);
  });

  it("flattens a tree back to a flat codes list with positions", () => {
    const tree = [
      {
        family_uid: "f1",
        family_name: "F1",
        codes: [
          { code_uid: "c1", name: "A", body: "" },
          { code_uid: "c2", name: "B", body: "" },
        ],
      },
    ];
    const flat = flattenTreeToCodes(tree);
    expect(flat.map((c) => c.code_uid)).toEqual(["c1", "c2"]);
    expect(flat.map((c) => c.position)).toEqual([0, 1]);
    expect(flat.every((c) => c.family_uid === "f1")).toBe(true);
  });

  it("marks a code with no code_uid as is_new rather than inventing one", () => {
    const tree = [{ family_uid: "f1", family_name: "F", codes: [{ name: "New", body: "" }] }];
    const flat = flattenTreeToCodes(tree);
    expect(flat[0].is_new).toBe(true);
    expect(flat[0]).not.toHaveProperty("code_uid");
  });

  it("marks a family with no family_uid as family_is_new", () => {
    const tree = [{ family_name: "New Family", codes: [{ code_uid: "c1", name: "A", body: "" }] }];
    const flat = flattenTreeToCodes(tree);
    expect(flat[0].family_is_new).toBe(true);
    expect(flat[0]).not.toHaveProperty("family_uid");
  });

  it("round-trips structured fields with cloneCodebookTree/groupCodesByFamily", () => {
    const original = [
      {
        code_uid: "c1",
        family_uid: "f1",
        family_name: "F",
        name: "C",
        body: "cc",
        definition: "a def",
        inclusion: "when",
        exclusion: "not when",
        keywords: "kw",
        example: "ex",
      },
    ];
    const tree = cloneCodebookTree(groupCodesByFamily(original));
    const flat = flattenTreeToCodes(tree);
    expect(flat[0].definition).toBe("a def");
    expect(flat[0].inclusion).toBe("when");
    expect(flat[0].exclusion).toBe("not when");
    expect(flat[0].keywords).toBe("kw");
    expect(flat[0].example).toBe("ex");
  });
});

describe("flattenCodebookCodes", () => {
  it("returns [] for non-array input", () => {
    expect(flattenCodebookCodes(null)).toEqual([]);
  });

  it("collects {code_uid, name} across families, deduped by uid and sorted by name", () => {
    const tree = [
      { family_name: "F1", codes: [{ code_uid: "c3", name: "Zebra" }, { code_uid: "c1", name: "apple" }] },
      { family_name: "F2", codes: [{ code_uid: "c1", name: "apple" }, { code_uid: "c2", name: "Banana" }] },
    ];
    expect(flattenCodebookCodes(tree)).toEqual([
      { code_uid: "c1", name: "apple" },
      { code_uid: "c2", name: "Banana" },
      { code_uid: "c3", name: "Zebra" },
    ]);
  });

  it("skips entries with a blank name or missing code_uid", () => {
    expect(
      flattenCodebookCodes([{ family_name: "F", codes: [{ code_uid: "c1", name: "  " }, { name: "no-uid" }] }]),
    ).toEqual([]);
  });
});

describe("getCodeColor", () => {
  it("returns a deterministic hsl() string", () => {
    const a = getCodeColor("uid-anxiety");
    const b = getCodeColor("uid-anxiety");
    expect(a).toBe(b);
    expect(a).toMatch(/^hsl\(\d+, 85%, \d+%\)$/);
  });

  it("different inputs generally produce different colors", () => {
    expect(getCodeColor("uid-anxiety")).not.toBe(getCodeColor("uid-depression"));
  });

  it("empty/null/undefined input is deterministic (hash starts at 0)", () => {
    expect(getCodeColor("")).toBe("hsl(0, 85%, 55%)");
    expect(getCodeColor(null)).toBe("hsl(0, 85%, 55%)");
    expect(getCodeColor(undefined)).toBe("hsl(0, 85%, 55%)");
  });

  it("hue is always in [0, 359] and lightness in [55, 74]", () => {
    for (const uid of ["a", "ab", "abc", "a very long uid here", "🎉emoji"]) {
      const match = getCodeColor(uid).match(/^hsl\((\d+), 85%, (\d+)%\)$/);
      expect(match).not.toBeNull();
      const hue = Number(match[1]);
      const lightness = Number(match[2]);
      expect(hue).toBeGreaterThanOrEqual(0);
      expect(hue).toBeLessThan(360);
      expect(lightness).toBeGreaterThanOrEqual(55);
      expect(lightness).toBeLessThan(75);
    }
  });
});
