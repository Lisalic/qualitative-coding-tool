# Generate Codebook

## Purpose

Have an LLM read a sample of a dataset and draft a qualitative codebook (themed code families with definitions, inclusion criteria, keywords, and examples).

## Where to find it

Sidebar → Generate Codebook (pipeline group), or `/codebook-generate` → `pages/GenerateCodebook.jsx` → `components/tool-panels/GenerateCodebookPanel.jsx`.

## Prerequisites

At least one raw or filtered dataset. An OpenRouter API key in the navbar.

## Inputs

| Field | Required | Default | Constraints | Notes |
|---|---|---|---|---|
| Database Type | — | `unfiltered` | `unfiltered` \| `filtered` | |
| Select Database | yes | — | must resolve to `proj_<id>` | |
| Select Project | no | — | | pre-selected via `state.projectId` when arriving from a project page's "Add" button (`useInitialProjectId`) |
| Prompt | no | — | | additional instructions appended to the fixed system prompt; example available, saveable to the [Prompt Manager](prompt-manager.md) library (`promptType="generate"`) |
| AI Model | no | — | falls back to a server default | the only one of the three form-builder tools where the model is optional |
| Sample Size | no | `100` | slider 1–100, **allows 0 at the schema level** | percentage of source rows sampled for the LLM to read |
| Codebook Name | yes | — | non-blank | |
| Description | no | — | | |

`GenerateCodebookRequest.sample_percentage` is the one field across all three tools where the Pydantic constraint is `ge=0` rather than `ge=1` — a 0% sample passes validation but is rejected downstream once the assembled content turns out empty.

## What happens on submit

Job-backed (`job_type="generate_codebook"`): `postFormAndPoll` → `POST /api/generate-codebook/` → `202 {job_id, status}` → poll.

Server-side (`backend/app/services/codebook_service.py::_run_generate_codebook_job`): samples submissions/comments via `raw_data_repo.sample_submissions`/`sample_comments`, assembles them into `"Title: ...\n<selftext>\n\n"` / `"<body>\n\n"` blocks, raises a validation error if that's empty, then calls `backend/scripts/codebook_generator.py::generate_codebook(assembled, api_key, prompt, MODEL=model)` (default model index 0 in the catalog — see [architecture.md#model-catalog](../architecture.md#model-catalog)).

The system prompt instructs the model to output, per code, **only**:
```
### Code Family: [Theme Name]
#### Code Name: [Name]
Definition: [Concise Definition]
Inclusion Criteria: [When to use this code]
Key Words: [Words or phrases frequently found in this code]
Example: [Quote from data]
```
with no conversational text. `backend/scripts/display_codebook.py::parse_codebook_to_json` (the tree-view parser) also tolerates missing/extra `#` markers, different casing, and no prefix at all, so an off-format response from the model still parses into a tree rather than an empty list.

Result is persisted as a new `codebook` File with the system/user prompts attached, and a `FileDependency` back to the source.

## Output

Job result: `{codebook: <text>, file: {id, schema_name, filename, description}}`. Success banner links to [View Codebook](view-codebook.md) with the new file's schema name passed as `state.selected`, which `useViewCodebookPage` matches against id, schema, or name in every branch (project-filtered or not), so the new codebook is preselected on arrival either way.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Error: API key not set..." | No `localStorage.apiKey` |
| `MissingFieldsError` | One of `apiKey, database, name` blank, or `database` not `proj_<id>`-shaped |
| Job fails with an empty-content validation error | Sample was empty — check the source has rows and the sample percentage isn't 0 |

## Developer reference

- Frontend: `pages/GenerateCodebook.jsx`, `components/tool-panels/GenerateCodebookPanel.jsx`, `frontend/src/lib/apiContracts.js::buildGenerateCodebookForm`.
- Backend: `backend/app/api/codebook_routes.py::POST /generate-codebook/` → `backend/app/services/codebook_service.py::start_generate_codebook_job` / `_run_generate_codebook_job` (`job_type="generate_codebook"`) → `backend/scripts/codebook_generator.py::generate_codebook`.
- Storage written: new `files` row (`codebook`, with `systemprompt`/`userprompt`), `file_dependencies`, `artifact_content`.
- Endpoint: `POST /api/generate-codebook/` — see [api-reference.md](../api-reference.md#codebooks--backendappapicodebook_routespy).
