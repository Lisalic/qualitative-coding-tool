# Architecture

Developer-facing reference for how the app is wired end to end. Tool pages under [tools/](tools/README.md) link back here instead of repeating this material.

## Frontend layering

- Routing is centralized in `frontend/src/App.jsx`; most feature pages are lazy-loaded (`React.lazy`) and wrapped in `ProtectedRoute` so anonymous sessions can't reach tool pages.
- `frontend/src/components/shell/` (`ToolPage`, `ToolPageShell`, `ToolPageBody`, `ToolPanelHost`, `ViewPageShell`) keeps the Import/Filter/Generate/Apply screens and the View screens visually and structurally consistent. Compare and Summarize Coding hand-roll their own container instead of using the shell.
- `frontend/src/components/tool-panels/useToolPanelData.js` is the shared data-loading hook for the three form-driven tool panels (Filter, Generate Codebook, Apply Codebook) — it fetches raw DBs, filtered DBs, projects, and (optionally) codebooks in parallel on mount, so every tool panel gets a consistent source-selection UX for free.
- `frontend/src/lib/apiContracts.js` mirrors the field expectations of `backend/app/api/schemas.py` and validates required fields client-side (`assertRequired`, `assertProjSchema`) before the network call, so invalid submissions fail fast instead of round-tripping to get a 422. Only three of the six AI tools (Filter Data, Generate Codebook, Apply Codebook) go through this builder layer — Compare Codebooks/Codings and Summarize Coding assemble their `FormData` inline in their own components.
- `frontend/src/api.js` exports the shared `axios` instance (`api`, cookie + Bearer-token auth via `localStorage.getItem("access_token")`) and:
  - `postForm(path, formData)` — normalizes a response to `{ok, status, data, error}`, flattening FastAPI 422 `detail[]` arrays into a readable string.
  - `postFormAndPoll(path, formData, {intervalMs=2000, timeoutMs=600000, ...})` — the shared kickoff-then-poll helper for every job-backed endpoint: POSTs expecting `202 {job_id, status}`, then polls `GET /api/jobs/{job_id}` until the job reaches `succeeded`/`failed`/timeout.
- Styling is Tailwind CSS v4, utility classes directly in JSX — see [style-guide.md](style-guide.md).

## Backend layering

- Entry point `backend/app/main.py` mounts every router under `/api` (see `backend/app/api/routes.py`) and creates ORM tables on startup via `Base.metadata.create_all` (convenience/tests only — real schema changes go through Alembic, see [Migrations](#migrations)).
- Domain routers live in `backend/app/api/*_routes.py`, one per feature area (auth, files, prompts, codebooks, coding, data, projects, content, models) plus `backend/app/jobs/routes.py`. Every route is uniformly async: `Depends(get_async_db)` for DB access, `Depends(require_user_id)` for auth.
- Routes stay thin and delegate to `backend/app/services/<domain>_service.py`, which in turn uses `backend/app/repositories/` for DB access and `backend/scripts/*.py` for pipeline/LLM logic.
- New layers introduced by the recent storage refactor, all under `backend/app/`:
  - `core/` — `exceptions.py` (the `AppError` hierarchy, translated to JSON by one global FastAPI exception handler in `main.py`), `auth_dependency.py::require_user_id`/`optional_user_id`, `schema_guard.py` (schema-name validation), `logging.py`.
  - `external/` — the single OpenRouter call seam (`openrouter_client.py::chat_completion`, built on `AsyncOpenAI` plus a shared `retry_async` backoff helper), plus `errors.py` and `response_parsers.py`.
  - `repositories/` — all DB access to the fixed storage tables.
  - `services/` — per-domain business logic and job handlers.
  - `jobs/` — the background job queue.

## Auth

Hand-rolled HMAC-SHA256 JWT (`backend/app/auth.py`), not a third-party JWT library: `create_access_token`/`decode_access_token` sign/verify with `settings.jwt_secret_key`. Token resolution order (`backend/app/api/utils.py::get_user_id_from_request`): the `access_token` cookie first, then an `Authorization: Bearer <token>` header. Passwords are hashed with PBKDF2-HMAC-SHA256 (100,000 iterations), stored as `salt$iterations$hashhex`.

Two FastAPI dependencies wrap this: `require_user_id` (raises `UnauthorizedError` → 401 if absent) and `optional_user_id` (returns `None` instead of raising — used by a couple of file routes that need to run format validation before the auth check). Every route other than `/api/login/`, `/api/register/`, and `/api/logout/` requires a user.

`Settings` (`backend/app/config.py`) reads `jwt_secret_key`, `jwt_algorithm` (`HS256`), `jwt_access_token_expire_minutes` (default 480), `jwt_refresh_token_expire_minutes` (default 10080) from `backend/.env`. **Set `JWT_SECRET_KEY` explicitly** — the fallback default in code is the literal string `"your-secret-key-here"`.

## Errors

`backend/app/core/exceptions.py` defines `AppError` (base, 500) and four subclasses: `NotFoundError` (404), `ForbiddenError` (403), `UnauthorizedError` (401), `ValidationAppError` (400), `UpstreamServiceError` (502). A single `@app.exception_handler(AppError)` in `main.py` renders any of these as `{"error": message}` with the matching status code. Separately, FastAPI's own request-validation errors (missing/malformed form fields on the Pydantic-backed endpoints) render as the standard `{"detail": [...]}` 422 shape, which `frontend/src/api.js::postForm` flattens into a readable string.

## Background jobs

Slow, LLM-backed endpoints don't block the request. Instead they return `202 {"job_id": <int>, "status": "pending"}` immediately, and the actual work runs as an `asyncio.create_task` in-process.

**Flow:**

1. A route calls `backend/app/services/<domain>_service.py::start_<x>_job`, which validates input, resolves any `schemaname` references to `file_id`s, then calls `backend/app/jobs/service.py::enqueue_job(session, user_id=..., job_type=..., payload=..., runtime_extra=...)`.
2. `enqueue_job` inserts a `pending` `Job` row (only `payload` is persisted — **never** `runtime_extra`, which is how the OpenRouter API key stays out of the database) and hands `_execute_job(...)` to the singleton `AsyncioJobRunner` (`backend/app/jobs/runner.py`), which keeps a reference in `self._tasks` (with a done-callback cleanup) specifically to dodge the classic "GC'd asyncio task" footgun.
3. `_execute_job` opens its own DB session (the original request's session is long closed by the time this runs), sets `status="running"`, looks up the handler registered for `job_type` via `backend/app/jobs/registry.py::get_handler`, awaits it, and persists the result. It **never raises** — any exception (handler bug, DB error mid-update) is caught and the job is marked `failed` with `error`/`error_code` set, so a job can't get stuck at `running` forever.
4. The frontend polls `GET /api/jobs/{job_id}` (`backend/app/jobs/routes.py`) via `postFormAndPoll` until the job reaches `succeeded` or `failed`.

**Registered handlers** (`@register_handler("<job_type>")`):

| `job_type` | Handler | Module | Triggering endpoint |
|---|---|---|---|
| `filter_data` | `_run_filter_data_job` | `services/data_service.py` | `POST /api/filter-data/` |
| `generate_codebook` | `_run_generate_codebook_job` | `services/codebook_service.py` | `POST /api/generate-codebook/` |
| `compare_codebooks` | `_run_compare_codebooks_job` | `services/codebook_service.py` | `POST /api/compare-codebooks/` |
| `apply_codebook` | `_run_apply_codebook_job` | `services/coding_service.py` | `POST /api/apply-codebook/` |
| `compare_codings` | `_run_compare_codings_job` | `services/coding_service.py` | `POST /api/compare-codings/` |
| `summarize_coding` | `_run_summarize_coding_job` | `services/coding_service.py` | `POST /api/summarize-coding/` |

**Durability trade-off, accepted deliberately:** since a job's API key only ever lives in the runner's in-memory closure, a job in flight is lost if the process restarts. `backend/app/jobs/service.py::reconcile_orphaned_jobs_on_startup` (called from `main.py`'s lifespan, after tables are created) marks any leftover `pending`/`running` row as `failed` with `"Worker restarted before this job finished. Please retry."`, so the frontend fails loudly instead of polling forever. This also means the job runner does not horizontally scale: a second worker process would fail the first worker's in-flight jobs on its own startup.

`Job` model (`backend/app/jobs/models.py`): `id`, `job_type`, `user_id` (FK, cascade delete), `status` (`pending`/`running`/`succeeded`/`failed`), `payload` (JSON), `result` (JSON, nullable), `error`/`error_code` (nullable), `created_at`/`started_at`/`finished_at`.

## The LLM call seam

Every OpenRouter call funnels through `backend/app/external/openrouter_client.py`:

- `chat_completion(*, system_prompt, user_prompt, api_key, model, temperature=0.05, timeout=300.0, response_format=None, use_middle_out=True, max_retries=3, on_retry=None) -> str` — the single entry point. Sends `extra_body={"transforms": ["middle-out"]}` when `use_middle_out` (OpenRouter's context-compaction feature), raises `ExternalServiceError("OpenRouter returned an empty completion")` on an empty response, and wraps any other exception as `ExternalServiceError` with an HTTP status code extracted from the error message.
- `retry_async(fn, *, max_retries=3, initial_delay_s=2.0, is_retryable=None, on_retry=None)` — shared exponential-backoff helper (`2.0 * 2^(attempt-1)`), reused by the OpenRouter client and by `tag_expansion.py`.

Per-script response *parsing* is intentionally **not** deduplicated into this seam, because the six pipeline scripts genuinely have different output contracts — free-form markdown (codebook generation), the `POST_ID`/`CODE`/`EVIDENCE` DSL (codebook application), a bare Python-literal array (AI filtering), and real JSON (tag expansion). Only the actually-shared primitives — markdown-fence stripping, OpenRouter error-code extraction and friendly messaging — are deduped into `backend/app/external/response_parsers.py` and `backend/app/external/errors.py` / `backend/scripts/openrouter_http.py`.

The OpenRouter API key is always supplied per-request by the caller (see [concepts.md#api-key-handling](concepts.md#api-key-handling)) — never stored server-side.

## Model catalog

`backend/app/ai_models.py` loads `backend/constants/openrouter_models.json` at import time into `AI_MODELS` (28 entries: 22 free, 6 paid) and exposes:

- `model_slug_at(index)` — clamped lookup, used by pipeline scripts to pick their module-level defaults.
- `is_paid_model(slug)` — live lookup against the current in-memory catalog.
- `set_catalog(models)` / `refresh_from_openrouter()` — replace the catalog; called once at startup and then every 24 hours by a background task spawned in `main.py`'s lifespan (`fetch_openrouter_catalog`, an unauthenticated `GET https://openrouter.ai/api/v1/models`, keeps only text-in/text-out models, and computes USD-per-million pricing).
- `GET /api/models` (`backend/app/api/models_routes.py`) — serves the live catalog to the frontend's `AiModelFormGroup`.

**Caveat:** `backend/scripts/codebook_generator.py::MODEL_1..MODEL_7` and `backend/scripts/codebook_apply.py::FREE_MODEL` are bound via `model_slug_at(...)` **at import time**, so they keep pointing at whichever free models were current at process start and do **not** track the daily refresh. `is_paid_model` and a fresh `GET /api/models` call both see the live catalog immediately, since they look it up at call time. `backend/scripts/filter_db.py::FREE_MODEL` and `backend/scripts/tag_expansion.py::DEFAULT_MODEL` don't consult the catalog at all — they hardcode `"meta-llama/llama-3.3-70b-instruct:free"`.

## Storage

### Relational metadata (`backend/app/database.py`)

| Table | Purpose |
|---|---|
| `users` | account records |
| `projects` | user-owned groupings of files |
| `project_files` | many-to-many between `projects` and `files` |
| `files` | one row per artifact — a git-style **ref**: `file_type`, `schemaname`, description. Identity only; no content and no prompts (those live on the version row, see below) |
| `file_tables` | per-`file_id` row counts, keyed by table name (`submissions`/`comments`) |
| `prompts` | the user's saved prompt library (see [Prompt Manager](tools/prompt-manager.md)) |

### Fixed content tables (`backend/app/storage_models.py`, `backend/app/versioning_models.py`)

Replaces the old per-artifact dynamic-schema model (see [concepts.md#schemaname](concepts.md#schemaname-an-opaque-identifier-not-a-postgres-schema)) with a handful of normal tables, all keyed by `file_id`:

| Table | Purpose | Key columns |
|---|---|---|
| `submissions` | raw/filtered post rows | `(file_id, id)` PK; `word_count` generated column, indexed with `file_id` |
| `comments` | raw/filtered comment rows | `(file_id, id)` PK; `word_count` generated column, indexed with `file_id` |
| `artifact_versions` | one **commit** per save, sealed the instant it's created — `version_no`, `origin` (generated/edited/imported/forked), `sealed_at`, `job_id`/`model`/`system_prompt` provenance, plus `user_instructions` (the human-authored fragment only) and `prompt_meta` (a length/hash of the LLM-rendered prompt — the rendered prompt itself is not stored, since it duplicates data already in `submissions`/`comments`), and `content` (used only by blob-storage artifact types: `codebook_comparison` / `coding_comparison` / `summary`) | `UNIQUE(file_id, version_no)`; self-FK `parent_version_id` (cross-file for a fork's v1) |
| `artifact_edges` | typed, ordered, version-pinned derivation between artifacts — replaces the old untyped `file_dependencies` | `(child_file_id, parent_file_id, parent_version_id, relation, role, position)` |
| `codebook_codes` | one row per code, keyed by a stable `code_uid`/`family_uid` so renames are recorded rather than inferred — the content of a `codebook` artifact and of a `coding` artifact's own codebook snapshot | `UNIQUE(version_id, code_uid)` |
| `coding_entries` | structured, SCD-2 range-versioned `(file_id, row_type, post_id, code_uid, evidence, notes, valid_from, valid_to)` rows — a row is **live** iff `valid_to IS NULL`; superseding at version `N` closes the old row with `valid_to = N - 1` rather than deleting it | `(file_id, code_uid)` and liveness-filtered indexes |

`coding_entries` exists so code-frequency queries (`GROUP BY code_uid`) can run directly in SQL instead of re-parsing a blob client-side — see `backend/app/repositories/coding_repo.py::code_frequency`. Every read goes through that module's `_live()` helper so a superseded (closed) range never reappears as current coding.

All access to these tables goes through `backend/app/repositories/`: `file_repo.py` (schemaname → `file_id` resolution, ownership checks), `raw_data_repo.py` (bulk insert, sampling, row copy for filter/merge), `version_repo.py` (dumb CRUD on `artifact_versions`/`artifact_edges`/`codebook_codes` — no policy), `coding_repo.py` (SCD-2 read/write + frequency queries), `project_repo.py`. Policy — no-op suppression, the three `commit_*` write paths, forking — lives one layer up in `backend/app/services/version_service.py`; see that module's docstring. Every commit is sealed the instant it's created (no unsealed "draft" state to open, mutate, or auto-seal) — the `POST /api/artifacts/{ref}/checkpoint` route that once let a user trigger sealing manually has been removed, since there was never anything left for it to do. History is strictly append-only — there is no revert route. Recovering an old state is "duplicate from that version" instead (`POST /api/coding/{ref}/duplicate` / `POST /api/codebook/{ref}/duplicate`, both taking an optional `from_version_no`) — non-destructive, so it needs no guard against another artifact's `parent_version_id` pin.

Not every version owns a `codebook_codes` row set of its own. v1, the 3 most recent versions of any file, and every 10th version ("keyframe") stay fully materialized; everything else is compacted to a field-level delta (`codes_delta`, `backend/app/core/codebook_delta.py::encode_delta`) computed directly against its nearest still-materialized ancestor, checked once per commit (O(1), never a sweep — `version_service._demote_if_eligible`). A coding version born from a row-only edit (`save_coding_rows`, an AI recode) skips materialization from birth rather than storing an empty delta, since its codes are identical to its predecessor's by construction; `version_service.read_codes` resolves either case (a plain inherit or a real compacted delta) by looking up the nearest earlier materialized version and applying `codes_delta` if there is one. Every version that existed before this scheme was added defaults to materialized, so no backfill was needed. See `ArtifactVersion.codes_materialized`'s docstring for the full policy and reasoning (including why each compacted version stores one delta computed directly against its anchor, not a step in a consecutive chain).

## Migrations

Alembic is used for schema changes (`alembic.ini` at repo root, `backend/alembic/`, revisions under `backend/alembic/versions/`). `Base.metadata.create_all` still runs at startup for convenience and in tests, but any real schema change goes through a new Alembic revision.

Revision `a1e6f2c9b3d7` ("baseline untracked schema") is the root of the chain and exists purely so `alembic upgrade head` works against a genuinely empty database — before it, most tables (`users`, `projects`, `files`, `file_tables`, `project_files`, a since-removed `file_dependencies`, `prompts`, `submissions`, `comments`, a since-removed `artifact_content`, `coding_entries`) had never actually been created by any revision, only by `create_all`, so the chain silently depended on that convenience path having already run. **No operator action is needed on any existing database** — a database already stamped past this point in history sees the new root as already-satisfied and `alembic upgrade head` is a no-op for it; only a fresh/empty database exercises this revision's DDL. See its module docstring for the full story, including how a Postgres-only `sa.Computed(...)` column now makes the `word_count` generated-column claim in `backend/app/storage_models.py` actually true.

Two later revisions, `c2e58b41d7af` ("artifact version spine") and `d4f97a2c6e1b` ("artifact version spine finalize"), replace `file_dependencies`/`artifact_content` with `artifact_versions`/`artifact_edges`/`codebook_codes` and add SCD-2 columns to `coding_entries` — additive first (so the backfill script below can run against both old and new shapes at once), then a second revision drops the old tables/columns once the backfill is confirmed clean. See "One-off scripts" below.

Three more revisions shrink `artifact_versions` itself, in sequence: `e7a3d1c9b482` drops the fully-rendered `user_prompt` (it duplicated data already in `submissions`/`comments` — 119 MB across 61 rows measured on the real dev database, 99.94% of the table) in favor of `user_instructions` (the human-authored fragment only) plus `prompt_meta` (a length/hash of what was actually sent); `f2b6c8e0a913` adds `codes_materialized` so a coding row-only save stops copying the whole codebook snapshot forward; `a4d7f931c8e5` adds `codes_delta` so a genuine codebook edit that ages out of the retained window is compacted to a field-level delta instead of staying materialized forever. None of the three needs a backfill — see each revision's own docstring for why the existing rows are already valid under the new scheme.

One-off scripts relate to storage migrations:

- `backend/scripts/drop_migrated_schemas.py` — irreversible `DROP SCHEMA` for already-migrated schemas; dry-run by default, requires `--confirm`.
(`backfill_codebook_codes.py`, referenced by the docstrings of `c2e58b41d7af`/`d4f97a2c6e1b` as the manual step between them, has been removed — it read `files.systemprompt`/`userprompt` and `artifact_content`, all of which `d4f97a2c6e1b` itself drops, so it could only ever run in the window between those two revisions. That window is closed on every real database, and a fresh database has nothing to backfill.)

(`migrate_to_fixed_tables.py`, the original dynamic-schema-to-fixed-table backfill, has been removed — its job was already done on every real database, and its target table, `artifact_content`, no longer exists after the version-spine cutover.)

## Deployment

Deployed to Azure Web App via `.github/workflows/main_qualitative-coding-tool.yml` on push to `main`. The workflow uploads the repo as-is (dependency install happens server-side via Azure Oryx); the Azure startup command runs `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. CORS in `main.py` is locked to `http://localhost:5173` plus the deployed Vercel frontend origins — update that list when adding a new frontend origin.

Several backend modules (`databasemanager.py`, `auth.py`) use a `try: from backend.app.X import ... except Exception: from app.X import ...` fallback pattern, because the Azure deployment and local `uvicorn backend.app.main:app` runs can end up with different values on `sys.path`/cwd.
