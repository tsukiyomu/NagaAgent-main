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
- [TODO] MIG-2: Port and adapt the Langfuse integration and deterministic Langfuse tests.
- [TODO] MIG-3: Port compatible testing infrastructure and CI assets against the new architecture.
- [TODO] MIG-4: Run proportional regression, record proof boundaries, and nominate the new baseline.

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

## 7. Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| UPMIG-0 | 2026-09-04 | Create and verify pre-migration source/history ZIP and journal | DONE | `F:\Programme\Agent\backups\NagaAgent-main-pre-upstream-c2caa907-2026-09-04.zip`; 794,816,514 bytes; SHA-256 `bc1534a2f5b6ea2a9d7ec317619651dcb51ee20649eb9f889eba368081e03d72`; archive list readable | MIG-1: create upstream-based branch and migrate/reconcile `docs/` |
| UPMIG-1 | 2026-09-04 | Create upstream-based branch and migrate/reconcile authored `docs/` | DONE | `codex/upstream-langfuse-sync` starts at `c2caa907...`; 54 docs tracked, 4 generated logs excluded, no product/test/CI staged; migration boundary recorded | MIG-2: port Langfuse adapter and deterministic tests |
