import { describe, it, expect } from "vitest";
import {
  MissingFieldsError,
  buildRecodeItemsPayload,
  buildFilterPreviewPayload,
  buildManualFilterPayload,
  buildCodebookPreviewPayload,
  buildManualCodebookPayload,
  buildManualCodingPayload,
} from "../apiContracts";

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

describe("buildFilterPreviewPayload", () => {
  const base = { apiKey: "k", database: "proj_abc", model: "openrouter/model" };

  it("builds the minimal JSON body", () => {
    expect(buildFilterPreviewPayload(base)).toEqual({
      api_key: "k",
      database: "proj_abc",
      model: "openrouter/model",
      sample_percentage: 100,
      decided_post_ids: [],
      decided_comment_ids: [],
    });
  });

  it("passes the already-decided ids through", () => {
    const payload = buildFilterPreviewPayload({
      ...base,
      decidedPostIds: ["s1", "s2"],
      decidedCommentIds: ["c1"],
    });
    expect(payload.decided_post_ids).toEqual(["s1", "s2"]);
    expect(payload.decided_comment_ids).toEqual(["c1"]);
  });

  it("strips a .db suffix from the database", () => {
    expect(buildFilterPreviewPayload({ ...base, database: "proj_abc.db" }).database).toBe(
      "proj_abc",
    );
  });

  it("omits blank optional fields and a zero minWords", () => {
    const payload = buildFilterPreviewPayload({
      ...base,
      prompt: "  ",
      filterTags: "  ",
      minWords: 0,
      contentScope: "",
    });
    expect(payload).not.toHaveProperty("prompt");
    expect(payload).not.toHaveProperty("filter_tags");
    expect(payload).not.toHaveProperty("min_words");
    expect(payload).not.toHaveProperty("content_scope");
  });

  it("includes non-blank optional fields, trimming keywords", () => {
    const payload = buildFilterPreviewPayload({
      ...base,
      prompt: "keep the good ones",
      filterTags: "  a, b  ",
      minWords: 25,
      contentScope: "posts",
    });
    expect(payload.prompt).toBe("keep the good ones");
    expect(payload.filter_tags).toBe("a, b");
    expect(payload.min_words).toBe(25);
    expect(payload.content_scope).toBe("posts");
  });

  it("clamps sample_percentage into range", () => {
    expect(buildFilterPreviewPayload({ ...base, samplePercentage: 0 }).sample_percentage).toBe(1);
    expect(buildFilterPreviewPayload({ ...base, samplePercentage: 250 }).sample_percentage).toBe(100);
  });

  it("throws MissingFieldsError when apiKey or model is blank", () => {
    expect(() => buildFilterPreviewPayload({ ...base, apiKey: "" })).toThrow(MissingFieldsError);
    expect(() => buildFilterPreviewPayload({ ...base, model: "" })).toThrow(MissingFieldsError);
  });

  it("rejects a non-proj database", () => {
    try {
      buildFilterPreviewPayload({ ...base, database: "not_proj" });
      expect.fail("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(MissingFieldsError);
      expect(err.flow).toBe("filter-preview");
    }
  });
});

describe("buildManualFilterPayload", () => {
  const base = { database: "proj_abc", name: "hand picked", postIds: ["s1"] };

  it("builds the minimal JSON body", () => {
    expect(buildManualFilterPayload(base)).toEqual({
      database: "proj_abc",
      name: "hand picked",
      post_ids: ["s1"],
      comment_ids: [],
    });
  });

  it("carries no api key or model -- submitting involves no LLM call", () => {
    const payload = buildManualFilterPayload(base);
    expect(payload).not.toHaveProperty("api_key");
    expect(payload).not.toHaveProperty("model");
  });

  it("trims the name and strips a .db suffix from the database", () => {
    const payload = buildManualFilterPayload({
      ...base,
      name: "  hand picked  ",
      database: "proj_abc.db",
    });
    expect(payload.name).toBe("hand picked");
    expect(payload.database).toBe("proj_abc");
  });

  it("includes description and a numeric project_id when given", () => {
    const payload = buildManualFilterPayload({
      ...base,
      description: "chosen by hand",
      projectId: "7",
    });
    expect(payload.description).toBe("chosen by hand");
    expect(payload.project_id).toBe(7);
  });

  it("omits project_id when it is blank or null", () => {
    expect(buildManualFilterPayload({ ...base, projectId: "" })).not.toHaveProperty("project_id");
    expect(buildManualFilterPayload({ ...base, projectId: null })).not.toHaveProperty("project_id");
  });

  it("throws MissingFieldsError when nothing is selected", () => {
    try {
      buildManualFilterPayload({ ...base, postIds: [], commentIds: [] });
      expect.fail("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(MissingFieldsError);
      expect(err.flow).toBe("manual-filter");
    }
  });

  it("throws MissingFieldsError when the name is blank", () => {
    expect(() => buildManualFilterPayload({ ...base, name: "  " })).toThrow(MissingFieldsError);
  });
});

describe("buildCodebookPreviewPayload", () => {
  const base = { apiKey: "k", database: "proj_abc", model: "m" };

  it("builds the minimal JSON body with an empty draft", () => {
    expect(buildCodebookPreviewPayload(base)).toEqual({
      api_key: "k",
      database: "proj_abc",
      model: "m",
      sample_percentage: 100,
      existing_codes: [],
    });
  });

  it("carries no name or project -- a preview creates nothing", () => {
    const payload = buildCodebookPreviewPayload({ ...base, existingCodes: [{ name: "a" }] });
    expect(payload).not.toHaveProperty("name");
    expect(payload).not.toHaveProperty("project_id");
    expect(payload.existing_codes).toEqual([{ name: "a" }]);
  });

  it("clamps the sample percentage and strips a .db suffix", () => {
    const payload = buildCodebookPreviewPayload({
      ...base,
      database: "proj_abc.db",
      samplePercentage: 500,
    });
    expect(payload.database).toBe("proj_abc");
    expect(payload.sample_percentage).toBe(100);
  });

  it("requires an api key, a database and a model", () => {
    expect(() => buildCodebookPreviewPayload({ ...base, apiKey: "" })).toThrow(
      MissingFieldsError,
    );
    expect(() => buildCodebookPreviewPayload({ ...base, model: "" })).toThrow(
      MissingFieldsError,
    );
    expect(() => buildCodebookPreviewPayload({ ...base, database: "nope" })).toThrow(
      MissingFieldsError,
    );
  });
});

describe("buildManualCodebookPayload", () => {
  const codes = [{ name: "Bullying", family_name: "Harm", is_new: true, family_is_new: true }];
  const base = { database: "proj_abc", name: "hand written", codes };

  it("builds the minimal JSON body", () => {
    expect(buildManualCodebookPayload(base)).toEqual({
      database: "proj_abc",
      name: "hand written",
      codes,
    });
  });

  it("carries no api key or model -- submitting involves no LLM call", () => {
    const payload = buildManualCodebookPayload(base);
    expect(payload).not.toHaveProperty("api_key");
    expect(payload).not.toHaveProperty("model");
  });

  it("rejects an empty draft with an actionable message", () => {
    expect(() => buildManualCodebookPayload({ ...base, codes: [] })).toThrow(
      /codes \(add at least one\)/,
    );
  });

  it("rejects a code that still has no name", () => {
    expect(() =>
      buildManualCodebookPayload({ ...base, codes: [...codes, { name: "  " }] }),
    ).toThrow(/still need a name/);
  });

  it("includes an optional description and project", () => {
    const payload = buildManualCodebookPayload({
      ...base,
      description: "notes",
      projectId: "7",
    });
    expect(payload.description).toBe("notes");
    expect(payload.project_id).toBe(7);
  });
});

describe("buildManualCodingPayload", () => {
  const base = { database: "proj_abc", codebook: "12", reportName: "by hand" };

  it("builds the minimal JSON body", () => {
    expect(buildManualCodingPayload(base)).toEqual({
      database: "proj_abc",
      codebook: "12",
      report_name: "by hand",
      sample_percentage: 100,
      post_ids: [],
      comment_ids: [],
    });
  });

  it("carries no api key, model or methodology -- no model runs", () => {
    const payload = buildManualCodingPayload(base);
    expect(payload).not.toHaveProperty("api_key");
    expect(payload).not.toHaveProperty("model");
    expect(payload).not.toHaveProperty("methodology");
  });

  it("accepts a proj_ codebook reference as well as a numeric id", () => {
    expect(buildManualCodingPayload({ ...base, codebook: "proj_def" }).codebook).toBe(
      "proj_def",
    );
  });

  it("rejects a codebook reference that is neither", () => {
    expect(() => buildManualCodingPayload({ ...base, codebook: "cb-1" })).toThrow(
      MissingFieldsError,
    );
  });

  it("passes explicit row ids through", () => {
    const payload = buildManualCodingPayload({ ...base, postIds: ["s1"], commentIds: ["c1"] });
    expect(payload.post_ids).toEqual(["s1"]);
    expect(payload.comment_ids).toEqual(["c1"]);
  });

  it("requires a source, a codebook and a name", () => {
    expect(() => buildManualCodingPayload({ ...base, reportName: "" })).toThrow(
      MissingFieldsError,
    );
    expect(() => buildManualCodingPayload({ ...base, database: "nope" })).toThrow(
      MissingFieldsError,
    );
  });
});
