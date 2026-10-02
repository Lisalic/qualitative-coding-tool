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
| POST | `/api/upload-zst/` | multipart: `file` (`.zst`, required), `data_type` (`posts`\|`comments`, required), `name`, `description`, `project_id` (required) | `{file_name, authenticated, display_name, description, schema_name, inserted_counts: {submissions, comments}}` |
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
| GET | `/api/list-codebooks` | — | `{"codebooks": [{id, name, metadata, description, source}]}` | direct |
| PUT | `/api/codebook/{ref}` | JSON `{codes}` | saves a new version (the codebook editor's Refine mode, and View Codebook's save) | direct |
| POST | `/api/codebook-preview/` | JSON `{api_key, database, model, prompt?, sample_percentage, content_scope, existing_codes?}` | `202 {job_id, status}` → result `{proposals, partial?}` — creates nothing | **job** |
| POST | `/api/codebook/manual` | JSON `{database, name, description?, project_id?, codes}` | `{message, file}` — the codebook editor's only create path | direct |
| POST | `/api/compare-codebooks/` | `as_form(CompareCodebooksRequest)` | `202 {job_id, status}` → result `{comparison, file}` | **job** |
| POST | `/api/integrate-codebook-preview/` | JSON `{api_key, codebooks, model, prompt?, existing_codes?}` | `202 {job_id, status}` → result `{proposals, partial?}` — creates nothing | **job** |
| POST | `/api/codebook/integrate` | JSON `{codebooks, name, description?, project_id, codes, assist_runs?}` | `{message, file}` — the integrate editor's only create path | direct |

See [tools/codebook.md](tools/codebook.md), [tools/view-codebook.md](tools/view-codebook.md), [tools/compare-codebooks.md](tools/compare-codebooks.md), [tools/integrate-codebook.md](tools/integrate-codebook.md).

## Coding — `backend/app/api/coding_routes.py`

| Method | Path | Body | Response | Kind |
|---|---|---|---|---|
| POST | `/api/coding/manual` | JSON `{database, codebook, report_name, description?, project_id?, sample_percentage?, content_scope?, post_ids?, comment_ids?}` | `{message, file, counts}` — the Apply Codebook editor's only create path, always uncoded | direct |
| GET | `/api/coding/{ref}` | — | codebook snapshot + parsed tree + row/coded counts + code frequency | direct |
| GET | `/api/coding/{ref}/rows` | query `limit`/`offset`/`only`/`code`/`q` | one page of the artifact's own rows, each with its codes | direct |
| PUT | `/api/coding/{ref}/revision` | JSON (codebook edits and/or row edits) | saves the whole editing session as at most one new version | direct |
| POST | `/api/coding/{ref}/recode` | JSON `{api_key, item_ids, model?, methodology?}` | `202 {job_id, status}` → result `{proposals, ...}` — stages proposals, writes nothing | **job** |
| POST | `/api/coding/{ref}/duplicate` | `{display_name, from_version_no?}` | forks the whole artifact | direct |
| POST | `/api/compare-codings/` | form: `coding_a`, `coding_b`, `api_key`, `name` (required), `model`, `prompt`, `description`, `project_id` (optional) | `202 {job_id, status}` → result `{comparison, file}` | **job** |
| POST | `/api/summarize-coding/` | form: `coding`, `api_key`, `name` (required), `model`, `prompt`, `description`, `project_id` (optional) | `202 {job_id, status}` → result `{summary, file}` | **job** |

`compare-codings` and `summarize-coding` use raw `Form(...)` params, not Pydantic schemas — unlike the job endpoints built on `as_form(...)`.

See [tools/apply-codebook.md](tools/apply-codebook.md), [tools/view-coding.md](tools/view-coding.md), [tools/compare-codings.md](tools/compare-codings.md), [tools/summarize-coding.md](tools/summarize-coding.md).

Structural (no-LLM) diffing between two versions of the *same* codebook/coding artifact — as opposed to the LLM narrative comparison of two arbitrary artifacts above — lives at `GET /api/artifacts/{ref}/diff` (`backend/app/api/version_routes.py`), not as a standalone comparison endpoint.

## Export — `backend/app/api/export_routes.py`

Owner-scoped, byte-deterministic for unchanged data. An explicit `version_no` that doesn't resolve to a real version 404s rather than silently returning an empty export.

Each endpoint accepts only the formats that suit its artifact — not a blanket CSV/JSON pair — and a format outside that set 422s rather than falling through to the default:

| Method | Path | Query | Response | Kind |
|---|---|---|---|---|
| GET | `/api/export/{file_id}/codebook` | `format` (qdc\|csv, default qdc), `version_no?` | qdc: [REFI-QDA Codebook](https://www.qdasoftware.org/refi-qda-codebook) XML, importable by NVivo/ATLAS.ti/MAXQDA (`backend/app/core/qdc.py`); csv: one row per code for a spreadsheet or R | direct |
| GET | `/api/export/{file_id}/coding` | `format` (csv\|json, default csv), `layout` (long\|wide, default long), `version_no?`, `include_source_text` (default false), `include_author` (default false) | long: one row per coded segment; wide: one row per dataset item including uncoded ones, one column per code | direct |
| GET | `/api/export/{file_id}/summary` | `format` (md only), `version_no?` | markdown frequency table, grouped by `code_uid` (stable across renames) | direct |
| GET | `/api/export/{file_id}/memos` | `format` (md\|csv, default md) | row memos; md keeps a memo body's paragraph breaks, which a single CSV cell flattens | direct |
| GET | `/api/export/projects/{project_id}/bundle` | `include_source_text` (default false), `include_author` (default false) | deterministic ZIP: exactly one export per project file in that artifact's best format (codebooks as `.qdc`), a SHA-256 `manifest.json`, and `lineage/project_lineage.json` | direct |

Codebooks lead with `.qdc` because REFI-QDA is the one codebook interchange standard other QDA packages implement — every other format arrives there as an undifferentiated table. The serializer maps this app's `code_uid` (a bare `uuid4().hex`) onto the schema's hyphenated `GUIDType`, re-hyphenating rather than replacing it where the uid is already a UUID, so identity survives the round trip; a code family becomes a non-codable parent `Code` holding its codes. Conformance rules are pinned in `tests/backend/core/test_qdc.py`.

Summary is markdown-only by design: a frequency table is a finished reading of a coding, not source data something downstream re-parses — anyone wanting the numbers exports the coding itself and counts. The project bundle writes **one file per project file**, never the same content in two formats; a file's row memos ride along as a single `.md` sidecar, which for a `raw_data`/`filtered_data` file is its only export.

`include_source_text`/`include_author` default to `False` everywhere — an export is opt-in to carrying a quote's full source text or its author, not opt-out. Backed by `backend/app/services/export_service.py` and `backend/app/repositories/export_repo.py`.

## Data — `backend/app/api/data_routes.py`

| Method | Path | Body | Response | Kind |
|---|---|---|---|---|
| GET | `/api/word-count-ranges/` | query `schema` | `{submissions: [{min_words, count}], comments: [...]}`, bins 0–1000 step 10 | direct |
| GET | `/api/file-entries/` | query `schema`, `limit` (default 10), `offset` (default 0) | `{submissions, comments, total_submissions, total_comments, database, date_created}` | direct |
| GET | `/api/comments/{submission_id}` | query `database` (default `"original"`) | `{"comments": [...]}` ordered by `created_utc` | direct |
| POST | `/api/post-contents/` | JSON `{schema, post_ids}` | `{"contents": {post_id: {title, content}}}` | direct |
| POST | `/api/filter-preview/` | JSON `{api_key, database, model, prompt?, filter_tags?, min_words?, sample_percentage, content_scope, decided_post_ids?, decided_comment_ids?}` | `202 {job_id, status}` → result `{post_ids, comment_ids, partial?}` — creates nothing | **job** |
| POST | `/api/filtered-data/manual` | JSON `{database, name, description?, project_id?, post_ids, comment_ids}` | `{message, file, counts}` — the filter editor's only create path | direct |

See [tools/data-browser.md](tools/data-browser.md), [tools/filter.md](tools/filter.md).

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

`CompareCodebooksRequest` is the one remaining endpoint built on `as_form(...)`
(`multipart/form-data`, whitespace-stripped, unknown fields ignored): `api_key`
(required), `codebook_a`/`codebook_b` (required, `proj_<hex>` pattern each,
`^proj_[A-Za-z0-9_]+$`), `name` (required), `model`/`prompt`/`description`/
`project_id` (all optional). The one-shot `FilterDataRequest`/
`GenerateCodebookRequest`/`ApplyCodebookRequest` schemas this table used to
compare it against were retired along with their endpoints; the editors that
replaced them (`FilterPreviewRequest`, `ManualFilterRequest`,
`CodebookPreviewRequest`, `ManualCodebookRequest`, `ManualCodingRequest`,
`RecodeItemsRequest`) are JSON bodies instead, since each carries a list
(decided ids, existing codes, or row ids) that doesn't map onto flat form
fields — see the request bodies in the tables above. `compare-codings`/
`summarize-coding` take raw `Form(...)` parameters per field, no Pydantic
model in between.

## Errors

All service-layer errors render as `{"error": "<message>"}` with the matching status code (`AppError` hierarchy — see [architecture.md#errors](architecture.md#errors)). FastAPI request-validation failures (missing/malformed form fields) render as the standard 422 `{"detail": [...]}` shape instead.
