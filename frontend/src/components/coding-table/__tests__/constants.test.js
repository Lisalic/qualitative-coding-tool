import { describe, it, expect } from "vitest";
import {
  clampColumnWidth,
  COLUMN_WIDTHS_MIN,
  COLUMN_WIDTHS_MAX,
  COLUMN_WIDTHS_DEFAULT,
} from "../constants";

describe("clampColumnWidth", () => {
  it("clamps a value below the known column's min", () => {
    expect(clampColumnWidth("postId", 10)).toBe(COLUMN_WIDTHS_MIN.postId);
  });

  it("clamps a value above the known column's max", () => {
    expect(clampColumnWidth("postId", 9999)).toBe(COLUMN_WIDTHS_MAX.postId);
  });

  it("passes through an in-range value unchanged", () => {
    expect(clampColumnWidth("postId", 250)).toBe(250);
  });

  it("unknown columnId falls back to min:120 / max:1200", () => {
    expect(clampColumnWidth("unknownCol", 10)).toBe(120);
    expect(clampColumnWidth("unknownCol", 5000)).toBe(1200);
  });

  it("non-finite width falls back to the column's default width", () => {
    expect(clampColumnWidth("postId", "not-a-number")).toBe(COLUMN_WIDTHS_DEFAULT.postId);
    expect(clampColumnWidth("postId", NaN)).toBe(COLUMN_WIDTHS_DEFAULT.postId);
    expect(clampColumnWidth("postId", undefined)).toBe(COLUMN_WIDTHS_DEFAULT.postId);
  });

  it("non-finite width for an unknown column falls back to min (no default exists)", () => {
    expect(clampColumnWidth("unknownCol", NaN)).toBe(120);
  });

  it("a numeric string is coerced", () => {
    expect(clampColumnWidth("postId", "250")).toBe(250);
  });
});
