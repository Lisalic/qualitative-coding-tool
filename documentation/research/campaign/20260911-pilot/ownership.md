# File Ownership Matrix — Pilot Wave

> Historical allocation from the completed 2026-09-11/12 pilot. Do not reuse it as a current ownership map.

**Wave:** Pilot milestone  
**Integration Lead:** Orchestrator

## Active Allocations

| Ticket | Agent | Owned Files & Directories | Disjoint Boundary / Interfaces |
|---|---|---|---|
| **QC-001** | Worker A | `backend/app/api/export_routes.py`<br>`backend/app/services/export_service.py`<br>`backend/app/api/routes.py` (exclusive edit for route inclusion)<br>`frontend/src/components/export/`<br>`tests/backend/routes/test_export_routes.py`<br>`tests/backend/services/test_export_service.py` | Exposes `/api/export/{file_id}/...`. Read-only against `version_service`, `coding_repo`, `memo_repo`. Does not modify existing version models. |
| **QC-002** | Worker B | `backend/app/core/codebook_diff.py`<br>`backend/app/core/coding_diff.py`<br>`backend/app/core/cross_comparison.py`<br>`backend/app/services/comparison_service.py`<br>`backend/app/api/comparison_routes.py`<br>`frontend/src/components/compare/`<br>`tests/backend/core/test_cross_comparison.py` | Replaces LLM compare as primary engine; computed diff returns deterministic dicts. No background job or API key required for computed mode. |
| **QC-005** | Worker C (Part 1) | `backend/app/external/openrouter_client.py`<br>`backend/app/jobs/models.py`<br>`backend/app/jobs/progress.py`<br>`backend/app/jobs/service.py`<br>`frontend/src/components/forms/AiAssistPanel.jsx`<br>`tests/backend/jobs/test_job_accounting.py` | Modifies job payload/progress accounting metadata: tokens, costs, durations, batch estimates. Precedes QC-006. |
| **QC-006** | Worker C (Part 2) | `backend/app/jobs/runner.py`<br>`backend/app/jobs/registry.py`<br>`backend/app/jobs/routes.py`<br>`frontend/src/components/feedback/ProgressBar.jsx`<br>`frontend/src/components/feedback/ErrorDisplay.jsx`<br>`tests/backend/jobs/test_partial_jobs.py` | Modifies job status enum/states to handle `completed`, `partial`, `retryable_failure`, `failed`, `cancelled`. Shares job directory with QC-005 sequentially. |
| **QC-007** | Worker D | `backend/app/core/coverage_metrics.py`<br>`backend/app/api/coverage_routes.py`<br>`backend/app/services/coverage_service.py`<br>`frontend/src/components/coding-table/workspace/CodingCoverageDashboard.jsx`<br>`tests/backend/core/test_coverage_metrics.py` | Pure calculation engine from coded entries/rows. Exposes coverage stats (coded/uncoded, code density, code family rollups). Plugs into workspace summary. |
| **Verification** | Reviewer | `documentation/research/campaign/20260911-pilot/verification.md`<br>Read-only review of all worker diffs and verification tests | Independent verification of diffs, tests, and visual contracts before integration. |

## Pre-existing User Changes Inventory & Safety Rules
The working tree contains pre-existing user-owned modifications (116 files + untracked files).
- **Rule 1:** Workers must never overwrite, discard, or include pre-existing uncommitted changes in ticket branches.
- **Rule 2:** Shared files (`routes.py`, `schemas.py`, `api.js`, `App.jsx`) are guarded: any change to them must be disjoint and integrated centrally.
- **Rule 3:** If a ticket cannot achieve its acceptance criteria without modifying a user-dirty file, the ticket owner pauses and reports the collision.
