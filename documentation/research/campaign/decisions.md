# Cross-Ticket Decisions

**Last updated:** 2026-09-11

## Decision Log

### 2026-09-11: Campaign Inception & Baseline Establishment
- **Context:** Commencing long-running multi-agent qualitative-coding implementation campaign per `gemini-antigravity-campaign-prompt.md`.
- **Pre-existing Tree State:** 116 modified files and 20 untracked files are recognized as user-owned work-in-progress (implementing human-in-the-loop editor rewrites, B1/C2 provenance, etc.).
- **Baseline Results:**
  - Backend pytest: 1,324 passed, 5 deselected.
  - Frontend Vitest: 9 passed test suites, 267 passed tests.
  - Frontend Lint: 19 issues (13 errors in `api.js`, `useLoginPage.js`, `useRegisterPage.js`, `FileUpload.jsx`, `PromptManager.jsx`, `Navbar.jsx`). Recorded as pre-existing baseline failures; workers must not touch unrelated dirty files.
  - Frontend Build: Passed.
- **Worker Allocation:**
  - Pilot consists of 5 tickets: QC-001 (Export), QC-002 (Comparison), QC-005 (Usage Accounting), QC-006 (Partial Jobs), QC-007 (Coverage Dashboard).
  - QC-005 and QC-006 are assigned sequentially to Worker C to eliminate concurrency conflicts on job engine files (`backend/app/jobs/`).
  - Workers A, B, and D work concurrently in disjoint namespaces.

### 2026-09-12: Integration campaign — salvage boundaries and rejected lineages
- **Context:** Consolidating 12 `t3code/*` exploration branches plus one dirty (`f0`) worktree onto `integration/consolidated`, per explicit instruction to salvage only the strongest individual hunks and never cherry-pick a whole conflicting commit or branch.
- **Alembic integrity:** found that the base tree's `e8a2b3c4d5f6` migration already correctly chains after the (then only locally dirty, now committed as `d1f4a8c2e6b9`) artifact-assist-provenance migration. Two candidate branches (`t3code/harden-pilot-recovery-integration`, `t3code/verify-pilot-recovery-tests`) both repoint `e8a2b3c4d5f6`'s `down_revision` to skip `d1f4a8c2e6b9` entirely — this is the explicitly rejected "Alembic-repoint" pattern. Neither branch's version of that file was taken; the base's correct chain was left untouched.
- **Job status naming:** two independent branches (`t3code/implement-roadmap-work`, and the f0 worktree's own dirty `jobs/models.py`) rename the success status from `"succeeded"` to `"completed"`. This is the explicitly rejected "'completed' rename." Neither was taken. Separately, the base tree's `jobs/models.py` was found to already carry a half-migrated state — both `"completed"` and `"succeeded"` present in `JOB_STATUSES`/`TERMINAL_STATUSES` even though the runtime path only ever wrote `"succeeded"` — which was cleaned up to just `"succeeded"` to close the ambiguity, per the instruction to preserve job status exactly as `"succeeded"` end-to-end.
- **Convergent validation:** the job-cancellation race fix (guarding `_execute_job`'s initial `running` transition against a job already cancelled) appears, with equivalent logic written independently, in both `t3code/harden-pilot-recovery-integration` and `t3code/verify-pilot-recovery-tests`. Two independent branches reaching the same fix was treated as corroborating evidence it's a genuine bug, not merely one branch's stylistic preference.
- **Explicitly out of scope for this campaign (left untouched or reverted where a candidate branch touched it incidentally):** `t3code/safe-versioned-exports`, `t3code/review-pilot-recovery-corrections`, `t3code/analysis-ready-export-v2` (hand-ported specific capabilities only, not merged wholesale — see W4 in `status.md`), any `.gitignore` change, a "completed" rename, and all uncommitted QC-010 (immutable prompt/job manifest) work on `t3code/implement-immutable-prompt-manifests`.
- **Frontend regression avoided:** `t3code/analysis-ready-export-v2`'s default for `include_source_text` was `True`; corrected to `False` when hand-ported, since an export should be opt-in to carrying a quote's source text, not opt-out. Separately, the f0 worktree's `CompareDualSelectPanel.jsx` predates this branch's Dropdown-primitive refactor (`editor-shell`/`primitives/Dropdown.jsx`, from the WIP committed in W1) — taking it would have reverted that UI work, so it was left alone even though the surrounding `ComparePageContainer.jsx`/`useComparePageData.js` trims from the same worktree were taken.
