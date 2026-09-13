# Qualitative Coding Roadmap Audit

**Audited:** 2026-09-11 · **Status revised:** 2026-09-12
**Source:** `qualitative-coding-landscape-and-expansion.md`
**Code snapshot:** the 2026-09-11 audit, the completed pilot campaign, and the owner's declared comparison-restoration state on 2026-09-12
**Purpose:** turn the research document's expansion avenues into a smaller, dependency-aware engineering campaign.

## Executive decision

The source contains **83 numbered avenues**, not 90. They should not become independent coding tasks: several describe the same underlying capability, several are market choices rather than software work, and several would add complexity before prerequisite capabilities exist.

The original audit converted the source into **42 canonical implementation tickets**. The first campaign completed `QC-001`, `QC-002`, `QC-005`, `QC-006`, and `QC-007`; 37 tickets remain candidates for future work and must be rechecked against the current code before dispatch. `QC-002`'s original computed-cross-artifact contract was subsequently superseded by the implemented hybrid comparison design:

- deterministic codebook comparison belongs in version history and uses the established version-history comparison UI;
- deterministic coding version comparison remains in version history;
- LLM-powered comparison remains the cross-artifact workflow for both codebooks and codings;
- LLM comparison results are stored and viewable as files; and
- project export includes those comparison artifacts.

The retained backlog lives in `qualitative-coding-implementation-tickets.md`. Operational ticket state lives only in `qualitative-coding-ticket-status.md`. The reusable orchestration instructions live in `agent-worktree-orchestration-process.md`; `documentation/research/campaign/` stores per-run dispatch plans, reports, intermediate results, and verification evidence.

## Product rule used in the audit

Prioritize the product's defensible core: **human-authored, auditable, statistically honest AI-assisted qualitative coding**. Do not optimize for the largest feature count. Use deterministic comparison for facts grounded in a shared artifact's version history; use clearly labeled LLM output for interpretive comparison between separate artifacts. Keep both exportable and reviewable, reuse the existing version spine and three-pane editor patterns, and add no dependency where the standard library or an installed dependency is enough.

## Verified baseline

The campaign evidence and owner-declared comparison restoration support these current-state claims:

- The one-shot AI filter/codebook/apply routes are gone; the editors use preview-and-review flows.
- `CodingEntry.coder`/`coder_model` and `ArtifactAssist` exist, with service and test coverage.
- Evidence offsets, versioned artifact history, structural same-artifact diffs, row memos, retrieval filters, and code frequency counts exist.
- Deterministic CSV/JSON exports, analysis-ready long/wide coding layouts, code summaries, and a deterministic project bundle exist. The project bundle includes stored comparison artifacts under the restored comparison contract.
- Deterministic codebook and coding comparisons are version-history tools. Cross-artifact codebook and coding comparison is LLM-powered, stored as files, and viewable through the restored comparison views.
- A corpus coverage dashboard exists. Reliability metrics, saturation reports, team membership, generic document ingest, a PII workflow, and a configurable non-OpenRouter endpoint remain open.
- Job accounting distinguishes unknown values from zero, and partial/cancellation behavior has explicit tested semantics.
- Jobs persist status but their secret is process-local; startup deliberately fails orphaned jobs rather than resuming them.
- The live OpenRouter catalog now updates through `ai_models.set_catalog()`. The old GAP-9 wording is stale. The remaining reproducibility gap is the absence of a per-run catalog snapshot and complete generation parameters.

Future campaigns follow `agent-worktree-orchestration-process.md` and dispatch only tickets marked `Prepared` in `qualitative-coding-ticket-status.md`. The `main` and `overhaul/human-in-the-loop-interface` worktrees are read-only; all implementation and integration happens in isolated campaign worktrees.

## Priority definitions

| Priority | Meaning | Dispatch rule |
|---|---|---|
| P0 | Removes a present blocker or makes autonomous work safer | Pilot and first production wave |
| P1 | Core promise: publishable, measurable, durable, privacy-aware | Start after the pilot passes |
| P2 | Valuable extension with meaningful dependencies or integration risk | Start only when prerequisite tickets are merged |
| P3 | Large new market or research bet | Require owner approval and evidence before dispatch |

## Complete disposition of all 83 source avenues

Every source ID appears exactly once below. “Merged” means the idea is accepted but implemented through the named canonical ticket rather than as an independent change.

### Theme A — Methodological depth

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| A1 | Accept, P3 | `QC-025` second-cycle theme artifacts |
| A2 | Merge | `QC-026` framework matrix and crosstabs; shares the same read model as E3 |
| A3 | Accept, P0 | `QC-003` extend an existing artifact's row set |
| A4 | Accept, P1 | `QC-012` project research profile |
| A5 | Accept, P1 | `QC-017` disconfirming-evidence review |
| A6 | Accept, P1 | `QC-014` saturation ledger and report |
| A7 | Accept with reduced scope, P1 | `QC-013` recorded random/stratified/purposive sampling; embedding-based maximum variation is deferred with E8 |
| A8 | Defer | Add in-vivo mode only after `QC-024` method-guided workflows and user demand show that a prompt variant deserves permanent UI |
| A9 | Accept, P2 | `QC-024` method-guided workflows |
| A10 | Merge | `QC-018` REFI-QDA codebook interoperability; nesting is introduced only where `.qdc` round-trip requires it |

### Theme B — Rigor and validation

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| B1 | Done | Verified `coding_entries.coder`/`coder_model` plus rollup and tests |
| B2 | Merge | `QC-027` blind assignment and double-coding, together with F2 |
| B3 | Accept, P1 | `QC-015` reliability metrics engine |
| B4 | Merge | `QC-028` repeat-run and multi-model robustness workbench |
| B5 | Merge | `QC-028`; prompts become explicit experimental treatments |
| B6 | Merge | `QC-028`; identical-run stability is one mode of the same runner |
| B7 | Merge | `QC-016` gold-set import, designation, and scoring, together with D10 |
| B8 | Accept, P3 | `QC-041` corrected quantitative inference; requires validated math and gold sets |
| B9 | Replace, P2 | Do not store an LLM's self-reported confidence as truth. `QC-028` orders review by observed disagreement or instability; use provider log probabilities only if consistently available and calibrated |
| B10 | Merge | `QC-010` versioned AI execution manifest, together with C9, H10, and I4 |
| B11 | Accept, P2 | `QC-029` evaluation harness |
| B12 | Accept, P2 | `QC-030` bias and coverage diagnostics |

### Theme C — Transparency and reporting

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| C1 | Accept, P0 | `QC-004` project audit timeline |
| C2 | Done | Verified `artifact_assists`, trusted job-derived provenance, and tests |
| C3 | Merge | `QC-011` methods and disclosure report package |
| C4 | Merge | `QC-011`; one report engine with a TROUT-AI section |
| C5 | Merge | `QC-011`; one report engine with a short journal disclosure output |
| C6 | Merge | `QC-031` portable research bundle, together with D2 and C7 |
| C7 | Merge with narrower claim | `QC-031`; export the evidence chain and document its schema, but do not claim formal ATI compatibility without testing against a published machine-readable specification |
| C8 | Merge | `QC-032` scoped read-only review and peer debriefing |
| C9 | Merge | `QC-010` versioned AI execution manifest |
| C10 | Done | `QC-005` usage, call-count, duration, and cost accounting completed in the first campaign |

### Theme D — Interoperability and ingest

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| D1 | Accept, P1 | `QC-018` `.qdc` import/export |
| D2 | Merge | `QC-031` `.qdpx` and portable research bundle |
| D3 | Done | `QC-001` deterministic CSV/JSON and analysis-ready exports plus project bundle; XLSX remains deferred until a real consumer requires it |
| D4 | Accept, P3 | `QC-042` generic text-unit ingest |
| D5 | Defer | Build 4CAT/Communalytic adapters only after the generic text-unit model exists and a real export sample is available |
| D6 | Defer | Arctic Shift acquisition adds network, policy, and provenance surface before core import/export is complete |
| D7 | Defer | Audio/video transcription is a separate product surface and not part of the current advantage |
| D8 | Defer | Validate multilingual behavior on generic text first; do not build translation storage speculatively |
| D9 | Accept only the cheap half, P2 | `QC-037` document and harden the existing REST API. Defer a Python client until users repeat enough boilerplate to define one |
| D10 | Merge | `QC-016` gold-set and existing-coding import |

### Theme E — Analysis and visualization

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| E1 | Done | `QC-007` corpus coverage dashboard completed in the first campaign |
| E2 | Accept, P2 | `QC-035` code co-occurrence analysis |
| E3 | Merge | `QC-026` framework matrix and crosstabs |
| E4 | Accept with reduced scope, P2 | `QC-036` transparent time buckets and filters. No change-point algorithm until users ask for it and its assumptions can be shown |
| E5 | Merge | `QC-041` corrected quantitative inference; never present raw AI-coded counts as inferential estimates |
| E6 | Accept, P0 | `QC-008` quote bank and evidence shortlist |
| E7 | Accept, P1 | `QC-019` full-text search over source, evidence, and memos |
| E8 | Defer | Embeddings add infrastructure, cost, and a second retrieval model before basic full-text search is proven insufficient |
| E9 | Done through E1 | `QC-007`; density remains part of corpus coverage rather than its own subsystem |
| E10 | Superseded and implemented | `QC-002` now separates deterministic same-artifact version comparison from stored, viewable, exportable LLM cross-artifact comparison |

### Theme F — Collaboration

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| F1 | Accept, P2 | `QC-033` project membership and roles |
| F2 | Merge | `QC-027` blind assignment and double-coding |
| F3 | Accept, P2 | `QC-034` disagreement discussion and reconciliation log |
| F4 | Merge | `QC-032` scoped read-only review and peer debriefing |
| F5 | Defer | Requires `QC-016`, `QC-027`, and `QC-033`; reconsider when teams have completed real double-coding sessions |
| F6 | Defer | Shared libraries need teams, import/export, citation semantics, and governance; premature now |

### Theme G — Ethics and compliance

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| G1 | Accept, P1 | `QC-020` PII scan and reversible redaction |
| G2 | Accept with safety limits, P2 | `QC-039` publication-risk review. Never promise anonymity or silently generate a “safe” paraphrase |
| G3 | Accept, P0 | `QC-009` contextual ethics warnings |
| G4 | Merge | `QC-021` ethics and data-handling record |
| G5 | Accept, P1 | `QC-023` configurable OpenAI-compatible provider endpoint |
| G6 | Accept, P2 | `QC-038` retention and verified deletion |
| G7 | Merge | `QC-021` data acquisition, consent, terms, and ethics provenance |
| G8 | Merge | `QC-009` provider data-use disclosure at model selection time |

### Theme H — Positioning and adjacent markets

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| H1 | Owner decision, not an engineering ticket | Use as positioning guidance; do not let an agent rewrite marketing without a product-owner brief |
| H2 | Defer | Teaching mode depends on gold sets, reliability metrics, and teams |
| H3 | Defer | Systematic-review screening depends on generic text ingest and a separate reporting-standard audit |
| H4 | Defer | Policy consultation becomes a go-to-market validation after generic text ingest |
| H5 | Owner decision, not an engineering ticket | A market segment is not a code change |
| H6 | Reject for this campaign | Crowded, lower-rigor segment with no evidence it strengthens the product's advantage |
| H7 | Merge | Institutional readiness is `QC-023` plus `QC-033`; SSO is deferred until a buyer requires a specific protocol |
| H8 | Owner decision, not an engineering ticket | Licensing and business model require the repository owner's decision |
| H9 | Defer | Run a validation study only after `QC-015`, `QC-016`, and `QC-029` exist; it is a research project, not an autonomous feature ticket |
| H10 | Merge | `QC-010` versioned AI execution manifest; DOI publication is a later release operation |

### Theme I — Platform work

| Source | Decision | Canonical ticket or reason |
|---|---|---|
| I1 | Merge | `QC-022` durable and resumable jobs |
| I2 | Merge | `QC-022`; resumption without idempotent batch checkpoints is not acceptable |
| I3 | Accept with tight limits, P1 | `QC-040` exact-request deduplication. No semantic cache and no cross-user cache |
| I4 | Merge | `QC-010`; live catalog rebinding is already fixed, so only snapshots/parameters remain |
| I5 | Done | `QC-006` explicit partial-job failure semantics completed in the first campaign |
| I6 | Done through C10 | `QC-005` preflight call, cost, and time estimates completed in the first campaign |
| I7 | Merge conditionally | `QC-022`; streaming is scheduled only after durable checkpoints prove partial results can be resumed safely |

## Contradictions resolved

1. **IRR versus reflexive thematic analysis.** Reliability features are opt-in and method-aware. `QC-024` hides or warns against IRR where it is a methodological category error; `QC-015` never presents a universal “quality score.”
2. **Verbatim evidence versus participant safety.** Stored evidence remains exact for analytic integrity. Publication exports pass through `QC-039`, which labels redaction/paraphrase decisions without altering the source artifact.
3. **Reproducibility versus floating model catalogs.** The live catalog may refresh for selection, while `QC-010` freezes the chosen model slug, provider metadata snapshot, prompt version/hash, and generation parameters on each run.
4. **Human authorship versus AI provenance.** Keep `ArtifactVersion.origin` for authorship and `ArtifactAssist`/entry coder fields for assistance. Do not merge those channels.
5. **Broad export versus minimal dependencies.** Ship CSV and JSON with the standard library first. `.qdc`, `.qdpx`, and optional XLSX are subsequent formats with separate contract tests.
6. **Long autonomous jobs versus BYO secret handling.** `QC-022` must define a recoverable credential strategy before retrying work after restart. Never persist plaintext API keys in `jobs.payload`.

## Recommended sequence

Do not redispatch the completed pilot tickets: `QC-001`, `QC-002`, `QC-005`, `QC-006`, or `QC-007`. Before each new campaign, inspect the current code and remove any newly completed or redundant assignments from the retained ticket backlog.

1. **Core reporting and rigor:** `QC-003`, `QC-004`, `QC-010`–`QC-017`, `QC-019`–`QC-023`.
2. **Interop and methodology:** `QC-018`, `QC-024`–`QC-031`, `QC-035`–`QC-040`.
3. **Collaboration:** `QC-032`–`QC-034` only after the authorization design is reviewed as one coherent change.
4. **Large bets:** `QC-041` and `QC-042` only with explicit product-owner approval and validation plans.

Follow `agent-worktree-orchestration-process.md`: dispatch only two to four distinct Flash implementation worktrees per wave, prohibit overlapping or redundant feature assignments, and require Opus report review and two-state planning before Sonnet integration. A wave advances only after independent review and observed backend, frontend, migration, build, lint-baseline, and browser gates as applicable.
