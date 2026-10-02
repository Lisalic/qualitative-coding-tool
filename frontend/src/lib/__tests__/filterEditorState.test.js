import { describe, expect, it } from "vitest";
import {
  applyAiResult,
  buildAssistRunsForSubmit,
  counts,
  decidedIds,
  deserializeDraft,
  draftStorageKey,
  emptySelection,
  excludedIds,
  includedIds,
  isAiDecided,
  keyFor,
  parseKey,
  serializeDraft,
  splitByType,
  stateOf,
  toggleExclude,
  toggleInclude,
} from "../filterEditorState";

describe("keyFor / parseKey", () => {
  it("round-trips a plain id", () => {
    expect(parseKey(keyFor("submission", "s1"))).toEqual({
      rowType: "submission",
      id: "s1",
    });
  });

  it("splits on the first colon only, so ids may contain colons", () => {
    expect(parseKey(keyFor("comment", "t1:abc:def"))).toEqual({
      rowType: "comment",
      id: "t1:abc:def",
    });
  });

  it("treats a key with no colon as a submission id", () => {
    expect(parseKey("s1")).toEqual({ rowType: "submission", id: "s1" });
  });
});

describe("stateOf", () => {
  it("defaults every row to undecided", () => {
    expect(stateOf(emptySelection(), "submission", "s1")).toBe("undecided");
  });

  it("reports included and excluded rows", () => {
    let s = toggleInclude(emptySelection(), "submission", "s1");
    s = toggleExclude(s, "submission", "s2");
    expect(stateOf(s, "submission", "s1")).toBe("included");
    expect(stateOf(s, "submission", "s2")).toBe("excluded");
  });
});

describe("toggleInclude / toggleExclude", () => {
  it("is a toggle", () => {
    const s = toggleInclude(toggleInclude(emptySelection(), "submission", "s1"), "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("undecided");
  });

  it("including clears a previous exclusion", () => {
    let s = toggleExclude(emptySelection(), "submission", "s1");
    s = toggleInclude(s, "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("included");
    expect(s.excluded.size).toBe(0);
  });

  it("excluding clears a previous inclusion and its AI badge", () => {
    let s = applyAiResult(emptySelection(), { includePostIds: ["s1"] }).selection;
    expect(isAiDecided(s, "submission", "s1")).toBe(true);
    s = toggleExclude(s, "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("excluded");
    expect(isAiDecided(s, "submission", "s1")).toBe(false);
  });

  it("un-including an AI-included row drops the badge", () => {
    let s = applyAiResult(emptySelection(), { includePostIds: ["s1"] }).selection;
    s = toggleInclude(s, "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("undecided");
    expect(s.aiDecided.size).toBe(0);
  });

  it("un-excluding an AI-excluded row drops the badge", () => {
    let s = applyAiResult(emptySelection(), { excludePostIds: ["s1"] }).selection;
    expect(isAiDecided(s, "submission", "s1")).toBe(true);
    s = toggleExclude(s, "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("undecided");
    expect(isAiDecided(s, "submission", "s1")).toBe(false);
  });

  it("manually including an AI-excluded row clears its badge", () => {
    let s = applyAiResult(emptySelection(), { excludePostIds: ["s1"] }).selection;
    s = toggleInclude(s, "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("included");
    expect(isAiDecided(s, "submission", "s1")).toBe(false);
  });

  it("does not mutate the input selection", () => {
    const before = emptySelection();
    toggleInclude(before, "submission", "s1");
    expect(before.included.size).toBe(0);
  });

  it("keeps submissions and comments with the same id separate", () => {
    let s = toggleInclude(emptySelection(), "submission", "shared");
    s = toggleExclude(s, "comment", "shared");
    expect(stateOf(s, "submission", "shared")).toBe("included");
    expect(stateOf(s, "comment", "shared")).toBe("excluded");
  });
});

describe("applyAiResult", () => {
  it("includes and badges the suggested include rows", () => {
    const { selection, includedCount, excludedCount } = applyAiResult(emptySelection(), {
      includePostIds: ["s1"],
      includeCommentIds: ["c1"],
    });
    expect(includedCount).toBe(2);
    expect(excludedCount).toBe(0);
    expect(stateOf(selection, "submission", "s1")).toBe("included");
    expect(isAiDecided(selection, "comment", "c1")).toBe(true);
  });

  it("excludes and badges the suggested exclude rows", () => {
    const { selection, includedCount, excludedCount } = applyAiResult(emptySelection(), {
      excludePostIds: ["s1"],
      excludeCommentIds: ["c1"],
    });
    expect(includedCount).toBe(0);
    expect(excludedCount).toBe(2);
    expect(stateOf(selection, "submission", "s1")).toBe("excluded");
    expect(isAiDecided(selection, "comment", "c1")).toBe(true);
  });

  it("applies both directions from the same run", () => {
    const { selection, includedCount, excludedCount } = applyAiResult(emptySelection(), {
      includePostIds: ["s1"],
      excludePostIds: ["s2"],
    });
    expect(includedCount).toBe(1);
    expect(excludedCount).toBe(1);
    expect(stateOf(selection, "submission", "s1")).toBe("included");
    expect(stateOf(selection, "submission", "s2")).toBe("excluded");
  });

  it("never re-includes a row the user excluded", () => {
    const base = toggleExclude(emptySelection(), "submission", "s1");
    const { selection, includedCount } = applyAiResult(base, { includePostIds: ["s1", "s2"] });
    expect(includedCount).toBe(1);
    expect(stateOf(selection, "submission", "s1")).toBe("excluded");
    expect(stateOf(selection, "submission", "s2")).toBe("included");
  });

  it("never re-excludes a row the user included", () => {
    const base = toggleInclude(emptySelection(), "submission", "s1");
    const { selection, excludedCount } = applyAiResult(base, { excludePostIds: ["s1", "s2"] });
    expect(excludedCount).toBe(1);
    expect(stateOf(selection, "submission", "s1")).toBe("included");
    expect(stateOf(selection, "submission", "s2")).toBe("excluded");
  });

  it("does not badge a row the user had already included by hand", () => {
    const base = toggleInclude(emptySelection(), "submission", "s1");
    const { selection, includedCount } = applyAiResult(base, { includePostIds: ["s1"] });
    expect(includedCount).toBe(0);
    expect(isAiDecided(selection, "submission", "s1")).toBe(false);
  });

  it("is additive across repeated runs", () => {
    const first = applyAiResult(emptySelection(), { includePostIds: ["s1"] }).selection;
    const { selection, includedCount } = applyAiResult(first, { includePostIds: ["s1", "s2"] });
    expect(includedCount).toBe(1);
    expect(counts(selection).included).toBe(2);
  });

  it("tolerates a missing or empty result", () => {
    const empty = applyAiResult(emptySelection(), {});
    expect(empty.includedCount).toBe(0);
    expect(empty.excludedCount).toBe(0);
    const noArg = applyAiResult(emptySelection());
    expect(noArg.includedCount).toBe(0);
    expect(noArg.excludedCount).toBe(0);
  });
});

describe("splitByType / decidedIds / includedIds / excludedIds", () => {
  it("splits keys by row type", () => {
    expect(splitByType(["submission:s1", "comment:c1", "submission:s2"])).toEqual({
      postIds: ["s1", "s2"],
      commentIds: ["c1"],
    });
  });

  it("decidedIds covers included AND excluded rows", () => {
    let s = toggleInclude(emptySelection(), "submission", "s1");
    s = toggleExclude(s, "submission", "s2");
    s = toggleExclude(s, "comment", "c1");
    const decided = decidedIds(s);
    expect(decided.postIds.sort()).toEqual(["s1", "s2"]);
    expect(decided.commentIds).toEqual(["c1"]);
  });

  it("includedIds covers only the rows that will be copied", () => {
    let s = toggleInclude(emptySelection(), "submission", "s1");
    s = toggleExclude(s, "submission", "s2");
    expect(includedIds(s)).toEqual({ postIds: ["s1"], commentIds: [] });
  });

  it("excludedIds covers only the rows ruled out", () => {
    let s = toggleInclude(emptySelection(), "submission", "s1");
    s = toggleExclude(s, "submission", "s2");
    expect(excludedIds(s)).toEqual({ postIds: ["s2"], commentIds: [] });
  });
});

describe("draft serialization", () => {
  it("namespaces the storage key per source database", () => {
    expect(draftStorageKey("proj_abc")).toBe("filterEditorDraft:proj_abc");
  });

  it("round-trips a selection through JSON", () => {
    let s = toggleInclude(emptySelection(), "submission", "s1");
    s = toggleExclude(s, "comment", "c1");
    s = applyAiResult(s, { includePostIds: ["s2"] }).selection;

    const restored = deserializeDraft(serializeDraft(s));
    expect(stateOf(restored, "submission", "s1")).toBe("included");
    expect(stateOf(restored, "comment", "c1")).toBe("excluded");
    expect(isAiDecided(restored, "submission", "s2")).toBe(true);
  });

  it("returns an empty selection for missing, malformed, or wrongly-typed input", () => {
    for (const raw of [null, "", "not json", "[1,2,3]", '"a string"', "42"]) {
      expect(counts(deserializeDraft(raw))).toEqual({
        included: 0,
        excluded: 0,
        aiDecided: 0,
      });
    }
  });

  it("ignores non-string entries in a stored draft", () => {
    const restored = deserializeDraft(
      JSON.stringify({ included: ["submission:s1", 42, null], excluded: "nope" }),
    );
    expect(counts(restored)).toEqual({ included: 1, excluded: 0, aiDecided: 0 });
  });

  it("resolves a key stored as both included and excluded in favour of included", () => {
    const restored = deserializeDraft(
      JSON.stringify({ included: ["submission:s1"], excluded: ["submission:s1"] }),
    );
    expect(stateOf(restored, "submission", "s1")).toBe("included");
    expect(counts(restored).excluded).toBe(0);
  });

  it("drops an AI badge on a row that is no longer decided", () => {
    const restored = deserializeDraft(
      JSON.stringify({ included: [], excluded: [], aiDecided: ["submission:s1"] }),
    );
    expect(isAiDecided(restored, "submission", "s1")).toBe(false);
  });
});

describe("assistRuns / buildAssistRunsForSubmit", () => {
  it("records nothing when applyAiResult is called with no jobId", () => {
    const { selection } = applyAiResult(emptySelection(), { includePostIds: ["s1"] });
    expect(buildAssistRunsForSubmit(selection)).toEqual([]);
  });

  it("records a run and counts every proposed row as accepted when untouched", () => {
    const { selection } = applyAiResult(emptySelection(), {
      jobId: 7,
      includePostIds: ["s1", "s2"],
      includeCommentIds: ["c1"],
    });
    const runs = buildAssistRunsForSubmit(selection);
    expect(runs).toEqual([
      {
        job_id: 7,
        proposed_count: 3,
        accepted_count: 3,
        dismissed_count: 0,
        accepted_refs: ["submission:s1", "submission:s2", "comment:c1"],
      },
    ]);
  });

  it("an AI-proposed exclusion that survives counts as accepted", () => {
    const { selection } = applyAiResult(emptySelection(), {
      jobId: 7,
      excludePostIds: ["s1"],
    });
    const [run] = buildAssistRunsForSubmit(selection);
    expect(run.proposed_count).toBe(1);
    expect(run.accepted_count).toBe(1);
    expect(run.accepted_refs).toEqual(["submission:s1"]);
  });

  it("a row unchecked after being proposed counts as dismissed, not accepted", () => {
    let { selection } = applyAiResult(emptySelection(), { jobId: 7, includePostIds: ["s1", "s2"] });
    selection = toggleInclude(selection, "submission", "s1");
    const [run] = buildAssistRunsForSubmit(selection);
    expect(run.accepted_count).toBe(1);
    expect(run.dismissed_count).toBe(1);
    expect(run.accepted_refs).toEqual(["submission:s2"]);
  });

  it("a proposed exclusion the user reverses to include counts as dismissed", () => {
    let { selection } = applyAiResult(emptySelection(), { jobId: 7, excludePostIds: ["s1"] });
    selection = toggleInclude(selection, "submission", "s1");
    const [run] = buildAssistRunsForSubmit(selection);
    expect(run.proposed_count).toBe(1);
    expect(run.accepted_count).toBe(0);
    expect(run.dismissed_count).toBe(1);
  });

  it("a row the AI proposed but the user had already excluded counts as dismissed", () => {
    let selection = toggleExclude(emptySelection(), "submission", "s1");
    ({ selection } = applyAiResult(selection, { jobId: 7, includePostIds: ["s1", "s2"] }));
    const [run] = buildAssistRunsForSubmit(selection);
    expect(run.proposed_count).toBe(2);
    expect(run.accepted_count).toBe(1);
    expect(run.accepted_refs).toEqual(["submission:s2"]);
  });

  it("accumulates one entry per run across repeated preview calls", () => {
    let { selection } = applyAiResult(emptySelection(), { jobId: 1, includePostIds: ["s1"] });
    ({ selection } = applyAiResult(selection, { jobId: 2, includePostIds: ["s2"] }));
    const runs = buildAssistRunsForSubmit(selection);
    expect(runs.map((r) => r.job_id)).toEqual([1, 2]);
  });

  it("survives a serialize/deserialize round-trip", () => {
    const { selection } = applyAiResult(emptySelection(), { jobId: 7, includePostIds: ["s1"] });
    const restored = deserializeDraft(serializeDraft(selection));
    expect(buildAssistRunsForSubmit(restored)).toEqual(buildAssistRunsForSubmit(selection));
  });

  it("drops a malformed stored run rather than throwing", () => {
    const restored = deserializeDraft(
      JSON.stringify({
        included: [],
        excluded: [],
        aiDecided: [],
        assistRuns: [{ jobId: 1 }, "garbage", null],
      }),
    );
    expect(buildAssistRunsForSubmit(restored)).toEqual([]);
  });
});
