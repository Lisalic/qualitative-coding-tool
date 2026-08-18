# Filter Data

## Purpose

Produce a `filtered_data` artifact — a subset of a raw dataset selected by keyword tags, an AI prompt, or both — without mutating the source.

## Where to find it

Sidebar → Filter (pipeline group), or `/filter` → `pages/Filter.jsx` → `components/tool-panels/FilterDataPanel.jsx`.

## Prerequisites

At least one raw or filtered dataset to filter from. An OpenRouter API key set in the navbar (see [concepts.md#api-key-handling](../concepts.md#api-key-handling)) — required even for a tags-only filter, because the form validation requires `model` regardless.

## Inputs

| Field | Required | Default | Constraints | Notes |
|---|---|---|---|---|
| Database Type | — | `unfiltered` | `unfiltered` \| `filtered` | switching clears the database selection |
| Select Database | yes | — | must resolve to `proj_<id>` | |
| Select Project | no | — | | `project_id` only sent if non-empty; pre-selected via `state.projectId` when arriving from a project page's "Add" button (`useInitialProjectId`) |
| Filtered Database Name | yes | — | non-blank | |
| Description | no | — | | |
| Prompt | no | — | | example available; can save/load from the [Prompt Manager](prompt-manager.md) library (`promptType="filter"`) |
| Keywords | no | — | comma-separated | pre-filters via tag expansion before/instead of the AI pass |
| AI Model | **yes** | — | | the only one of the three form-builder tools where the model is required |
| Minimum Words | no | `0` | slider 0–1000 step 10 | only sent if `> 0` |
| Sample Size | no | `100` | slider 1–100 step 1 | percentage of eligible rows sampled before filtering |

Selecting a database triggers `GET /api/word-count-ranges/?schema=...`, which drives live captions on both sliders (records matching the word-count floor, and how many of those the sample percentage will include).

## What happens on submit

Job-backed (`job_type="filter_data"`): `postFormAndPoll` → `POST /api/filter-data/` (`as_form(FilterDataRequest)`) → `202 {job_id, status}` → poll `GET /api/jobs/{job_id}`.

Server-side (`backend/app/services/data_service.py`):

1. Validates the schema and API key, resolves the source `file_id`.
2. Samples eligible rows (`word_count >= min_words` and any tag predicate) via `ORDER BY RANDOM() LIMIT ceil(eligible * pct / 100)`.
3. If keywords were given with no prompt: keeps the sampled ids directly (tags-only path), and records a synthetic `systemprompt`/`userprompt` noting no AI criteria were applied.
4. Otherwise: calls `backend/scripts/filter_db.py::filter_posts_with_ai` / `filter_comments_with_ai`. Entries are batched to fit the chosen model's context window (batches capped at 3 for free models, sampled evenly across the full batch list; uncapped for paid models). Each batch asks the LLM to return **only a raw Python array of string IDs** to keep (e.g. `['t3_abc', 't3_xyz']`, `[]` if none) — no markdown, no explanation.
5. Materializes a new `filtered_data` File, copies the kept rows via `raw_data_repo.copy_rows_by_id`, records a `FileDependency` back to the source, and links it to the project if given.

## Output

Job result: `{message, submissions_length, comments_length, posts_filtered_count, comments_filtered_count, file: {id, schema_name, filename}, tag_filter?: {original_tags, expanded_terms}}`. Success banner links to [Data Browser](data-browser.md) (`/filtered-data`) with the new file preselected.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Error: API key not set. Please set your API key in the navbar." | No `localStorage.apiKey` |
| `MissingFieldsError` before any network call | One of `apiKey, database, name, model` is blank, or `database` isn't `proj_<id>`-shaped |
| Job fails on the very first batch | `AIFilterError` re-raised immediately — typically an auth/config problem with the model or key |
| Job returns fewer IDs than expected, partial result | A later batch failed after the first succeeded; the job returns whatever was collected so far rather than failing the whole run |
| "free model overloaded" style message | An empty completion from a free model was remapped to a friendlier `AIFilterError(code=502)` |

## Developer reference

- Frontend: `pages/Filter.jsx`, `components/tool-panels/FilterDataPanel.jsx`, `components/tool-panels/useToolPanelData.js`, `frontend/src/lib/apiContracts.js::buildFilterDataForm`.
- Backend: `backend/app/api/data_routes.py::POST /filter-data/` → `backend/app/services/data_service.py::start_filter_data_job` (enqueue) / `_run_filter_data_job` (handler, `job_type="filter_data"`) → `backend/scripts/filter_db.py` (AI filtering), `backend/scripts/tag_expansion.py` (keyword expansion) → `backend/app/repositories/raw_data_repo.py`.
- Storage written: new `files` row (`filtered_data`), `file_dependencies`, `file_tables`, `submissions`/`comments` rows copied under the new `file_id`.
- Endpoint: `POST /api/filter-data/` — see [api-reference.md](../api-reference.md#data--backendappapidata_routespy).
