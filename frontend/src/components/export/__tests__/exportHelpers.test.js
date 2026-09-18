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
    it("returns codebook options", () => {
      const opts = getExportOptions("codebook");
      expect(opts).toEqual([{ label: "Codebook (.csv)", target: "codebook", format: "csv" }]);
    });

    it("returns a single coding export option (segments, long, csv)", () => {
      const opts = getExportOptions("coding");
      expect(opts).toEqual([
        { label: "Coding Segments, long (.csv)", target: "coding", format: "csv", extraParams: { layout: "long" } },
      ]);
    });

    it("returns summary options", () => {
      const opts = getExportOptions("summary");
      expect(opts).toEqual([
        { label: "Summary (.csv)", target: "summary", format: "csv" },
        { label: "Summary (.json)", target: "summary", format: "json" },
      ]);
    });

    it("returns fallback options for custom artifact types", () => {
      const opts = getExportOptions("custom");
      expect(opts).toEqual([
        { label: "CSV (.csv)", target: "custom", format: "csv" },
        { label: "JSON (.json)", target: "custom", format: "json" },
      ]);
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
