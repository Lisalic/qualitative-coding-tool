# Campaign Status

**Last updated:** 2026-09-12 (Recovery remediation completed)  
**Current wave:** Pilot milestone (Passed after remediation)

## Ticket States

| Ticket | Title | Wave | State | Owner | Branch / Commit |
|---|---|---|---|---|---|
| QC-001 | CSV and JSON export foundation | Pilot | Passed | Recovery Lead | `daf10cd` + recovery commits |
| QC-007 | Corpus coverage dashboard | Pilot | Passed | Recovery Lead | `dcf34a9` |
| QC-002 | Computed cross-artifact comparison | Pilot | Passed | Recovery Lead | `324128b` |
| QC-005 | Usage, call-count, duration, and cost accounting | Pilot | Passed | Recovery Lead | `1162008` + recovery commits |
| QC-006 | Explicit partial-job semantics | Pilot | Passed | Recovery Lead | `1162008` + recovery commits |

## State Definitions
- **Queued**: Ready to dispatch once preflight passes.
- **Active**: Implementation in progress on worker branch.
- **Review**: Worker completed; under independent verification and integration review.
- **Passed**: Verification and gates passed.
- **Blocked**: Cannot proceed due to documented dependency/collision.
- **Merged**: Integrated into integration branch.

## Pilot Gate Status
- **Backend Import & Test Collection**: Fully restored.
- **Full Backend Pytest Suite**: 1,369 passing tests, 12 deselected, 0 failures.
- **Database Schema & Migration Suite**: 6 passed against live PostgreSQL in `tests/backend/integration/test_alembic_migration.py` with 0 unallowed schema drift.
- **Frontend Vitest Suite**: 276 passing tests across 11 test files (0 failures).
- **Frontend Vite Build**: Passing (built cleanly in ~824ms).
- **Frontend ESLint**: Exactly 19 baseline problems (13 errors, 6 warnings, 0 regressions).

## Recovery Review and Remediation Summary
An independent review identified four release blockers after the initial pilot completion:
1. **Production Schema Migration Missing**: `Job.accounting` and `Job.salvaged_output` had been added to `backend/app/jobs/models.py` without an Alembic revision. Remediated in revision `e8a2b3c4d5f6` chained from `d1f4a8c2e6b9` with verified upgrade, downgrade, and schema reflection against live PostgreSQL.
2. **Terminal Cancellation Semantics & Race Condition**: `cancel_job` omitted `partial` and `retryable_failure` from terminal status checks, allowing relabeling of terminal jobs. Furthermore, concurrent job execution and cancellation could clobber status. Remediated by introducing shared `TERMINAL_STATUSES` in `backend/app/jobs/models.py`, adding atomic `where(Job.status.notin_(TERMINAL_STATUSES))` guards to both `cancel_job` and `_execute_job`, and adding regression test coverage in `tests/backend/jobs/test_partial_and_cancellation.py`.
3. **Export Determinism & Versioned Summary**: Exports included non-deterministic `exported_at` UTC timestamps breaking byte-identical determinism on unchanged data. In addition, `/api/export/{file_id}/summary` and `export_service.export_summary` did not accept or apply `version_no`. Remediated by removing timestamps, threading `version_no` through the route and service using `coding_repo.entries_as_of`, attaching `_v{version_no}` filename suffixes, and verifying byte-identical exports and versioned output via automated tests.
4. **Export UX Accessible Error State**: `ExportDropdown.jsx` caught export failures only via `console.error`. Remediated by introducing a visible, accessible error alert (`role="alert"`, `aria-live="assertive"`) that clears upon user dismissal or when starting a new export attempt, backed by tests in `ExportDropdown.test.jsx`.

**Process Defect Notice**: Pre-existing uncommitted modifications in the worktree were swallowed into commits `daf10cd`, `dcf34a9`, `324128b`, and `1162008`. To avoid destructive git history surgery, the recovery changes are committed in tightly scoped conventional commits staging strictly only the verified remediation files.
