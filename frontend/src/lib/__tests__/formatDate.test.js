import { describe, expect, it } from "vitest";
import { formatDate } from "../formatDate";

describe("formatDate", () => {
  it("returns an empty string for missing or invalid input", () => {
    expect(formatDate(null)).toBe("");
    expect(formatDate(undefined)).toBe("");
    expect(formatDate("")).toBe("");
    expect(formatDate("not a date")).toBe("");
  });

  it("formats to the minute, without seconds", () => {
    const text = formatDate("2026-04-03T12:30:07Z");
    expect(text).not.toBe("");
    expect(text).not.toMatch(/:07\b/);
  });
});
