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
