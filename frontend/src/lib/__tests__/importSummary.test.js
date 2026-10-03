import { describe, expect, it } from "vitest";
import { describeSkippedRecords } from "../importSummary";

describe("describeSkippedRecords", () => {
  it("lists each reason with its count", () => {
    expect(describeSkippedRecords({ duplicate: 2, no_text: 1500 })).toBe(
      "Skipped records: 1,500 had no text, or were deleted or removed; 2 repeated an earlier id.",
    );
  });

  it("returns null when nothing was skipped", () => {
    expect(describeSkippedRecords({})).toBeNull();
    expect(describeSkippedRecords(undefined)).toBeNull();
  });
});
