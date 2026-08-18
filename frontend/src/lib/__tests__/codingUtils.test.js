import { describe, it, expect } from "vitest";
import {
  normalizeEvidenceText,
  cloneCodebookTree,
  serializeCodebookTreeToText,
  getCodeColor,
  getUniqueCodes,
  getFilteredCoding,
  getPostDataById,
  parseCodingData,
  formatCodingData,
} from "../codingUtils";

describe("normalizeEvidenceText", () => {
  it("returns empty string for falsy input", () => {
    expect(normalizeEvidenceText("")).toBe("");
    expect(normalizeEvidenceText(null)).toBe("");
    expect(normalizeEvidenceText(undefined)).toBe("");
    expect(normalizeEvidenceText(0)).toBe("");
  });

  it("strips one leading/trailing quote and trims", () => {
    expect(normalizeEvidenceText('"hello"')).toBe("hello");
    expect(normalizeEvidenceText("'hello'")).toBe("hello");
    expect(normalizeEvidenceText('  "hello"  ')).toBe("hello");
  });

  it("normalizes smart quotes to straight quotes", () => {
    expect(normalizeEvidenceText("“hello”")).toBe("hello");
    expect(normalizeEvidenceText("‘hello’")).toBe("hello");
  });

  it("strips markdown formatting", () => {
    expect(normalizeEvidenceText("**bold**")).toBe("bold");
    expect(normalizeEvidenceText("__u__")).toBe("u");
    expect(normalizeEvidenceText("`code`")).toBe("code");
    expect(normalizeEvidenceText("[text](http://x)")).toBe("text");
  });

  it("strips a single leading bullet marker", () => {
    expect(normalizeEvidenceText("- item")).toBe("item");
    expect(normalizeEvidenceText("* item")).toBe("item");
    expect(normalizeEvidenceText("+ item")).toBe("item");
  });

  it("collapses internal whitespace to single spaces", () => {
    expect(normalizeEvidenceText("a   b\n\nc")).toBe("a b c");
  });

  it("coerces non-string input via String()", () => {
    expect(normalizeEvidenceText(123)).toBe("123");
  });
});

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
    const parsed = [
      { codeEvidence: [{ code: "b" }, { code: "a" }] },
      { codeEvidence: [{ code: "a" }] },
    ];
    expect(getUniqueCodes(parsed)).toEqual(["a", "b"]);
  });

  it("skips falsy code values", () => {
    const parsed = [{ codeEvidence: [{ code: "" }, { code: null }, { code: "x" }] }];
    expect(getUniqueCodes(parsed)).toEqual(["x"]);
  });

  it("defaults missing codeEvidence to []", () => {
    expect(getUniqueCodes([{}])).toEqual([]);
  });

  it("sort is case-sensitive (uppercase sorts before lowercase)", () => {
    const parsed = [{ codeEvidence: [{ code: "apple" }, { code: "Zebra" }] }];
    expect(getUniqueCodes(parsed)).toEqual(["Zebra", "apple"]);
  });
});

describe("getFilteredCoding", () => {
  const parsed = [
    { postId: "1", codeEvidence: [{ code: "a" }] },
    { postId: "2", codeEvidence: [{ code: "b" }] },
  ];

  it("returns [] for non-array input", () => {
    expect(getFilteredCoding("x", [])).toEqual([]);
  });

  it("returns the SAME reference when no filter codes are selected", () => {
    expect(getFilteredCoding(parsed, [])).toBe(parsed);
    expect(getFilteredCoding(parsed, null)).toBe(parsed);
    expect(getFilteredCoding(parsed, undefined)).toBe(parsed);
  });

  it("filters to posts with at least one matching code", () => {
    expect(getFilteredCoding(parsed, ["a"])).toEqual([parsed[0]]);
  });

  it("returns [] when the filter code matches nothing", () => {
    expect(getFilteredCoding(parsed, ["nonexistent"])).toEqual([]);
  });

  it("excludes posts with no codeEvidence", () => {
    expect(getFilteredCoding([{ postId: "1" }], ["a"])).toEqual([]);
  });
});

describe("getPostDataById", () => {
  const posts = { ABC123: { title: "t" } };

  it("returns null for falsy postContents or postId", () => {
    expect(getPostDataById(null, "x")).toBeNull();
    expect(getPostDataById(posts, "")).toBeNull();
    expect(getPostDataById(posts, 0)).toBeNull();
  });

  it("looks up case-insensitively", () => {
    expect(getPostDataById(posts, "abc123")).toEqual({ title: "t" });
    expect(getPostDataById(posts, "ABC123")).toEqual({ title: "t" });
  });

  it("coerces a numeric postId via String()", () => {
    expect(getPostDataById({ "123": { title: "t" } }, 123)).toEqual({ title: "t" });
  });

  it("returns null when no key matches", () => {
    expect(getPostDataById(posts, "nomatch")).toBeNull();
  });
});

describe("parseCodingData", () => {
  it("returns [] for non-string or empty content", () => {
    expect(parseCodingData(null)).toEqual([]);
    expect(parseCodingData("")).toEqual([]);
  });

  it("parses the split POST_ID / CODE / EVIDENCE form", () => {
    const content = `POST_ID: p1\nCODE: anxiety\nEVIDENCE: "feeling anxious"`;
    const result = parseCodingData(content);
    expect(result).toEqual([
      { postId: "p1", codeEvidence: [{ code: "anxiety", evidence: "feeling anxious" }] },
    ]);
  });

  it("parses the inline one-liner form", () => {
    const content = `POST_ID: p1 - CODE: anxiety - EVIDENCE: "feeling anxious" - NOTES: important`;
    const result = parseCodingData(content);
    expect(result).toEqual([
      {
        postId: "p1",
        codeEvidence: [{ code: "anxiety", evidence: "feeling anxious", notes: "important" }],
      },
    ]);
  });

  it("accepts multiple POST_ID header spellings", () => {
    for (const header of ["POST_ID:", "POST ID:", "POST-ID:", "Post_Id:"]) {
      const content = `${header} p1\nCODE: c\nEVIDENCE: "e"`;
      expect(parseCodingData(content)[0].postId).toBe("p1");
    }
  });

  it("splits multiple quoted evidence spans into separate entries", () => {
    const content = `POST_ID: p1\nCODE: c\nEVIDENCE: "first" "second"`;
    const result = parseCodingData(content);
    expect(result[0].codeEvidence).toEqual([
      { code: "c", evidence: "first" },
      { code: "c", evidence: "second" },
    ]);
  });

  it("splits on section-sign when no quotes are present", () => {
    const content = `POST_ID: p1\nCODE: c\nEVIDENCE: first§second`;
    const result = parseCodingData(content);
    expect(result[0].codeEvidence.map((e) => e.evidence)).toEqual(["first", "second"]);
  });

  it("drops an entry with a code but zero evidence snippets", () => {
    const content = `POST_ID: p1\nCODE: c\nEVIDENCE:`;
    expect(parseCodingData(content)).toEqual([]);
  });

  it("does not create a post for a trailing bare POST_ID with no code/evidence", () => {
    const content = `POST_ID: p1\nCODE: c\nEVIDENCE: "e"\nPOST_ID: p2`;
    const result = parseCodingData(content);
    expect(result.map((p) => p.postId)).toEqual(["p1"]);
  });

  it("a second CODE before any EVIDENCE discards the pending code", () => {
    const content = `POST_ID: p1\nCODE: first\nCODE: second\nEVIDENCE: "e"`;
    const result = parseCodingData(content);
    expect(result[0].codeEvidence).toEqual([{ code: "second", evidence: "e" }]);
  });

  it("CODE/EVIDENCE lines before any POST_ID are ignored", () => {
    const content = `CODE: c\nEVIDENCE: "e"\nPOST_ID: p1\nCODE: c2\nEVIDENCE: "e2"`;
    const result = parseCodingData(content);
    expect(result).toEqual([{ postId: "p1", codeEvidence: [{ code: "c2", evidence: "e2" }] }]);
  });

  it("duplicate POST_ID values produce two separate rows", () => {
    const content = `POST_ID: p1\nCODE: a\nEVIDENCE: "ea"\nPOST_ID: p1\nCODE: b\nEVIDENCE: "eb"`;
    const result = parseCodingData(content);
    expect(result).toHaveLength(2);
    expect(result[0].postId).toBe("p1");
    expect(result[1].postId).toBe("p1");
  });

  it("strips markdown code fences and horizontal rules from input", () => {
    const content = "```\nPOST_ID: p1\n---\nCODE: c\nEVIDENCE: \"e\"\n```";
    const result = parseCodingData(content);
    expect(result[0].postId).toBe("p1");
  });
});

describe("formatCodingData", () => {
  it("returns '' for non-array input", () => {
    expect(formatCodingData(null)).toBe("");
  });

  it("formats a simple post", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ code: "c", evidence: "e" }] }];
    expect(formatCodingData(rows)).toBe('POST_ID: p1\nCODE: c\nEVIDENCE: "e"');
  });

  it("includes NOTES only when present", () => {
    const rows = [
      { postId: "p1", codeEvidence: [{ code: "c", evidence: "e", notes: "n" }] },
    ];
    expect(formatCodingData(rows)).toBe('POST_ID: p1\nCODE: c\nNOTES: n\nEVIDENCE: "e"');
  });

  it("joins multiple evidence snippets with section-sign, quoting each", () => {
    const rows = [
      {
        postId: "p1",
        codeEvidence: [{ code: "c", evidence: ["a", "b"].join("§") }],
      },
    ];
    // formatEvidenceBlock re-splits on § and re-wraps each in quotes.
    expect(formatCodingData(rows)).toContain('"a"§"b"');
  });

  it("converts inner double quotes to single quotes in evidence", () => {
    // A matched pair of quotes (`"hi"`) would be treated as a quoted span
    // by splitEvidenceSnippets and extracted on its own -- use a single,
    // unmatched quote so the whole string is kept as one snippet and the
    // quote-conversion step in formatEvidenceBlock is what's exercised.
    const rows = [{ postId: "p1", codeEvidence: [{ code: "c", evidence: 'she said "hi' }] }];
    const out = formatCodingData(rows);
    expect(out).toContain("she said 'hi");
  });

  it("skips a post with blank postId", () => {
    const rows = [{ postId: "  ", codeEvidence: [{ code: "c", evidence: "e" }] }];
    expect(formatCodingData(rows)).toBe("");
  });

  it("skips a post with zero valid entries", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ code: "", evidence: "" }] }];
    expect(formatCodingData(rows)).toBe("");
  });

  it("round-trips through parseCodingData for a multi-snippet case", () => {
    const rows = [
      {
        postId: "p1",
        codeEvidence: [
          { code: "anxiety", evidence: "first snippet" },
          { code: "anxiety", evidence: "second snippet" },
        ],
      },
    ];
    const text = formatCodingData(rows);
    const reparsed = parseCodingData(text);
    expect(reparsed).toEqual(rows);
  });
});
