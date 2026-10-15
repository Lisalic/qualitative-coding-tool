import { describe, expect, it } from "vitest";
import { codePointToUtf16Index, sliceByCodePoints, utf16ToCodePointIndex } from "../textOffsets";

// Two emoji before the quote: the backend stores "I was anxious" at
// code points 12..25, which are UTF-16 indices 14..27.
const TEXT = "😭😭 honestly I was anxious all week";

describe("textOffsets", () => {
  it("slices a stored code point span to the right text despite emoji", () => {
    expect(sliceByCodePoints(TEXT, 12, 25)).toBe("I was anxious");
  });

  it("converts code points to UTF-16 indices", () => {
    expect(codePointToUtf16Index(TEXT, 12)).toBe(14);
    expect(codePointToUtf16Index("plain", 3)).toBe(3);
  });

  it("round-trips a DOM (UTF-16) selection to code points", () => {
    const start = TEXT.indexOf("I was");
    expect(utf16ToCodePointIndex(TEXT, start)).toBe(12);
    expect(codePointToUtf16Index(TEXT, utf16ToCodePointIndex(TEXT, start))).toBe(start);
  });

  it("clamps offsets past the end", () => {
    expect(codePointToUtf16Index("ab", 10)).toBe(2);
    expect(utf16ToCodePointIndex("ab", 10)).toBe(2);
  });
});
