# NagaAgent Upstream Migration Plan

## 1. Objective

Migrate the current testing, Langfuse, and documentation work onto the latest
`RTGS2017/NagaAgent` codebase without rewriting the existing evidence branches
or hiding the fact that the two Git histories have no common ancestor.

## 2. Fixed inputs

- Current evidence branch: `codex/c0-4-intentional-red`
- Current revision: `d6553a96f6987c5f58fdafddb99fc28e19c72eb0`
- Upstream remote: `https://github.com/RTGS2017/NagaAgent.git`
- Upstream baseline: `c2caa9079b9eb48129f550c43a5485231d404d3b`
- Migration strategy: create a new branch from `upstream/main`, then port and
  adapt selected assets. Do not merge unrelated histories.

## 3. Invariants

1. A verified pre-migration ZIP must exist before a migration branch is created.
2. Existing local and `origin` evidence branches remain unchanged.
3. Ignored `docs/` content is explicitly migrated; branch switching alone does
   not preserve it in Git.
4. Langfuse remains an observability side channel and must not become pytest or
   CI gate truth.
5. Tests are not described as migrated or passing until they exist on the new
   branch and have been executed there.
6. Secrets and reconstructable dependency/build caches are excluded from the
   portable source backup and recorded explicitly.

## 4. Current Execution Checklist

- [DONE] MIG-0: Create and verify the pre-migration source/history ZIP; create the execution journal.
  - Completed in: `UPMIG-0`
  - Evidence: external ZIP is readable, contains representative Git/Langfuse/test/docs/untracked entries, and has a recorded SHA-256.
- [DONE] MIG-1: Create `codex/upstream-langfuse-sync` from `upstream/main` and migrate/reconcile `docs/`.
  - Completed in: `UPMIG-1`
  - Evidence: branch created from exact upstream baseline; 54 authored/upstream docs are tracked in the index; four Typora logs are ignored; staged scope contains only `.gitignore` and `docs/`.
- [DONE] MIG-2: Port and adapt the Langfuse integration and deterministic Langfuse tests.
  - Completed in: `UPMIG-2` (2026-09-07); code/test commit `c7122124`.
  - Evidence: 58 adapter cases pass, including in a pytest-only isolated environment; SDK context failures and cleanup regressions reproduced and fixed. Runtime wiring remains inactive, matching the pre-existing MIG-2 boundary in `../MIGRATION_STATUS.md`.
- [DONE] MIG-3: Port compatible testing infrastructure and CI assets against the new architecture.
  - Completed in `UPMIG-3`; code commit `981821be`. Selected assets ported; collection-time offline isolation added; smoke/stream/isolation probes and frozen dependency installation passed. See the MIG-3 report for the source/target boundary.
- [DONE] MIG-4: Run proportional regression, record proof boundaries, and nominate the new baseline.
  - Completed in `UPMIG-4`; local testing baseline `981821be`: 179 passed, 1 skipped, 2 xfailed, plus 12 passed subtests. Smoke/Stream each repeated three times; negative probes and reporting verified. Remote CI, runtime Langfuse, performance promotion and deployment remain excluded.
  - Evidence: [MIG-4 report](../reports/upstream-migration-mig-4-execution-journal.md) and [baseline manifest](../reports/upstream-migration-mig-4-baseline.json). P3-0 migration prerequisite satisfied; P3-0 itself not started.
- [DONE] MIG-5: Restore usable Langfuse runtime observability against the user's saved LAN deployment.
  - Run `UPMIG-5`; explicitly authorized after MIG-0 through MIG-4 completed. This extends the earlier migration scope rather than reclassifying their exclusions as completed work.
  - Completed 2026-09-08, code `7c88065c`; SDK/runtime wiring restored, full regression 189 passed / 2 skipped / 2 xfailed + 12 passed subtests. Post-commit LAN probe passed: two synthetic traces and seven observations read back. See [journal](../reports/upstream-migration-mig-5-execution-journal.md).

## 5. Explicit exclusions for MIG-0

- No checkout or branch creation.
- No production, test, CI, dependency, or configuration changes.
- No real Langfuse, LLM, Remote Memory, MCP, staging, or deployment execution.
- No merge, rebase, cherry-pick, push, PR update, or gate-policy change.

## 6. MIG-1 scope and acceptance

In scope:

- Create `codex/upstream-langfuse-sync` directly from `upstream/main`.
- Preserve the three upstream-tracked root documents as authoritative; their
  blobs have been verified byte-identical to the current workspace copies.
- Version all authored Markdown and image assets currently under `docs/`.
- Exclude generated `Typora_Hook_Log.txt` editor logs from Git; they remain in
  the verified pre-migration ZIP.
- Add a migration-status document and reader-facing notices that distinguish
  pre-migration evidence from coverage verified on the new branch.
- Create a MIG-1 execution journal and deterministic file/status evidence.

Acceptance criteria:

1. New branch HEAD begins at the fetched upstream baseline
   `c2caa9079b9eb48129f550c43a5485231d404d3b` before documentation changes.
2. Existing evidence branches remain unchanged.
3. Authored `docs/` files are visible to Git on the new branch.
4. Typora hook logs and root-level backup directories are not staged.
5. No Langfuse, test, CI, dependency, product, or gate change is included.
6. Documents explicitly state that old test/gate evidence is not yet
   revalidated against the new upstream code.

Explicit exclusions:

- No Langfuse production/test port; that is MIG-2.
- No pytest/CI asset port or execution; that is MIG-3/MIG-4.
- No push, PR, merge, rebase, Required Check, or release change.

## 7. MIG-2 scope and acceptance

The preserved revision contains the adapter and three helper tests, but no runtime
callers or Langfuse dependency. This unit migrates that existing boundary; it does
not restore the historical runtime integration described as a proposal in the
Langfuse architecture document.

Acceptance:

1. Port the real adapter source and preserve the three helper contracts on the target branch.
2. Verify configuration/no-op, payload fields, context error isolation, caller
   exception/cancellation preservation, and cleanup with deterministic tests.
3. Keep collection and execution independent of API startup, local credentials,
   and real SDK/LLM/Remote Memory/tool services.
4. Inspect the upstream LLM, tool dispatcher, chat and shutdown boundaries, and
   distinguish future wiring from current unit-level evidence.
5. Record results and synchronize current progress and Langfuse architecture status.

Exclusions: runtime call-site restoration, SDK installation/pinning, live-service
validation, other test/CI migration, full regression, push/PR and gate-policy changes.

## 8. MIG-3 / MIG-4 scope and acceptance

MIG-3 preserves compatible smoke, SSE, loop, Golden Case, quality-report helpers,
historical baselines and PR workflow assets; it keeps upstream tests/product code
authoritative, updates test dependencies/lock, and isolates local data and network
before collection. Smoke and Stream selections and JUnit-on-failure behavior must
remain explicit. Historical numeric baselines are not automatically promoted.

MIG-4 verifies the migrated tree in a separate frozen-lock environment: full local
regression (including upstream tests and the MIG-2 adapter), repeated exact CI
selections, negative failure/artifact probes, and reporting integration. Nomination
must bind a code revision, commands, exclusions, known gaps and evidence. This is
a local testing baseline, not a release approval or real GitHub execution claim.

Both units exclude live LLM/Remote Memory/Langfuse execution, Langfuse runtime
wiring, push/PR/merge, Required Check changes, release and deployment. Remote CI
remains unverified until the branch is published and real runs are obtained.

## 9. MIG-5 scope and acceptance (user-authorized extension)

Restore the runtime observability side channel using the existing adapter and saved
LAN configuration, without changing business answers, SSE contracts, retry policy,
tool concurrency or CI gate truth. Keep MIG-0 through MIG-4's historical boundaries.

Acceptance:

1. Pin a compatible SDK in the project/lock and retain no-op behavior when disabled,
   credentials are missing, or ordinary SDK operations fail. Do not print secrets.
2. Create one root observation per chat request; share session grouping across
   requests while keeping unique traces. Streaming lifetime covers actual iteration
   and cleanup, not merely the creation of StreamingResponse.
3. Record each actual LLM attempt and individual tool execution, including output,
   supplied usage, errors and cancellation, without changing retries or concurrency.
4. Centralize payload policy: safe default excludes content; explicitly enabled
   content capture is bounded/redacted. Never capture auth-refresh SSE tokens.
5. Wire initialization and off-event-loop, bounded shutdown; observation failures
   must not change business failures or stall API shutdown indefinitely.
6. Verify deterministic success/failure/cancellation/concurrency and preserved API
   contracts, then send synthetic-only evidence to the saved Langfuse instance and
   read it back with session/trace/parent-child identities. Distinguish real SDK /
   server from controlled LLM, tools, persistence and memory.
7. Record one concise journal and synchronize current status and Langfuse usage docs.

Exclusions: real paid LLM calls, real Memory/MCP operations, historic chat upload,
server upgrade/redeployment, frontend playback acknowledgement, evaluator/dataset/
prompt-management platform expansion, push/PR/merge, Required rules and deployment.
LAN synthetic trace writes and readback are authorized by the usable-integration
request; do not delete unrelated existing traces or expose keys in evidence.

## 10. Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| UPMIG-0 | 2026-09-04 | Create and verify pre-migration source/history ZIP and journal | DONE | `F:\Programme\Agent\backups\NagaAgent-main-pre-upstream-c2caa907-2026-09-04.zip`; 794,816,514 bytes; SHA-256 `bc1534a2f5b6ea2a9d7ec317619651dcb51ee20649eb9f889eba368081e03d72`; archive list readable | MIG-1: create upstream-based branch and migrate/reconcile `docs/` |
| UPMIG-1 | 2026-09-04 | Create upstream-based branch and migrate/reconcile authored `docs/` | DONE | migration commit `0cd39102`; branch starts at `c2caa907...`; 54 docs tracked, 4 generated logs excluded, no product/test/CI included; migration boundary recorded | MIG-2: port Langfuse adapter and deterministic tests |
| UPMIG-2 | 2026-09-07 | Port/adapt Langfuse adapter and deterministic tests; inspect upstream integration boundaries | DONE | `c7122124`; 58 passed, same identities across isolated red/green runs; runtime and CI `NOT_WIRED`; [execution record](../reports/upstream-migration-mig-2-execution-journal.md) | MIG-3: port compatible testing infrastructure and CI assets |
| UPMIG-3 | 2026-09-07 | Port compatible test/CI assets with collection-time isolation | DONE | 30 preserved assets restored; test deps locked; smoke 3 passed; isolation/stream probe 15 passed + 1 known xfail; frozen sync succeeded; [execution record](../reports/upstream-migration-mig-3-execution-journal.md) | MIG-4: local regression and baseline nomination (authorized batch continues) |
| UPMIG-4 | 2026-09-07 | Independent frozen-environment regression, reporting and local baseline nomination | DONE | `981821be`; full 179 passed / 1 skipped / 2 xfailed + 12 passed subtests; identical full/reporting identities; Smoke 3x3 and Stream 2x3; expected exit-1 probes; [report](../reports/upstream-migration-mig-4-execution-journal.md), [manifest](../reports/upstream-migration-mig-4-baseline.json) | P3-0 re-entry is available; Langfuse runtime and target GitHub validation remain separate, unstarted work |
| UPMIG-5 | 2026-09-08 | Restore runtime Langfuse and verify saved LAN ingestion/readback | DONE | `7c88065c`; full 189 passed / 2 skipped / 2 xfailed + 12 subtests; post-commit LAN 1 passed, 2 traces / 7 observations; [journal](../reports/upstream-migration-mig-5-execution-journal.md), [manifest](../reports/upstream-migration-mig-5-evidence.json) | P3-0 re-entry using the updated runtime baseline; no P3 unit started |
