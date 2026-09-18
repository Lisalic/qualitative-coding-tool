# Compare Codebooks

## Purpose

Ask an LLM to compare two codebooks — similarities/differences, conflicting or duplicate codes, merge suggestions, an overall recommendation — and save the result as a `codebook_comparison` artifact.

For a deterministic, no-LLM structural diff (added/removed/renamed/redefined/moved/reordered codes) between two versions of the *same* codebook's own history, open that codebook's Version History page (`/versions?ref=...`, `components/versioning/VersionHistoryPanel.jsx`) instead — see [architecture.md](../architecture.md) for the artifact-versioning model. That diff is free, needs no API key, and is what this page used to also offer inline before the two were split apart. This page is for the LLM narrative comparison of two (possibly unrelated) codebooks, which Version History does not do.

## Where to find it

Sidebar → Compare Codebook (pipeline group), or `/compare-codebook` → `pages/CompareCodebook.jsx` → `components/compare/ComparePageContainer.jsx` with `mode="codebook"`.

This shares one implementation with [Compare Codings](compare-codings.md) — `ComparePageContainer`'s `CONFIG_BY_MODE` is the only difference between the two pages. See [architecture.md](../architecture.md) for the shared plumbing.

## Prerequisites

At least two codebook artifacts. An OpenRouter API key in the navbar.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Codebook A | yes | from `GET /api/my-files/?file_type=codebook` |
| Codebook B | yes | when arriving with a preselected A (e.g. from View Codebook), B auto-picks the first other item |
| Name | yes | non-blank |
| Project | yes | every artifact belongs to one |
| AI Model | yes | |
| Prompt | no | additional instructions; an example prompt is available via "Load Example Prompt" (this flow does **not** use the shared `apiContracts.EXAMPLE_PROMPTS`/Prompt Manager save-to-library path — the example lives inline in `ComparePageContainer`) |

## What happens on submit

Job-backed (`job_type="compare_codebooks"`): FormData is assembled inline (not through `apiContracts.js`) with `codebook_a`, `codebook_b`, `api_key`, `name`, `project_id`, `model`, optional `prompt` → `postFormAndPoll` → `POST /api/compare-codebooks/` (a `CompareCodebooksRequest` read via the `as_form` adapter, see `backend/app/api/schemas.py`) → `202 {job_id, status}` → poll.

Server-side (`backend/app/services/codebook_service.py::_run_compare_codebooks_job`): reads both codebooks' stored content (after sealing each one's head via `version_service.pin_parent`), builds a fixed comparison prompt ("major similarities/differences, conflicting or duplicate codes, merge/refine suggestions, overall recommendation + confidence... Return the full comparison as text"), calls the LLM, and persists a new `codebook_comparison` File with `artifact_edges` (`relation=compared`, `role=side_a`/`side_b`) back to both source codebooks.

## Output

Job result: `{comparison: <text>, file: {id, schema_name, filename}}`. The comparison markdown renders inline; the success banner links to [View Codebook](view-codebook.md) with the new comparison's schema passed as `state.selected`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Select two codebooks to compare" | One of the two selects is empty |
| "Set your API key in the navbar first" | No `localStorage.apiKey` |
| "These two codebooks are too large to compare with `<model>`" | Combined content overflows the model's context window (no batching — a comparison is inherently over both whole codebooks); choose a larger-context model |

## Developer reference

- Frontend: `pages/CompareCodebook.jsx`, `components/compare/ComparePageContainer.jsx`, `CompareDualSelectPanel.jsx`, `CompareModelPromptPanel.jsx`, `CompareResultPanel.jsx`, `useComparePageData.js`.
- Backend: `backend/app/api/codebook_routes.py::POST /compare-codebooks/` → `backend/app/services/codebook_service.py::start_compare_codebooks_job` / `_run_compare_codebooks_job` (`job_type="compare_codebooks"`) → `backend/scripts/codebook_generator.py::get_client`.
- Storage written: new `files` row (`codebook_comparison`), two `artifact_edges` rows, `artifact_versions` content blob.
- Endpoint: `POST /api/compare-codebooks/` — see [api-reference.md](../api-reference.md#codebooks--backendappapicodebook_routespy).
- Structural (no-LLM) codebook diffing lives at `GET /api/artifacts/{ref}/diff`, rendered by `components/versioning/VersionHistoryPanel.jsx`.
