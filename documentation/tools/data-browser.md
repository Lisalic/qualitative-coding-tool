# Data Browser (View Data / View Filtered Data)

## Purpose

Browse, search, and edit rows of a raw or filtered dataset — the only tool that mutates content in place rather than producing a new artifact.

## Where to find it

Sidebar → "View Data" (`/data`, raw datasets) and "View Filtered Data" (`/filtered-data`, filtered datasets), under the Views group. Both routes render the same implementation with a different `mode`: `pages/Data.jsx` and `pages/FilteredData.jsx`.

## Prerequisites

At least one `raw_data` (or `filtered_data`) file must exist. No API key needed.

## Inputs

| Control | Notes |
|---|---|
| Project filter | narrows the file selection list to one project |
| Database selector | pick which file's rows to view |
| Search box | full-text search; fetches up to 5000 matching rows at once rather than paging |
| Page size | default 10 |
| Row checkboxes + target-database select | for moving rows between files |

Arriving from another tool with `location.state.selectedDatabase` preselects the matching file (accepts a plain schema-name string or `{name|id}`).

## What happens on submit

All actions are direct (non-job) calls, no LLM involved:

- Load rows: `GET /api/file-entries/?schema=...&limit=...&offset=...`.
- View a comment thread: `GET /api/comments/{submission_id}?database=...`, ordered oldest-first.
- Delete: confirm dialog → `POST /api/delete-row/` (single) or a loop of the same call (bulk).
- Move rows to another file: `POST /api/move-rows/` (JSON `{source_schema, target_schema, table, row_ids}`), once per affected table.

## Output

No new artifact — edits mutate the underlying `submissions`/`comments` rows for that `file_id` directly. `FileTable` row counts are refreshed best-effort after delete/move.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Unhandled error loading a database | The schema name doesn't match `^proj_[A-Za-z0-9_]+(?:\.db)?$` — `file-entries` is guarded by this regex and the request never resolves cleanly if it fails |
| "No matching rows found" on move | The selected rows no longer exist in the source (already deleted/moved) |

## Developer reference

- Frontend: `pages/Data.jsx` / `pages/FilteredData.jsx`, `components/data/useDataBrowserPage.js`, `useProjectScopedFiles.js`, `useDataTableActions.js`, `components/data/DatabaseSelectionSection.jsx`, `SelectedDatabaseTableSection.jsx`, `DataTable.jsx`, `EntryModal.jsx`.
- Backend: `backend/app/api/data_routes.py` (reads) + `backend/app/api/file_routes.py` (delete/move) → `backend/app/services/data_service.py` / `file_service.py` → `backend/app/repositories/raw_data_repo.py`.
- Endpoints: `GET /api/file-entries/`, `GET /api/comments/{id}`, `POST /api/post-contents/`, `POST /api/delete-row/`, `POST /api/move-rows/` — see [api-reference.md](../api-reference.md#data--backendappapidata_routespy).
