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

The migration order is: documentation boundary (MIG-1), preserved Langfuse adapter/tests
(MIG-2), testing/CI assets (MIG-3), then regression and baseline nomination
(MIG-4).

As of 2026-09-07, MIG-0 through MIG-4 are complete within the local migration scope.
The nominated code/testing baseline is `981821be`: 179 passed, 1 skipped, 2 xfailed,
plus 12 passed subtests in an independent frozen-lock environment. This includes
58 adapter cases and the preserved upstream tests. On 2026-09-08, user-authorized
MIG-5 restored Langfuse runtime/SDK at `7c88065c`, with 189 passed / 2 skipped /
2 xfailed + 12 subtests and successful synthetic LAN ingestion/readback.
At that migration checkpoint, target GitHub execution and Required rules were unverified. Testing status and selected architecture entry points
are reconciled; the entire historical architecture tree is not fully re-certified.
See the testing migration status for the exact boundaries.

On 2026-09-11, P3-0 published code baseline `357a8a6f` to
`tsukiyomu/NagaAgent-main` on `codex/upstream-langfuse-sync`. Both manual GitHub
Smoke / Stream runs passed; downloaded JUnit ZIP digests and testcase identities
were verified against the local baseline. PR #2 was closed without merging, and
its evidence branch was preserved. Main and Required rules were not changed.
See the [P3-0 journal](testing/reports/p3-0-execution-journal.md). Historical architecture
details remain `PARTIAL`; this is not full product or release acceptance.
