# API Reference

Every endpoint is mounted under `/api` (`backend/app/main.py` → `backend/app/api/routes.py`). Unless noted, all routes require auth via `Depends(require_user_id)` (401 `{"error": "Not authenticated"}` if missing — see [architecture.md#auth](architecture.md#auth)).

"Job" endpoints return `202 {"job_id": <int>, "status": "pending"}` immediately; poll `GET /api/jobs/{job_id}` for the result. See [architecture.md#background-jobs](architecture.md#background-jobs).

One route exists outside `/api`: `GET /` → `{"message": "Qualitative Coding API"}`, no auth, defined directly on the FastAPI app.

## Authentication — `backend/app/api/auth_routes.py`

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/api/login/` | none | JSON `{email, password}` | `{id, email, access_token}` + `Set-Cookie access_token`; 401 on bad credentials |
| POST | `/api/register/` | none | JSON `{email, password}` (password at least 8 characters, email must look like an address) | same shape as login; 400 if email taken |
| GET | `/api/me/` | required | — | `{id, email}` |
| POST | `/api/logout/` | none | — | `{"message": "Logged out"}`, clears the cookie |

See [tools/authentication.md](tools/authentication.md).

## Files — `backend/app/api/file_routes.py`

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/upload-zst/` | multipart: `file` (`.zst`, required), `data_type` (`posts`\|`comments`, required), `name`, `description`, `project_id` (required) | `{file_name, authenticated, display_name, description, schema_name, inserted_counts: {submissions, comments}, skipped_counts}` -- `skipped_counts` tallies records left out by reason (`no_text`, `duplicate`, `unreadable`, `no_id`); a truncated or unreadable file is a 400 and creates nothing |
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
| GET | `/api/codebook-comparisons` | query `codebooks` (repeated, ≥2) | `{comparisons: [{id, schema_name, filename, created_at}]}` — comparisons between two of the given codebooks | direct |
| POST | `/api/integrate-codebook-preview/` | JSON `{api_key, codebooks, model, prompt?, existing_codes?}` | `202 {job_id, status}` → result `{proposals, partial?}` — creates nothing | **job** |
| POST | `/api/codebook/integrate` | JSON `{codebooks, name, description?, project_id, codes, assist_runs?}` | `{message, file}` — the integrate editor's only create path | direct |

See [tools/codebook.md](tools/codebook.md), [tools/view-codebook.md](tools/view-codebook.md), [tools/compare-codebooks.md](tools/compare-codebooks.md), [tools/integrate-codebook.md](tools/integrate-codebook.md).

## Coding — `backend/app/api/coding_routes.py`

| Method | Path | Body | Response | Kind |
|---|---|---|---|---|
| POST | `/api/coding/manual` | JSON `{database, codebook, report_name, description?, project_id?, sample_percentage?, content_scope?, post_ids?, comment_ids?}` | `{message, file, counts}` — the Apply Codebook editor's only create path, always uncoded | direct |
| GET | `/api/coding/{ref}` | — | codebook snapshot + parsed tree + row/coded counts + code frequency | direct |
| GET | `/api/coding/{ref}/rows` | query `limit`/`offset`/`only` (`all`\|`coded`\|`uncoded`\|`ai`\|`human`)/`code` (a `code_uid`)/`q` | one page of the artifact's own rows, each with its codes; `ai` = rows with any AI-coded entry, `human` = coded rows with none | direct |
| GET | `/api/coding/{ref}/quotes` | query `limit`/`offset`/`code` (name or `code_uid`)/`coder`/`q`/`starred_only`/`version_no` | `{quotes, total}` — one row per coded quote with source context and the caller's star | direct |
| PUT | `/api/coding/{ref}/quotes/{entry_id}/star` | JSON `{starred}` | `{entry_id, starred}` — star is keyed on the quote's identity (row + code + span), so it survives re-saves | direct |
| PATCH | `/api/coding/{ref}/quotes/{entry_id}/notes` | JSON `{notes}` | `{entry_id, notes}` — saved as a new coding version, so `entry_id` is the quote's **new** id; only live quotes can be annotated | direct |
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

`{ref}` is a file's numeric id or its `schema_name`. Each endpoint accepts only the formats that suit its artifact — not a blanket CSV/JSON pair — and a format outside that set 422s rather than falling through to the default:

| Method | Path | Query | Response | Kind |
|---|---|---|---|---|
| GET | `/api/export/{ref}/codebook` | `format` (docx\|xlsx\|qdc\|csv, default docx), `version_no?` | docx: a readable codebook (families as headings, each code's definition/include/exclude/example/keywords); xlsx: one row per code; qdc: [REFI-QDA Codebook](https://www.qdasoftware.org/refi-qda-codebook) XML, importable by NVivo/ATLAS.ti/MAXQDA (`backend/app/core/qdc.py`); csv: one row per code for R | direct |
| GET | `/api/export/{ref}/coding` | `format` (xlsx\|docx\|csv\|json, default xlsx), `layout` (long\|wide, csv/json only, default long -- passing it with xlsx/docx is a 400), `version_no?`, `include_source_text` (default false), `include_author` (default false) | xlsx: one workbook with *Coded quotes*, *Matrix* (every item incl. uncoded, one column per code), *Codebook*, *Code counts* and *About this export* sheets; docx: a code report, every quote under its code; csv/json long: one row per coded segment; wide: one row per dataset item, one column per code | direct |
| GET | `/api/export/{ref}/summary` | `format` (docx\|xlsx\|md, default docx), `version_no?` | code-frequency table, grouped by `code_uid` (stable across renames) | direct |
| GET | `/api/export/{ref}/memos` | `format` (docx\|xlsx\|md\|csv, default docx) | row memos; docx/md keep a memo body's paragraph breaks, which a single CSV cell flattens | direct |
| GET | `/api/export/{ref}/document` | `format` (docx\|md, default docx), `version_no?` | a saved `summary` or `codebook_comparison`/`coding_comparison`: docx renders its stored markdown (headings, lists, tables, emphasis; raw HTML stays literal text and links become `text (url)`), md returns it as stored | direct |
| GET | `/api/export/projects/{project_id}/bundle` | `include_source_text` (default false), `include_author` (default false), `codebook_formats` (`docx`\|`xlsx`\|`qdc`\|`csv`, default `docx`), `coding_formats` (`xlsx`\|`docx`\|`csv_long`\|`csv_wide`\|`json`, default `xlsx`), `comparison_formats` / `summary_formats` (`docx`\|`md`, default `docx`), `memo_formats` (`docx`\|`xlsx`\|`md`\|`csv`, default `docx`) -- each format param repeatable | deterministic ZIP: one export per project file per requested format (by default just Word/Excel), a SHA-256 `manifest.json` (schema 3.0, recording the formats used), and `lineage/project_lineage.json` | direct |

Word and Excel lead every export because most users aren't technical: a `.docx`/`.xlsx` opens with a double-click and holds multi-line text and several related tables properly. The interchange formats stay available after them. `.qdc` is still the way to move a codebook into another QDA package, since REFI-QDA is the one codebook interchange standard they implement. The serializer maps this app's `code_uid` (a bare `uuid4().hex`) onto the schema's hyphenated `GUIDType`, re-hyphenating rather than replacing it where the uid is already a UUID, so identity survives the round trip; a code family becomes a non-codable parent `Code` holding its codes. Conformance rules are pinned in `tests/backend/core/test_qdc.py`.

By default the project bundle writes **one file per project file**, in its Word/Excel format; repeating a `*_formats` param writes the same artifact once per requested format (the Project page's **Download** dialog exposes these as checkboxes). A file's row memos ride along as a sidecar (`.docx` by default), which for a `raw_data`/`filtered_data` file is its only export. Word/Excel files are frozen to fixed timestamps (`backend/app/core/xlsx_render.py::freeze_ooxml`), so a bundle stays byte-identical for unchanged data.

**Injection safety.** Every export query is ORM-built with bound parameters, and `ref` is only ever a bound value matched inside the owner-scoped query (`file_repo._lookup_file`). User text passes through the sanitizer for its destination (`backend/app/core/export_text.py`):
- spreadsheet cells can't become formulas. CSV gets a `'` prefix, including payloads behind leading whitespace. XLSX stores every string as a string cell, never a formula, and flags formula-like ones with Excel's `quotePrefix`.
- XML formats (qdc/docx/xlsx) drop the control characters XML forbids.
- generated markdown headings and table cells escape newlines, pipes, block markers and raw HTML.

An over-long XLSX cell (Excel caps cells at 32,767 characters) is cut with a visible marker and counted on the *About this export* sheet. The download name travels as RFC 6266 `filename*`; the frontend's `filenameFromDisposition` additionally removes path separators and control characters.

`include_source_text`/`include_author` default to `False` everywhere — an export is opt-in to carrying a quote's full source text or its author, not opt-out. Backed by `backend/app/services/export_service.py` and `backend/app/repositories/export_repo.py`.

## Data — `backend/app/api/data_routes.py`

| Method | Path | Body | Response | Kind |
|---|---|---|---|---|
| GET | `/api/word-count-ranges/` | query `schema` | `{submissions: [{min_words, count}], comments: [...]}`, bins 0–1000 step 10 | direct |
| GET | `/api/file-entries/` | query `schema`, `limit` (default 10, max 1000), `offset` (default 0), `q` (only rows whose text, subreddit or author contains it; totals count matches) | `{submissions, comments, total_submissions, total_comments, database, date_created}` | direct |
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
