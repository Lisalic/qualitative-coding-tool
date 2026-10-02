# Integrate Codebook

## Purpose

Merge two or more existing codebooks into one, with an AI assistant that proposes merged codes (each showing which source code(s) it came from) for human-in-the-loop review — accept, dismiss, edit, or hand-copy a source code the assistant missed — before saving a normal `codebook` artifact.

## Where to find it

Sidebar → Integrate Codebook (pipeline group, right after Compare Codebook), or `/integrate-codebook` → `pages/IntegrateCodebook.jsx` → `components/integrate-codebook/IntegrateCodebookEditor.jsx`. Also reachable from View Codebook's "Integrate" toolbar button, which preselects the codebook being viewed.

Structurally this is a third mode of the same editor pattern as [Codebook](codebook.md) (a setup step, then a 3-pane workspace built on `EditorWorkspace`/`EditorSetupStep`), not a variant of [Compare Codebooks](compare-codebooks.md) — the AI here is an in-workspace assistant whose proposals land in a review tray, not a one-shot job that writes prose.

## Prerequisites

At least two codebook artifacts (a `codebook_comparison` cannot be selected). An OpenRouter API key in the navbar, only needed to run the AI assistant — the workspace itself, and hand-copying source codes, need no key.

## Inputs

**Setup step**

| Field | Required | Notes |
|---|---|---|
| Source codebooks | yes, 2+ | searchable card grid of every codebook owned by the user (`IntegrateSourcePicker.jsx`); selections also collect into a removable chip strip above the grid |
| Codebook name | yes | non-blank |
| Description | no | |
| Project | yes | every artifact belongs to one |

**Workspace (AI assist panel)**

| Field | Required | Notes |
|---|---|---|
| Your suggestions | no | the researcher's own merge suggestions (codes to keep separate, rename, combine) |
| AI Model | no | |
| Comparison | no | set from the rail's Comparison tab ("Use this comparison to guide the AI merge"); sent as `comparisons: [cmp_…]` |

No sample-size or content-scope controls — nothing is sampled; the assistant reads every source codebook in full.

**Workspace (right rail)**

The rail has two tabs: **Code** (the full text of the source code last clicked in the left pane) and **Comparison**. The Comparison tab lists every [Compare Codebooks](compare-codebooks.md) report made from the selected sources — found through each source's `GET /api/artifacts/{ref}/lineage` children, reports covering two or more of the sources first — and renders the chosen one. When a report covers the selection the workspace opens on it, since compare-then-integrate is the intended workflow. With "Use this comparison to guide the AI merge" ticked, the report's text goes to the model after the source codebooks and before the researcher's suggestions, as guidance only: proposals must still cite the codebooks themselves.

## What happens on submit

Two independent calls, mirroring [Codebook](codebook.md)'s preview/manual pair:

- **AI assist** (`job_type="integrate_codebook_preview"`, re-runnable any number of times): `buildIntegratePreviewPayload` → `postJsonAndPoll` → `POST /api/integrate-codebook-preview/` → `202 {job_id, status}` → poll. Server-side (`backend/app/services/codebook_service.py::_run_integrate_codebook_job`): reads every source codebook's content (sealing each one's head via `version_service.pin_parent` first), plus any `comparisons` (each ownership- and type-checked as a `codebook_comparison` by `_resolve_comparisons`, and pinned the same way), asks the LLM to merge them (`backend/scripts/codebook_generator.py::integrate_codebooks`, one call — no batching, since a merge is inherently over every source at once), verifies each proposal's claimed sources against the codebooks actually read (`_verify_proposal_sources`, dropping anything the model invented), and drops any proposal already covered by the researcher's current draft (sent as `existing_codes`). Creates nothing — a proposal is not an artifact.
- **Submit** (synchronous, no LLM call): `flattenTreeToCodes` → `buildIntegrateCodebookPayload` → `POST /api/codebook/integrate` → `backend/app/services/codebook_service.py::create_integrated_codebook` → `_materialize_codebook` with N `merged_from`/`merge_input` `artifact_edges` (one per source codebook, in selection order) → `origin=edited`, no model provenance on the version. AI-assist contribution (if any) is recorded separately via `assist_service.record_assist_runs(stage="integrate")`.

Every accepted or hand-added code mints a **fresh** `code_uid`/`family_uid` on the client — never a source codebook's own identity, since the merged codebook is a new artifact and a code merged from several sources cannot honestly wear one source's uid. Per-code merge provenance stays recoverable via that run's `artifact_assists.accepted_refs` → its `job_id` → the job's `result.proposals[].sources`.

The left pane's "Add" button (`IntegrateSourcePane.jsx`) guards against adding an exact duplicate of a code already in the draft, checked fresh against the current draft on every click rather than a stored flag — an earlier version instead set a persistent "merged" badge on accept/add that never cleared, which drifted from the truth the moment a code was renamed, merged further, or deleted from the draft. There is no such badge now; the footer shows a live draft-size count instead.

## Output

`POST /codebook/integrate` returns `{message, file: {id, schema_name, filename, description, version_no}}`. The success banner links to [View Codebook](view-codebook.md) with the new codebook's schema passed as `state.selected`. The result is an ordinary `codebook` — usable immediately by Apply Codebook, Compare Codebook, or the Create Codebook editor's Refine mode, with no conversion step.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Select at least two distinct codebooks to integrate" | Fewer than two (or duplicate) codebooks selected |
| "API key not set. Please set your API key in the navbar." | No `localStorage.apiKey`, only affects the AI assist panel |
| A proposal reads "No matching source code — the assistant may have invented this." | The model claimed a source that didn't resolve against the codebooks it was actually given — review the merge by hand before accepting |
| "These N codebooks are too large to integrate with {model}. Choose a larger-context model or integrate fewer at a time." | The combined content doesn't fit the chosen model's context window; there is no batching fallback for a merge |

## Developer reference

- Frontend: `pages/IntegrateCodebook.jsx`, `components/integrate-codebook/IntegrateCodebookEditor.jsx`, `IntegrateSourcePicker.jsx`, `IntegrateSourcePane.jsx`, `IntegrateSourceDetail.jsx`, `IntegrateBuilderPane.jsx`, `IntegrateProposalTray.jsx`, `IntegrateRail.jsx`, `IntegrateAiPanel.jsx`, `useSourceCodebooks.js`; state machine shared with Create Codebook in `lib/codebookEditorState.js` (`copySourceCode`/`integrateDraftStorageKey`) via `components/codebook-editor/useCodebookEditorState.js`.
- Backend: `backend/app/api/codebook_routes.py::POST /integrate-codebook-preview/` → `codebook_service.start_integrate_codebook_job` / `_run_integrate_codebook_job` (`job_type="integrate_codebook_preview"`) → `backend/scripts/codebook_generator.py::integrate_codebooks`; `POST /codebook/integrate` → `codebook_service.create_integrated_codebook` → `_materialize_codebook`.
- Storage written: new `files` row (`file_type="codebook"`), one `artifact_versions` row (`origin="edited"`), `codebook_codes` rows, N `artifact_edges` rows (`relation="merged_from"`, `role="merge_input"`), one `artifact_assists` row per AI-assist run (`stage="integrate"`) when any proposal was accepted.
- Endpoints: `POST /api/integrate-codebook-preview/`, `POST /api/codebook/integrate` — see [api-reference.md](../api-reference.md#codebooks--backendappapicodebook_routespy).
