import { describe, it, expect } from "vitest";
import {
  MissingFieldsError,
  buildRecodeItemsPayload,
  buildFilterPreviewPayload,
  buildManualFilterPayload,
  buildCodebookPreviewPayload,
  buildManualCodebookPayload,
  buildIntegratePreviewPayload,
  buildIntegrateCodebookPayload,
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
  const base = { apiKey: "k", itemIds: ["t3_1", "t1_2"], model: "openrouter/model" };

  it("builds a plain object body with api_key, item_ids, and model", () => {
    expect(buildRecodeItemsPayload(base)).toEqual({
      api_key: "k",
      item_ids: ["t3_1", "t1_2"],
      model: "openrouter/model",
    });
  });

  it("includes methodology only when non-blank", () => {
    const payload = buildRecodeItemsPayload({
      ...base,
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

  it("throws MissingFieldsError when model is blank", () => {
    try {
      buildRecodeItemsPayload({ ...base, model: "" });
      expect.fail("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(MissingFieldsError);
      expect(err.missing).toEqual(["model"]);
      expect(err.flow).toBe("recode-items");
    }
  });

  it("throws MissingFieldsError when itemIds is missing or empty", () => {
    expect(() => buildRecodeItemsPayload({ ...base, itemIds: [] })).toThrow(MissingFieldsError);
    expect(() => buildRecodeItemsPayload({ apiKey: "k", model: "m" })).toThrow(MissingFieldsError);
  });
});

describe("buildFilterPreviewPayload", () => {
  const base = {
    apiKey: "k",
    database: "proj_abc",
    model: "openrouter/model",
    includePrompt: "keep the good ones",
  };

  it("builds the minimal JSON body", () => {
    expect(buildFilterPreviewPayload(base)).toEqual({
      api_key: "k",
      database: "proj_abc",
      model: "openrouter/model",
      use_examples: false,
      sample_percentage: 100,
      included_post_ids: [],
      included_comment_ids: [],
      excluded_post_ids: [],
      excluded_comment_ids: [],
      include_prompt: "keep the good ones",
    });
  });

  it("passes the already-decided ids through", () => {
    const payload = buildFilterPreviewPayload({
      ...base,
      includedPostIds: ["s1", "s2"],
      includedCommentIds: ["c1"],
      excludedPostIds: ["s3"],
      excludedCommentIds: ["c2"],
    });
    expect(payload.included_post_ids).toEqual(["s1", "s2"]);
    expect(payload.included_comment_ids).toEqual(["c1"]);
    expect(payload.excluded_post_ids).toEqual(["s3"]);
    expect(payload.excluded_comment_ids).toEqual(["c2"]);
  });

  it("strips a .db suffix from the database", () => {
    expect(buildFilterPreviewPayload({ ...base, database: "proj_abc.db" }).database).toBe(
      "proj_abc",
    );
  });

  it("omits blank optional fields and a zero minWords", () => {
    const payload = buildFilterPreviewPayload({
      ...base,
      excludePrompt: "  ",
      filterTags: "  ",
      minWords: 0,
      contentScope: "",
    });
    expect(payload).not.toHaveProperty("exclude_prompt");
    expect(payload).not.toHaveProperty("filter_tags");
    expect(payload).not.toHaveProperty("min_words");
    expect(payload).not.toHaveProperty("content_scope");
  });

  it("includes non-blank optional fields, trimming keywords", () => {
    const payload = buildFilterPreviewPayload({
      ...base,
      excludePrompt: "drop the spam",
      filterTags: "  a, b  ",
      minWords: 25,
      contentScope: "posts",
    });
    expect(payload.include_prompt).toBe("keep the good ones");
    expect(payload.exclude_prompt).toBe("drop the spam");
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

  it("throws when there is no include/exclude prompt, tags, or examples", () => {
    const noPrompt = { ...base };
    delete noPrompt.includePrompt;
    expect(() => buildFilterPreviewPayload(noPrompt)).toThrow(MissingFieldsError);
  });

  it("exclude prompt alone is sufficient", () => {
    const noPrompt = { ...base };
    delete noPrompt.includePrompt;
    const payload = buildFilterPreviewPayload({ ...noPrompt, excludePrompt: "drop spam" });
    expect(payload.exclude_prompt).toBe("drop spam");
  });

  it("filterTags alone is sufficient", () => {
    const noPrompt = { ...base };
    delete noPrompt.includePrompt;
    const payload = buildFilterPreviewPayload({ ...noPrompt, filterTags: "anxiety" });
    expect(payload.filter_tags).toBe("anxiety");
  });

  it("useExamples with no decided rows throws", () => {
    const noPrompt = { ...base };
    delete noPrompt.includePrompt;
    expect(() => buildFilterPreviewPayload({ ...noPrompt, useExamples: true })).toThrow(
      MissingFieldsError,
    );
  });

  it("useExamples with a decided row is valid even without prompts", () => {
    const noPrompt = { ...base };
    delete noPrompt.includePrompt;
    const payload = buildFilterPreviewPayload({
      ...noPrompt,
      useExamples: true,
      includedPostIds: ["s1"],
    });
    expect(payload.use_examples).toBe(true);
    expect(payload).not.toHaveProperty("include_prompt");
  });
});

describe("buildManualFilterPayload", () => {
  const base = { database: "proj_abc", name: "hand picked", postIds: ["s1"], projectId: "7" };

  it("builds the minimal JSON body", () => {
    expect(buildManualFilterPayload(base)).toEqual({
      database: "proj_abc",
      name: "hand picked",
      post_ids: ["s1"],
      comment_ids: [],
      assist_runs: [],
      project_id: 7,
    });
  });

  it("carries assist_runs through when given", () => {
    const run = { job_id: 7, proposed_count: 2, accepted_count: 1, dismissed_count: 1, accepted_refs: ["submission:s1"] };
    const payload = buildManualFilterPayload({ ...base, assistRuns: [run] });
    expect(payload.assist_runs).toEqual([run]);
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

  it("includes description and a numeric project_id", () => {
    const payload = buildManualFilterPayload({
      ...base,
      description: "chosen by hand",
    });
    expect(payload.description).toBe("chosen by hand");
    expect(payload.project_id).toBe(7);
  });

  it("rejects a blank project -- every artifact belongs to one", () => {
    expect(() => buildManualFilterPayload({ ...base, projectId: "" })).toThrow(MissingFieldsError);
    expect(() => buildManualFilterPayload({ ...base, projectId: null })).toThrow(MissingFieldsError);
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
  const base = { database: "proj_abc", name: "hand written", codes, projectId: "7" };

  it("builds the minimal JSON body", () => {
    expect(buildManualCodebookPayload(base)).toEqual({
      database: "proj_abc",
      name: "hand written",
      codes,
      assist_runs: [],
      project_id: 7,
    });
  });

  it("carries assist_runs through when given", () => {
    const run = { job_id: 3, proposed_count: 1, accepted_count: 1, dismissed_count: 0, accepted_refs: ["u1"] };
    const payload = buildManualCodebookPayload({ ...base, assistRuns: [run] });
    expect(payload.assist_runs).toEqual([run]);
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

  it("includes an optional description alongside the required project", () => {
    const payload = buildManualCodebookPayload({ ...base, description: "notes" });
    expect(payload.description).toBe("notes");
    expect(payload.project_id).toBe(7);
  });

  it("rejects a blank project -- every artifact belongs to one", () => {
    expect(() => buildManualCodebookPayload({ ...base, projectId: "" })).toThrow(
      MissingFieldsError,
    );
  });
});

describe("buildIntegratePreviewPayload", () => {
  const base = { apiKey: "k", codebooks: ["proj_a", "proj_b"], model: "m" };

  it("builds the minimal JSON body with an empty draft", () => {
    expect(buildIntegratePreviewPayload(base)).toEqual({
      api_key: "k",
      codebooks: ["proj_a", "proj_b"],
      model: "m",
      existing_codes: [],
    });
  });

  it("sends comparisons only when given, deduped", () => {
    expect(buildIntegratePreviewPayload({ ...base, comparisons: [] })).not.toHaveProperty("comparisons");
    expect(
      buildIntegratePreviewPayload({ ...base, comparisons: ["cmp_x", "cmp_x"] }).comparisons,
    ).toEqual(["cmp_x"]);
  });

  it("rejects a non-comparison ref in comparisons", () => {
    expect(() => buildIntegratePreviewPayload({ ...base, comparisons: ["proj_a"] })).toThrow(
      MissingFieldsError,
    );
  });

  it("carries no name or project -- a preview creates nothing", () => {
    const payload = buildIntegratePreviewPayload({ ...base, existingCodes: [{ name: "a" }] });
    expect(payload).not.toHaveProperty("name");
    expect(payload).not.toHaveProperty("project_id");
    expect(payload.existing_codes).toEqual([{ name: "a" }]);
  });

  it("carries no sample_percentage or content_scope -- nothing is sampled", () => {
    const payload = buildIntegratePreviewPayload(base);
    expect(payload).not.toHaveProperty("sample_percentage");
    expect(payload).not.toHaveProperty("content_scope");
  });

  it("strips a .db suffix and dedupes repeated refs", () => {
    const payload = buildIntegratePreviewPayload({
      ...base,
      codebooks: ["proj_a.db", "proj_b", "proj_a"],
    });
    expect(payload.codebooks).toEqual(["proj_a", "proj_b"]);
  });

  it("rejects fewer than two codebooks", () => {
    expect(() => buildIntegratePreviewPayload({ ...base, codebooks: ["proj_a"] })).toThrow(
      /select at least 2/,
    );
  });

  it("rejects a non-proj codebook reference", () => {
    expect(() =>
      buildIntegratePreviewPayload({ ...base, codebooks: ["proj_a", "not_proj"] }),
    ).toThrow(MissingFieldsError);
  });

  it("requires an api key and a model", () => {
    expect(() => buildIntegratePreviewPayload({ ...base, apiKey: "" })).toThrow(
      MissingFieldsError,
    );
    expect(() => buildIntegratePreviewPayload({ ...base, model: "" })).toThrow(
      MissingFieldsError,
    );
  });

  it("omits a blank prompt", () => {
    expect(buildIntegratePreviewPayload({ ...base, prompt: "  " })).not.toHaveProperty("prompt");
    expect(buildIntegratePreviewPayload({ ...base, prompt: "merge carefully" }).prompt).toBe(
      "merge carefully",
    );
  });
});

describe("buildIntegrateCodebookPayload", () => {
  const codes = [{ name: "Bullying", family_name: "Harm", is_new: true, family_is_new: true }];
  const base = { codebooks: ["proj_a", "proj_b"], name: "integrated", codes, projectId: "7" };

  it("builds the minimal JSON body", () => {
    expect(buildIntegrateCodebookPayload(base)).toEqual({
      codebooks: ["proj_a", "proj_b"],
      name: "integrated",
      codes,
      assist_runs: [],
      project_id: 7,
    });
  });

  it("carries assist_runs through when given", () => {
    const run = { job_id: 3, proposed_count: 1, accepted_count: 1, dismissed_count: 0, accepted_refs: ["u1"] };
    const payload = buildIntegrateCodebookPayload({ ...base, assistRuns: [run] });
    expect(payload.assist_runs).toEqual([run]);
  });

  it("carries no api key or model -- submitting involves no LLM call", () => {
    const payload = buildIntegrateCodebookPayload(base);
    expect(payload).not.toHaveProperty("api_key");
    expect(payload).not.toHaveProperty("model");
  });

  it("rejects fewer than two codebooks", () => {
    expect(() => buildIntegrateCodebookPayload({ ...base, codebooks: ["proj_a"] })).toThrow(
      /select at least 2/,
    );
  });

  it("rejects a non-proj codebook reference", () => {
    expect(() =>
      buildIntegrateCodebookPayload({ ...base, codebooks: ["proj_a", "not_proj"] }),
    ).toThrow(MissingFieldsError);
  });

  it("strips a .db suffix from each codebook ref", () => {
    const payload = buildIntegrateCodebookPayload({ ...base, codebooks: ["proj_a.db", "proj_b"] });
    expect(payload.codebooks).toEqual(["proj_a", "proj_b"]);
  });

  it("rejects an empty draft with an actionable message", () => {
    expect(() => buildIntegrateCodebookPayload({ ...base, codes: [] })).toThrow(
      /codes \(add at least one\)/,
    );
  });

  it("rejects a code that still has no name", () => {
    expect(() =>
      buildIntegrateCodebookPayload({ ...base, codes: [...codes, { name: "  " }] }),
    ).toThrow(/still need a name/);
  });

  it("includes an optional description alongside the required project", () => {
    const payload = buildIntegrateCodebookPayload({ ...base, description: "notes" });
    expect(payload.description).toBe("notes");
    expect(payload.project_id).toBe(7);
  });

  it("rejects a blank project -- every artifact belongs to one", () => {
    expect(() => buildIntegrateCodebookPayload({ ...base, projectId: "" })).toThrow(
      MissingFieldsError,
    );
  });

  it("rejects a missing name", () => {
    expect(() => buildIntegrateCodebookPayload({ ...base, name: "" })).toThrow(
      MissingFieldsError,
    );
  });
});

describe("buildManualCodingPayload", () => {
  const base = { database: "proj_abc", codebook: "12", reportName: "by hand", projectId: "7" };

  it("builds the minimal JSON body", () => {
    expect(buildManualCodingPayload(base)).toEqual({
      database: "proj_abc",
      codebook: "12",
      report_name: "by hand",
      sample_percentage: 100,
      post_ids: [],
      comment_ids: [],
      project_id: 7,
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

  it("requires a source, a codebook, a name and a project", () => {
    expect(() => buildManualCodingPayload({ ...base, reportName: "" })).toThrow(
      MissingFieldsError,
    );
    expect(() => buildManualCodingPayload({ ...base, projectId: "" })).toThrow(
      MissingFieldsError,
    );
    expect(() => buildManualCodingPayload({ ...base, database: "nope" })).toThrow(
      MissingFieldsError,
    );
  });
});
