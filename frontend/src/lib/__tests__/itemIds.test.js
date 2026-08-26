import { describe, it, expect } from "vitest";
import { SUBMISSION, COMMENT, qualifyItemId, splitItemId } from "../itemIds";

describe("qualifyItemId", () => {
  it("prefixes a submission id with t3_", () => {
    expect(qualifyItemId(SUBMISSION, "abc123")).toBe("t3_abc123");
  });

  it("prefixes a comment id with t1_", () => {
    expect(qualifyItemId(COMMENT, "xyz789")).toBe("t1_xyz789");
  });

  it("throws for an unknown row type", () => {
    expect(() => qualifyItemId("reply", "abc123")).toThrow();
  });
});

describe("splitItemId", () => {
  it("round-trips a qualified submission id", () => {
    expect(splitItemId(qualifyItemId(SUBMISSION, "abc123"))).toEqual({
      rowType: SUBMISSION,
      rawId: "abc123",
    });
  });

  it("round-trips a qualified comment id", () => {
    expect(splitItemId(qualifyItemId(COMMENT, "xyz789"))).toEqual({
      rowType: COMMENT,
      rawId: "xyz789",
    });
  });

  it("defaults an unprefixed id to submission", () => {
    // Every coding artifact saved before item types existed only ever
    // contains bare ids -- this default is what keeps them meaning
    // exactly what they always meant.
    expect(splitItemId("abc123")).toEqual({ rowType: SUBMISSION, rawId: "abc123" });
  });

  it("defaults an empty/nullish id to submission with an empty rawId", () => {
    expect(splitItemId("")).toEqual({ rowType: SUBMISSION, rawId: "" });
    expect(splitItemId(null)).toEqual({ rowType: SUBMISSION, rawId: "" });
    expect(splitItemId(undefined)).toEqual({ rowType: SUBMISSION, rawId: "" });
  });
});
