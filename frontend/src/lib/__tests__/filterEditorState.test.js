import { describe, expect, it } from "vitest";
import {
  applyAiResult,
  counts,
  decidedIds,
  deserializeDraft,
  draftStorageKey,
  emptySelection,
  includedIds,
  isAiAdded,
  keyFor,
  parseKey,
  serializeDraft,
  splitByType,
  stateOf,
  toggleAll,
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
    let s = applyAiResult(emptySelection(), { postIds: ["s1"] }).selection;
    expect(isAiAdded(s, "submission", "s1")).toBe(true);
    s = toggleExclude(s, "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("excluded");
    expect(isAiAdded(s, "submission", "s1")).toBe(false);
  });

  it("un-including an AI-added row drops the badge", () => {
    let s = applyAiResult(emptySelection(), { postIds: ["s1"] }).selection;
    s = toggleInclude(s, "submission", "s1");
    expect(stateOf(s, "submission", "s1")).toBe("undecided");
    expect(s.aiAdded.size).toBe(0);
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

describe("toggleAll", () => {
  it("includes every row when not all are included", () => {
    const s = toggleAll(emptySelection(), "submission", ["s1", "s2", "s3"]);
    expect(counts(s).included).toBe(3);
  });

  it("clears them all when every row is already included", () => {
    let s = toggleAll(emptySelection(), "submission", ["s1", "s2"]);
    s = toggleAll(s, "submission", ["s1", "s2"]);
    expect(counts(s).included).toBe(0);
  });

  it("clears an exclusion when including a page", () => {
    let s = toggleExclude(emptySelection(), "submission", "s1");
    s = toggleAll(s, "submission", ["s1", "s2"]);
    expect(stateOf(s, "submission", "s1")).toBe("included");
  });

  it("is a no-op on an empty page", () => {
    const s = toggleAll(emptySelection(), "submission", []);
    expect(counts(s)).toEqual({ included: 0, excluded: 0, aiAdded: 0 });
  });
});

describe("applyAiResult", () => {
  it("includes and badges the suggested rows", () => {
    const { selection, addedCount } = applyAiResult(emptySelection(), {
      postIds: ["s1"],
      commentIds: ["c1"],
    });
    expect(addedCount).toBe(2);
    expect(stateOf(selection, "submission", "s1")).toBe("included");
    expect(isAiAdded(selection, "comment", "c1")).toBe(true);
  });

  it("never re-includes a row the user excluded", () => {
    const base = toggleExclude(emptySelection(), "submission", "s1");
    const { selection, addedCount } = applyAiResult(base, { postIds: ["s1", "s2"] });
    expect(addedCount).toBe(1);
    expect(stateOf(selection, "submission", "s1")).toBe("excluded");
    expect(stateOf(selection, "submission", "s2")).toBe("included");
  });

  it("does not badge a row the user had already included by hand", () => {
    const base = toggleInclude(emptySelection(), "submission", "s1");
    const { selection, addedCount } = applyAiResult(base, { postIds: ["s1"] });
    expect(addedCount).toBe(0);
    expect(isAiAdded(selection, "submission", "s1")).toBe(false);
  });

  it("is additive across repeated runs", () => {
    const first = applyAiResult(emptySelection(), { postIds: ["s1"] }).selection;
    const { selection, addedCount } = applyAiResult(first, { postIds: ["s1", "s2"] });
    expect(addedCount).toBe(1);
    expect(counts(selection).included).toBe(2);
  });

  it("tolerates a missing or empty result", () => {
    expect(applyAiResult(emptySelection(), {}).addedCount).toBe(0);
    expect(applyAiResult(emptySelection()).addedCount).toBe(0);
  });
});

describe("splitByType / decidedIds / includedIds", () => {
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
});

describe("draft serialization", () => {
  it("namespaces the storage key per source database", () => {
    expect(draftStorageKey("proj_abc")).toBe("filterEditorDraft:proj_abc");
  });

  it("round-trips a selection through JSON", () => {
    let s = toggleInclude(emptySelection(), "submission", "s1");
    s = toggleExclude(s, "comment", "c1");
    s = applyAiResult(s, { postIds: ["s2"] }).selection;

    const restored = deserializeDraft(serializeDraft(s));
    expect(stateOf(restored, "submission", "s1")).toBe("included");
    expect(stateOf(restored, "comment", "c1")).toBe("excluded");
    expect(isAiAdded(restored, "submission", "s2")).toBe(true);
  });

  it("returns an empty selection for missing, malformed, or wrongly-typed input", () => {
    for (const raw of [null, "", "not json", "[1,2,3]", '"a string"', "42"]) {
      expect(counts(deserializeDraft(raw))).toEqual({
        included: 0,
        excluded: 0,
        aiAdded: 0,
      });
    }
  });

  it("ignores non-string entries in a stored draft", () => {
    const restored = deserializeDraft(
      JSON.stringify({ included: ["submission:s1", 42, null], excluded: "nope" }),
    );
    expect(counts(restored)).toEqual({ included: 1, excluded: 0, aiAdded: 0 });
  });

  it("resolves a key stored as both included and excluded in favour of included", () => {
    const restored = deserializeDraft(
      JSON.stringify({ included: ["submission:s1"], excluded: ["submission:s1"] }),
    );
    expect(stateOf(restored, "submission", "s1")).toBe("included");
    expect(counts(restored).excluded).toBe(0);
  });

  it("drops an AI badge on a row that is no longer included", () => {
    const restored = deserializeDraft(
      JSON.stringify({ included: [], excluded: [], aiAdded: ["submission:s1"] }),
    );
    expect(isAiAdded(restored, "submission", "s1")).toBe(false);
  });
});
