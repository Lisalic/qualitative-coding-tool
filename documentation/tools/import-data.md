# Import Data

## Purpose

Upload a `.zst`-compressed dataset (Reddit-style posts or comments, one JSON object per line) into a project as a new `raw_data` artifact — the starting point of the pipeline.

## Where to find it

Sidebar → Import (pipeline group), or `/import` → `pages/Import.jsx`.

## Prerequisites

At least one project must exist (create one from Home first — see [Projects](projects.md)). The whole form is disabled with a "Go to home" prompt if there are no projects. No API key needed — import does not call an LLM.

## Inputs

| Field | Required | Default | Constraints | Notes |
|---|---|---|---|---|
| File | yes | — | must end in `.zst` | client-rejects other extensions before upload |
| Select Project | yes | — | from `GET /api/projects/` | |
| Data Type | yes | `posts` | `posts` \| `comments` | maps to `submissions`/`comments` server-side |
| Database Name | yes | — | non-blank | display name for the new file |
| Description | no | — | | |
| Subreddits | no | — | tag chips | Enter/comma/Add button; lowercased and deduplicated client-side; used as a pre-filter on the ingested rows |

## What happens on submit

Direct (non-job) call — the file is small enough that ingestion runs synchronously within the request:

`POST /api/upload-zst/` (multipart: `file`, `data_type`, `name`, `description`, `project_id`).

Server-side (`backend/app/services/file_service.py::upload_zst`): creates the `File` row (`file_type="raw_data"`, new `proj_<hex>` schemaname) and links it to the project; writes the upload to a temp `.zst` file; pulls 1000-row batches off `backend/scripts/import_db.py::iter_zst_records` on a worker thread (decompresses, parses each JSON line, skips malformed lines, empty/`[deleted]` bodies and repeated ids) and bulk-inserts each batch into the fixed `submissions`/`comments` tables keyed by the new `file_id`; records the row count in `FileTable`; deletes the temp file.

## Output

A `raw_data` File artifact with `submissions`/`comments` rows populated. On success the form resets and shows an "artifact created" banner linking to [Data Browser](data-browser.md) (`/data`) with the new file preselected. A "View Imported Data" button is also shown.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Please select a .zst file" | Wrong file extension |
| Form fields disabled, prompt to go to Home | No projects exist yet |
| `inserted_counts` shows 0 for a table | Every row in that table was malformed JSON, empty, or `[deleted]` — these are silently skipped by the importer |

## Developer reference

- Frontend: `pages/Import.jsx`, `components/data/FileUpload.jsx`.
- Backend: `backend/app/api/file_routes.py::POST /upload-zst/` → `backend/app/services/file_service.py::upload_zst` → `backend/scripts/import_db.py::iter_zst_records` (parsing/decompression) → `backend/app/repositories/raw_data_repo.py::bulk_insert_submissions`/`bulk_insert_comments`.
- Storage written: `files`, `file_tables`, `project_files`, `submissions`/`comments` (fixed tables, keyed by the new `file_id`).
- Endpoint: `POST /api/upload-zst/` — see [api-reference.md](../api-reference.md#files--backendappapifile_routespy).
