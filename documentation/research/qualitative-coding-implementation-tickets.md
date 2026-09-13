# Qualitative Coding Implementation Tickets

**Prepared:** 2026-09-11  
**Input audit:** `qualitative-coding-roadmap-audit.md`  
**Use:** canonical backlog for a multi-agent implementation campaign

## Global definition of done

Every ticket must satisfy all of these in addition to its own acceptance checks:

- Preserve the async route → service → repository split; routes stay thin.
- Reuse existing models, versioning, editor-shell components, and utilities before adding abstractions.
- Add an Alembic revision for persistent schema changes and exercise it in the integration migration test.
- Add focused backend and/or colocated frontend regression tests.
- Run `.venv/bin/python -m pytest -q`, `cd frontend && npm run test:run`, `cd frontend && npm run lint`, and `cd frontend && npm run build` before integration. Run the PostgreSQL integration suite when a migration or PostgreSQL-specific query changes.
- Follow `documentation/style-guide.md`: square corners, black/white surfaces, existing `PageShell`/`Panel`/`uiClasses`, visible focus states, and no nested `Panel` borders.
- For a visible change, capture desktop and narrow-viewport screenshots of the changed state plus loading, empty, error, and keyboard-focus states where those exist.
- Update API, workflow, architecture, and tool documentation only where behavior changed.
- One ticket per commit using a Conventional Commit prefix. Never mix pre-existing user changes into the ticket commit.
- No new dependency without an explicit note proving the standard library, browser platform, and installed dependencies are insufficient.

## P0 — unblock use and prove the campaign

### QC-001 — CSV and JSON export foundation

- **Desired result:** an authenticated user can export a codebook, coding entries, row memos, and frequency summary from a selected current or historical version as UTF-8 CSV or JSON. Exports are deterministic and preserve stable IDs, row type/id, exact quote, offsets, code/coder provenance, and version metadata.
- **Affected area:** new export route/service under `backend/app/api/` and `backend/app/services/`; existing repositories/version reads; export actions on the relevant view pages; API/tool documentation.
- **Dependencies:** none. Use Python `csv`, `json`, and streaming/file responses; XLSX is out of scope.
- **Acceptance:** unauthorized or cross-owner refs fail; CSV opens with correct quoting/newlines; JSON validates against documented examples; historical export matches historical reads; empty artifacts export headers/metadata rather than erroring; focused route/service/UI tests pass.
- **Visual reference:** place an `Export` action in the `PageShell` toolbar of existing view pages, using the existing dropdown and button primitives; screenshot the menu and successful download state.

### QC-002 — Computed cross-artifact comparison

- **Desired result:** replace free-form LLM comparison as the default with deterministic codebook and coding comparisons: only-in-A/B, stable-identity matches, renamed/redefined/moved codes, per-code counts, applied/removed evidence, and a clear “unrelated histories” case. LLM semantic matching may be an explicit optional assist, never the source of computed facts.
- **Affected area:** `backend/app/core/codebook_diff.py`, `core/coding_diff.py`, comparison services/routes, comparison React components, old comparison docs/tests.
- **Dependencies:** none; reuse the existing same-artifact diff logic.
- **Acceptance:** fixture comparisons pin every result category; swapping A/B reverses directional fields; no model/API key is required for computed comparison; unrelated codebooks match only by documented rules; current comparison files remain readable or receive a documented migration path.
- **Visual reference:** reuse `CompareDualSelectPanel` and render a split results table in the existing comparison page; screenshot identical, divergent, and empty comparisons.

### QC-003 — Extend an existing artifact's row set

- **Desired result:** a researcher can add explicitly selected rows from a compatible source-data parent to an existing coding artifact as one new version without changing existing codings or memos.
- **Affected area:** coding schema/route/service, `raw_data_repo.copy_rows_by_id`, `memo_repo.copy_memos_by_id`, coding workspace selection UI, version/diff tests.
- **Dependencies:** none.
- **Acceptance:** duplicate IDs are no-ops; incompatible or unowned sources fail; existing coding entries and memos are byte-for-byte unchanged; new rows begin uncoded; version history and data diff record the addition; operation is atomic.
- **Visual reference:** a toolbar action opens the existing source/row selection pattern and previews “N new, M already present”; screenshot preview and completed state.

### QC-004 — Project audit timeline

- **Desired result:** a project-level chronological view combines artifact versions, lineage events, row-memo changes at their available timestamp granularity, and AI-assist records into a filterable audit trail.
- **Affected area:** version/assist/memo repositories, new read-model service and route, project page/timeline component.
- **Dependencies:** shipped `B1` and `C2` provenance.
- **Acceptance:** all events are owner-scoped, stably ordered, paginated, and link to the relevant file/version; AI assistance remains distinct from artifact authorship; filters by file/event/date work; empty projects render an empty state.
- **Visual reference:** `PageShell width="wide"` with one flat chronological list inside a single `Panel`; screenshot mixed-event, filtered, and empty states.

### QC-005 — Usage, call-count, duration, and cost accounting

- **Desired result:** before an AI assist, show estimated batches/calls, duration range, and cost when price metadata exists; after it, show actual calls, elapsed time, tokens, and provider-reported cost when available. Unknown values are labeled unknown, never displayed as zero.
- **Affected area:** OpenRouter client response handling, `Job`/assist metadata, context-window batching, model catalog, shared `AiAssistPanel`, job/result schemas.
- **Dependencies:** none.
- **Acceptance:** estimates are deterministic for fixture inputs; actual usage survives a page refresh; free/unknown pricing is represented honestly; no API key is persisted; tests cover missing provider usage and partial jobs.
- **Visual reference:** add a compact preflight line to `AiAssistPanel` and a post-run details disclosure; screenshot known-price and unknown-price states.

### QC-006 — Explicit partial-job semantics

- **Desired result:** every batched AI job returns a uniform status distinguishing complete success, usable partial result, retryable failure, permanent failure, and cancellation, with completed/total batch counts and a safe retry action.
- **Affected area:** jobs models/progress/service/routes, all registered job handlers, frontend polling/error components, API contracts.
- **Dependencies:** none.
- **Acceptance:** contract tests cover every terminal state; partial proposals are clearly labeled and never silently submitted as complete; retry targets only incomplete work where supported; auth/credit errors do not retry; old job records remain readable.
- **Visual reference:** reuse `ProgressBar`/`ErrorDisplay`; screenshot complete, partial, permanent-error, and retry states.

### QC-007 — Corpus coverage dashboard

- **Desired result:** the coding view reports share coded/uncoded, codes per row distribution, code-family rollups, and code-density buckets from computed data. It does not imply statistical representativeness.
- **Affected area:** coding repository/service response, coding workspace summary UI, pure calculation tests.
- **Dependencies:** none.
- **Acceptance:** counts reconcile exactly to the exported/live rows; zero-row and zero-code artifacts avoid division errors; historical versions show historical metrics; family totals handle renamed codes by stable UID.
- **Visual reference:** extend the current code-frequency sidebar with text-first bars/tables using existing per-code colors only; screenshot populated and empty states.

### QC-008 — Quote bank and evidence shortlist

- **Desired result:** researchers can browse one row per coded quote, filter by code/coder/search, star quotes for writing, attach/edit the existing quote note, and copy a citation containing configurable attribution fields.
- **Affected area:** coding read model/routes, a small persisted shortlist model if starring must survive, quote-bank React view, export integration.
- **Dependencies:** `QC-001` for exporting shortlisted evidence.
- **Acceptance:** exact source offsets remain inspectable in context; starring is owner-scoped and version behavior is documented; copy output never exposes author/URL unless chosen; filters are paginated; keyboard operation and focus are tested.
- **Visual reference:** add a Quote Bank view mode alongside existing coding views, using a flat list rather than another nested workspace; screenshot filtering, starred-only, source context, and focus states.

### QC-009 — Contextual ethics and provider notices

- **Desired result:** import and model-selection surfaces display concise, non-blocking notices when a corpus may involve sensitive communities and disclose the selected provider's known data-use/privacy metadata. Unknown provider policy is explicitly unknown.
- **Affected area:** import metadata, model catalog normalization, `AiModelFormGroup`, import/setup forms, documentation.
- **Dependencies:** none.
- **Acceptance:** warnings are driven by transparent rules and can be dismissed per project; no content is sent to a model to decide whether to warn; provider policy links/metadata have a checked timestamp; warnings never claim IRB approval or legal compliance.
- **Visual reference:** existing info/error alert styling only; screenshot a sensitive-corpus notice, unknown-provider notice, and keyboard dismissal.

## P1 — make the core reportable, measurable, durable, and private

### QC-010 — Versioned AI execution manifest

- **Desired result:** each AI run records an immutable prompt version/hash, selected model slug, a snapshot of relevant catalog/provider metadata, temperature and supported sampling parameters, batch hashes/counts, and response contract version. A user can inspect which artifacts used a prompt version.
- **Affected area:** `Prompt`, `Job`, `ArtifactVersion`/`ArtifactAssist`, prompt service/routes/UI, `ai_models.py`, migrations and provenance displays.
- **Dependencies:** none; live catalog refresh already works and must remain live for future selection.
- **Acceptance:** changing a prompt creates a new immutable version; old artifacts resolve the old version; secrets and full duplicated source batches are not stored; identical manifests hash identically; missing legacy fields render as unknown; tests prove `ArtifactVersion.origin` semantics remain unchanged.
- **Visual reference:** version history and prompt manager show compact version badges and a details disclosure; screenshot current and historical prompt use.

### QC-011 — Methods and disclosure report package

- **Desired result:** generate three deterministic drafts from project data: a Methods appendix, a 20-question TROUT-AI worksheet, and a short journal AI-use statement. Known facts are prefilled with source links; unknown researcher claims remain explicit blanks/questions.
- **Affected area:** new reporting service/route, project research profile, exports, version/assist/job reads, report view/download UI.
- **Dependencies:** `QC-001`, `QC-004`, `QC-005`, `QC-010`, `QC-012`; optionally include outputs from `QC-014` and `QC-015` when available.
- **Acceptance:** fixture projects produce stable snapshots; the generator never invents IRB approval, competence, consent, saturation, or reliability; every prefilled claim identifies its stored source; Markdown and JSON exports are supported; missing optional metrics degrade cleanly.
- **Visual reference:** `PageShell width="prose"` with checklist completion states and download actions; screenshot complete and incomplete reports.

### QC-012 — Project research profile

- **Desired result:** projects store the study tradition, unit of analysis, sampling/selection rationale, reflexivity/positionality statement, acquisition basis, ethics reference, and intended disclosure standard, all optional and editable with history of material changes.
- **Affected area:** `Project` model/migration, project schemas/service/routes, project setup/settings UI, audit timeline.
- **Dependencies:** none.
- **Acceptance:** blank profiles remain valid; only project members/owner under current auth can read/write; revisions appear in `QC-004`; the UI explains that fields are researcher assertions; API tests cover length and unsafe markup handling.
- **Visual reference:** a single research-profile `Panel` on the project page, grouped by method/ethics rather than a wizard; screenshot blank and completed states.

### QC-013 — Recorded sampling strategies

- **Desired result:** create or extend an artifact using random, stratified, or explicit purposive selection, with seed, strata/quotas, candidate frame, chosen IDs, and rationale recorded as provenance. Do not implement embedding diversity in this ticket.
- **Affected area:** raw-data repository sampling queries, request schemas/services, artifact metadata/manifest, setup forms.
- **Dependencies:** `QC-003`, `QC-012`.
- **Acceptance:** seeded random/stratified samples repeat; quotas and insufficient strata are explicit; purposive mode records explicit IDs without claiming randomness; invalid fields fail before mutation; PostgreSQL query tests cover large candidate frames.
- **Visual reference:** extend existing source setup with a compact strategy selector and conditional fields; screenshot random, stratified, and purposive configurations.

### QC-014 — Saturation ledger and report

- **Desired result:** record the order and corpus increment for codebook-assist passes, count accepted genuinely new codes and changed dimensions, plot cumulative code discovery, and generate separate, cautiously worded code- and meaning-saturation summaries.
- **Affected area:** codebook editor state/submission payload, `ArtifactAssist` or sibling analytic-event model, saturation service/route, codebook/project report UI.
- **Dependencies:** `QC-004`, `QC-010`, `QC-013` for defensible ordered sampling metadata.
- **Acceptance:** novelty is based on stable UID/accepted human decision, not raw model proposals; reordered or renamed codes do not count as new; users can mark a definition change as a new dimension; report shows observations rather than declaring universal saturation; unit tests pin curves.
- **Visual reference:** small cumulative step chart plus underlying run table; screenshot multiple runs and insufficient-data state.

### QC-015 — Reliability metrics engine

- **Desired result:** compute percent agreement, Cohen's kappa, Krippendorff's alpha, Fleiss' kappa where applicable, and Gwet's AC1 for aligned coder decisions, with per-code confusion/support tables and plain-language caveats.
- **Affected area:** new pure `core` statistics module, reliability service/route, comparison/report UI, fixtures with published or hand-calculated examples.
- **Dependencies:** shipped coder identity; `QC-024` later controls method-appropriate visibility.
- **Acceptance:** formulas match independent reference fixtures including missing data and skewed prevalence; alignment unit is explicit; undefined statistics display undefined with reason; no aggregate score is called validity/quality; no heavyweight statistics dependency without proof it is needed.
- **Visual reference:** results table with metric, value, support, and interpretation note; screenshot normal, kappa-paradox, and undefined cases.

### QC-016 — Existing-coding import, gold designation, and scoring

- **Desired result:** import a documented CSV/JSON coding schema, map its rows/codes to an owned corpus/codebook, preview all unmatched/invalid evidence, save accepted rows with imported coder identity, designate a frozen gold subset, and score AI/human runs against it.
- **Affected area:** import parser/core validation, coding services/repositories, small gold-set model/migration, import/reconciliation UI, reliability engine.
- **Dependencies:** `QC-001` defines the round-trip schema; `QC-015` supplies agreement metrics.
- **Acceptance:** export→import round-trip is lossless for supported fields; unmatched row/code/evidence never silently drops; duplicate imports are idempotent; gold revisions are immutable and traceable; scoring reports support and per-code precision/recall/F1.
- **Visual reference:** setup → mapping preview → exceptions → commit flow using existing form and review-tray patterns; screenshot clean and error-heavy imports.

### QC-017 — Disconfirming-evidence review

- **Desired result:** for a chosen code or theme claim, run an opt-in AI assist over a user-selected corpus subset to propose contradicting or boundary-challenging excerpts into a review tray; accepted items become labeled analytic notes, never automatic recoding.
- **Affected area:** coding/theme assist job, evidence verification, review tray/state, memo or a dedicated reviewed-evidence record.
- **Dependencies:** `QC-006`, `QC-010`; theme mode can extend after `QC-025`.
- **Acceptance:** all proposed quotes pass existing offset verification; the system prompt asks for counterevidence rather than agreement; accepted/dismissed counts enter assist provenance; no coding is changed; partial jobs are labeled.
- **Visual reference:** reuse the proposal tray within Quote Bank or coding workspace; screenshot proposed, accepted, and no-counterevidence states.

### QC-018 — REFI-QDA codebook `.qdc` interoperability

- **Desired result:** import and export `.qdc` codebooks with stable internal identity, labels, definitions/memos, color where representable, and hierarchy sufficient for lossless round-trip of supported fixtures.
- **Affected area:** new serializer/parser in `core`, codebook service/routes, code hierarchy model only where required, import/export UI, fixture files.
- **Dependencies:** `QC-001` export conventions. No arbitrary hierarchy abstraction beyond the standard's needs.
- **Acceptance:** validate against official/sample `.qdc` fixtures; import→export→import preserves supported semantics and order; unsupported elements produce a visible warning; XML parsing disables external entities; flat current codebooks export without schema migration if feasible.
- **Visual reference:** codebook toolbar Import/Export actions plus a mapping/warnings panel; screenshot clean import and unsupported-field warning.

### QC-019 — Full-text search over source, evidence, and memos

- **Desired result:** searchable source body/title, verified evidence text, and row memos with documented boolean syntax and highlighted matches; preserve current substring behavior as the simple default.
- **Affected area:** PostgreSQL indexes/query helpers in repositories, data/coding routes, shared row-list search UI, migration.
- **Dependencies:** none.
- **Acceptance:** search is owner/file scoped, parameterized, paginated, and deterministic; submission/comment collisions remain separate; tests cover phrases, boolean combinations, punctuation, empty queries, and memo/evidence matches; SQLite unit fallback and PostgreSQL integration behavior are both explicit.
- **Visual reference:** current search field gains a simple/advanced disclosure, not a new page; screenshot match highlighting and no-results state.

### QC-020 — PII scan and reversible redaction

- **Desired result:** optionally scan imported data for configured PII classes, present findings for human review, and create a redacted derived artifact while keeping the mapping encrypted or excluded according to project policy. Originals are never silently altered.
- **Affected area:** ingest post-processing, redaction core/service, derived-artifact lineage, project ethics settings, review UI, threat-model documentation.
- **Dependencies:** `QC-012`; coordinate with `QC-038` retention/deletion.
- **Acceptance:** deterministic detectors cover email, URL, handle, and configured usernames before any model use; every replacement is reviewed and traceable; source offsets in the redacted artifact are recomputed; permissions prevent mapping leakage; tests cover false-positive dismissal and repeated identity consistency.
- **Visual reference:** review tray showing source span, proposed class, replacement, accept/dismiss; screenshot mixed decisions and completed derived artifact.

### QC-021 — Ethics and data-handling record

- **Desired result:** generate an editable project record covering acquisition method/terms, consent basis, ethics/IRB reference, storage, model/provider exposure, retention, de-identification, and unresolved decisions; export it with reports.
- **Affected area:** project research profile, provider metadata, reporting/export services, project UI.
- **Dependencies:** `QC-009`, `QC-011`, `QC-012`, `QC-023`; integrate `QC-038` when available.
- **Acceptance:** system-known facts and researcher assertions are visually/source-distinct; unknowns remain unresolved; report reflects the provider actually used per run; no legal or ethics approval claim is generated automatically.
- **Visual reference:** use the report checklist pattern from `QC-011`; screenshot resolved and unresolved records.

### QC-022 — Durable, resumable, idempotent jobs

- **Desired result:** long batched jobs survive process restart, resume at the first incomplete batch, never duplicate accepted work, and expose cancellation. Credential recovery uses an approved secure strategy and never plaintext `jobs.payload`.
- **Affected area:** jobs model/service/runner/progress/registry, batch handlers, credential boundary, polling UI; streaming partial proposals may be added only after checkpoint semantics pass.
- **Dependencies:** `QC-006`, `QC-010`.
- **Acceptance:** kill/restart integration test resumes a fixture job; replaying a completed batch is a no-op by idempotency key; cancellation is terminal and safe; orphan reconciliation no longer discards resumable work; credentials are absent from logs/DB fixtures; partial output is tied to checkpoint IDs.
- **Visual reference:** existing progress UI gains resumed/cancelled labels; if streaming is included, proposals show a stable “partial” boundary; screenshot running, resumed, and cancelled states.

### QC-023 — Configurable OpenAI-compatible provider endpoint

- **Desired result:** a project/user can choose OpenRouter or a validated custom OpenAI-compatible base URL (for Ollama/vLLM/etc.), test connectivity, select a model, and see where data will be sent.
- **Affected area:** `external/openrouter_client.py` generalized to an OpenAI-compatible client, configuration storage, model selection, provider disclosure, tests with mocked endpoints.
- **Dependencies:** `QC-009`, `QC-010`; coordinate secret handling with `QC-022`.
- **Acceptance:** OpenRouter behavior remains unchanged; custom URL validation blocks unsafe schemes and does not leak credentials; provider choice is recorded per run; unavailable catalog endpoints allow a manually entered model; errors name the endpoint/provider without exposing secrets.
- **Visual reference:** extend `AiModelFormGroup` with provider selector and test status; screenshot OpenRouter, custom-connected, and failed-connect states.

### QC-024 — Method-guided workflows

- **Desired result:** the project's declared tradition configures labels, available stages, prompts, and methodological warnings without forking the whole application. Reflexive TA suppresses/reframes IRR; codebook content analysis enables it; framework method exposes the matrix when available.
- **Affected area:** project profile, small method-policy module, editor/navigation configuration, report templates, tests.
- **Dependencies:** `QC-012`, `QC-015`; integrates `QC-026` when shipped.
- **Acceptance:** policies are declarative and tested; changing method never deletes data; every hidden feature remains reachable after an explicit override with a caveat; unknown/custom method uses a neutral workflow; no separate page/component tree per method.
- **Visual reference:** project setting plus contextual one-line notices in existing pages; screenshot reflexive-TA and codebook workflows.

## P2 — methodological depth, interoperability, and collaboration

### QC-026 — Framework matrix and attribute crosstabs

- **Desired result:** a read-only matrix places configurable cases on rows and codes/themes on columns, with counts/excerpts in cells, drill-down, totals, and export; Reddit attributes work first through an explicit attribute registry.
- **Affected area:** new analysis read model/query service, route, matrix page/components, export integration.
- **Dependencies:** `QC-001`, `QC-007`; `QC-025` for theme columns, but code columns ship independently.
- **Acceptance:** totals reconcile with coding entries; sparse data is paginated/virtualized without loading the corpus at once; attributes are allow-listed and parameterized; empty cells and missing attributes are distinct; CSV export matches the visible filters.
- **Visual reference:** one scrollable table in an unpadded `Panel` with sticky row/column headers; screenshot dense, sparse, and drill-down states.

### QC-027 — Blind assignment and double-coding

- **Desired result:** project owners can assign a seeded subset to a second coder with prior decisions hidden, track completion, reveal only during reconciliation, and retain both immutable decision sets.
- **Affected area:** assignment/coder-decision models and migrations, authorization, coding workspace blind mode, reconciliation/read models.
- **Dependencies:** `QC-013`, `QC-015`, `QC-033`; an AI-as-second-coder pilot may precede human teams if isolation is real.
- **Acceptance:** hidden decisions are absent from API responses, not merely CSS-hidden; sample fraction/count is recorded; coders cannot overwrite each other; reveal is audited and irreversible for that round; metrics align the frozen decision sets.
- **Visual reference:** existing coding workspace with assignment progress and a blind-state notice; screenshot coder and owner views before/after reveal.

### QC-028 — Repeat-run and multi-model robustness workbench

- **Desired result:** run an identical or explicitly varied coding task across models, prompt versions, or repeats; compare decision stability; route disagreements to review ordered by observed disagreement, not an uncalibrated self-confidence score.
- **Affected area:** experiment manifest/model, fan-out job orchestration, comparison core, review tray, usage accounting.
- **Dependencies:** `QC-005`, `QC-010`, `QC-015`, `QC-022`.
- **Acceptance:** each treatment differs only in declared factors; repeated runs are independently stored; agreement and support reconcile to decisions; unanimous/majority labels are suggestions only; costs are shown before dispatch; cancellation leaves inspectable partial treatments.
- **Visual reference:** compact experiment setup and a disagreement-first results table; screenshot preflight, partial, and completed experiments.

### QC-029 — Evaluation harness

- **Desired result:** a small, versioned fixture corpus and expected codings can evaluate prompts/models offline or in an explicitly opt-in live suite, producing machine-readable regression results without making network calls in default CI.
- **Affected area:** `tests/backend/` fixtures, evaluation core/script, prompt manifest, documentation/CI configuration.
- **Dependencies:** `QC-010`, `QC-015`, `QC-016`.
- **Acceptance:** default tests are deterministic and offline; live evaluation requires an explicit marker/key; output includes dataset/prompt/model versions and per-code metrics; threshold changes require reviewed fixture evidence; no private corpus is committed.
- **Visual reference:** none; CLI/report artifact only.

### QC-030 — Bias and coverage diagnostics

- **Desired result:** show coding rate, evidence count, abstention/unmatched rate, and validation error by allowed corpus attributes and length buckets, with sample sizes and warnings against causal interpretation.
- **Affected area:** analysis query/service, reliability/gold data, dashboard/report UI.
- **Dependencies:** `QC-007`, `QC-013`, `QC-016`; use `QC-041` corrected estimates only when available.
- **Acceptance:** every subgroup displays denominator and missingness; small groups are suppressed or warned by documented rule; calculations match exported rows; attribute choice cannot inject SQL; output is descriptive unless corrected inference exists.
- **Visual reference:** tables and simple bars, no decorative charts; screenshot balanced, skewed, and insufficient-support cases.

### QC-031 — Portable research bundle (`.qdpx`, evidence, reproducibility)

- **Desired result:** export one deterministic archive containing a manifest, source or hashes/acquisition recipe, codebooks, codings/offsets, memos, audit/assist provenance, reports, and a validated `.qdpx` representation where supported. Include a documented claim→note→excerpt→source evidence file without claiming ATI conformance until proven.
- **Affected area:** export service, REFI serializer, manifest schema, archive streaming, project UI, fixture validators.
- **Dependencies:** `QC-001`, `QC-004`, `QC-010`, `QC-011`, `QC-018`, `QC-021`.
- **Acceptance:** archive order/timestamps are normalized for deterministic hashes; every manifest file hash verifies; source exclusion mode works for sensitive projects; `.qdpx` round-trips supported fixtures; large exports stream; no secret or plaintext redaction map appears.
- **Visual reference:** project Export Bundle dialog with content checklist and privacy warning; screenshot full and source-excluded configurations.

### QC-032 — Scoped read-only review and peer debriefing

- **Desired result:** owners can create revocable, expiring, least-privilege review links scoped to selected project files/versions, optionally with structured debrief questions and reviewer comments that cannot edit analytic data.
- **Affected area:** review-token model/migration, authorization dependency, read-only routes/views, comments/audit integration.
- **Dependencies:** `QC-004`, `QC-012`; coordinate with `QC-033` but external token review may ship independently.
- **Acceptance:** tokens are hashed at rest, time/file/version scoped, revocable, and excluded from logs; reviewer routes expose no unscoped project data; comments are attributed to the review session; security tests cover ID enumeration and expiry.
- **Visual reference:** reuse view pages in a clearly labeled read-only shell plus one debrief sidebar; screenshot owner link controls and reviewer view.

### QC-033 — Project membership and roles

- **Desired result:** projects support owner, analyst, reviewer, and read-only members with centralized authorization; existing single-owner projects migrate with their owner intact.
- **Affected area:** `Project`/`File` ownership model, membership migration/repository/service/routes, every `require_user_id` ownership call site, project/member UI.
- **Dependencies:** security design review before coding; `QC-004` audit events.
- **Acceptance:** a permission matrix is written first and enforced by shared helpers; cross-project/file access tests cover every route group; last owner cannot be removed; invites are scoped/expiring; migration preserves all current access; no worker independently edits auth call sites outside the integration owner's plan.
- **Visual reference:** one Members `Panel` on the project page; screenshot each role's available actions and forbidden state.

### QC-034 — Disagreement discussion and reconciliation log

- **Desired result:** coders can discuss a code/row disagreement, propose a resolution, record rationale, and close it without deleting either original decision; the resolution appears in audit/report exports.
- **Affected area:** reconciliation discussion models/routes, double-coding read model, row/quote UI, audit/export.
- **Dependencies:** `QC-004`, `QC-027`, `QC-033`.
- **Acceptance:** original decisions are immutable; edits append events; permissions separate participant/reviewer/owner actions; concurrent comments do not overwrite; resolved/reopened states and rationale export correctly.
- **Visual reference:** a single discussion drawer from the disagreement row; screenshot open, resolved, and keyboard-focus states.

### QC-035 — Code co-occurrence analysis

- **Desired result:** compute same-item, overlapping-span, and configurable proximity co-occurrence with support counts and filters; provide matrix first, network only if the matrix proves insufficient.
- **Affected area:** coding repository/query service, analysis route/page, export.
- **Dependencies:** `QC-001`, `QC-007`.
- **Acceptance:** symmetric counts and diagonal semantics are documented; offsets drive overlap/proximity; filters reconcile with source rows; large corpora use bounded queries; matrix export matches UI.
- **Visual reference:** sticky matrix in an unpadded `Panel`; defer interactive network visualization. Screenshot populated and sparse matrices.

### QC-036 — Transparent temporal trends

- **Desired result:** show code prevalence/count over explicit UTC time buckets with filters and denominators; no automatic change-point detection.
- **Affected area:** coding/data query service, analysis UI, export.
- **Dependencies:** `QC-001`, `QC-007`, `QC-013`; corrected inference can integrate after `QC-041`.
- **Acceptance:** bucket boundaries and timezone are visible; missing timestamps are counted separately; filtered totals reconcile; users can switch count/share; no trend is labeled significant without corrected inference.
- **Visual reference:** simple line/bar chart plus accessible data table; screenshot counts, shares, and missing-time state.

### QC-037 — Document and harden the existing REST API

- **Desired result:** publish a complete OpenAPI-backed usage guide for authentication, pagination, artifact/version refs, imports, exports, and jobs; add examples generated or tested against real schemas. Do not create a Python client yet.
- **Affected area:** FastAPI route metadata/schemas, `documentation/api-reference.md`, example scripts/tests.
- **Dependencies:** `QC-001`, `QC-006`; document later endpoints as they land.
- **Acceptance:** every public route has request/response/error documentation; examples pass in a smoke test; secrets use environment placeholders; pagination/version semantics are consistent; generated OpenAPI has no duplicate operation IDs.
- **Visual reference:** none.

### QC-038 — Retention and verified deletion

- **Desired result:** projects can declare retention metadata and owners can perform a previewed hard delete of project data, derived files, jobs, review tokens, and sensitive mappings with a verifiable deletion report. Automatic scheduled deletion is a later opt-in.
- **Affected area:** project/settings model, deletion service, foreign-key audit, security UI, docs/tests.
- **Dependencies:** `QC-012`, `QC-020`, `QC-021`, `QC-033` authorization.
- **Acceptance:** preview lists exact counts/types; deletion is owner-only and transactional where possible; shared/derived relationships are handled explicitly; a disposable integration DB proves no orphaned rows; recovery limits are clearly stated; no broad filesystem deletion is introduced.
- **Visual reference:** destructive confirmation modal using existing danger style, with typed project name and exact scope; screenshot preview and confirmation.

### QC-039 — Publication-risk review for evidence

- **Desired result:** before export/copy, flag verbatim evidence as potentially searchable, let a researcher choose omit, quote, redact, paraphrase, or label a composite vignette, and record that publication transformation separately from the analytic source.
- **Affected area:** quote bank, publication-export transform model/service, ethics report, UI.
- **Dependencies:** `QC-008`, `QC-020`, `QC-021`.
- **Acceptance:** original evidence never changes; transformations are human-confirmed and labeled in output; the tool never promises anonymity; no web search sends sensitive text without explicit case-by-case consent; audit records who chose what and why.
- **Visual reference:** publication-review tray with original/context on one side and selected output treatment on the other; screenshot each treatment label.

### QC-040 — Exact-request AI deduplication

- **Desired result:** within one user/project privacy boundary, an identical model/provider, execution manifest, prompt hash, source-version hash, and response-contract hash can reuse a completed successful response; all other cases execute normally.
- **Affected area:** job enqueue/service, execution manifest, result storage/retention, usage UI.
- **Dependencies:** `QC-005`, `QC-010`, `QC-022`.
- **Acceptance:** cross-user and cross-project reuse is impossible; partial/failed/cancelled results never cache; cache hits record provenance and zero new provider usage; invalidation follows any input/version/parameter change; sensitive-project policy can disable reuse; no semantic similarity cache.
- **Visual reference:** one “reused prior identical run” status line in existing progress/result UI; no cache-management page.

## P3 — explicit approval required

### QC-025 — Second-cycle theme artifacts

- **Desired result:** introduce a versioned `theme` artifact connecting codes to categories/themes, with definition, boundary conditions, analytic memo, and exemplar evidence; AI may propose, while humans accept/edit/dismiss and author the saved artifact.
- **Affected area:** file/artifact types, version storage/edges, theme service/routes, new editor reusing codebook proposal patterns, lineage/report/export support.
- **Dependencies:** `QC-008`, `QC-010`, `QC-017`, `QC-024`, `QC-031` export design.
- **Acceptance:** stable theme/category IDs survive rename/reorder; every exemplar resolves to an owned verified quote; source codebook/coding versions are pinned; AI assistance uses the separate provenance channel; recursive review is supported without claiming themes “emerged.”
- **Visual reference:** three-pane editor with code/evidence source left, theme builder center, AI assist right; produce desktop/narrow screenshots before merge.

### QC-041 — Corrected quantitative inference

- **Desired result:** implement a reviewed design-based/prediction-powered estimator over AI-coded populations plus randomized expert-labeled samples, returning corrected prevalence/differences and confidence intervals with assumptions and diagnostics.
- **Affected area:** isolated pure statistics module, gold/sampling services, analysis/report UI, reference validation fixtures.
- **Dependencies:** `QC-013`, `QC-015`, `QC-016`, `QC-029`, `QC-030`.
- **Acceptance:** formulas and intervals match published reference code or independently reproduced fixtures; random sampling design is enforced/recorded; raw and corrected estimates are clearly distinguished; unsupported designs fail closed; a qualified statistical reviewer approves before release.
- **Visual reference:** estimate table with raw, corrected, interval, validation n, and assumptions; charts are secondary.

### QC-042 — Generic text-unit ingest

- **Desired result:** generalize the pipeline from Reddit submissions/comments to versioned text units with source document, participant/case, speaker, sequence, text, and optional attributes; import TXT and mapped CSV first. PDF/DOCX/audio remain out of scope.
- **Affected area:** storage/migration, item-type abstraction, all data/coding repositories/services, import UI, evidence offsets, exports, tests.
- **Dependencies:** `QC-001`, `QC-003`, `QC-013`, `QC-019`, `QC-031`; architecture review required.
- **Acceptance:** existing Reddit flows and historical artifacts remain compatible; TXT/CSV round-trip through coding/export; stable text-unit IDs and offsets survive derivation; mapping preview rejects ambiguous rows; a migration/backfill plan is proven on a disposable PostgreSQL database.
- **Visual reference:** import mapper reusing the two-step form/editor language; screenshot TXT, clean CSV mapping, and invalid mapping.

## Pilot wave

The first autonomous wave is deliberately five tickets:

1. `QC-001` CSV/JSON export
2. `QC-002` computed comparison
3. `QC-005` usage/cost accounting
4. `QC-006` partial-job semantics
5. `QC-007` coverage dashboard

Assign one worker per ticket only after an integration lead establishes non-overlapping file ownership. If `QC-005` and `QC-006` overlap in the job/client contract, sequence them or give both to one worker. Promote beyond the pilot only if at least four of five tickets meet acceptance without regressions and the integration reviewer can explain every residual failure.
