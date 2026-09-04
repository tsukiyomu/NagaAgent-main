# Suspended Testing Plans

This directory preserves plans that are temporarily inactive, overlapping, superseded as the current source of truth, or intentionally deferred.

Suspended does not mean rejected or deleted. These files remain useful as detailed design and historical context, but implementation status must be rechecked against current code, tests and CI before resuming them.

The active priority source is [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md). The active detailed execution checklist is [`../closed-loop-v1-implementation-plan.md`](../closed-loop-v1-implementation-plan.md).

## Suspended Inventory

| Plan | Reason for suspension | Resume trigger |
|---|---|---|
| `current-progress-and-priorities.md` | Broad status source is stale and overlaps the new roadmap | Reconcile historical statuses if a full portfolio audit is needed |
| `chat_stream_test_closure_roadmap.md` | P0/P1 quick view is stale after Stream PR wiring | Resume only as component history; active User Stop work belongs in the new roadmap |
| `golden-cases-implementation.md` | Golden V1 is landed; production assembly, baseline and CI expansion are later phases | Resume after SOP Runtime V0 and Prompt Assembly contract |
| `agentic-tool-loop-next-steps.md` | Unit gate is mostly landed; context/memory and real MCP work are deferred | Resume for P7/P8 or targeted duplicate-ID work |
| `agent-workflow-gate-strategy.md` | Strategic design overlaps the active roadmap and existing architecture docs | Resume only when revising the overall gate architecture |
| `allure-quality-reporting.md` | Core reporting is more important than visualization polish | Resume after CI artifacts and enforce are stable |
| `testing-docs-reorganization.md` | Initial directory reorganization is complete; residual deduplication is low priority | Resume during a dedicated documentation audit |

## Use Rules

- Do not use a suspended document as the current implementation or gate truth.
- Preserve its progress ledger and historical evidence.
- When resuming a plan, first audit it against current repository and CI evidence.
- Move it back to `plans/` only after its next task becomes active and the active roadmap is updated.
