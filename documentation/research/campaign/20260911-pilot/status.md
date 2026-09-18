# Campaign Status

> Historical record of the completed 2026-09-11/12 campaign. It is not the current product specification or a live dispatch queue.

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

---

## Integration Campaign: T3 Branch Consolidation (2026-09-12)

**Context:** 12 parallel `t3code/*` exploration branches plus a dirty (uncommitted) `t3code/f0-truth-audit-hardening` worktree existed alongside the `overhaul/human-in-the-loop-interface` branch's own large uncommitted WIP (the codebook-integrate/coder-attribution feature above). This wave consolidated the WIP and salvaged specific, named fixes from those branches into `integration/consolidated`, without cherry-picking any branch wholesale.

| Wave | Scope | State | Tag |
|---|---|---|---|
| W0 | Backup: tags on every branch tip, dirty-tree patch + tagged commit, untracked-file archive, full-repo bundle | Passed | — |
| W1 | Committed the existing WIP (codebook-integrate, coder attribution/`artifact_assists`, filter few-shot examples, `editor-shell` refactor) as 18 path-grouped commits onto `integration/consolidated`; verified via a fresh clone diffed byte-identical against the source tree | Passed | `wave/W1-pass` |
| W2 | Job lifecycle: unknown usage/cost now `None` (never coerced to `0`); fixed a real cancellation race in `_execute_job`; removed a vestigial `"completed"` status value (kept `"succeeded"` only); added API-key redaction and `logger.exception` on job failure | Passed | `wave/W2-pass` |
| W3 | Removed the LLM-generated `compare_codebooks`/`compare_codings` jobs and their routes/panels; preserved the deterministic `GET /api/comparison/*` viewers and all previously-created comparison artifacts | Passed | `wave/W3-pass` |
| W4 | Hand-ported export-v2 capabilities onto the existing hardened exporter: long/wide coding layouts, `code_uid`-keyed summary, deterministic project-bundle ZIP; fixed a real pre-existing gap (bad `version_no` silently returned an empty export instead of 404) | Passed | `wave/W4-pass` |

**Explicitly rejected and not merged, per instruction:** the "completed" job-status rename (present in `t3code/implement-roadmap-work` and the f0 worktree), the `e8a2b3c4d5f6` Alembic down-revision repoint to skip `d1f4a8c2e6b9` (present in `t3code/harden-pilot-recovery-integration` and `t3code/verify-pilot-recovery-tests`), a `DELETE /jobs/{id}` cancellation alias, `t3code/safe-versioned-exports`, `t3code/review-pilot-recovery-corrections`, a stale pre-Dropdown-primitive `CompareDualSelectPanel.jsx`, `t3code/analysis-ready-export-v2` wholesale, and all uncommitted QC-010 (immutable prompt/job manifest) work.

**Gate results as of `wave/W4-pass` (`f629d3d`):**
- Backend: `.venv/bin/python -m pytest -v` → **1359 passed, 12 deselected**, 0 failures.
- Frontend: `npm run test:run` → **278 passed across 11 test files**, 0 failures.
- Frontend build: `npm run build` → clean.
- Frontend lint: `npm run lint` → **19 problems (13 errors, 6 warnings)** — identical to the pre-integration baseline (verified by running lint against the original WIP tip in an isolated worktree); zero regressions introduced.
- Alembic: single head `e8a2b3c4d5f6`, chain `...→ c8f1b04e7a29 → d1f4a8c2e6b9 → e8a2b3c4d5f6` unbroken, no down-revision repoint.

Not yet run: the disposable-Postgres migration roundtrip and browser smoke flows (require explicit user go-ahead before touching a database, per instruction). W5 (this section, plus the doc fixes below) is documentation-only and needed no such gate.
