# Apply Codebook

## Purpose

Classify each post/comment in a dataset against an existing codebook, producing a `coding` artifact with per-item code assignments and supporting evidence.

## Where to find it

Sidebar → Apply Codebook (pipeline group), or `/codebook-apply` → `pages/ApplyCodebook.jsx` → `components/tool-panels/ApplyCodebookPanel.jsx`.

## Prerequisites

At least one dataset and one codebook. An OpenRouter API key in the navbar. The panel blocks submission entirely if no codebooks exist for the user.

## Inputs

| Field | Required | Default | Constraints | Notes |
|---|---|---|---|---|
| Database Type | — | `unfiltered` | `unfiltered` \| `filtered` | |
| Select Database | yes | — | must resolve to `proj_<id>` | |
| Select Project | no | — | | pre-selected via `state.projectId` when arriving from a project page's "Add" button (`useInitialProjectId`) |
| Select Codebook | yes | first available | numeric File id **or** `proj_<hex>` schema | auto-defaults to the first codebook in the list |
| Prompt (methodology) | no | — | | optional instructions steering the classifier; example available, saveable to the [Prompt Manager](prompt-manager.md) library (`promptType="apply"`) |
| AI Model | no | — | | |
| Sample Size | no | `100` | slider 1–100 | |
| Report Name | yes | — | non-blank | |
| Description | no | — | | |

## What happens on submit

Job-backed (`job_type="apply_codebook"`): `postFormAndPoll` → `POST /api/apply-codebook/` → `202 {job_id, status}` → poll.

Server-side (`backend/app/services/coding_service.py::_run_apply_codebook_job`): reads the codebook's content, samples submissions/comments from the source, assembles them as `POST_ID: <id>  Title: <title>  <selftext>` / `POST_ID: <id>  <body>` blocks, then calls `backend/scripts/codebook_apply.py::classify_posts(codebook_text, assembled, methodology, api_key, model)`.

The system prompt requires the model to reply using **only** this DSL, one or more times per post that has an applicable code, omitting posts with none:
```
POST_ID: <exact_post_id_from_input>
CODE: <exact_code_name_from_codebook>
EVIDENCE: "<exact_snippet>"§"<exact_snippet>"
```
Code names must match the codebook exactly (without the family name); evidence must be exact contiguous substrings from the input, quoted, with `§` only separating multiple snippets for the same code; no markdown, bullets, or explanation. The response is normalized (smart quotes, markdown artifacts stripped) and checked against this shape — if it doesn't validate, the **raw** (or normalized) text is returned anyway rather than raising, so downstream storage always gets something, even if it doesn't parse.

The classification output is persisted to `artifact_content` **and** parsed into structured `coding_entries` rows (one per post/code pair). `FileDependency` rows are recorded back to both the source data file and the codebook file; the new coding file is linked to the source's own projects, but only when the source itself is `raw_data` (not `filtered_data`) — a narrowing carried over unchanged from the pre-refactor handler.

## Output

Job result: `{classification_output: <text>, file: {id, schema_name, filename, description}}`. Success banner links to [View Coding](view-coding.md) with the new file's schema name passed as `state.selectedCodedData`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Error: API key not set..." | No `localStorage.apiKey` |
| `MissingFieldsError` mentioning "codebook (must be numeric File id or proj_<id> schema)" | The codebook reference is neither a valid `proj_<hex>` string nor parseable as an integer |
| Submit disabled, "No codebooks available" | No codebook artifacts exist yet for this user — go create one via [Generate Codebook](generate-codebook.md) |
| Output looks messy / codes don't match the codebook cleanly | The classifier didn't follow the DSL and `validate_coding_output` failed — the raw text is still stored, but structured `coding_entries` for that run may be incomplete |

## Developer reference

- Frontend: `pages/ApplyCodebook.jsx`, `components/tool-panels/ApplyCodebookPanel.jsx`, `frontend/src/lib/apiContracts.js::buildApplyCodebookForm`.
- Backend: `backend/app/api/coding_routes.py::POST /apply-codebook/` → `backend/app/services/coding_service.py::start_apply_codebook_job` / `_run_apply_codebook_job` (`job_type="apply_codebook"`) → `backend/scripts/codebook_apply.py::classify_posts` (+ `_extract_structured_records`, `_format_evidence_segments`) → `backend/app/repositories/coding_repo.py::bulk_insert_coding_entries`, `artifact_content_repo.write_content`.
- Storage written: new `files` row (`coding`, with `systemprompt`/`userprompt`), two `file_dependencies` rows (source + codebook), `artifact_content`, `coding_entries`.
- Endpoint: `POST /api/apply-codebook/` — see [api-reference.md](../api-reference.md#coding--backendappapicoding_routespy).
