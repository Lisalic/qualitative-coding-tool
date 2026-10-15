import { describe, expect, it } from "vitest";
import {
  acceptAll,
  acceptProposal,
  addProposals,
  buildAssistRunsForSubmit,
  codeKey,
  copySourceCode,
  counts,
  deserializeDraft,
  dismissAll,
  dismissProposal,
  draftKeys,
  draftStorageKey,
  emptyState,
  existingCodeRefs,
  integrateDraftStorageKey,
  isAiAccepted,
  seedDraftFromTree,
  serializeDraft,
  setDraft,
} from "../codebookEditorState";

const proposal = (name, familyName = "Harm", extra = {}) => ({
  name,
  family_name: familyName,
  definition: `${name} definition`,
  ...extra,
});

/** A merge proposal (integrate editor), carrying source provenance. */
const mergeProposal = (name, sources, extra = {}) =>
  proposal(name, "Harm", { sources, rationale: sources.length > 1 ? "merged" : "", ...extra });

const sourceCode = (name, familyName = "Harm", extra = {}) => ({
  name,
  family_name: familyName,
  definition: `${name} definition`,
  ...extra,
});

/** A draft tree as it comes back from an existing codebook: real uids, no
 * `is_new` anywhere. */
const existingTree = [
  {
    family_uid: "fam-1",
    family_name: "Harm",
    codes: [
      { code_uid: "code-1", family_uid: "fam-1", family_name: "Harm", name: "Bullying" },
    ],
  },
];

describe("codeKey", () => {
  it("normalizes case and surrounding whitespace", () => {
    expect(codeKey("  Harm ", "Bullying")).toBe(codeKey("harm", "  bullying"));
  });

  it("does not collide when a name contains the other field's text", () => {
    // A space separator would make ("a b", "c") and ("a", "b c") identical.
    expect(codeKey("a b", "c")).not.toBe(codeKey("a", "b c"));
  });

  it("treats the same code name in different families as distinct", () => {
    expect(codeKey("Harm", "Support")).not.toBe(codeKey("Coping", "Support"));
  });
});

describe("addProposals", () => {
  it("puts proposals in the tray and never in the draft", () => {
    const seeded = seedDraftFromTree(emptyState(), existingTree);
    const { state, addedCount } = addProposals(seeded, [proposal("Exclusion")]);

    expect(addedCount).toBe(1);
    expect(state.proposals).toHaveLength(1);
    expect(counts(state).draft).toBe(1);
    expect(draftKeys(state.draft).has(codeKey("Harm", "Exclusion"))).toBe(false);
  });

  it("skips a proposal already covered by a draft code", () => {
    const seeded = seedDraftFromTree(emptyState(), existingTree);
    const { state, addedCount, skippedCount } = addProposals(seeded, [
      proposal("bullying"),
      proposal("Exclusion"),
    ]);

    expect(addedCount).toBe(1);
    expect(skippedCount).toBe(1);
    expect(state.proposals.map((entry) => entry.name)).toEqual(["Exclusion"]);
  });

  it("skips a duplicate within one run and across two runs", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion"), proposal("Exclusion")]);
    expect(first.addedCount).toBe(1);
    expect(first.skippedCount).toBe(1);

    const second = addProposals(first.state, [proposal("Exclusion")]);
    expect(second.addedCount).toBe(0);
    expect(second.state.proposals).toHaveLength(1);
  });

  it("never re-offers a dismissed proposal", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion")]);
    const dismissed = dismissProposal(first.state, first.state.proposals[0].key);

    const second = addProposals(dismissed, [proposal("Exclusion")]);
    expect(second.addedCount).toBe(0);
    expect(second.state.proposals).toHaveLength(0);
  });

  it("never re-offers a code accepted in an earlier run", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion")]);
    const accepted = acceptProposal(first.state, first.state.proposals[0].key);

    const second = addProposals(accepted, [proposal("Exclusion")]);
    expect(second.addedCount).toBe(0);
    expect(second.skippedCount).toBe(1);
  });

  it("ignores an entry with no name", () => {
    const { state, addedCount } = addProposals(emptyState(), [{ name: "   " }, null]);
    expect(addedCount).toBe(0);
    expect(state.proposals).toHaveLength(0);
  });
});

describe("acceptProposal", () => {
  it("mints identity and marks the code as new", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion")]);
    const state = acceptProposal(first.state, first.state.proposals[0].key);

    const code = state.draft[0].codes[0];
    expect(code.name).toBe("Exclusion");
    expect(code.code_uid).toMatch(/^[0-9a-f]{32}$/);
    expect(code.is_new).toBe(true);
    expect(state.proposals).toHaveLength(0);
  });

  it("reuses an existing family's uid rather than minting a second family", () => {
    const seeded = seedDraftFromTree(emptyState(), existingTree);
    const first = addProposals(seeded, [proposal("Exclusion", "Harm")]);
    const state = acceptProposal(first.state, first.state.proposals[0].key);

    expect(state.draft).toHaveLength(1);
    const [family] = state.draft;
    expect(family.family_uid).toBe("fam-1");
    expect(family.family_is_new).toBeUndefined();
    expect(family.codes.map((code) => code.name)).toEqual(["Bullying", "Exclusion"]);
    expect(family.codes[1].family_uid).toBe("fam-1");
  });

  it("mints a family flagged as new when the family does not exist yet", () => {
    const first = addProposals(emptyState(), [proposal("Denial", "Coping")]);
    const state = acceptProposal(first.state, first.state.proposals[0].key);

    const [family] = state.draft;
    expect(family.family_name).toBe("Coping");
    expect(family.family_is_new).toBe(true);
    expect(family.codes[0].family_uid).toBe(family.family_uid);
  });

  it("gives two proposals in one family a single shared family_uid", () => {
    const first = addProposals(emptyState(), [
      proposal("Denial", "Coping"),
      proposal("Avoidance", "Coping"),
    ]);
    const state = acceptAll(first.state);

    expect(state.draft).toHaveLength(1);
    const uids = new Set(state.draft[0].codes.map((code) => code.family_uid));
    expect(uids.size).toBe(1);
  });

  it("does nothing for an unknown key", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion")]);
    expect(acceptProposal(first.state, "no-such-key")).toEqual(first.state);
  });
});

describe("AI provenance", () => {
  it("badges an accepted code and survives a draft edit", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion")]);
    const accepted = acceptProposal(first.state, first.state.proposals[0].key);
    const uid = accepted.draft[0].codes[0].code_uid;

    expect(isAiAccepted(accepted, uid)).toBe(true);
    expect(counts(accepted).aiAccepted).toBe(1);

    // Editing the tree round-trips through cloneCodebookTree, which
    // whitelists fields -- the badge must not be lost by that.
    const edited = setDraft(accepted, accepted.draft);
    expect(isAiAccepted(edited, uid)).toBe(true);
  });

  it("does not badge a hand-written code", () => {
    const seeded = seedDraftFromTree(emptyState(), existingTree);
    expect(isAiAccepted(seeded, "code-1")).toBe(false);
    expect(counts(seeded).aiAccepted).toBe(0);
  });
});

describe("addProposals -- merge provenance", () => {
  it("carries sources and rationale onto the tray entry", () => {
    const sources = [{ codebook: "proj_a", family_name: "Harm", name: "Bullying" }];
    const { state } = addProposals(emptyState(), [mergeProposal("Merged", sources)]);
    expect(state.proposals[0].sources).toEqual(sources);
    expect(state.proposals[0].rationale).toBe("");
  });

  it("defaults sources to an empty array and rationale to null when absent", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion")]);
    expect(state.proposals[0].sources).toEqual([]);
    expect(state.proposals[0].rationale).toBeNull();
  });

  it("ignores a non-array sources value", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion", "Harm", { sources: "not-an-array" })]);
    expect(state.proposals[0].sources).toEqual([]);
  });
});

describe("acceptProposal -- accepting a merge does not write sources onto the draft", () => {
  it("does not write sources onto the accepted draft node", () => {
    const sources = [{ codebook: "proj_a", family_name: "Harm", name: "Bullying" }];
    const first = addProposals(emptyState(), [mergeProposal("Merged", sources)]);
    const state = acceptProposal(first.state, first.state.proposals[0].key);
    expect(state.draft[0].codes[0].sources).toBeUndefined();
  });
});

describe("copySourceCode", () => {
  it("mints a fresh code_uid distinct from the source's own identity", () => {
    const state = copySourceCode(emptyState(), sourceCode("Bullying"));
    const code = state.draft[0].codes[0];
    expect(code.code_uid).toMatch(/^[0-9a-f]{32}$/);
    expect(code.is_new).toBe(true);
    expect(code.name).toBe("Bullying");
  });

  it("reuses an existing same-named family's uid", () => {
    const seeded = seedDraftFromTree(emptyState(), existingTree);
    const state = copySourceCode(seeded, sourceCode("Exclusion", "Harm"));
    expect(state.draft).toHaveLength(1);
    expect(state.draft[0].family_uid).toBe("fam-1");
  });

  it("does not add the copied code to aiAccepted", () => {
    const state = copySourceCode(emptyState(), sourceCode("Bullying"));
    const code = state.draft[0].codes[0];
    expect(isAiAccepted(state, code.code_uid)).toBe(false);
  });

  it("does not add a duplicate when the same (family, name) is already in the draft", () => {
    const first = copySourceCode(emptyState(), sourceCode("Bullying", "Harm"));
    const second = copySourceCode(first, sourceCode("Bullying", "Harm"));
    expect(second).toBe(first);
    expect(second.draft[0].codes).toHaveLength(1);
  });

  it("the duplicate check is case/whitespace-insensitive, like codeKey", () => {
    const first = copySourceCode(emptyState(), sourceCode("Bullying", "Harm"));
    const second = copySourceCode(first, sourceCode("  bullying  ", " HARM "));
    expect(second.draft[0].codes).toHaveLength(1);
  });

  it("a code with the same name but a different family is not a duplicate", () => {
    const first = copySourceCode(emptyState(), sourceCode("Worry", "Harm"));
    const second = copySourceCode(first, sourceCode("Worry", "Coping"));
    expect(second.draft).toHaveLength(2);
  });

  it("re-adding after the copied code was deleted from the draft is allowed", () => {
    // The whole point of dropping the persistent "covered" flag: once a
    // code leaves the draft, re-adding its source must work again rather
    // than being silently blocked by stale bookkeeping.
    const added = copySourceCode(emptyState(), sourceCode("Bullying", "Harm"));
    const deleted = setDraft(added, []);
    const readded = copySourceCode(deleted, sourceCode("Bullying", "Harm"));
    expect(readded.draft[0].codes).toHaveLength(1);
  });
});

describe("integrateDraftStorageKey", () => {
  it("is order-independent over the same set of codebooks", () => {
    expect(integrateDraftStorageKey(["proj_b", "proj_a"])).toBe(
      integrateDraftStorageKey(["proj_a", "proj_b"]),
    );
  });

  it("dedupes repeated refs", () => {
    expect(integrateDraftStorageKey(["proj_a", "proj_a", "proj_b"])).toBe(
      integrateDraftStorageKey(["proj_a", "proj_b"]),
    );
  });

  it("differs for a different set of codebooks", () => {
    expect(integrateDraftStorageKey(["proj_a", "proj_b"])).not.toBe(
      integrateDraftStorageKey(["proj_a", "proj_c"]),
    );
  });
});

describe("assistRuns / buildAssistRunsForSubmit", () => {
  it("records nothing when addProposals is called with no jobId", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion")]);
    expect(buildAssistRunsForSubmit(state)).toEqual([]);
  });

  it("records a run and counts an accepted proposal by its minted code_uid", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion")], 7);
    const key = state.proposals[0].key;
    const accepted = acceptProposal(state, key);
    const uid = accepted.draft[0].codes[0].code_uid;

    const runs = buildAssistRunsForSubmit(accepted);
    expect(runs).toEqual([
      { job_id: 7, proposed_count: 1, accepted_count: 1, dismissed_count: 0, accepted_refs: [uid] },
    ]);
  });

  it("a proposal left in the tray at submit time counts as dismissed", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion"), proposal("Denial")], 7);
    const [run] = buildAssistRunsForSubmit(state);
    expect(run.proposed_count).toBe(2);
    expect(run.accepted_count).toBe(0);
    expect(run.dismissed_count).toBe(2);
  });

  it("an explicitly dismissed proposal counts as dismissed", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion")], 7);
    const dismissed = dismissProposal(state, state.proposals[0].key);
    const [run] = buildAssistRunsForSubmit(dismissed);
    expect(run.accepted_count).toBe(0);
    expect(run.dismissed_count).toBe(1);
  });

  it("skipped (duplicate) proposals never enter a run", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion")], 1);
    const second = addProposals(first.state, [proposal("Exclusion")], 2);
    expect(second.skippedCount).toBe(1);
    expect(buildAssistRunsForSubmit(second.state)).toHaveLength(1);
  });

  it("survives a serialize/deserialize round-trip", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion")], 7);
    const accepted = acceptProposal(state, state.proposals[0].key);
    const restored = deserializeDraft(serializeDraft(accepted));
    expect(buildAssistRunsForSubmit(restored)).toEqual(buildAssistRunsForSubmit(accepted));
  });

  it("seedDraftFromTree clears assist provenance along with proposals", () => {
    const { state } = addProposals(emptyState(), [proposal("Exclusion")], 7);
    const seeded = seedDraftFromTree(state, existingTree);
    expect(buildAssistRunsForSubmit(seeded)).toEqual([]);
  });
});

describe("dismissAll", () => {
  it("empties the tray and remembers every key", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion"), proposal("Denial")]);
    const state = dismissAll(first.state);

    expect(state.proposals).toHaveLength(0);
    expect(counts(state).dismissed).toBe(2);
    expect(addProposals(state, [proposal("Denial")]).addedCount).toBe(0);
  });
});

describe("seedDraftFromTree", () => {
  it("carries real identity through and never marks a code as new", () => {
    const state = seedDraftFromTree(emptyState(), existingTree);
    const code = state.draft[0].codes[0];

    expect(code.code_uid).toBe("code-1");
    expect(code.family_uid).toBe("fam-1");
    expect(code.is_new).toBeUndefined();
    expect(state.draft[0].family_is_new).toBeUndefined();
  });

  it("clears proposals and dismissals from the previous target", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion")]);
    const dismissed = dismissProposal(first.state, first.state.proposals[0].key);
    const state = seedDraftFromTree(dismissed, existingTree);

    expect(state.proposals).toHaveLength(0);
    expect(counts(state).dismissed).toBe(0);
  });
});

describe("existingCodeRefs", () => {
  it("sends family, name and definition only", () => {
    const seeded = seedDraftFromTree(emptyState(), existingTree);
    expect(existingCodeRefs(seeded)).toEqual([
      { family_name: "Harm", name: "Bullying", definition: null },
    ]);
  });

  it("skips a code with no name yet", () => {
    const state = setDraft(emptyState(), [
      { family_uid: "f", family_name: "Harm", codes: [{ code_uid: "c", name: "  " }] },
    ]);
    expect(existingCodeRefs(state)).toEqual([]);
  });
});

describe("draftStorageKey", () => {
  it("separates the New target from a Refine target on the same source", () => {
    expect(draftStorageKey("proj_a")).not.toBe(draftStorageKey("proj_a", "proj_b"));
  });
});

describe("serializeDraft / deserializeDraft", () => {
  it("round-trips draft, tray, dismissals and badges", () => {
    const first = addProposals(emptyState(), [proposal("Exclusion"), proposal("Denial")]);
    const accepted = acceptProposal(first.state, first.state.proposals[0].key);
    const state = dismissProposal(accepted, accepted.proposals[0].key);

    const restored = deserializeDraft(serializeDraft(state));
    expect(restored.draft).toEqual(state.draft);
    expect(restored.proposals).toEqual(state.proposals);
    expect([...restored.dismissed]).toEqual([...state.dismissed]);
    expect([...restored.aiAccepted]).toEqual([...state.aiAccepted]);
  });

  it("degrades to an empty state on anything malformed", () => {
    expect(deserializeDraft(null)).toEqual(emptyState());
    expect(deserializeDraft("{not json")).toEqual(emptyState());
    expect(deserializeDraft('"a string"')).toEqual(emptyState());
    expect(deserializeDraft("[1,2,3]")).toEqual(emptyState());
  });

  it("drops a stored proposal that the draft now covers", () => {
    const raw = JSON.stringify({
      draft: existingTree,
      proposals: [{ name: "Bullying", family_name: "Harm" }],
      dismissed: [],
    });
    expect(deserializeDraft(raw).proposals).toHaveLength(0);
  });

  it("drops a stored proposal that was already dismissed", () => {
    const raw = JSON.stringify({
      draft: [],
      proposals: [{ name: "Denial", family_name: "Coping" }],
      dismissed: [codeKey("Coping", "Denial")],
    });
    expect(deserializeDraft(raw).proposals).toHaveLength(0);
  });

  it("drops a badge for a code no longer in the draft", () => {
    const raw = JSON.stringify({
      draft: existingTree,
      proposals: [],
      dismissed: [],
      aiAccepted: ["code-1", "gone-uid"],
    });
    expect([...deserializeDraft(raw).aiAccepted]).toEqual(["code-1"]);
  });

  it("round-trips an open proposal's sources and rationale", () => {
    const sources = [{ codebook: "proj_a", family_name: "Harm", name: "Bullying" }];
    const { state } = addProposals(emptyState(), [mergeProposal("Merged", sources)]);

    const restored = deserializeDraft(serializeDraft(state));
    expect(restored.proposals[0].sources).toEqual(sources);
    expect(restored.proposals[0].rationale).toBe(state.proposals[0].rationale);
  });

  it("drops a malformed sources entry on a restored proposal", () => {
    const raw = JSON.stringify({
      draft: [],
      proposals: [
        {
          name: "Merged",
          family_name: "Harm",
          sources: [
            { codebook: "proj_a", name: "Bullying" },
            { codebook: 123, name: "Bad" },
            { codebook: "proj_b" },
          ],
        },
      ],
      dismissed: [],
    });
    expect(deserializeDraft(raw).proposals[0].sources).toEqual([
      { codebook: "proj_a", name: "Bullying" },
    ]);
  });
});
