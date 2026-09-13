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
