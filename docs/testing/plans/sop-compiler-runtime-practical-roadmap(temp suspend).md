# SOP Compiler / Runtime Practical Testing Roadmap

## 1. Positioning

- Document status: `ACTIVE / CANDIDATE`
- Current execution detail: [`closed-loop-v1-implementation-plan.md`](closed-loop-v1-implementation-plan.md)
- Repository evidence boundary: current workspace branch `codex/verify-stream-contract-gate`, observed HEAD `44a0af5` on 2026-08-18.
- Purpose: obtain one complete, practical testing-engineering experience first, then extract a reusable SOP Compiler / Runtime from verified NagaAgent workflows.

The target is not a longer prompt or a general autonomous test platform. The target is an evidence-backed pipeline:

```text
Natural-language SOP
  -> AI-generated CANDIDATE IR
  -> human-reviewed REVIEWED IR
  -> deterministic Compiler validation
  -> Runtime actions
  -> deterministic Validators
  -> Gate decision
  -> Artifact Contract
  -> human-confirmed VERIFIED evidence
```

The LLM may propose the intermediate representation, but it is not the blocking oracle. State transitions, validators, gate rules and artifact checks must remain deterministic and reviewable.

## 2. Current Evidence Baseline

| Capability | Implementation status | Gate status | Evidence boundary |
|---|---|---|---|
| Smoke PR check | `LANDED` | `PR_BLOCKING` on the reviewed Draft PR | Three deterministic smoke cases; does not prove Agent Workflow integration |
| Stream Contract PR check | `LANDED` | `NON_BLOCKING` | Two deterministic SSE contracts ran on `pull_request`; real route + fake loop + persistence spy |
| Closed Loop V1 | `PARTIAL / CANDIDATE` | Mixed | C0-1 and C0-2 are done; C0-3 through C0-6 remain |
| Chat Stream User Stop | `XFAIL_GAP` | `NOT_WIRED` | Executable expected-failure contract exists; product cancellation semantics are not landed |
| Duplicate `tool_call_id` | `XFAIL_GAP` | `NOT_WIRED` | Executable expected-failure contract exists; cross-round deduplication is not landed |
| Stub Golden Cases | `PARTIAL` | `NOT_WIRED` | Five deterministic scripted cases; production prompt/context quality is not proven |
| Local Quality Gate | `PARTIAL` | Local/diagnostic | JSON/Markdown/pass-warn-fail logic exists; enforce and CI publication are incomplete |

## 3. Practical Completion Target

The first complete experience must cover the whole testing lifecycle:

1. Requirement and risk interpretation.
2. Workflow and state modelling.
3. Scenario selection and human review.
4. Deterministic test implementation.
5. Red test or negative gate evidence.
6. Product or test correction.
7. Repeatable local and CI execution.
8. Failure triage and classification.
9. Gate decision and branch-protection boundary.
10. JUnit, quality report and Gate Record preservation.
11. SOP feedback based on observed evidence.

Completion is not measured by case count. It is measured by whether another engineer can inspect the contract, reproduce the run, understand a failure and extend the workflow safely.

## 4. Active Execution Path

### P0 — Finish Closed Loop V1 Evidence and Governance

- Status: `IN_PROGRESS`; C0-1 and C0-2 are `DONE`, next unit is C0-3.
- Detailed checklist: [`closed-loop-v1-implementation-plan.md`](closed-loop-v1-implementation-plan.md)
- Purpose: turn the existing green PR checks into a reproducible and auditable testing closure.
- Actions:
  - save separate Smoke and Stream JUnit results;
  - upload minimum CI artifacts even when a test fails;
  - obtain three repeatable green runs;
  - create one deterministic red run and restore green;
  - record Risk -> Scenario -> Case -> Run -> Triage -> Gate Record;
  - let the human repository owner decide whether Stream becomes a Required Check.
- Acceptance:
  - C0-3 through C0-6 have concrete evidence;
  - the plan can be human-promoted from `CANDIDATE` to `VERIFIED`;
  - `PR_BLOCKING` is claimed only with platform configuration evidence.

### P1 — Close One Real Product Gap: Chat Stream User Stop

- Status: `XFAIL_GAP`.
- Primary test: `tests/integration/chat_stream/test_resilience.py::TestChatStreamRouteWithFakeLoop::test_chat_stream_user_stop_contract_gap`.
- Runtime path:

```text
frontend AbortSignal
  -> HTTP/SSE disconnect
  -> async generator cleanup
  -> active-state release
  -> finalize exactly once
  -> partial-response persistence policy
  -> final_status=cancelled
```

- Deterministic validators:
  - cancellation reaches the defined terminal state;
  - active state is cleared exactly once;
  - finalize occurs at most once;
  - a non-empty partial response is saved at most once;
  - an empty response saves only the user message;
  - the current `xfail` is removed without weakening assertions.
- Proof boundary: this proves application cancellation and persistence semantics; it does not prove internet-level network performance or real-LLM quality.

### P2 — Define SOP Contract IR V0

- Status: `TODO`.
- Purpose: convert the reviewed Chat Stream SOP into a small machine-readable contract before building a general compiler.
- Minimum schema:
  - `workflow_id`, `version`, `revision`;
  - `states`, `initial_state`, `terminal_states`;
  - `transitions` with event, guard and next state;
  - `actions` mapped to repository-native commands or handlers;
  - `validators` mapped to deterministic assertions;
  - `gates` with blocking/non-blocking policy;
  - `artifacts` with required path, type and producer;
  - `evidence` with command, environment, exit code and run identity.
- Acceptance:
  - the User Stop workflow can be represented without free-form executable logic;
  - every state, transition, validator and artifact has a stable identifier;
  - the reviewed IR is stored separately from AI-generated candidates.

### P3 — Implement SOP Compiler V0

- Status: `TODO`.
- Purpose: reject invalid or ambiguous contracts before execution.
- Static checks:
  - referenced states and terminal states exist;
  - transition identifiers are unique;
  - terminal states have no unintended outgoing transition;
  - actions and validators resolve to registered implementations;
  - blocking gates do not depend on real LLM or uncontrolled external services;
  - required artifacts have a producer;
  - cyclic transitions are explicitly bounded.
- Output: a normalized executable manifest, not generated pytest code as the only source of truth.

### P4 — Implement SOP Runtime V0

- Status: `TODO`.
- Purpose: execute the compiled contract and produce auditable evidence.
- Runtime responsibilities:
  - invoke existing pytest/CI commands rather than replace pytest;
  - capture revision, environment, command, timestamps and exit code;
  - evaluate deterministic validators and gate policy;
  - consume JUnit and quality-report output;
  - emit a Gate Record with `case_id`, `failure_stage`, `final_status` and artifact links;
  - keep human-only transitions such as `REVIEWED` and final `VERIFIED` approval outside autonomous control.
- Acceptance: the same reviewed contract produces equivalent local and CI gate decisions from equivalent evidence.

### P5 — Make Prompt Assembly an Executable Contract

- Status: `TODO`.
- Existing design input: `system/prompts/assembler.manifest.example.yaml`.
- Production entries: `system.config.build_system_prompt()` and `system.config.build_context_supplement()`.
- Purpose: prove that the Compiler / Runtime can handle a second architecture-owned workflow, not only Chat Stream.
- Candidate validators:
  - required source layers exist;
  - component references and assembly order are valid;
  - optional layers degrade safely;
  - engine-specific outputs are rebuilt from source layers;
  - agent-private soul, memory and skills do not leak across agent contexts;
  - compiled output remains deterministic under controlled dynamic inputs.
- Evidence boundary: deterministic prompt assembly can be blocked in PR; semantic model quality remains non-blocking.

### P6 — Add Skill Lifecycle as the Second Business Workflow

- Status: `TODO`.
- Runtime entries: `/skills/catalog`, `/skills/import`, `/skills/clone`, `/skills/{name}`, and Chat skill-context injection.
- Purpose: demonstrate that the SOP Runtime can cover security, filesystem state, API behavior and downstream context assembly.
- Candidate contract:

```text
package received
  -> name/path validated
  -> staged
  -> installed
  -> catalog visible
  -> selected by chat
  -> instructions injected
  -> removed or rolled back
```

- Validators: path safety, conflict policy, rollback, catalog/filesystem consistency, agent isolation and effective context injection.

### P7 — Extend to Context and Memory

- Status: `TODO`.
- Purpose: add AI-specific data-flow quality after the deterministic runtime is stable.
- Profiles:
  - memory hit;
  - memory empty;
  - conflicting context;
  - compression boundary;
  - cross-session and cross-agent isolation.
- Gate rule: deterministic assembly and isolation may be PR blocking; retrieval/model quality remains non-blocking or scheduled unless stabilized.

### P8 — Add MCP / OpenClaw Staging

- Status: `TODO / DEFERRED`.
- Purpose: validate one production-like external tool boundary after local contracts are trustworthy.
- Initial scope: one harmless tool, explicit environment ownership, timeout, cleanup and artifact capture.
- Gate rule: `STAGING` or `NON_BLOCKING`; do not make real external services a default PR requirement.

## 5. Architecture and Career Outcomes

This roadmap is intended to demonstrate the following capabilities:

- translating natural-language quality requirements into a typed intermediate representation;
- modelling asynchronous workflow state and terminal semantics;
- designing deterministic boundaries around non-deterministic Agent behavior;
- preserving real route, loop, context and persistence boundaries where they matter;
- separating PR-blocking contracts from real-LLM and staging evidence;
- producing reproducible failure packages, Gate Records and traceability;
- evolving a single verified workflow into a reusable compiler/runtime without premature generalization.

## 6. Explicit Non-goals for the Short Term

- No generic natural-language-to-production execution without human review.
- No LLM-as-a-Judge blocking gate.
- No dashboard or extensive Allure customization before trustworthy artifacts exist.
- No large Golden Case count expansion using only scripted outputs and test-specific prompts.
- No MQTT/hardware expansion.
- No real LLM, MCP or OpenClaw dependency in the default PR blocking perimeter.
- No simultaneous expansion into login, forum, voice and other unrelated product modules.

## 7. Active and Suspended Plan Policy

Active plans under `docs/testing/plans/`:

1. This roadmap: current priority and architecture direction.
2. [`closed-loop-v1-implementation-plan.md`](closed-loop-v1-implementation-plan.md): detailed execution checklist for P0.

Temporarily inactive, overlapping or historical planning documents are preserved under [`suspend/`](suspend/README.md). They remain reference material, but they are not current execution truth and must not override this roadmap or current repository/CI evidence.

## 8. Current Execution Checklist

- [DONE] R0: Consolidate the active plan set and preserve inactive plans under `plans/suspend/`.
  - Completed in: `sop-runtime-roadmap-001`.
  - Evidence: created this roadmap and the suspension index; retained Closed Loop V1 as the active execution detail; relocated seven overlapping or deferred plan documents without deleting their content; updated testing-document navigation and references.
- [TODO] R1: Execute Closed Loop V1 C0-3 and save minimum CI artifacts.
- [TODO] R2: Execute C0-4 repeatability and red-to-green evidence.
- [TODO] R3: Execute C0-5 Traceability and Gate Record.
- [TODO] R4: Execute C0-6 human Required Check decision and closure review.
- [TODO] R5: Design and implement the User Stop state contract.
- [TODO] R6: Define SOP Contract IR V0 from the verified workflow.
- [TODO] R7: Implement Compiler V0.
- [TODO] R8: Implement Runtime V0.
- [TODO] R9: Compile and validate the Prompt Assembly contract.
- [TODO] R10: Add Skill Lifecycle as the second workflow.

## 9. Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| sop-runtime-roadmap-001 | 2026-08-18 | Consolidate active testing plans and record the SOP Compiler / Runtime practical path | DONE | Added the active roadmap and `suspend/README.md`; preserved `closed-loop-v1-implementation-plan.md` as the active detailed plan; moved seven inactive/overlapping plans to `suspend/`; repaired documentation references and verified the resulting plan inventory | Execute Closed Loop V1 C0-3: save minimum JUnit and CI artifacts |
