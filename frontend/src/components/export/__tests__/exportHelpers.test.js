import { describe, expect, it } from "vitest";
import {
  buildExportPath,
  buildProjectBundlePath,
  filenameFromDisposition,
  getExportOptions,
  PROJECT_BUNDLE_KINDS,
  slugify,
} from "../exportHelpers";

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

    it("repeats a param per chosen format and sends only enabled flags", () => {
      const path = buildProjectBundlePath(7, {
        formats: { codebook_formats: ["qdc", "csv"], coding_formats: ["json"] },
        flags: { include_author: true, include_source_text: false },
      });
      expect(path).toBe(
        "/api/export/projects/7/bundle?codebook_formats=qdc&codebook_formats=csv&coding_formats=json&include_author=true",
      );
    });
  });

  describe("getExportOptions", () => {
    const formats = (type) => getExportOptions(type).map((o) => o.format);

    it("leads with Word, then Excel, REFI-QDA and csv for a codebook", () => {
      expect(formats("codebook")).toEqual(["docx", "xlsx", "qdc", "csv"]);
    });

    it("leads with the Excel workbook for coding, sending a layout only for csv/json", () => {
      expect(getExportOptions("coding")).toEqual([
        { label: "Excel workbook (.xlsx)", target: "coding", format: "xlsx" },
        { label: "Word document (.docx)", target: "coding", format: "docx" },
        { label: "CSV – one row per quote", target: "coding", format: "csv", extraParams: { layout: "long" } },
        { label: "CSV – matrix", target: "coding", format: "csv", extraParams: { layout: "wide" } },
        { label: "JSON (.json)", target: "coding", format: "json", extraParams: { layout: "long" } },
      ]);
    });

    it("leads with Word for summaries, documents and memos", () => {
      expect(formats("summary")).toEqual(["docx", "xlsx", "md"]);
      expect(formats("document")).toEqual(["docx", "md"]);
      expect(formats("memos")).toEqual(["docx", "xlsx", "md", "csv"]);
    });

    it("returns fallback options for custom artifact types", () => {
      expect(formats("custom")).toEqual(["csv", "json"]);
    });

    it("gives every option a distinct label naming its extension or shape", () => {
      for (const type of ["codebook", "coding", "summary", "document", "memos", "custom"]) {
        const opts = getExportOptions(type);
        expect(new Set(opts.map((o) => o.label)).size).toBe(opts.length);
        for (const opt of opts) {
          expect(opt.label).toMatch(/\(\.[a-z]+\)$|^CSV – /);
        }
      }
    });
  });

  describe("PROJECT_BUNDLE_KINDS", () => {
    it("defaults every kind to Word or Excel and lets each be chosen", () => {
      const defaults = Object.fromEntries(PROJECT_BUNDLE_KINDS.map((k) => [k.key, k.formats[0].value]));
      expect(defaults).toEqual({
        codebook: "docx",
        coding: "xlsx",
        comparison: "docx",
        summary: "docx",
        memos: "docx",
      });
      for (const kind of PROJECT_BUNDLE_KINDS) {
        expect(kind.param).toMatch(/_formats$/);
        expect(kind.formats.length).toBeGreaterThan(1);
      }
    });
  });

  describe("slugify", () => {
    it("lowercases and underscores a project name", () => {
      expect(slugify("My Project!", "fallback")).toBe("my_project");
      expect(slugify("Café 東京", "fallback")).toBe("café_東京");
    });

    it("falls back for an empty or all-punctuation name", () => {
      expect(slugify("", "fallback")).toBe("fallback");
      expect(slugify("!!!", "fallback")).toBe("fallback");
    });
  });

  describe("filenameFromDisposition", () => {
    it("prefers the UTF-8 filename* over the ASCII stand-in", () => {
      const header = `attachment; filename="Childrens needs.qdc"; filename*=UTF-8''Children%E2%80%99s%20needs.qdc`;
      expect(filenameFromDisposition(header, "x")).toBe("Children’s needs.qdc");
    });

    it("falls back to the plain filename, then to the fallback", () => {
      expect(filenameFromDisposition('attachment; filename="plain.csv"', "x")).toBe("plain.csv");
      expect(filenameFromDisposition(null, "fallback.csv")).toBe("fallback.csv");
    });

    it("never yields a path or a control character", () => {
      const traversal = `attachment; filename*=UTF-8''..%2F..%2Fetc%2Fpasswd`;
      expect(filenameFromDisposition(traversal, "x")).toBe("_.._etc_passwd");
      const windows = `attachment; filename*=UTF-8''..%5Cevil%0D%0A.docx`;
      expect(filenameFromDisposition(windows, "x")).toBe("_evil__.docx");
      expect(filenameFromDisposition(`attachment; filename*=UTF-8''..%2F`, "fallback.docx")).toBe("_");
      expect(filenameFromDisposition(`attachment; filename*=UTF-8''..`, "fallback.docx")).toBe("fallback.docx");
    });
  });
});
