import { describe, expect, it } from "vitest";
import { buildExportPath, buildProjectBundlePath, getExportOptions } from "../exportHelpers";

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
      expect(opts).toEqual([
        { label: "Codebook (.csv)", target: "codebook", format: "csv" },
        { label: "Codebook (.json)", target: "codebook", format: "json" },
      ]);
    });

    it("returns coding options including long/wide layouts and memos", () => {
      const opts = getExportOptions("coding");
      expect(opts).toHaveLength(6);
      expect(opts.map((o) => o.label)).toEqual([
        "Coding Segments, long (.csv)",
        "Coding Segments, long (.json)",
        "Coding Matrix, wide (.csv)",
        "Coding Matrix, wide (.json)",
        "Row Memos (.csv)",
        "Row Memos (.json)",
      ]);
      expect(opts[0].extraParams).toEqual({ layout: "long" });
      expect(opts[2].extraParams).toEqual({ layout: "wide" });
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
});
