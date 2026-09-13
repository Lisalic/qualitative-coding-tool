# Compare Codings

## Purpose

Ask an LLM to compare two coding outputs — overlaps/divergences in coding decisions, inconsistent or misapplied codes, reconciliation suggestions, an overall recommendation — and save the result as a `coding_comparison` artifact.

For a deterministic, no-LLM diff of two versions of the *same* coding artifact's own classification history (recoded/newly-coded/newly-uncoded rows, per-code counts and deltas, applied/removed evidence), open that artifact's Version History page (`/versions?ref=...`, `components/versioning/VersionHistoryPanel.jsx`'s `CodingDiffSummary`) instead — that diff is free and needs no API key. This page is for the LLM narrative comparison of two (possibly unrelated) coding artifacts, which Version History does not do.

## Where to find it

Sidebar → Compare Coding (pipeline group), or `/compare-coding` → `pages/CompareCoding.jsx` → `components/compare/ComparePageContainer.jsx` with `mode="coding"`.

Shares one implementation with [Compare Codebooks](compare-codebooks.md) — see that page and [architecture.md](../architecture.md) for the shared plumbing (`ComparePageContainer`'s `CONFIG_BY_MODE`).

This is also the page the coding workspace's Compare button opens; the codebook workspace's equivalent opens [Compare Codebooks](compare-codebooks.md) instead.

## Prerequisites

At least two coding artifacts. An OpenRouter API key in the navbar.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Coding A | yes | from `GET /api/my-files/?file_type=coding` |
| Coding B | yes | auto-picks the first other item when A arrives preselected |
| Name | yes | non-blank |
| Project | yes | every artifact belongs to one |
| AI Model | yes | |
| Prompt | no | additional instructions; example available inline, not via the shared Prompt Manager library |

## What happens on submit

Job-backed (`job_type="compare_codings"`): inline FormData (`coding_a`, `coding_b`, `api_key`, `name`, `project_id`, `model`, optional `prompt`) → `postFormAndPoll` → `POST /api/compare-codings/` (raw `Form(...)` params, not a Pydantic schema — unlike the codebook/apply/filter endpoints) → `202 {job_id, status}` → poll.

Server-side (`backend/app/services/coding_service.py::_run_compare_codings_job`): reads both codings' rendered content (a coding artifact's classification is generated fresh from its `coding_entries`, not read from a stored blob), builds a fixed comparison prompt ("overlaps/divergences in coding decisions, inconsistent or misapplied codes, reconciliation/re-labeling suggestions, overall recommendation + confidence... Return the full comparison in a markdown format"), calls the LLM, persists a new `coding_comparison` File with `artifact_edges` (`relation=compared`, `role=side_a`/`side_b`) back to both sources. If the raw rendered text overflows the model's context window, each side is compacted to per-code counts + sampled evidence (the same aggregation `summarize-coding` uses) before falling back to a hard failure.

## Output

Job result: `{comparison: <text>, file: {id, schema_name, filename}}`. Success banner links to [View Coding](view-coding.md) with the new comparison's schema passed as `state.selectedCodedData`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Select two codings to compare" | One of the two selects is empty |
| "Set your API key in the navbar first" | No `localStorage.apiKey` |
| "These two codings are too large to compare with `<model>`, even after summarizing" | Even the per-code-count aggregation overflows the window; choose a larger-context model |

## Developer reference

- Frontend: `pages/CompareCoding.jsx`, `components/compare/ComparePageContainer.jsx`, `CompareDualSelectPanel.jsx`, `CompareModelPromptPanel.jsx`, `CompareResultPanel.jsx`, `useComparePageData.js`.
- Backend: `backend/app/api/coding_routes.py::POST /compare-codings/` → `backend/app/services/coding_service.py::start_compare_codings_job` / `_run_compare_codings_job` (`job_type="compare_codings"`) → `backend/scripts/codebook_generator.py::get_client`.
- Storage written: new `files` row (`coding_comparison`), two `artifact_edges` rows, `artifact_versions` content blob.
- Endpoint: `POST /api/compare-codings/` — see [api-reference.md](../api-reference.md#coding--backendappapicoding_routespy).
- Structural (no-LLM) coding diffing lives at `GET /api/artifacts/{ref}/diff`, rendered by `components/versioning/VersionHistoryPanel.jsx`.
