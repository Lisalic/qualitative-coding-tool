# Next Wave: Coding Row Extension and Project Audit Timeline

**Prepared:** 2026-09-12  
**Status:** PREPARED — BLOCKED FROM DISPATCH  
**Audited code:** `7f17fc1202c4943aa5ea5d02858c86d774298f70` plus inspection of the current working tree  
**Campaign baseline commit:** `PENDING`

No model has been dispatched for this wave. The current protected checkout contains uncommitted comparison-restoration work associated with `QC-002`. First give that work a named commit, observe its verification, and confirm that the protected `main` and `overhaul/human-in-the-loop-interface` worktrees are clean. Then replace `PENDING` with the exact baseline commit and create all campaign worktrees from it.

## Assignment matrix

| Worker | Model | Ticket and unique outcome | Owned paths | Read-only dependencies | Do not implement |
|---|---|---|---|---|---|
| A | Gemini Flash | `QC-003`: add explicitly selected source-parent rows to an existing coding artifact as one atomic new version, preserving existing entries and memos and leaving added rows uncoded | `backend/app/api/coding_routes.py`; the smallest necessary coding schemas in `backend/app/api/schemas.py`; `backend/app/services/coding_service.py`; focused backend tests; one isolated coding-workspace component/hook and colocated tests | `raw_data_repo.copy_rows_by_id`; `memo_repo.copy_memos_by_id`; version services; existing source/row-selection UI patterns | `file_service.move_rows`; source-row deletion/closing; sampling; quote bank; search; LLM calls; comparisons; generic ingest |
| B | Gemini Flash | `QC-004`: expose an owner-scoped, stably ordered, paginated project timeline aggregated from existing version, lineage, memo, and AI-assist records | New `backend/app/repositories/audit_repo.py`, `backend/app/services/audit_service.py`, and `backend/app/api/audit_routes.py`; focused backend tests; new `frontend/src/components/project/ProjectAuditTimeline.jsx` and hook/tests | Existing version, lineage, memo, assist, and project reads/models | New event table; invented memo edit/delete history; research profile; prompt manifest; methods report; collaboration/roles |

Suggested disposable branches/worktrees:

- Worker A: `campaign/qc-003-extend-coding-rows`
- Worker B: `campaign/qc-004-project-audit-timeline`
- Integration: `campaign/next-wave-integration`

Shared integration points—including `backend/app/api/routes.py`, broad frontend API exports, and top-level page/router wiring—have no worker owner. Workers document the required hook-up; Sonnet applies it once in the integration worktree.

## Current-code findings

- `QC-003` is absent. `coding_service.create_manual_coding` accepts selected IDs only while creating a new artifact; `raw_data_repo.copy_rows_by_id` and `memo_repo.copy_memos_by_id` are reusable primitives. `file_service.move_rows` is not the operation needed here because it closes rows in the source and versions both artifacts.
- `QC-004` is absent. Current read endpoints already expose artifact versions, lineage, and assists, but there is no project-level chronological aggregation. `frontend/src/pages/Project.jsx` currently renders only `ProjectHeaderSection` and `ProjectFilesSection`.
- The existing models are sufficient for this audit-timeline slice. Memo history can only be represented at the timestamps the schema currently stores, so a new event table would add complexity without improving the evidence already available.

## Acceptance focus

### Worker A — `QC-003`

- Accept explicit row IDs only from a compatible, owned source-data parent.
- Treat IDs already present in the coding artifact as no-ops and preview new versus existing counts.
- Produce one atomic new coding version; on failure, preserve the old version without partial copies.
- Preserve existing coding entries and memos byte-for-byte; added rows begin uncoded.
- Leave the source artifact unchanged.
- Prove authorization, incompatible-source rejection, duplicate handling, rollback, version history, and data-diff behavior with focused tests.
- Reuse the existing source/row-selection interaction and show preview, success, loading, empty, error, and keyboard-focus states where applicable.

### Worker B — `QC-004`

- Aggregate existing records rather than introducing a new audit-event persistence model.
- Owner-scope every event and link it to the relevant project file and version when available.
- Define a stable sort key and cursor or page contract that cannot duplicate or omit equal-timestamp events.
- Filter by file, event kind, and date range.
- Keep AI assistance separate from artifact authorship.
- Describe row-memo events only at the timestamp granularity the current schema can prove.
- Prove owner isolation, ordering ties, pagination, filters, links, and empty-project behavior with focused tests.
- Render one flat chronological list inside one project-page panel, including mixed, filtered, loading, error, and empty states.

## Sequencing decisions

Do not add more workers to this wave:

- `QC-008` follows `QC-003` because both change coding data reads and workspace presentation.
- `QC-019` follows `QC-003` because both change coding queries and search surfaces.
- `QC-010` follows `QC-004` because both consume provenance/version history and should share a settled timeline contract.
- `QC-012` follows `QC-004` because both modify the project page and project-level presentation.

This is sequencing, not rejection. Re-audit those four tickets after this wave is integrated.

## Required run artifacts

Create these files inside this directory as the campaign advances:

- `workers/qc-003.md`
- `workers/qc-004.md`
- `opus-plan.md` containing both required planning states from one prompt
- `integration.md`
- `verification.md`
- `exit-report.md`

Each worker report must satisfy the completion contract in `../../agent-worktree-orchestration-process.md` and identify branch, worktree, model/application, commit, diff statistics, observed verification, risks, and handoff advice.

## Preflight gate

Do not dispatch until all boxes can be checked:

- [ ] The comparison-restoration work has a named commit and recorded verification.
- [ ] Both protected worktrees are clean and remain read-only.
- [ ] `Campaign baseline commit` above contains the exact reviewed commit rather than `PENDING`.
- [ ] Baseline backend, frontend test, build, and lint results are recorded, including any pre-existing failures.
- [ ] Worker and integration worktrees are created from that exact baseline.
- [ ] The visible paths and prompts have been checked once more for overlap with comparison work or newly landed changes.

After the preflight passes, the orchestrator may start the two Flash workers. It must still stop any session that opens a protected worktree or crosses the assignment boundary.
