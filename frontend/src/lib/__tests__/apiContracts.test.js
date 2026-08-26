import { describe, it, expect } from "vitest";
import {
  MissingFieldsError,
  buildFilterDataForm,
  buildGenerateCodebookForm,
  buildApplyCodebookForm,
  buildRecodeItemsPayload,
} from "../apiContracts";

function fdEntries(fd) {
  return Object.fromEntries([...fd.entries()]);
}

function fdKeys(fd) {
  return [...fd.keys()];
}

describe("MissingFieldsError", () => {
  it("carries the missing field list, flow, and a formatted message", () => {
    const err = new MissingFieldsError(["a", "b"], "some-flow");
    expect(err.name).toBe("MissingFieldsError");
    expect(err.missing).toEqual(["a", "b"]);
    expect(err.flow).toBe("some-flow");
    expect(err.message).toBe("Missing required fields for some-flow: a, b");
    expect(err).toBeInstanceOf(Error);
  });
});

describe("buildFilterDataForm", () => {
  const base = { apiKey: "k", database: "proj_abc", name: "n", model: "m" };

  it("builds the expected FormData for a minimal valid payload", () => {
    const fd = buildFilterDataForm(base);
    expect(fdEntries(fd)).toEqual({
      api_key: "k",
      database: "proj_abc",
      name: "n",
      model: "m",
      sample_percentage: "100",
    });
  });

  it("throws MissingFieldsError listing every blank required field, in order", () => {
    try {
      buildFilterDataForm({ apiKey: "", database: undefined, name: null, model: "" });
      expect.fail("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(MissingFieldsError);
      expect(err.missing).toEqual(["apiKey", "database", "name", "model"]);
      expect(err.flow).toBe("filter-data");
    }
  });

  it("whitespace-only name counts as missing (isBlank trims)", () => {
    expect(() => buildFilterDataForm({ ...base, name: "   " })).toThrow(MissingFieldsError);
  });

  it("rejects a database that doesn't match proj_<id>", () => {
    try {
      buildFilterDataForm({ ...base, database: "not_proj" });
      expect.fail("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(MissingFieldsError);
      expect(err.missing).toEqual(["database (must match proj_<id>)"]);
    }
  });

  it("strips a trailing .db suffix from database", () => {
    const fd = buildFilterDataForm({ ...base, database: "proj_abc.db" });
    expect(fd.get("database")).toBe("proj_abc");
  });

  it("trims name but leaves other free-text fields untrimmed", () => {
    const fd = buildFilterDataForm({ ...base, name: "  n  ", prompt: "  p  " });
    expect(fd.get("name")).toBe("n");
    expect(fd.get("prompt")).toBe("  p  ");
  });

  it("appends project_id only when defined/non-null/non-empty, including 0", () => {
    expect(fdKeys(buildFilterDataForm(base))).not.toContain("project_id");
    expect(buildFilterDataForm({ ...base, projectId: 0 }).get("project_id")).toBe("0");
    expect(buildFilterDataForm({ ...base, projectId: "" }).get("project_id")).toBeNull();
    expect(buildFilterDataForm({ ...base, projectId: 5 }).get("project_id")).toBe("5");
  });

  it("omits prompt/description/filter_tags when blank", () => {
    const fd = buildFilterDataForm(base);
    expect(fdKeys(fd)).not.toEqual(expect.arrayContaining(["prompt", "description", "filter_tags"]));
  });

  it("trims filter_tags but not prompt/description", () => {
    const fd = buildFilterDataForm({
      ...base,
      prompt: "  p  ",
      description: "  d  ",
      filterTags: "  t1, t2  ",
    });
    expect(fd.get("prompt")).toBe("  p  ");
    expect(fd.get("description")).toBe("  d  ");
    expect(fd.get("filter_tags")).toBe("t1, t2");
  });

  it("clamps sample_percentage: undefined -> 100, null -> 1 (not 100)", () => {
    expect(buildFilterDataForm(base).get("sample_percentage")).toBe("100");
    expect(
      buildFilterDataForm({ ...base, samplePercentage: null }).get("sample_percentage"),
    ).toBe("1");
    expect(
      buildFilterDataForm({ ...base, samplePercentage: 150 }).get("sample_percentage"),
    ).toBe("100");
    expect(
      buildFilterDataForm({ ...base, samplePercentage: -5 }).get("sample_percentage"),
    ).toBe("1");
  });

  it("min_words: only appended when finite and > 0", () => {
    expect(fdKeys(buildFilterDataForm(base))).not.toContain("min_words");
    expect(buildFilterDataForm({ ...base, minWords: 0 }).get("min_words")).toBeNull();
    expect(buildFilterDataForm({ ...base, minWords: -3 }).get("min_words")).toBeNull();
    expect(buildFilterDataForm({ ...base, minWords: "abc" }).get("min_words")).toBeNull();
    expect(buildFilterDataForm({ ...base, minWords: "12" }).get("min_words")).toBe("12");
    expect(buildFilterDataForm({ ...base, minWords: 2.7 }).get("min_words")).toBe("2.7");
  });

  it("throws a TypeError for a non-string name (isBlank passes, .trim() doesn't exist)", () => {
    expect(() => buildFilterDataForm({ ...base, name: 5 })).toThrow(TypeError);
  });

  it("omits content_scope when not given, includes it verbatim when given", () => {
    expect(fdKeys(buildFilterDataForm(base))).not.toContain("content_scope");
    expect(buildFilterDataForm({ ...base, contentScope: "posts" }).get("content_scope")).toBe(
      "posts",
    );
  });
});

describe("buildGenerateCodebookForm", () => {
  const base = { apiKey: "k", database: "proj_abc", name: "n" };

  it("does not require model (contrast with filter-data)", () => {
    const fd = buildGenerateCodebookForm(base);
    expect(fdKeys(fd)).not.toContain("model");
  });

  it("throws MissingFieldsError for the three required fields only", () => {
    try {
      buildGenerateCodebookForm({ apiKey: "", database: "", name: "" });
      expect.fail("did not throw");
    } catch (err) {
      expect(err.missing).toEqual(["apiKey", "database", "name"]);
      expect(err.flow).toBe("generate-codebook");
    }
  });

  it("sample_percentage: undefined -> 100, null -> 0 (min:0 here, unlike filter-data's 1)", () => {
    expect(buildGenerateCodebookForm(base).get("sample_percentage")).toBe("100");
    expect(
      buildGenerateCodebookForm({ ...base, samplePercentage: null }).get("sample_percentage"),
    ).toBe("0");
    expect(
      buildGenerateCodebookForm({ ...base, samplePercentage: 0 }).get("sample_percentage"),
    ).toBe("0");
    expect(
      buildGenerateCodebookForm({ ...base, samplePercentage: -4 }).get("sample_percentage"),
    ).toBe("0");
  });

  it("omits model when blank, includes it when present", () => {
    expect(buildGenerateCodebookForm({ ...base, model: "" }).get("model")).toBeNull();
    expect(buildGenerateCodebookForm({ ...base, model: "m" }).get("model")).toBe("m");
  });

  it("strips trailing .db from database", () => {
    expect(
      buildGenerateCodebookForm({ ...base, database: "proj_abc.db" }).get("database"),
    ).toBe("proj_abc");
  });

  it("omits content_scope when not given, includes it verbatim when given", () => {
    expect(fdKeys(buildGenerateCodebookForm(base))).not.toContain("content_scope");
    expect(
      buildGenerateCodebookForm({ ...base, contentScope: "comments" }).get("content_scope"),
    ).toBe("comments");
  });
});

describe("buildApplyCodebookForm", () => {
  const base = {
    apiKey: "k",
    database: "proj_abc",
    codebook: "123",
    reportName: "r",
  };

  it("builds the expected minimal FormData", () => {
    const fd = buildApplyCodebookForm(base);
    expect(fdEntries(fd)).toEqual({
      api_key: "k",
      database: "proj_abc",
      codebook: "123",
      report_name: "r",
      sample_percentage: "100",
    });
  });

  it("throws MissingFieldsError for the four required fields", () => {
    try {
      buildApplyCodebookForm({ apiKey: "", database: "", codebook: "", reportName: "" });
      expect.fail("did not throw");
    } catch (err) {
      expect(err.missing).toEqual(["apiKey", "database", "codebook", "reportName"]);
      expect(err.flow).toBe("apply-codebook");
    }
  });

  it("accepts a numeric-string codebook id, trimmed", () => {
    expect(buildApplyCodebookForm({ ...base, codebook: "  7  " }).get("codebook")).toBe("7");
  });

  it("accepts a proj_<id> codebook schema", () => {
    expect(buildApplyCodebookForm({ ...base, codebook: "proj_x" }).get("codebook")).toBe(
      "proj_x",
    );
  });

  it("codebook keeps a trailing .db suffix, unlike database (no stripDbSuffix applied)", () => {
    expect(
      buildApplyCodebookForm({ ...base, codebook: "proj_x.db" }).get("codebook"),
    ).toBe("proj_x.db");
  });

  it("codebook accepts the loose proj_ prefix check even when the full pattern would reject it", () => {
    // `isProjRef` is a bare `.startsWith("proj_")`, not the stricter
    // PROJ_SCHEMA_RE used for `database` -- "proj_" alone and
    // "proj_a-b!" both pass here even though `database` would reject them.
    expect(() => buildApplyCodebookForm({ ...base, codebook: "proj_" })).not.toThrow();
    expect(() => buildApplyCodebookForm({ ...base, codebook: "proj_a-b!" })).not.toThrow();
  });

  it("rejects a codebook that is neither numeric nor proj_-prefixed", () => {
    for (const bad of ["abc", "1.5", "-1", "file_3"]) {
      expect(() => buildApplyCodebookForm({ ...base, codebook: bad })).toThrow(
        MissingFieldsError,
      );
    }
  });

  it("codebook: 0 is accepted (isBlank(0) is false, and /^\\d+$/ matches '0')", () => {
    expect(buildApplyCodebookForm({ ...base, codebook: 0 }).get("codebook")).toBe("0");
  });

  it("throws TypeError for a non-string reportName", () => {
    expect(() => buildApplyCodebookForm({ ...base, reportName: 7 })).toThrow(TypeError);
  });

  it("omits methodology/model/description when blank", () => {
    const fd = buildApplyCodebookForm(base);
    expect(fdKeys(fd)).not.toEqual(
      expect.arrayContaining(["methodology", "model", "description"]),
    );
  });

  it("omits content_scope when not given, includes it verbatim when given", () => {
    expect(fdKeys(buildApplyCodebookForm(base))).not.toContain("content_scope");
    expect(buildApplyCodebookForm({ ...base, contentScope: "both" }).get("content_scope")).toBe(
      "both",
    );
  });
});

describe("buildRecodeItemsPayload", () => {
  const base = { apiKey: "k", itemIds: ["t3_1", "t1_2"] };

  it("builds a plain object body with api_key and item_ids", () => {
    expect(buildRecodeItemsPayload(base)).toEqual({
      api_key: "k",
      item_ids: ["t3_1", "t1_2"],
    });
  });

  it("includes model/methodology only when non-blank", () => {
    const payload = buildRecodeItemsPayload({
      ...base,
      model: "openrouter/model",
      methodology: "  ",
    });
    expect(payload.model).toBe("openrouter/model");
    expect(payload).not.toHaveProperty("methodology");
  });

  it("throws MissingFieldsError when apiKey is blank", () => {
    try {
      buildRecodeItemsPayload({ ...base, apiKey: "" });
      expect.fail("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(MissingFieldsError);
      expect(err.missing).toEqual(["apiKey"]);
      expect(err.flow).toBe("recode-items");
    }
  });

  it("throws MissingFieldsError when itemIds is missing or empty", () => {
    expect(() => buildRecodeItemsPayload({ ...base, itemIds: [] })).toThrow(MissingFieldsError);
    expect(() => buildRecodeItemsPayload({ apiKey: "k" })).toThrow(MissingFieldsError);
  });
});
