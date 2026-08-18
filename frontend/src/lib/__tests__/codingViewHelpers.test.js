import { describe, it, expect } from "vitest";
import {
  cloneParsedCodingRows,
  normalizeParsedCodingRows,
  extractApiErrorMessage,
} from "../codingViewHelpers";

describe("cloneParsedCodingRows", () => {
  it("defaults to [] when called with no argument", () => {
    expect(cloneParsedCodingRows()).toEqual([]);
  });

  it("returns [] for non-array input", () => {
    expect(cloneParsedCodingRows("x")).toEqual([]);
  });

  it("stringifies fields and always includes notes (as '' when absent)", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ code: "c", evidence: "e" }] }];
    expect(cloneParsedCodingRows(rows)).toEqual([
      { postId: "p1", codeEvidence: [{ code: "c", evidence: "e", notes: "" }] },
    ]);
  });

  it("numeric 0 postId becomes '' (falsy guard), but 123 becomes '123'", () => {
    expect(cloneParsedCodingRows([{ postId: 0 }])[0].postId).toBe("");
    expect(cloneParsedCodingRows([{ postId: 123 }])[0].postId).toBe("123");
  });

  it("null row / null codeEvidence entries become empty strings / []", () => {
    expect(cloneParsedCodingRows([null])).toEqual([
      { postId: "", codeEvidence: [] },
    ]);
    expect(cloneParsedCodingRows([{ postId: "p1", codeEvidence: "not-array" }])[0].codeEvidence).toEqual(
      [],
    );
  });

  it("produces a deep, independent copy", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ code: "c", evidence: "e" }] }];
    const cloned = cloneParsedCodingRows(rows);
    cloned[0].postId = "changed";
    expect(rows[0].postId).toBe("p1");
  });
});

describe("normalizeParsedCodingRows", () => {
  it("defaults to [] and rejects empty input", () => {
    expect(normalizeParsedCodingRows()).toEqual({
      ok: false,
      error: "Cannot save an empty coding table.",
    });
    expect(normalizeParsedCodingRows([])).toEqual({
      ok: false,
      error: "Cannot save an empty coding table.",
    });
  });

  it("rejects a blank/whitespace-only postId with a 1-indexed message", () => {
    expect(normalizeParsedCodingRows([{ postId: "  " }])).toEqual({
      ok: false,
      error: "Entry 1 is missing a Post ID.",
    });
  });

  it("rejects a row with empty codeEvidence", () => {
    expect(normalizeParsedCodingRows([{ postId: "p1", codeEvidence: [] }])).toEqual({
      ok: false,
      error: "Entry 1 must include at least one code and evidence pair.",
    });
  });

  it("rejects code-without-evidence (and vice versa)", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ code: "c", evidence: "" }] }];
    expect(normalizeParsedCodingRows(rows)).toEqual({
      ok: false,
      error: "Entry 1, code/evidence row 1 must include both code and evidence.",
    });
  });

  it("silently skips a fully-blank code/evidence/notes entry", () => {
    const rows = [
      {
        postId: "p1",
        codeEvidence: [{ code: "", evidence: "", notes: "" }, { code: "c", evidence: "e" }],
      },
    ];
    const result = normalizeParsedCodingRows(rows);
    expect(result.ok).toBe(true);
    expect(result.rows[0].codeEvidence).toEqual([{ code: "c", evidence: "e" }]);
  });

  it("a notes-only entry does NOT get silently skipped -- it hits the both-required error", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ notes: "just a note" }] }];
    expect(normalizeParsedCodingRows(rows)).toEqual({
      ok: false,
      error: "Entry 1, code/evidence row 1 must include both code and evidence.",
    });
  });

  it("all entries skipped -> a specific 'at least one complete pair' error", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ code: "", evidence: "", notes: "" }] }];
    expect(normalizeParsedCodingRows(rows)).toEqual({
      ok: false,
      error: "Entry 1 must include at least one complete code and evidence pair.",
    });
  });

  it("trims fields and omits notes when empty on success", () => {
    const rows = [
      { postId: "  p1  ", codeEvidence: [{ code: "  c  ", evidence: "  e  ", notes: "  " }] },
    ];
    const result = normalizeParsedCodingRows(rows);
    expect(result).toEqual({
      ok: true,
      rows: [{ postId: "p1", codeEvidence: [{ code: "c", evidence: "e" }] }],
    });
  });

  it("keeps notes when non-empty", () => {
    const rows = [{ postId: "p1", codeEvidence: [{ code: "c", evidence: "e", notes: "n" }] }];
    const result = normalizeParsedCodingRows(rows);
    expect(result.rows[0].codeEvidence[0]).toEqual({ code: "c", evidence: "e", notes: "n" });
  });

  it("fails on the first bad row without validating later rows", () => {
    const rows = [
      { postId: "" },
      { postId: "also-not-checked", codeEvidence: [{ code: "c", evidence: "e" }] },
    ];
    expect(normalizeParsedCodingRows(rows)).toEqual({
      ok: false,
      error: "Entry 1 is missing a Post ID.",
    });
  });
});

describe("extractApiErrorMessage", () => {
  const fallback = "fallback message";

  it("prefers `error` over `detail`/`message`", async () => {
    const response = { json: async () => ({ error: "E", detail: "D", message: "M" }) };
    expect(await extractApiErrorMessage(response, fallback)).toBe("E");
  });

  it("falls back to `detail` when `error` is absent", async () => {
    const response = { json: async () => ({ detail: "D" }) };
    expect(await extractApiErrorMessage(response, fallback)).toBe("D");
  });

  it("falls back to `message` when both `error` and `detail` are absent", async () => {
    const response = { json: async () => ({ message: "M" }) };
    expect(await extractApiErrorMessage(response, fallback)).toBe("M");
  });

  it("falls back to fallbackMessage when json() resolves to {}", async () => {
    const response = { json: async () => ({}) };
    expect(await extractApiErrorMessage(response, fallback)).toBe(fallback);
  });

  it("falls back to response.text() when json() rejects", async () => {
    const response = {
      json: async () => {
        throw new Error("not json");
      },
      text: async () => "raw text body",
    };
    expect(await extractApiErrorMessage(response, fallback)).toBe("raw text body");
  });

  it("falls back to fallbackMessage when json() rejects and text() is empty", async () => {
    const response = {
      json: async () => {
        throw new Error("x");
      },
      text: async () => "",
    };
    expect(await extractApiErrorMessage(response, fallback)).toBe(fallback);
  });

  it("falls back to fallbackMessage when both json() and text() reject", async () => {
    const response = {
      json: async () => {
        throw new Error("x");
      },
      text: async () => {
        throw new Error("y");
      },
    };
    expect(await extractApiErrorMessage(response, fallback)).toBe(fallback);
  });

  it("stringifies a non-string payload value (array `detail` becomes '[object Object]'-like)", async () => {
    const response = { json: async () => ({ detail: [{ msg: "bad" }] }) };
    const result = await extractApiErrorMessage(response, fallback);
    expect(typeof result).toBe("string");
    expect(result).not.toBe(fallback);
  });

  it("numeric error: 0 is falsy, falls through to fallback", async () => {
    const response = { json: async () => ({ error: 0 }) };
    expect(await extractApiErrorMessage(response, fallback)).toBe(fallback);
  });
});
