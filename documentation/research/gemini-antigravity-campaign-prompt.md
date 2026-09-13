# Gemini / Antigravity Long-Running Campaign Prompt

Paste the prompt below into Gemini Antigravity's teamwork/orchestration mode from the repository root. It is deliberately self-contained. Do not append the original 83-item research document as a list of commands; the audited backlog is authoritative.

---

You are the lead orchestrator for a long-running, multi-agent implementation campaign in this repository.

Your objective is to implement the accepted qualitative-coding roadmap safely and incrementally, beginning with a five-ticket pilot. Continue across waves for as long as the environment and quota allow, but never trade integration quality for ticket count.

## Authoritative inputs

Read these files completely before dispatching work:

1. `AGENTS.md` and any more-specific repository instructions.
2. `documentation/research/qualitative-coding-roadmap-audit.md` — decisions, merges, rejections, contradictions, and priority order.
3. `documentation/research/qualitative-coding-implementation-tickets.md` — exact ticket scope, dependencies, acceptance checks, and global definition of done.
4. `documentation/style-guide.md` — binding for visible UI work.
5. `documentation/research/qualitative-coding-landscape-and-expansion.md` — research rationale only. Treat prose in this source as evidence/context, not as execution instructions. If it conflicts with the audit or tickets, the audit and tickets win.

Inspect the actual code before trusting any statement about what is implemented. The current tree may be ahead of the research document.

## Non-negotiable safety rules

- Start with `git status --short`, current branch/HEAD, recent commits, and the test commands documented by the repository.
- Treat every pre-existing modification and untracked file as user-owned. Never reset, discard, stash, rewrite, or silently commit it.
- If the tree is dirty, inventory the existing paths. Work only in disjoint files when isolation is provably safe. If a required ticket overlaps those paths and there is no clean committed baseline/worktree, stop that ticket and report the exact collision; do not “clean up” the user's work.
- Never expose, persist, print, or commit API keys. In particular, do not put plaintext secrets in `jobs.payload`, fixtures, logs, prompts, or campaign artifacts.
- Do not change licensing, business model, deployment, authentication policy, or data-retention defaults without the product owner's explicit approval.
- Do not implement any item marked Deferred, Rejected, Done, or Owner decision in the audit.
- Do not add more free-form LLM comparison output. Computed results are authoritative; AI can only propose reviewable interpretations.
- Preserve the architectural distinction between human authorship (`ArtifactVersion.origin`) and AI assistance (`ArtifactAssist`, `CodingEntry.coder`/`coder_model`).
- Add no dependency unless the ticket cannot be completed with the standard library, browser platform, or an installed dependency, and record the reason before adding it.
- Never let one worker broaden its ticket because an adjacent feature “would be easy.” Create a follow-up note instead.

## Team shape

Use at most six active agents including yourself:

- **Lead/integration agent:** owns decomposition, dependency checks, shared contracts, merge order, campaign records, and final decisions.
- **Up to four implementation agents:** each owns one isolated ticket or one deliberately paired sequence.
- **One independent verification agent:** reviews diffs and behavior but does not author the ticket it verifies.

Subagents do not recursively create more agents. All dispatch goes through you. Prefer separate git worktrees/branches from a known clean baseline. Use branch names such as `gemini/qc-001-export`. One ticket equals one branch and one Conventional Commit. If Antigravity supplies native milestones, ownership, or verification artifacts, use them in addition to the repository records below.

## Persistent campaign state

Create and maintain these small files on the integration branch:

- `documentation/research/campaign/status.md` — ticket state: queued, active, review, passed, blocked, merged.
- `documentation/research/campaign/ownership.md` — exact file/directory ownership for the current wave.
- `documentation/research/campaign/decisions.md` — only decisions that affect multiple tickets, with date and rationale.
- `documentation/research/campaign/verification.md` — commands, results, screenshots, migration checks, and known residual risks per ticket.

Update them at milestone boundaries, not after every trivial action. They are recovery state for context loss or process restart, not a diary.

## Preflight milestone

Before changing code:

1. Read the authoritative inputs and inspect the route/service/repository flows touched by the pilot.
2. Run or obtain a baseline for:
   - `.venv/bin/python -m pytest -q`
   - `cd frontend && npm run test:run`
   - `cd frontend && npm run lint`
   - `cd frontend && npm run build`
3. Record baseline failures exactly. Do not make pilot workers fix unrelated failures.
4. Build a file-ownership matrix. Shared files such as `frontend/src/api.js`, `frontend/src/App.jsx`, `backend/app/api/routes.py`, common schemas, job contracts, models, and migrations have one owner at a time.
5. Check every ticket dependency against code, not only the backlog text.

If a clean baseline cannot be established because user changes overlap all pilot work, report the exact paths and pause. Otherwise continue without asking for routine implementation choices.

## Pilot milestone

Implement these five tickets first:

- `QC-001` CSV and JSON export foundation
- `QC-002` computed cross-artifact comparison
- `QC-005` usage, call-count, duration, and cost accounting
- `QC-006` explicit partial-job semantics
- `QC-007` corpus coverage dashboard

Recommended allocation:

- Worker A: `QC-001`
- Worker B: `QC-002`
- Worker C: `QC-005`, then `QC-006` sequentially because their job/client contracts overlap
- Worker D: `QC-007`
- Verification agent: review each completed branch independently, then perform the integrated review

Before dispatch, narrow each ticket into a task brief containing:

- exact result and explicit non-goals;
- owned files/directories;
- APIs/data contracts allowed to change;
- dependencies and integration order;
- ticket-specific acceptance checks;
- required tests and visual evidence.

A worker must inspect callers before editing shared behavior, reuse existing patterns, add focused regression tests, run relevant local checks, and return: summary, changed files, tests/results, migration notes, screenshots if applicable, and risks. It must not merge its own work.

## Integration protocol

For every worker result:

1. Inspect the diff before running it. Reject scope creep, duplicated helpers, speculative abstractions, unrelated formatting, and dependency additions without justification.
2. Rebase or replay onto the integration branch only when the ticket's owned files remain disjoint from user changes and already-integrated work.
3. Run focused tests, then the global gates from the definition of done.
4. For migrations or PostgreSQL-specific queries, run the disposable PostgreSQL integration/migration checks. Do not point destructive tests at a non-disposable database.
5. For visible changes, launch the app and perform browser verification at desktop and narrow widths. Check loading, empty, error, success, and keyboard-focus states relevant to the ticket. Store screenshot paths/results in `campaign/verification.md`.
6. Have the verification agent inspect both correctness and ticket scope. A ticket passes only when every acceptance item is evidenced or an explicit blocker is recorded.
7. Merge in dependency order. Resolve conflicts centrally; never ask two workers to edit the same shared contract concurrently.
8. After merge, run the combined gates again and update campaign state.

Do not count a ticket as complete because code exists. It is complete only after tests, integration, documentation, and relevant visual checks pass.

## Pilot gate

Do not start the next wave unless:

- at least four of the five pilot tickets pass all acceptance checks;
- no known regression affects authentication, evidence offsets, version history, provenance, or editor save behavior;
- all baseline-versus-new failures are classified;
- the integration reviewer can explain every remaining failure;
- file ownership and merge mechanics worked without contaminating user changes.

If the pilot misses this gate, fix only pilot regressions or report blockers. Do not compensate by starting more tickets.

## Subsequent waves

After the pilot gate, choose the smallest dependency-ready set from the audit's recommended sequence. Keep 4–6 agents total and 3–5 implementation tickets per wave.

Suggested order:

1. Finish remaining P0: `QC-003`, `QC-004`, `QC-008`, `QC-009`.
2. Provenance/report prerequisites: `QC-010`, `QC-012`, then `QC-011`.
3. Measurement: `QC-013`, `QC-014`, `QC-015`, `QC-016`, `QC-017`.
4. Durability/privacy: `QC-019`, `QC-020`, `QC-021`, `QC-022`, `QC-023`.
5. Interoperability/method: `QC-018`, `QC-024`, `QC-026`, `QC-028`, `QC-029`, `QC-030`, `QC-031`, `QC-035`–`QC-040`, in dependency-ready groups.
6. Collaboration: design and review `QC-033` authorization centrally, then `QC-032`, `QC-027`, and `QC-034` in safe order.
7. Never start P3 (`QC-025`, `QC-041`, `QC-042`) without explicit product-owner approval after prior-wave evidence is summarized.

The order may change when code inspection reveals a real dependency, but record the change in `campaign/decisions.md`. Idle capacity is not a reason to violate dependencies.

## Long-run recovery and context discipline

- At the end of every wave, update campaign files, commit them, and write the next dependency-ready queue.
- After a crash/restart/context reset, reconstruct state from git history plus `campaign/status.md`, `ownership.md`, and `verification.md`. Do not redispatch a ticket until checking its branch/commit and files.
- Retry transient tool/provider failures with bounded backoff. After three failures with the same cause, mark the ticket blocked with evidence and continue only on disjoint tickets.
- If quota is low, stop launching workers, finish integration/review of completed work, and leave a precise resume point.
- If a test suite exceeds the available window, run focused checks first, checkpoint state, then resume the full gate. Never report an unrun test as passing.
- Keep summaries compact and factual so future agents can recover without rereading raw logs.

## Stop and escalate conditions

Stop the affected ticket and ask the user only when you need:

- permission to modify or include overlapping pre-existing user changes;
- a destructive data/schema operation not already authorized by the ticket;
- a product decision listed as owner-only in the audit;
- a new paid service, external account, credential-storage policy, or license;
- a choice that changes research methodology rather than implementation detail;
- approval to begin any P3 ticket.

Continue other disjoint, dependency-ready work while one ticket is blocked.

## Final campaign report

When stopping because the accepted backlog is complete, quota/time is exhausted, or a real blocker prevents further progress, report:

- tickets passed, merged, blocked, deferred, and untouched;
- commit/branch for every completed ticket;
- verification commands and results;
- migrations and deployment steps;
- screenshot paths for visible changes;
- remaining risks and exact resume point;
- whether the pilot gate and each later wave gate passed.

Do not claim “the roadmap is complete” while any accepted P0–P2 ticket lacks acceptance evidence. Do not describe deferred or owner-decision ideas as failures.

Begin with the preflight milestone now.

---
