# API Reference

Every endpoint is mounted under `/api` (`backend/app/main.py` → `backend/app/api/routes.py`). Unless noted, all routes require auth via `Depends(require_user_id)` (401 `{"error": "Not authenticated"}` if missing — see [architecture.md#auth](architecture.md#auth)).

"Job" endpoints return `202 {"job_id": <int>, "status": "pending"}` immediately; poll `GET /api/jobs/{job_id}` for the result. See [architecture.md#background-jobs](architecture.md#background-jobs).

One route exists outside `/api`: `GET /` → `{"message": "Qualitative Coding API"}`, no auth, defined directly on the FastAPI app.

## Authentication — `backend/app/api/auth_routes.py`

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/api/login/` | none | JSON `{email, password}` | `{id, email, access_token}` + `Set-Cookie access_token`; 401 on bad credentials |
| POST | `/api/register/` | none | JSON `{email, password}` | same shape as login; 400 if email taken |
| GET | `/api/me/` | required | — | `{id, email}` |
| POST | `/api/logout/` | none | — | `{"message": "Logged out"}`, clears the cookie |

See [tools/authentication.md](tools/authentication.md).

## Files — `backend/app/api/file_routes.py`

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/upload-zst/` | multipart: `file` (`.zst`, required), `data_type` (`posts`\|`comments`, required), `subreddits` (JSON array, optional), `name`, `description`, `project_id` (optional) | `{status, file_name, display_name, description, schema_name, inserted_counts: {submissions, comments}}` |
| POST | `/api/merge-databases/` | `databases` (JSON array of schema names, required), `name`, `description`, `project_id` | `{message, file: {id, schema_name, display_name, description}, file_migrated}` |
| DELETE | `/api/delete-database/{db_name}` | path param, must start `proj_`/`cmp_`/`sum_` | `{"message": "File '<filename>' deleted"}` |
| POST | `/api/delete-row/` | form: `schemaname` (`proj_...`), `table` (`submissions`\|`comments`), `row_id` | `{"deleted": 0\|1}` |
| POST | `/api/move-rows/` | JSON: `source_schema`, `target_schema`, `table`, `row_ids` (non-empty list) | `{"moved": n}` |

See [tools/import-data.md](tools/import-data.md), [tools/projects.md](tools/projects.md), [tools/data-browser.md](tools/data-browser.md).

## Prompts — `backend/app/api/prompt_routes.py`

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/prompts/` | query `prompt_type` (optional) | `{"prompts": [{id, user_id, promptname, prompt, type}]}` |
| POST | `/api/prompts/` | `promptname`, `prompt`, `type` (all required) | the created prompt |
| POST | `/api/prompts/{prompt_id}/update` | any of `promptname`/`prompt`/`type` | the updated prompt; 404/403 on bad ownership |
| DELETE | `/api/prompts/{prompt_id}` | — | `{"deleted": true, "id": int}` |

See [tools/prompt-manager.md](tools/prompt-manager.md).

## Codebooks — `backend/app/api/codebook_routes.py`

| Method | Path | Body | Response | Kind |
|---|---|---|---|---|
| GET | `/api/codebook` | query `codebook_id` | `{codebook, systemprompt, userprompt}` | direct |
| GET | `/api/parse-codebook` | query `codebook_id` | `{"parsed": [{family_name, content, codes: [{code_name, content}]}]}` | direct |
| GET | `/api/list-codebooks` | — | `{"codebooks": [{id, name, metadata, description, source}]}` | direct |
| POST | `/api/save-file-codebook/` | `schema_name`, `content` (required), `display_name` (optional) | `{message, id, display_name}` | direct |
| POST | `/api/generate-codebook/` | `as_form(GenerateCodebookRequest)` — see below | `202 {job_id, status}` → result `{codebook, file}` | **job** |
| POST | `/api/compare-codebooks/` | `as_form(CompareCodebooksRequest)` | `202 {job_id, status}` → result `{comparison, file}` | **job** |

See [tools/generate-codebook.md](tools/generate-codebook.md), [tools/view-codebook.md](tools/view-codebook.md), [tools/compare-codebooks.md](tools/compare-codebooks.md).

## Coding — `backend/app/api/coding_routes.py`

| Method | Path | Body | Response | Kind |
|---|---|---|---|---|
| GET | `/api/coded-data` | query `coded_id` | `{coded_data, codebook_text, codebook_tree, systemprompt, userprompt}` | direct |
| POST | `/api/save-file-coded-data/` | `schema_name`, `content`, `display_name` (optional) | `{message, id, filename}` | direct |
| POST | `/api/save-file-coded-data-duplicate/` | `source_schema_name`, `content`, `display_name` (all required) | `{message, id, schema_name, filename}` | direct |
| POST | `/api/apply-codebook/` | `as_form(ApplyCodebookRequest)` | `202 {job_id, status}` → result `{classification_output, file}` | **job** |
| POST | `/api/compare-codings/` | form: `coding_a`, `coding_b`, `api_key`, `name` (required), `model`, `prompt`, `description`, `project_id` (optional) | `202 {job_id, status}` → result `{comparison, file}` | **job** |
| POST | `/api/summarize-coding/` | form: `coding`, `api_key`, `name` (required), `model`, `prompt`, `description`, `project_id` (optional) | `202 {job_id, status}` → result `{summary, file}` | **job** |

`compare-codings` and `summarize-coding` use raw `Form(...)` params, not Pydantic schemas — unlike the other four job endpoints.

See [tools/apply-codebook.md](tools/apply-codebook.md), [tools/view-coding.md](tools/view-coding.md), [tools/compare-codings.md](tools/compare-codings.md), [tools/summarize-coding.md](tools/summarize-coding.md).

## Data — `backend/app/api/data_routes.py`

| Method | Path | Body | Response | Kind |
|---|---|---|---|---|
| GET | `/api/word-count-ranges/` | query `schema` | `{submissions: [{min_words, count}], comments: [...]}`, bins 0–1000 step 10 | direct |
| GET | `/api/file-entries/` | query `schema`, `limit` (default 10), `offset` (default 0) | `{submissions, comments, total_submissions, total_comments, database, date_created}` | direct |
| GET | `/api/comments/{submission_id}` | query `database` (default `"original"`) | `{"comments": [...]}` ordered by `created_utc` | direct |
| POST | `/api/post-contents/` | JSON `{schema, post_ids}` | `{"contents": {post_id: {title, content}}}` | direct |
| POST | `/api/filter-data/` | `as_form(FilterDataRequest)` | `202 {job_id, status}` → result `{message, submissions_length, comments_length, posts_filtered_count, comments_filtered_count, file, tag_filter?}` | **job** |

See [tools/data-browser.md](tools/data-browser.md), [tools/filter-data.md](tools/filter-data.md).

## Projects — `backend/app/api/project_routes.py`

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/my-files/` | query `file_type` (default `raw_data`) | `{"projects": [{id, display_name, description, schema_name, file_type, created_at, tables, parent_files}]}` (flat file list despite the key name) |
| POST | `/api/create-project/` | `name` (required), `description` | `{"project": {id, projectname, description, created_at}}` |
| POST | `/api/update-project/` | `project_id`, `name` (required), `description` | same project shape |
| GET | `/api/projects/` | — | `{"projects": [{id, projectname, description, created_at, files: [...]}]}` |
| POST | `/api/rename-file/` | `schema_name`, `display_name` (required), `description` | `{message, id, display_name, description}` |

`file_type` query values `"codebook"` and `"coding"` also match their `_comparison` counterparts (see `backend/app/services/project_service.py::_file_type_filter`).

See [tools/projects.md](tools/projects.md).

## Content — `backend/app/api/content_routes.py`

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/save-comparison/` | `content`, `title` (required), `description`, `file_type` (default `"comparison"`), `project_id`, `parent_file_ids` (JSON array of ints) | `{message, file_id, schema_name}` |
| POST | `/api/save-summary/` | `content`, `name` (required), `description`, `project_id` | `{message, file: {id, schema_name, filename}}` |
| GET | `/api/summary/{summary_id}` | — | `{"summary": {content, display_name, description}}` |

## Models — `backend/app/api/models_routes.py`

| Method | Path | Response |
|---|---|---|
| GET | `/api/models` | `[{value, label, paid, pricing: {inputUsdPerMillion, outputUsdPerMillion} \| null}]` — live in-memory catalog, see [architecture.md#model-catalog](architecture.md#model-catalog) |

## Jobs — `backend/app/jobs/routes.py`

| Method | Path | Response |
|---|---|---|
| GET | `/api/jobs/{job_id}` | `{id, job_type, status, result, error, error_code, created_at, started_at, finished_at}`; 404 if missing, 403 if owned by another user |

## Request schemas (Pydantic, `backend/app/api/schemas.py`)

The four endpoints built on `as_form(...)` validate against these models (`multipart/form-data`, whitespace-stripped, unknown fields ignored). A `proj_<hex>` pattern is `^proj_[A-Za-z0-9_]+$`.

| Field | `FilterDataRequest` | `GenerateCodebookRequest` | `ApplyCodebookRequest` | `CompareCodebooksRequest` |
|---|---|---|---|---|
| `api_key` | required, min 1 | required, min 1 | required, min 1 | required, min 1 |
| `database` / `codebook_a`+`codebook_b` | required, `proj_` pattern, `.db` suffix stripped | required, `proj_` pattern, `.db` stripped | required, `proj_` pattern, `.db` stripped | required, `proj_` pattern each |
| `name` | required, min 1 | required, min 1 | (`report_name`) required, min 1 | required, min 1 |
| `model` | required, min 1 | optional | optional | optional |
| `codebook` | — | — | required, min 1 — numeric File id **or** `proj_<hex>` | — |
| `project_id` | optional int | optional int | optional int | optional int |
| `prompt` | optional | optional | (`methodology`) optional | optional |
| `description` | optional | optional | optional | optional |
| `sample_percentage` | `100.0`, `ge=1, le=100` | `100.0`, **`ge=0`**, `le=100` | `100.0`, `ge=1, le=100` | — |
| `min_words` | `0`, `ge=0` | — | — | — |
| `filter_tags` | optional | — | — | — |

Note `GenerateCodebookRequest.sample_percentage` allows `0`, unlike the other two — a 0% sample is rejected downstream in the service layer (empty-content check), not by the schema.

## Errors

All service-layer errors render as `{"error": "<message>"}` with the matching status code (`AppError` hierarchy — see [architecture.md#errors](architecture.md#errors)). FastAPI request-validation failures (missing/malformed form fields) render as the standard 422 `{"detail": [...]}` shape instead.
