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
| GET | `/api/list-codebooks` | — | `{"codebooks": [{id, name, metadata, description, source}]}` | direct |
| PUT | `/api/codebook/{ref}` | JSON `{codes}` | saves a new version (the codebook editor's Refine mode, and View Codebook's save) | direct |
| POST | `/api/codebook-preview/` | JSON `{api_key, database, model, prompt?, sample_percentage, content_scope, existing_codes?}` | `202 {job_id, status}` → result `{proposals, partial?}` — creates nothing | **job** |
| POST | `/api/codebook/manual` | JSON `{database, name, description?, project_id?, codes}` | `{message, file}` — the codebook editor's only create path | direct |
| POST | `/api/integrate-codebook-preview/` | JSON `{api_key, codebooks, model, prompt?, existing_codes?}` | `202 {job_id, status}` → result `{proposals, partial?}` — creates nothing | **job** |
| POST | `/api/codebook/integrate` | JSON `{codebooks, name, description?, project_id, codes, assist_runs?}` | `{message, file}` — the integrate editor's only create path | direct |

`compare-codebooks` (an LLM-generated, job-backed comparison) has been retired in favor of the deterministic `GET /api/comparison/codebooks` — see the Comparisons section below.

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
| POST | `/api/summarize-coding/` | form: `coding`, `api_key`, `name` (required), `model`, `prompt`, `description`, `project_id` (optional) | `202 {job_id, status}` → result `{summary, file}` | **job** |

`summarize-coding` uses raw `Form(...)` params, not a Pydantic schema. `compare-codings` (an LLM-generated, job-backed comparison) has been retired in favor of the deterministic `GET /api/comparison/codings` — see the Comparisons section below.

See [tools/apply-codebook.md](tools/apply-codebook.md), [tools/view-coding.md](tools/view-coding.md), [tools/compare-codings.md](tools/compare-codings.md), [tools/summarize-coding.md](tools/summarize-coding.md).

## Comparisons — `backend/app/api/comparison_routes.py`

Deterministic, no-LLM cross-artifact diffs. No API key, no background job — computed and returned synchronously.

| Method | Path | Query | Response | Kind |
|---|---|---|---|---|
| GET | `/api/comparison/codebooks` | `file_a`, `file_b` (ref or id), `version_a?`, `version_b?` | structural code diff: `added`/`removed`/`renamed`/`redefined`/`moved`/`reordered`/`unchanged`, `unrelated_histories`, `is_empty` | direct |
| GET | `/api/comparison/codings` | `file_a`, `file_b` (ref or id), `version_a?`, `version_b?` | classification diff: row/coded counts, `rows_recoded`/`rows_newly_coded`/`rows_newly_uncoded`, per-code deltas with evidence | direct |

Backed by `backend/app/services/comparison_service.py` (`compare_codebooks`/`compare_codings`) and `backend/app/core/codebook_diff.py`/`coding_diff.py`. Swapping A/B is a tested reversibility invariant. See [tools/compare-codebooks.md](tools/compare-codebooks.md), [tools/compare-codings.md](tools/compare-codings.md).

## Export — `backend/app/api/export_routes.py`

CSV/JSON/ZIP exports, owner-scoped, byte-deterministic for unchanged data. An explicit `version_no` that doesn't resolve to a real version 404s rather than silently returning an empty export.

| Method | Path | Query | Response | Kind |
|---|---|---|---|---|
| GET | `/api/export/{file_id}/codebook` | `format` (csv\|json), `version_no?` | codebook codes file | direct |
| GET | `/api/export/{file_id}/coding` | `format`, `layout` (long\|wide, default long), `version_no?`, `include_source_text` (default false), `include_author` (default false) | long: one row per coded segment; wide: one row per dataset item including uncoded ones, one column per code | direct |
| GET | `/api/export/{file_id}/summary` | `format`, `version_no?` | code frequency, grouped by `code_uid` (stable across renames) | direct |
| GET | `/api/export/{file_id}/memos` | `format` | row memos | direct |
| GET | `/api/export/projects/{project_id}/bundle` | `include_source_text` (default false), `include_author` (default false) | deterministic ZIP: every project artifact's exports, a SHA-256 `manifest.json`, and `lineage/project_lineage.json` | direct |

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

Every request body in the tables above is a JSON body validated against one
of these models — there is no remaining endpoint built on `as_form(...)`.
That adapter (which turned a Pydantic model into a FastAPI dependency
reading `multipart/form-data` fields) existed for exactly one caller,
`CompareCodebooksRequest`; once `compare-codebooks` was retired (see the
Comparisons section above), `as_form` had zero remaining callers and was
deleted rather than kept as unused infrastructure. The handful of
endpoints still on multipart (`summarize-coding`, and the retired
one-shot `FilterDataRequest`/`GenerateCodebookRequest`/
`ApplyCodebookRequest` tools before them) never went through it: they
take raw `Form(...)` parameters per field, no Pydantic model in between.
The editors (`FilterPreviewRequest`, `ManualFilterRequest`,
`CodebookPreviewRequest`, `ManualCodebookRequest`, `ManualCodingRequest`,
`RecodeItemsRequest`) are JSON bodies instead, since each carries a list
(decided ids, existing codes, or row ids) that doesn't map onto flat form
fields — see the request bodies in the tables above.

## Errors

All service-layer errors render as `{"error": "<message>"}` with the matching status code (`AppError` hierarchy — see [architecture.md#errors](architecture.md#errors)). FastAPI request-validation failures (missing/malformed form fields) render as the standard 422 `{"detail": [...]}` shape instead.
