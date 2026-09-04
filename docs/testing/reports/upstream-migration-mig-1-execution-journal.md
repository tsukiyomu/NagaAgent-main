# Evidence-Backed Execution Journal — MIG-1 Documentation Migration

## 1. Work Unit

- Journal ID: `UPMIG-1`
- Date: `2026-09-04`
- Plan: [`../plans/upstream-migration-plan.md`](../plans/upstream-migration-plan.md)
- Task ID: `MIG-1`
- Objective: create the upstream-based migration branch and make the current
  authored documentation durable there without transferring stale coverage
  claims to the new codebase.
- Completion criteria: branch created from exact upstream revision; authored
  docs tracked; editor logs excluded; migration status and proof boundaries
  recorded; no production/test/CI migration included.
- Implementation status: `DONE`
- Learning status: `TEACH_BACK_PENDING`

## 2. Learning Objective

After this unit, the user should be able to explain why documentation files can
be migrated before code while their `LANDED`, passing, and gate claims must stay
tied to the revision that produced the evidence.

## 3. Initial Understanding

### Confirmed facts

- The verified MIG-0 backup exists outside the workspace.
- `upstream/main` is `c2caa9079b9eb48129f550c43a5485231d404d3b`.
- Local/current and upstream histories have no merge base.
- Upstream tracks only `docs/build-windows.md`,
  `docs/naga-network-requirements.md`, and
  `docs/travel-exploration-system.md`.
- Those three current/upstream document blobs are byte-identical.
- Current testing/architecture/plans/reports are ignored by the old branch and
  are not present on upstream.
- Four `Typora_Hook_Log.txt` files are generated editor logs, not engineering
  specifications or execution evidence.

### Assumptions and inferences

- Authored Markdown and image assets should be tracked on the migration branch.
- Historical C0 execution reports remain valid for their recorded old revisions,
  but do not prove behavior on the upstream-based branch.

### Unknowns

- Which old architecture/test documents remain accurate after code migration.
- Whether existing test suites can be ported without redesign.

## 4. Project Review Inventory

| File or symbol | Why reviewed | Behavior found | Evidence | Design impact |
|---|---|---|---|---|
| `upstream/main:.gitignore` | Determine whether docs can be tracked | Does not ignore the complete `docs/` tree | `git grep` | New branch can version migrated docs |
| Upstream `docs/` tree | Preserve upstream-owned documents | Three tracked root docs | `git ls-tree` | Keep upstream versions |
| Current `docs/` inventory | Identify migration assets | Testing architecture, plans, reports, images, templates, and four editor logs | `rg --files docs` | Track authored assets; exclude logs |
| Current/upstream document blob hashes | Detect overlapping-content conflict | Three overlapping files are identical | `git hash-object` vs `git rev-parse` | Checkout does not require content merge |
| Current CI/tests vs upstream | Bound documentation claims | Current test/CI assets are not yet on upstream | prior tree comparison | Add NOT_YET_REVALIDATED boundary |

## 5. Problem Model

### Invariants

- Branch ancestry begins at exact upstream HEAD.
- No unrelated-history merge is created.
- Historical reports retain their original revision meaning.
- Planned, migrated, and verified coverage remain separate statuses.
- Generated local logs do not become repository documentation.

### State transition

~~~text
old evidence branch + ignored docs
  -> switch to new branch rooted at upstream/main
  -> upstream-owned docs remain authoritative
  -> add authored local docs
  -> label test architecture/status as pre-migration evidence
  -> verify staged scope
~~~

### Coverage boundary

- This unit proves: branch ancestry and durable documentation migration.
- This unit does not prove: Langfuse integration, pytest compatibility, CI
  behavior, or any test result on the new branch.

## 6. Options and Trade-offs

| Option | Benefits | Costs and risks | Decision |
|---|---|---|---|
| Track all files including Typora logs | Literal byte-for-byte docs copy | Commits generated local/editor noise and unrelated paths | Rejected; ZIP already preserves logs |
| Track authored docs and immediately claim old statuses apply | Simple narrative | Creates false coverage and gate claims against code not yet migrated | Rejected |
| Track authored docs with an explicit migration boundary | Preserves knowledge and evidence without overclaiming | Requires later revalidation as MIG-2/MIG-3 land | Selected |

## 7. Decision Record

- Selected option: upstream-rooted branch plus authored documentation migration
  and an explicit pre-migration/revalidation boundary.
- Rollback: return to the untouched evidence branch or restore MIG-0 ZIP.
- Invalidation condition: an excluded Typora log is shown to be the sole source
  of required engineering evidence rather than generated editor output.

## 8. Guided-Learning Checkpoint

- Not required: repository evidence eliminates the unsafe alternatives. A stale
  test claim cannot be promoted to current coverage before its code/test exists
  and executes on the target branch.
- User decision already supplied: migrate `docs/` along with the latest version.

## 9. Requirement-to-Change-to-Evidence Mapping

| Requirement or risk | Planned change | Verification |
|---|---|---|
| Exact upstream ancestry | create `codex/upstream-langfuse-sync` from `upstream/main` | `git merge-base --is-ancestor upstream/main HEAD` before docs commit |
| Preserve authored docs | stage Markdown/images under `docs/` | staged inventory/count and representative paths |
| Avoid editor noise | ignore `docs/**/Typora_Hook_Log.txt` | `git status --ignored` and staged-path absence |
| Prevent stale coverage claims | add migration status and entry notices | text search for target status and revision |
| Keep MIG-1 isolated | no production/test/CI staged files | staged diff name/status |

## 10. Planned Changes

| File or symbol | Planned change | Reason |
|---|---|---|
| Git branch | create from `upstream/main` | clean latest-version base |
| `.gitignore` | ignore generated Typora hook logs and local root docs backups | prevent accidental migration noise |
| `docs/testing/MIGRATION_STATUS.md` | add branch/revision/proof-boundary map | reader-facing source of truth |
| `docs/testing/README.md` | add migration notice and link | make boundary visible at entry point |
| `docs/testing/CURRENT_PROGRESS.md` | mark migration prerequisite current | prevent stale current-progress reading |
| migration plan/journal | record result and evidence | durable execution trace |

## 11. Actual Changes

| File or symbol | Actual change | Difference from plan |
|---|---|---|
| `codex/upstream-langfuse-sync` | Created from `upstream/main@c2caa907...` | None |
| `.gitignore` | Added `docs/**/Typora_Hook_Log.txt` | None |
| `docs/MIGRATION_STATUS.md` | Added all-docs origin and validity boundary | Added after detecting tracked old architecture docs removed by checkout |
| `docs/testing/MIGRATION_STATUS.md` | Added testing implementation/evidence/gate migration boundary | None |
| Testing README/current progress/final plan | Switched current truth to migration plan and paused P3-0 | None |
| Testing architecture entry and module docs | Added target-branch `REVIEW_NEEDED` / `NOT_WIRED` notices | Expanded beyond only overview so direct readers see the boundary |
| Old tracked architecture docs | Restored eight missing docs from `codex/c0-4-intentional-red` | Required because branch checkout removed files tracked only in old history |
| Authored docs and image | Added to target branch index | None |
| Migration commit | Created `0cd39102` (`docs:migrate-testing-knowledge-onto-upstream-baseline`) | Commit uses a shell-safe no-space message because of the recorded Windows wrapper behavior |

No production, Langfuse, pytest, CI workflow, dependency, secret, gate, or release file was migrated.

## 12. Execution Evidence

| Command or check | Result | What it proves | What it does not prove |
|---|---|---|---|
| `git switch -c codex/upstream-langfuse-sync upstream/main` | exit 0; initial HEAD `c2caa907...` | Branch began at exact fetched upstream baseline | Documentation correctness or code compatibility |
| Blob comparison for three overlapping upstream docs | all three hashes identical | Upstream copies could remain authoritative without content merge | Other old architecture docs are current |
| `git restore --source=codex/c0-4-intentional-red -- <8 docs>` | exit 0 | Old tracked architecture/testing design was recovered from evidence branch | Recovered docs match current upstream implementation |
| `git ls-files docs` after staging | 54 tracked docs | Authored and upstream documentation is durable in target index | Files have been pushed or reviewed |
| `rg --files --no-ignore docs` + ignored status | 58 workspace files; exactly four Typora logs ignored | No authored docs were silently omitted by the log rule | Semantic completeness of every doc |
| Staged scope check | 52 staged paths: 51 docs + `.gitignore`; no outside-scope path | MIG-1 contains no product/test/CI implementation change | Later ports will be conflict-free |
| Target workflow tree | only `.github/workflows/build-release.yml` | Old Smoke/Stream PR gates are correctly marked `NOT_WIRED` on target | Build-release behavior was executed |
| Old evidence branch head check | remains `d6553a96...` | Branch creation did not rewrite the preserved evidence head | Remote branch availability beyond fetched refs |
| `git diff --cached --check` | exit 2 on pre-existing/intentional Markdown trailing spaces and EOF blanks in migrated historical docs | Formatting debt is visible rather than hidden | It is not a product/test failure; no bulk rewrite was made |
| Migration commit | `0cd39102`; 52 changed paths and 14,978 insertions | Documentation and ignore rule are durably recorded on the target branch | Remote publication or code/test compatibility |

Pytest was not run: MIG-1 intentionally changes only documentation and ignore hygiene, while target tests are a later migration unit.

## 13. Deviations and Recovery

| Initial assumption or failure | New evidence | Revised decision | Recovery result |
|---|---|---|---|
| Ignored docs would remain, so the visible workspace tree would be sufficient | Eight docs were tracked only on the old branch and disappeared during upstream checkout | Restore exact files from preserved evidence branch | All old tracked documentation recovered and staged |
| One central notice might be sufficient | Directly opened architecture/CI/Langfuse docs would still show stale current-state claims | Add local notices to primary architecture modules and plan/current-progress entries | Readers see target proof boundary without first knowing repository history |
| Full staged diff should pass whitespace check | Historical Markdown already contains hard-break trailing spaces and EOF blanks | Record debt; avoid unrelated 14k-line formatting rewrite | Migration content remains semantically unchanged |
| Quoted commit message would be passed as one `-m` argument | Windows command wrapper split the quoted message into pathspec arguments; commit exited 1 before writing history | Retry with a no-space shell-safe commit message | Staged content and branch remained unchanged after the failed attempt |

## 14. Remaining Risks and Uncertainty

- Code/test compatibility remains intentionally unresolved until MIG-2/MIG-3.
- Historical docs may require targeted edits after their owning code is ported.
- The branch is local and has not been pushed or opened as a PR.
- Historical Markdown contains whitespace warnings that were preserved to avoid a broad formatting-only rewrite.

## 15. Teach-Back

Ask the user to explain why migrating a document file does not migrate the code
or execution evidence that originally supported its claims.

### User explanation or application evidence

- `TEACH_BACK_PENDING`; no independent explanation has been supplied for MIG-1 yet.

## 16. Final Proof

- Acceptance result: `DONE` — upstream-rooted branch created, authored docs tracked, editor logs excluded, stale coverage boundary visible, staged scope isolated.
- Evidence location: migration commit `0cd39102`, this journal, migration plan, and target branch index.
- Gate or release effect: none.

## 17. Next Recommended Task

- MIG-2: port and adapt Langfuse integration and deterministic unit tests.
