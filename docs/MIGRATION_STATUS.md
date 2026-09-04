# Documentation Migration Status

> Branch: `codex/upstream-langfuse-sync`
> Target baseline: `upstream/main@c2caa9079b9eb48129f550c43a5485231d404d3b`
> Source evidence: `codex/c0-4-intentional-red@d6553a96f6987c5f58fdafddb99fc28e19c72eb0`

The documentation tree contains two origins and must not be read as one uniform
set of current upstream facts:

| Document group | Origin | Target-branch status |
|---|---|---|
| `build-windows.md`, `naga-network-requirements.md`, `travel-exploration-system.md` | latest upstream | `CURRENT_UPSTREAM` |
| `architecture/` restored from the source evidence branch | previous NagaAgent snapshot | `MIGRATED / REVIEW_NEEDED` |
| `testing/` authored workspace docs | previous test/CI work and migration records | see [`testing/MIGRATION_STATUS.md`](testing/MIGRATION_STATUS.md) |
| Typora hook logs | generated local editor output | backed up, intentionally not tracked |

`MIGRATED` means the file is preserved on the new branch. It does not mean every
symbol, module path, test result, or CI status in that file has been revalidated
against the latest upstream code.

The migration order is: documentation boundary (MIG-1), Langfuse implementation
(MIG-2), testing/CI assets (MIG-3), then execution and baseline nomination
(MIG-4).
