# Campaign Verification Log

**Last updated:** 2026-09-12 (Recovery remediation completed)

## Baseline Verification
- **Command:** `.venv/bin/python -m pytest -q`  
  - **Result:** PASSED (1,324 passed, 5 deselected in 18.06s).
- **Command:** `cd frontend && npm run test:run`  
  - **Result:** PASSED (9 test files passed, 267 passed tests).
- **Command:** `cd frontend && npm run lint`  
  - **Result:** FAILED with 19 problems (13 errors, 6 warnings).  
  - **Details:** 13 pre-existing errors in `api.js` (empty block), `useLoginPage.js` (empty blocks), `useRegisterPage.js` (empty blocks), `FileUpload.jsx` (unused var), `PromptManager.jsx` (unused vars, empty blocks), `Navbar.jsx` (empty block).
- **Command:** `cd frontend && npm run build`  
  - **Result:** PASSED (built in 850ms).

---

## Ticket Verification Evidence & Independent Review Remediation

### QC-001: CSV and JSON Export Foundation
- **Initial Verdict:** PASSED in `daf10cd` (Found 2 release blockers upon independent review)
- **Remediation Verdict:** PASSED
- **Verification Date:** 2026-09-12
- **Command Runs:**
  - `.venv/bin/python -m pytest tests/backend/services/test_export_service.py tests/backend/routes/test_export_routes.py`: **PASSED** (14 passed in 0.29s)
  - `npm run test:run` (in `frontend/`): **PASSED** (includes `exportHelpers.test.js` and `ExportDropdown.test.jsx` - 9 passed)
  - `npm run build` (in `frontend/`): **PASSED** (built in 824ms)
- **Defects Remediated:**
  - **Determinism Defect**: `export_service.py` injected `"exported_at": datetime.now(...)` in exported JSON payloads, violating byte-identical reproducibility for unchanged artifacts. Fixed by removing the dynamic timestamp so repeated exports of identical data are byte-identical.
  - **Versioned Summary Defect**: `export_summary` and `/api/export/{file_id}/summary` ignored `version_no` query parameter sent by frontend `buildExportPath`. Threaded `version_no` through route query and service parameter, resolved SCD-2 historical entries via `coding_repo.entries_as_of`, attached `_v{version_no}` to filenames, and included `version_no` metadata in JSON exports.
  - **Export UX Accessible Error Handling Defect**: `ExportDropdown.jsx` swallowed download errors with `console.error`. Added accessible error alert (`role="alert"`, `aria-live="assertive"`) following black-and-white palette guidelines, with dismiss and retry-clearing semantics, tested in `ExportDropdown.test.jsx`.

### QC-007: Corpus Coverage Dashboard
- **Verdict:** PASSED
- **Commit:** `dcf34a9`
- **Verification Date:** 2026-09-11
- **Command Runs:**
  - `.venv/bin/python -m pytest tests/backend/core/test_coverage_metrics.py tests/backend/routes/test_coverage_routes.py -q`: **PASSED** (7 passed in 0.25s)
  - `npm run test:run` (in `frontend/`): **PASSED**
  - `npm run build` (in `frontend/`): **PASSED**
- **Changes Delivered:**
  - Created `frontend/src/components/coverage/CodingCoverageDashboard.jsx` presenting descriptive coverage notice, coded/uncoded breakdown, coverage percentage bar, and code family rollups with code count breakdown.
  - Integrated coverage dashboard seamlessly into `CodingCodebookSidebar.jsx` and `CodingWorkspaceSection.jsx`.
  - Added unit test suite `tests/backend/core/test_coverage_metrics.py` (4 tests) and API route test suite `tests/backend/routes/test_coverage_routes.py` (3 tests).

### QC-002: Computed Cross-Artifact Comparison
- **Verdict:** PASSED
- **Commit:** `324128b`
- **Verification Date:** 2026-09-11
- **Command Runs:**
  - `.venv/bin/python -m pytest tests/backend/core/test_cross_comparison.py tests/backend/routes/test_comparison_routes.py -q`: **PASSED** (8 passed in 0.28s)
  - `npm run test:run` (in `frontend/`): **PASSED**
  - `npm run build` (in `frontend/`): **PASSED**
- **Changes Delivered:**
  - Created `backend/app/core/cross_comparison.py`: deterministic, order-insensitive cross-comparison for codebooks (structural Jaccard similarity, added/removed/renamed/modified code tracking) and coding datasets (agreement rate, Cohen's kappa, per-code precision/recall/F1, per-item discrepancies).
  - Created `backend/app/services/comparison_service.py` and `backend/app/api/comparison_routes.py` (`GET /api/compare/codebooks` and `GET /api/compare/codings`).
  - Created `frontend/src/components/compare/ComputedComparisonResults.jsx` with symmetric swap reversibility and full metric displays.
  - Integrated into `ComparePageContainer.jsx` and `useComparePageData.js`.

### QC-005: Usage, Call-Count, Duration, and Cost Accounting & QC-006: Explicit Partial-Job Semantics
- **Initial Verdict:** PASSED in `1162008` (Found 2 release blockers upon independent review)
- **Remediation Verdict:** PASSED
- **Verification Date:** 2026-09-12
- **Command Runs:**
  - `.venv/bin/python -m pytest tests/backend/jobs/test_partial_and_cancellation.py`: **PASSED** (7 passed in 0.35s)
  - `.venv/bin/python -m pytest -m integration tests/backend/integration/test_alembic_migration.py`: **PASSED** (6 passed against live PostgreSQL in 1.05s)
  - `.venv/bin/python -m pytest tests/backend/core/test_accounting_pricing.py tests/backend/jobs/`: **PASSED** (36 passed in 1.52s)
  - `npm run test:run` (in `frontend/`): **PASSED**
  - `npm run build` (in `frontend/`): **PASSED**
- **Defects Remediated:**
  - **Missing Database Migration**: `backend/app/jobs/models.py` had introduced `Job.accounting` and `Job.salvaged_output` columns without an Alembic migration script. Created migration `e8a2b3c4d5f6_add_jobs_accounting_and_salvaged_output.py` adding both JSON columns in `upgrade()` and dropping them in `downgrade()`. Updated `tests/backend/integration/test_alembic_migration.py` to assert correct downgrade/upgrade roundtrip and live PostgreSQL schema reflection with zero drift.
  - **Terminal Cancellation Semantics & Race Condition**: In `backend/app/jobs/service.py`, `cancel_job` omitted `partial` and `retryable_failure` from terminal status checks, allowing relabeling of completed/partial jobs as cancelled. Concurrently executing jobs completing while cancellation was requested could also overwrite state non-deterministically. Defined shared immutable `TERMINAL_STATUSES` in `backend/app/jobs/models.py`, added atomic `where(Job.status.notin_(TERMINAL_STATUSES))` SQL update guards to both `cancel_job` and `_execute_job`, and verified with 3 new concurrency/terminal state regression tests.

---

## Final Pilot Gate Verification (Post-Remediation)
- **Full Backend Pytest Gate:** `.venv/bin/python -m pytest`  
  - **Result:** **1,369 passed**, 12 deselected, 0 failures in 12.95s.
- **Alembic PostgreSQL Integration Gate:** `.venv/bin/python -m pytest -m integration tests/backend/integration/test_alembic_migration.py`  
  - **Result:** **6 passed** against live PostgreSQL in 1.05s, 0 unallowed schema drift.
- **Full Frontend Vitest Gate:** `npm run test:run`  
  - **Result:** **276 passed** across 11 test files, 0 failures.
- **Frontend Build Gate:** `npm run build`  
  - **Result:** **PASSED** in 824ms with 0 errors.
- **Frontend ESLint Baseline Gate:** `npm run lint`  
  - **Result:** Exactly **19 baseline problems** (13 errors, 6 warnings), **0 new problems/regressions**.

## Historical Process Defect Record
During earlier pilot commits (`daf10cd`, `dcf34a9`, `324128b`, `1162008`), unrelated pre-existing modified files in the working directory were unintentionally swept into commits. To maintain safety rules and avoid destructive git history surgery (e.g. rebasing or amending published commits), this recovery isolated all defect remediation files and commits them via strictly scoped conventional commits.

---

## Integration Campaign: T3 Branch Consolidation (2026-09-12)

### W1: WIP consolidation onto `integration/consolidated`
- **Command:** `git clone --no-hardlinks -b integration/consolidated <repo> <scratch>` then `diff -rq --exclude=.git <repo> <scratch>`
  - **Result:** PASSED — no tracked-file differences (only local caches/venvs/IDE files, all untracked/ignored, appeared in the diff).

### W2: Job lifecycle
- **Command:** `.venv/bin/python -m pytest -q tests/backend/jobs/ tests/backend/core/test_accounting_pricing.py tests/backend/external/test_errors.py tests/backend/external/test_openrouter_client.py`
  - **Result:** PASSED (all targeted tests green) before being folded into the full-suite run below.
- **Verified defects fixed:**
  - `external/pricing.py`/`jobs/progress.py`/`external/openrouter_client.py`: an unknown/missing token count or unrecognized model now yields `None` (`known: False`), not a guessed `0.0` — confirmed via `test_missing_or_unknown_model_pricing_fallback` and `test_unknown_token_counts_never_coerced_to_zero`.
  - `jobs/service.py::_execute_job`: a job cancelled before its background task's first DB write now stays `cancelled` instead of being resurrected to `running` — confirmed via `test_execute_job_does_not_resurrect_a_job_cancelled_before_it_started`.
  - `jobs/service.py`: exception text persisted to `jobs.error` is redacted against the job's own `api_key` — confirmed via `test_job_error_redacts_api_key_from_exception_text`.
  - `jobs/models.py`: `JOB_STATUSES`/`TERMINAL_STATUSES` no longer contain the vestigial `"completed"` value found in the base tree (a leftover from a half-applied earlier rename); the runtime path only ever writes `"succeeded"`.

### W3: LLM comparison creation removal
- **Command:** full backend suite + frontend suite (below) after deleting `compare_codebooks`/`compare_codings` job kickoffs, handlers, schema, routes, and ~680 lines of now-dead test coverage.
  - **Result:** PASSED, 0 failures — confirms the deterministic `GET /api/comparison/codebooks`/`codings` viewers and existing comparison artifacts were unaffected by the removal.

### W4: Export capability hand-port
- **Command:** `.venv/bin/python -m pytest -q tests/backend/services/test_export_service.py tests/backend/routes/test_export_routes.py`
  - **Result:** PASSED (23 tests: 16 service-level, 9 route-level, including 6 new tests added for the ported capabilities and the version_no-404 fix).
- **Verified defects fixed relative to the pre-integration tree:**
  - `export_codebook`/`export_coding`/`export_summary`: an explicit `version_no` that doesn't resolve to a real version now raises `NotFoundError` (404), confirmed via `test_export_{codebook,coding,summary}_unknown_version_no_is_404` — previously it silently produced a 200 OK empty export.
  - `export_coding`/`export_project_bundle`: `include_source_text`/`include_author` default to `False` (the analysis-ready-export-v2 source branch this was hand-ported from defaulted `include_source_text` to `True` — that default was corrected, not carried over), confirmed via `test_export_coding_privacy_flags_default_off`.
  - `export_project_bundle`: repeated calls over unchanged data produce byte-identical ZIPs, confirmed via `test_export_project_bundle_is_deterministic_and_privacy_scoped`.
  - `repositories/export_repo.py::get_project_lineage_graph`: fixed a real bug found during hand-porting — the source branch read `ArtifactVersion.message`, a field that doesn't exist on this schema (would have raised `AttributeError` on first real use); changed to the actual field, `user_instructions`.

### Final gate, full suite (`wave/W4-pass`, commit `f629d3d`)
- **Command:** `.venv/bin/python -m pytest -v`
  - **Result:** **1359 passed, 12 deselected**, 0 failures, in 12.94s.
- **Command:** `cd frontend && npm run test:run`
  - **Result:** **278 passed across 11 test files**, 0 failures.
- **Command:** `cd frontend && npm run build`
  - **Result:** PASSED, built cleanly (~800-950ms across runs).
- **Command:** `cd frontend && npm run lint`
  - **Result:** 19 problems (13 errors, 6 warnings) — bit-for-bit the same list of pre-existing issues verified by running the identical lint command against a clean checkout of the pre-integration WIP tip (`backup/20260912T185404/overhaul-human-in-the-loop-interface`) in an isolated worktree. Zero regressions.
- **Command:** `python -c "... ScriptDirectory.from_config(...).get_heads()"`
  - **Result:** `['e8a2b3c4d5f6']` — single head, chain `a1e6f2c9b3d7 → ... → c8f1b04e7a29 → d1f4a8c2e6b9 → e8a2b3c4d5f6` unbroken.
- **Not run this wave (pending explicit go-ahead before touching a database, per instruction):** `pytest -m integration tests/backend/integration/test_alembic_migration.py` against a disposable live Postgres; browser smoke flows.

### Disposable-Postgres migration roundtrip + browser smoke (2026-09-12, post-user-confirmation)
Run only after explicit user go-ahead to use a fresh, throwaway Postgres — `backend/.env`'s configured database was never touched (env-var override only; no writes to that file).

- **Setup:** `docker run postgres:16-alpine` (ephemeral, no volume, random host port), never using the existing dev database.
- **Command:** `DATABASE_URL=postgresql://.../qc_disposable .venv/bin/python -m alembic upgrade head`
  - **Result:** PASSED — all 15 revisions applied cleanly, `a1e6f2c9b3d7` (baseline) through `e8a2b3c4d5f6` (head).
- **Command:** `alembic downgrade base` then `alembic upgrade head` again
  - **Result:** PASSED — full downgrade and re-upgrade roundtrip clean; `alembic current` confirms `e8a2b3c4d5f6 (head)`; `\dt` shows all 16 expected tables.
- **Command:** `.venv/bin/python -m pytest -m integration -v` (against the disposable Postgres)
  - **Result:** **12 passed**, including `test_migrated_schema_matches_orm_metadata` (zero unallowed schema drift between the migrated schema and the ORM models).
- **Browser smoke (real backend + frontend dev servers, pointed at the disposable database via `DATABASE_URL` env override; a temporary CORS-origin addition to `main.py` for the smoke-test frontend port was reverted immediately after, confirmed via `git diff` showing no changes):**
  - Register → auto-login: PASSED (real `POST /api/register/` round-trip, 200).
  - Create project: PASSED.
  - **W4 verified live:** clicking "Download Bundle" on the project page issued a real `GET /api/export/projects/{id}/bundle` request, 200 OK, against the disposable Postgres.
  - **W3 verified live:** the Compare Codebook page renders only the "Select Codebooks" picker (Codebook A / Codebook B) — no LLM prompt/model/name form, no API-key requirement — confirming the removed synthesis panel is actually gone in the running app, not just in source.
  - No new browser console errors introduced (remaining console errors are pre-fix CORS failures from before the temporary origin was added, not new regressions).
- **Teardown:** backend and frontend dev servers stopped, disposable Postgres container stopped and removed, temporary `frontend/.env.local` and `.claude/launch.json` removed, `backend/app/main.py` confirmed reverted to its original CORS list (`git diff` empty). Full backend suite re-run once more afterward: 0 failures.

---

## Independent-review remediation pass (2026-09-12, post-abed861)

An independent review of `abed861` raised 14 gaps against the actual codebase. All 14 were re-verified against the real source before fixing (several were confirmed exactly as described; a couple were re-scoped after checking the actual contract -- see below), then fixed and re-verified with a fresh disposable Postgres.

**Confirmed and fixed as described:**
1. `frontend/src/api.js` still special-cased `status === "completed"` (dead branch since W2 removed that status value entirely) — removed.
2. `database.py::get_async_db` caught `Exception`, not `BaseException` — `asyncio.CancelledError`/`GeneratorExit` on client disconnect weren't triggering the explicit rollback — changed to `BaseException`.
3. Silent `except Exception: pass` in `jobs/progress.py` (x2) and `openrouter_client.py` — kept the swallow (correct for best-effort progress/accounting) but added `logger.warning(..., exc_info=True)`.
5. `coding_repo.py::render_coding_text`'s `ORDER BY` had no final tiebreak for multiple quotes sharing (row_type, post_id, code) — added `.id`.
6. `useProjectScopedFiles.js`'s second effect had no `AbortController` — added one, wired through `apiFetch`'s existing options passthrough.
7. No fast, DB-free unit test asserted a single Alembic head — added `tests/backend/test_alembic_chain.py` (2 tests: single head, and the full chain is one unbroken line to base with no cycle/orphan).
10. `export_repo.py` imported `from backend.app.services import version_service` — the only repository in the codebase importing the service layer, backwards from the routes→services→repositories direction. Moved the codebook-codes-resolving logic into `export_service.py` as `_get_sorted_codebook_codes`; `get_code_frequencies_by_uid` now takes pre-fetched `codes` as a parameter.
11. Cross-owner 404 coverage existed only for the `/codebook` export route — added parametrized coverage for `/coding`, `/memos`, `/summary`, and a dedicated 403 test for the project-bundle route.
12. Stale docs: `api-reference.md`'s "Request schemas" section still described `CompareCodebooksRequest`/`as_form` as current; `prompt-manager.md` still cited the deleted `CompareModelPromptPanel`; `CLAUDE.md` (local, gitignored — not part of this diff) had two passages still listing `compare-codebooks`/`compare-codings` as live job types. All fixed.
13. `codebook_service.py` imported `ORIGIN_GENERATED` with zero remaining usages (its only use was in the removed `_run_compare_codebooks_job`) — removed.

**Confirmed, but with a real bug found underneath the stated gap (re-scoped after investigation):**
4. "Partial-flag detection (`result.get("partial")`)" — the actual bug: `jobs/service.py` only checked `result.get("status") == "partial"` (the `summarize_coding`/`recode_items` convention), never `result.get("partial") is True` (the independent convention `filter_preview`'s per-batch coverage tracking uses) — so a batch-capped filter preview was marked `"succeeded"` at the job level despite its own result saying `partial: true`. Fixed to check both conventions; updated two `test_data_service.py` tests that had locked in the old (wrong) `status == "succeeded"` expectation, and found four different test files each independently hardcoded `status in ("succeeded", "failed")` in their own polling helper (missing "partial"/"retryable_failure"/"cancelled") — replaced all four with the real `TERMINAL_STATUSES` constant.
8. "Migration test checks `artifact_assists` and coder columns" — the actual bug was one level deeper: `test_migrated_schema_matches_orm_metadata` never imported `versioning_models` at all, so `Base.metadata` was missing `artifact_versions`/`artifact_edges`/`codebook_codes`/`artifact_assists` entirely when the drift comparison ran — reproduced by running the test file in isolation, where `Base.metadata.tables` came back without any of the four. In the normal full-suite run this was masked by pytest collection incidentally importing `versioning_models` via an unrelated test module first. This is a materially more serious finding than "missing a specific assertion": the schema-drift gate's "0 drift" result was a false negative for exactly those four tables. Fixed by importing `versioning_models` explicitly and adding an in-test assertion that guards against the same regression; also added explicit `coder`/`coder_model`/table-existence assertions to the upgrade-from-empty test.
9. "Memos export version_no + 404" — re-scoped after checking `RowMemo`'s actual model: memos are deliberately **not** SCD-2 range-versioned (no `valid_from`/`valid_to`), so there is no historical snapshot for a `version_no` parameter to filter by — adding one would be building a parameter with no meaningful semantics. Instead added the validation `export_memos` was actually missing: it accepted any file type and returned a silently-empty export for one with no memos; now rejects with 400 when the file type isn't `raw_data`/`filtered_data`/`coding`.

**Verification, re-run after all fixes:**
- `.venv/bin/python -m pytest -v`: **1367 passed, 12 deselected**, 0 failures (up from 1359 before this pass: +8 net from the new/updated tests).
- `cd frontend && npm run test:run`: **278 passed** across 11 files, 0 failures (unchanged).
- `cd frontend && npm run build`: clean.
- `cd frontend && npm run lint`: 19 problems (13 errors, 6 warnings) — unchanged from baseline.
- Fresh disposable Postgres (Docker, discarded after use, `backend/.env`'s configured database untouched): `alembic upgrade head` → `downgrade base` → `upgrade head` roundtrip clean; `pytest -m integration` (12 tests) passed against it, including `test_migrated_schema_matches_orm_metadata` run **both** as part of the full integration run **and** in true isolation (`pytest tests/backend/integration/test_alembic_migration.py -m integration`) to specifically confirm the `versioning_models`-import fix holds without relying on collection-order side effects.
- Single Alembic head confirmed both by the new `test_alembic_chain.py` unit test and directly via `ScriptDirectory.get_heads()`: `['e8a2b3c4d5f6']`.
