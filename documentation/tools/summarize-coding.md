# Summarize Coding

## Purpose

Ask an LLM for a thematic-analysis-style narrative summary of a coding artifact (key themes, code frequency/distribution, relationships between codes and themes, representative quotes, insights, methodological observations), saved as a `summary` artifact.

## Where to find it

Sidebar → Summarize Coding (pipeline group), or `/summarize-coding` → `pages/SummarizeCoding.jsx`. Unlike the other pipeline pages, this one does not use the shared `ToolPage` shell — it hand-rolls its own container.

## Prerequisites

At least one coding artifact. An OpenRouter API key in the navbar.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Coding | yes | auto-selected to the first available coding artifact (`GET /api/my-files/?file_type=coding`) |
| Name | yes | non-blank |
| AI Model | no | |
| Prompt | no | this tool's example prompt is hardcoded in `PromptEditorSection.jsx`, separate from `apiContracts.EXAMPLE_PROMPTS` — it has no Save/Load-to-library integration with the [Prompt Manager](prompt-manager.md) |

## What happens on submit

Job-backed (`job_type="summarize_coding"`): `postFormAndPoll` → `POST /api/summarize-coding/` (raw `Form(...)` params, not a Pydantic schema) → `202 {job_id, status}` → poll.

Server-side (`backend/app/services/coding_service.py::_run_summarize_coding_job`): resolves the coding file to an owned `file_id`, reads its content via `artifact_content_repo.read_content`, calls `backend/scripts/summarize_coding.py::summarize_coding(coding_data, prompt, api_key, model)` (default model index 2 in the catalog), and persists a new `summary` File with a `FileDependency` back to the source coding file.

## Output

Job result: `{summary: <text>, file: {id, schema_name, filename}}`. Rendered inline with a Copy button; success banner links to [View Summary](view-summary.md) with the new file's schema passed as `state.selectedSummary`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Job fails with "No content found in coding" | The source coding file's `artifact_content` row is empty (rare — every coding artifact produced by [Apply Codebook](apply-codebook.md) writes one) |
| "Set your API key in the navbar first" | No `localStorage.apiKey` |
| Name field blank on submit | client-checked non-blank before the request |

## Developer reference

- Frontend: `pages/SummarizeCoding.jsx`, `components/summarize/useSummarizeCodingPage.js`, `SummarizeRequestSection.jsx`, `SummarizeCodingPanel.jsx`, `SummarizeModelPromptPanel.jsx`, `PromptEditorSection.jsx`, `SummaryOutputSection.jsx`.
- Backend: `backend/app/api/coding_routes.py::POST /summarize-coding/` → `backend/app/services/coding_service.py` (job start + `_run_summarize_coding_job`, `job_type="summarize_coding"`) → `backend/scripts/summarize_coding.py::summarize_coding`.
- Storage written: new `files` row (`summary`), `file_dependencies`, `artifact_content`.
- Endpoint: `POST /api/summarize-coding/` — see [api-reference.md](../api-reference.md#coding--backendappapicoding_routespy).
