import { describe, expect, it } from "vitest";
import { buildExportPath, buildProjectBundlePath, getExportOptions, slugify } from "../exportHelpers";

describe("exportHelpers", () => {
  describe("buildExportPath", () => {
    it("builds path without version_no", () => {
      const path = buildExportPath(42, "codebook", "csv");
      expect(path).toBe("/api/export/42/codebook?format=csv");
    });

    it("builds path with version_no", () => {
      const path = buildExportPath("schema_1", "coding", "json", 3);
      expect(path).toBe("/api/export/schema_1/coding?format=json&version_no=3");
    });

    it("builds path with extraParams (layout/privacy flags)", () => {
      const path = buildExportPath(42, "coding", "csv", null, { layout: "wide", include_author: true });
      expect(path).toBe("/api/export/42/coding?format=csv&layout=wide&include_author=true");
    });
  });

  describe("buildProjectBundlePath", () => {
    it("builds the project bundle path", () => {
      expect(buildProjectBundlePath(7)).toBe("/api/export/projects/7/bundle");
    });
  });

  describe("getExportOptions", () => {
    it("leads with REFI-QDA then csv for a codebook", () => {
      expect(getExportOptions("codebook")).toEqual([
        { label: ".qdc", target: "codebook", format: "qdc" },
        { label: ".csv", target: "codebook", format: "csv" },
      ]);
    });

    it("offers csv then json for coding, both pinned to the long layout", () => {
      expect(getExportOptions("coding")).toEqual([
        { label: ".csv", target: "coding", format: "csv", extraParams: { layout: "long" } },
        { label: ".json", target: "coding", format: "json", extraParams: { layout: "long" } },
      ]);
    });

    it("offers markdown alone for a summary", () => {
      expect(getExportOptions("summary")).toEqual([{ label: ".md", target: "summary", format: "md" }]);
    });

    it("offers md first for memos, since a memo body is prose", () => {
      expect(getExportOptions("memos")).toEqual([
        { label: ".md", target: "memos", format: "md" },
        { label: ".csv", target: "memos", format: "csv" },
      ]);
    });

    it("returns fallback options for custom artifact types", () => {
      expect(getExportOptions("custom")).toEqual([
        { label: ".csv", target: "custom", format: "csv" },
        { label: ".json", target: "custom", format: "json" },
      ]);
    });

    it("labels every option with the bare extension and nothing else", () => {
      for (const type of ["codebook", "coding", "summary", "memos", "custom"]) {
        const opts = getExportOptions(type);
        // Two formats everywhere but summary, which is markdown-only.
        expect(opts).toHaveLength(type === "summary" ? 1 : 2);
        for (const opt of opts) {
          expect(opt.label).toMatch(/^\.[a-z]+$/);
        }
      }
    });
  });

  describe("slugify", () => {
    it("lowercases and underscores a project name", () => {
      expect(slugify("My Project!", "fallback")).toBe("my_project");
    });

    it("falls back for an empty or all-punctuation name", () => {
      expect(slugify("", "fallback")).toBe("fallback");
      expect(slugify("!!!", "fallback")).toBe("fallback");
    });
  });
});
