import { describe, it, expect } from "vitest";
import { normalizeCodingRowEdits } from "../codingViewHelpers";

describe("normalizeCodingRowEdits", () => {
  it("rejects non-array input", () => {
    expect(normalizeCodingRowEdits(undefined)).toEqual({ ok: false, error: "No rows to save." });
  });

  it("accepts an empty array (nothing to save is not an error)", () => {
    expect(normalizeCodingRowEdits([])).toEqual({ ok: true, rows: [] });
  });

  it("rejects a blank/whitespace-only itemId with a 1-indexed message", () => {
    expect(normalizeCodingRowEdits([{ itemId: "  " }])).toEqual({
      ok: false,
      error: "Row 1 is missing an item id.",
    });
  });

  it("a row with zero codes is valid -- it just means 'not coded'", () => {
    expect(normalizeCodingRowEdits([{ itemId: "t3_1", codes: [] }])).toEqual({
      ok: true,
      rows: [{ item_id: "t3_1", entries: [] }],
    });
  });

  it("rejects code-without-quote (and vice versa)", () => {
    const rows = [{ itemId: "t3_1", codes: [{ code_uid: "c", quote: "", start_offset: 0, end_offset: 3 }] }];
    expect(normalizeCodingRowEdits(rows)).toEqual({
      ok: false,
      error: "Row 1, code 1 must include a code, a quote, and a valid offset range.",
    });
  });

  it("rejects a missing or invalid offset range even with a code and quote", () => {
    const rows = [{ itemId: "t3_1", codes: [{ code_uid: "c", quote: "e" }] }];
    expect(normalizeCodingRowEdits(rows)).toEqual({
      ok: false,
      error: "Row 1, code 1 must include a code, a quote, and a valid offset range.",
    });
  });

  it("rejects end_offset <= start_offset", () => {
    const rows = [{ itemId: "t3_1", codes: [{ code_uid: "c", quote: "e", start_offset: 5, end_offset: 5 }] }];
    expect(normalizeCodingRowEdits(rows)).toEqual({
      ok: false,
      error: "Row 1, code 1 must include a code, a quote, and a valid offset range.",
    });
  });

  it("silently skips a fully-blank code/quote/notes entry", () => {
    const rows = [
      {
        itemId: "t3_1",
        codes: [
          { code_uid: "", quote: "", notes: "" },
          { code_uid: "c", quote: "e", start_offset: 0, end_offset: 1 },
        ],
      },
    ];
    const result = normalizeCodingRowEdits(rows);
    expect(result).toEqual({
      ok: true,
      rows: [{ item_id: "t3_1", entries: [{ code_uid: "c", quote: "e", start_offset: 0, end_offset: 1 }] }],
    });
  });

  it("a notes-only entry does NOT get silently skipped -- it hits the both-required error", () => {
    const rows = [{ itemId: "t3_1", codes: [{ notes: "just a note" }] }];
    expect(normalizeCodingRowEdits(rows)).toEqual({
      ok: false,
      error: "Row 1, code 1 must include a code, a quote, and a valid offset range.",
    });
  });

  it("trims code/quote/notes and omits notes when empty on success", () => {
    const rows = [
      {
        itemId: "  t3_1  ",
        codes: [{ code_uid: "  c  ", quote: "  e  ", notes: "  ", start_offset: 0, end_offset: 1 }],
      },
    ];
    expect(normalizeCodingRowEdits(rows)).toEqual({
      ok: true,
      rows: [{ item_id: "t3_1", entries: [{ code_uid: "c", quote: "e", start_offset: 0, end_offset: 1 }] }],
    });
  });

  it("keeps notes when non-empty", () => {
    const rows = [{ itemId: "t3_1", codes: [{ code_uid: "c", quote: "e", notes: "n", start_offset: 0, end_offset: 1 }] }];
    const result = normalizeCodingRowEdits(rows);
    expect(result.rows[0].entries[0]).toEqual({ code_uid: "c", quote: "e", start_offset: 0, end_offset: 1, notes: "n" });
  });

  it("fails on the first bad row without validating later rows", () => {
    const rows = [
      { itemId: "" },
      { itemId: "also-not-checked", codes: [{ code_uid: "c", quote: "e", start_offset: 0, end_offset: 1 }] },
    ];
    expect(normalizeCodingRowEdits(rows)).toEqual({
      ok: false,
      error: "Row 1 is missing an item id.",
    });
  });
});
