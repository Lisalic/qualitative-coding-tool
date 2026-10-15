import { describe, it, expect } from "vitest";
import { formatCitation } from "../citationHelpers";

describe("citationHelpers (QC-008)", () => {
  const sampleQuote = {
    quote: "Qualitative coding requires rigorous evidence extraction.",
    code: "Methodology",
    coder: "human",
    post_id: "p101",
    row_type: "submission",
    start_offset: 12,
    end_offset: 70,
    author: "secret_user",
    url: "https://reddit.com/r/qual/comments/p101",
    notes: "Crucial point for chapter 4.",
  };

  it("formats standard citation without author or URL by default", () => {
    const citation = formatCitation(sampleQuote);
    expect(citation).toContain('"Qualitative coding requires rigorous evidence extraction."');
    expect(citation).toContain("Code: Methodology");
    expect(citation).toContain("Coder: Human");
    expect(citation).toContain("submission #p101 (chars 12–70)");
    // Privacy assertions: NEVER include author or URL by default
    expect(citation).not.toContain("secret_user");
    expect(citation).not.toContain("https://reddit.com");
  });

  it("includes author only when explicitly opted-in", () => {
    const citation = formatCitation(sampleQuote, { includeAuthor: true });
    expect(citation).toContain("Author: secret_user");
    expect(citation).not.toContain("https://reddit.com");
  });

  it("includes URL only when explicitly opted-in", () => {
    const citation = formatCitation(sampleQuote, { includeUrl: true });
    expect(citation).toContain("URL: https://reddit.com/r/qual/comments/p101");
    expect(citation).not.toContain("secret_user");
  });

  it("formats AI coder with model name when available", () => {
    const aiQuote = {
      ...sampleQuote,
      coder: "ai",
      coder_model: "gpt-4o",
    };
    const citation = formatCitation(aiQuote);
    expect(citation).toContain("Coder: AI (gpt-4o)");
  });

  it("includes notes when includeNotes is enabled", () => {
    const citation = formatCitation(sampleQuote, { includeNotes: true });
    expect(citation).toContain("Note: Crucial point for chapter 4.");
  });

  it("handles null or empty quote safely", () => {
    expect(formatCitation(null)).toBe("");
    expect(formatCitation({})).toBe("");
  });
});
