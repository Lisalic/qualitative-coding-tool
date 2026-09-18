# Qualitative Coding Ticket Status

**Updated:** 2026-09-12  
**Last code audit:** `7f17fc1202c4943aa5ea5d02858c86d774298f70` plus the visible uncommitted comparison-restoration work  
**Next campaign baseline:** `PENDING`

This is the sole operational ledger for ticket state. The roadmap decides priority, the ticket file defines scope and acceptance, and run-specific campaign files hold transient plans and evidence. A ticket may be dispatched only when this ledger says `Prepared` and the run records a clean baseline commit.

The comparison restoration represented by `QC-002` is owner-declared complete but was still uncommitted at this audit. Do not establish the next baseline or dispatch workers until that work has a named commit and the protected `main` and `overhaul/human-in-the-loop-interface` worktrees are clean.

## State definitions

| State | Meaning |
|---|---|
| Completed | Implemented and supported by recorded evidence. |
| Verification pending | Owner-declared or visible implementation exists, but the final commit/evidence is not yet recorded. |
| Prepared | Re-audited against current code and assigned a non-overlapping next-wave scope. |
| Held | Valid candidate deliberately sequenced after an overlapping active ticket. |
| Blocked | A named prerequisite or design decision is incomplete. |
| Backlog | Retained candidate not re-audited for dispatch against the current baseline. |
| Owner approval | P3 product bet that cannot be dispatched without an explicit decision and validation plan. |

## Operational ledger

| Ticket | State | Audit or dependency note |
|---|---|---|
| `QC-001` | Completed | CSV/JSON and project-bundle export; see `campaign/20260911-pilot/verification.md`. |
| `QC-002` | Verification pending | Hybrid comparison contract is owner-declared complete; record its commit and observed verification before changing this to Completed. |
| `QC-003` | Prepared | Re-audited at `7f17fc1`; next-wave scope is isolated in `campaign/20260912-next-wave-prep/next-wave.md`. |
| `QC-004` | Prepared | Re-audited at `7f17fc1`; next-wave scope is isolated in `campaign/20260912-next-wave-prep/next-wave.md`. |
| `QC-005` | Completed | Accounting; see pilot verification. |
| `QC-006` | Completed | Partial-job semantics; see pilot verification. |
| `QC-007` | Completed | Corpus coverage; see pilot verification. |
| `QC-008` | Held | Sequence after `QC-003`; both touch the coding read model and workspace. |
| `QC-009` | Backlog | Not re-audited for the next baseline. |
| `QC-010` | Held | Sequence after `QC-004`; both touch provenance and project history. |
| `QC-011` | Blocked | Requires `QC-004`, `QC-010`, and `QC-012`. |
| `QC-012` | Held | Sequence after `QC-004`; both change the project page and project-level metadata presentation. |
| `QC-013` | Blocked | Requires `QC-003` and `QC-012`. |
| `QC-014` | Blocked | Requires `QC-004`, `QC-010`, and `QC-013`. |
| `QC-015` | Backlog | Coder identity exists; implementation has not been re-audited for dispatch. |
| `QC-016` | Blocked | Requires `QC-015`; `QC-001` is complete. |
| `QC-017` | Blocked | Requires `QC-010`; `QC-006` is complete. |
| `QC-018` | Backlog | `QC-001` is complete; implementation has not been re-audited for dispatch. |
| `QC-019` | Held | Sequence after `QC-003`; both touch coding queries and workspace search surfaces. |
| `QC-020` | Blocked | Requires `QC-012`. |
| `QC-021` | Blocked | Requires `QC-009`, `QC-011`, `QC-012`, and `QC-023`. |
| `QC-022` | Blocked | Requires `QC-010` and a recoverable credential decision; `QC-006` is complete. |
| `QC-023` | Blocked | Requires `QC-009` and `QC-010`; coordinate its credential contract with `QC-022`. |
| `QC-024` | Blocked | Requires `QC-012` and `QC-015`. |
| `QC-025` | Owner approval | Large second-cycle product bet with unresolved prerequisites. |
| `QC-026` | Backlog | `QC-001` and `QC-007` are complete; implementation has not been re-audited. |
| `QC-027` | Blocked | Requires `QC-013`, `QC-015`, and `QC-033`. |
| `QC-028` | Blocked | Requires `QC-010`, `QC-015`, and `QC-022`. |
| `QC-029` | Blocked | Requires `QC-010`, `QC-015`, and `QC-016`. |
| `QC-030` | Blocked | Requires `QC-013` and `QC-016`. |
| `QC-031` | Blocked | Requires `QC-004`, `QC-010`, `QC-011`, `QC-018`, and `QC-021`; `QC-001` is complete. |
| `QC-032` | Blocked | Requires `QC-004` and `QC-012`. |
| `QC-033` | Blocked | Requires `QC-004` and a coherent authorization design/security review. |
| `QC-034` | Blocked | Requires `QC-004`, `QC-027`, and `QC-033`. |
| `QC-035` | Backlog | `QC-001` and `QC-007` are complete; implementation has not been re-audited. |
| `QC-036` | Blocked | Requires `QC-013`; `QC-001` and `QC-007` are complete. |
| `QC-037` | Backlog | `QC-001` and `QC-006` are complete; implementation has not been re-audited. |
| `QC-038` | Blocked | Requires `QC-012`, `QC-020`, `QC-021`, and `QC-033`. |
| `QC-039` | Blocked | Requires `QC-008`, `QC-020`, and `QC-021`. |
| `QC-040` | Blocked | Requires `QC-010` and `QC-022`; `QC-005` is complete. |
| `QC-041` | Owner approval | Large statistical product bet; also requires `QC-013`, `QC-015`, `QC-016`, `QC-029`, and `QC-030`. |
| `QC-042` | Owner approval | Large storage/ingest redesign; also requires `QC-001`, `QC-003`, `QC-013`, `QC-019`, and `QC-031`. |

## Updating this ledger

Change state only after inspecting the current code and recording the evidence or blocker. When a campaign finishes, link its verification and feature commit here, then create the next run's `next-wave.md`. Do not paste worker narratives or detailed implementation plans into this file.
