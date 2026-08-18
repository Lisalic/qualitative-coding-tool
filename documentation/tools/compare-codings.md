# Compare Codings

## Purpose

Ask an LLM to compare two coding outputs — overlaps/divergences in coding decisions, inconsistent or misapplied codes, reconciliation suggestions, an overall recommendation — and save the result as a `coding_comparison` artifact.

## Where to find it

Sidebar → Compare Coding (pipeline group), or `/compare-coding` → `pages/CompareCoding.jsx` → `components/compare/ComparePageContainer.jsx` with `mode="coding"`.

Shares one implementation with [Compare Codebooks](compare-codebooks.md) — see that page and [architecture.md](../architecture.md) for the shared plumbing (`ComparePageContainer`'s `CONFIG_BY_MODE`).

This is also the page `MarkdownView`'s Compare button opens when rendered for a coding artifact (it opens [Compare Codebooks](compare-codebooks.md) instead when rendered for a codebook — see `ArtifactMarkdownSection`'s `comparePath`/`compareStateKey` config).

## Prerequisites

At least two coding artifacts. An OpenRouter API key in the navbar.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Coding A | yes | from `GET /api/my-files/?file_type=coding` |
| Coding B | yes | auto-picks the first other item when A arrives preselected |
| Name | yes | non-blank |
| AI Model | no | |
| Prompt | no | additional instructions; example available inline, not via the shared Prompt Manager library |

## What happens on submit

Job-backed (`job_type="compare_codings"`): inline FormData (`coding_a`, `coding_b`, `api_key`, `name`, optional `model`/`prompt`) → `postFormAndPoll` → `POST /api/compare-codings/` (raw `Form(...)` params, not a Pydantic schema — unlike the codebook/apply/filter endpoints) → `202 {job_id, status}` → poll.

Server-side (`backend/app/services/coding_service.py::_run_compare_codings_job`): reads both codings' stored content, builds a fixed comparison prompt ("overlaps/divergences in coding decisions, inconsistent or misapplied codes, reconciliation/re-labeling suggestions, overall recommendation + confidence... Return the full comparison in a markdown format"), calls the LLM, persists a new `coding_comparison` File with `FileDependency` rows back to both sources.

## Output

Job result: `{comparison: <text>, file: {id, schema_name, filename}}`. Success banner links to [View Coding](view-coding.md) with the new comparison's schema passed as `state.selectedCodedData`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Select two codings to compare" | One of the two selects is empty |
| "Set your API key in the navbar first" | No `localStorage.apiKey` |

## Developer reference

- Frontend: `pages/CompareCoding.jsx`, `components/compare/ComparePageContainer.jsx`, `CompareDualSelectPanel.jsx`, `CompareModelPromptPanel.jsx`, `CompareResultPanel.jsx`, `useComparePageData.js`.
- Backend: `backend/app/api/coding_routes.py::POST /compare-codings/` → `backend/app/services/coding_service.py::start_compare_codings_job` / `_run_compare_codings_job` (`job_type="compare_codings"`) → `backend/scripts/codebook_generator.py::get_client`.
- Storage written: new `files` row (`coding_comparison`), two `file_dependencies` rows, `artifact_content`.
- Endpoint: `POST /api/compare-codings/` — see [api-reference.md](../api-reference.md#coding--backendappapicoding_routespy).
