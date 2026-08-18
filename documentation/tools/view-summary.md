# View Summary

## Purpose

Read a saved coding summary.

## Where to find it

Sidebar → View Summary (Views group), or `/summaryview` → `pages/ViewSummary.jsx`.

## Prerequisites

At least one `summary` artifact (from [Summarize Coding](summarize-coding.md)). No API key needed.

## Inputs

Read-only: a project filter plus an artifact selector (`ArtifactSelector`). No editing, no form fields.

## What happens on submit

Direct (non-job) calls only: `GET /api/projects/` and `GET /api/my-files/?file_type=summary` populate the selector (filtering the project's own `files[]` when a project is chosen instead of the flat list); selecting a summary calls `GET /api/summary/{schema_name}`.

## Output

No artifact produced — this is a pure viewer. Renders `summary.content` (falling back to `summary.summary` or a raw JSON dump if neither is present) via `MarkdownDisplay`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "No content found" / 404 | The summary's `file_id` has no row in `artifact_content` |

## Developer reference

- Frontend: `pages/ViewSummary.jsx`, `components/summarize/useViewSummaryPage.js`, `components/shell/ViewPageShell.jsx`, `components/primitives/ArtifactSelector.jsx`, `MarkdownDisplay`.
- Backend: `backend/app/api/content_routes.py::GET /summary/{summary_id}` → `backend/app/services/content_service.py::get_summary` (3-way lookup: schemaname → filename → int id, scoped to the user, falling back to the most recent) → `backend/app/repositories/artifact_content_repo.py::read_content`.
- Endpoint: `GET /api/summary/{summary_id}` — see [api-reference.md](../api-reference.md#content--backendappapicontent_routespy).
