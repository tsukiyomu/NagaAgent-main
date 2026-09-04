# CI / PR Gate

> **Migration status：`NOT_WIRED` on target branch。** 下述 workflow/run/Gate 事实属于旧
> source revision；MIG-3 尚未把对应 GitHub Actions 迁入当前 upstream-based branch。
> 详见 [`../MIGRATION_STATUS.md`](../MIGRATION_STATUS.md)。

## 1. 文档定位

本文档是 NagaAgent 测试体系中 GitHub Actions 与 PR 准入规则的事实来源，负责说明：

1. 哪个 workflow 会被触发。
2. GitHub runner 实际执行哪些测试。
3. GitHub Actions 成功与 Branch Protection 强制合并门禁的区别。
4. 如何在本地复现 CI 命令。

模块测试文档，例如 [`part-02-api-stream.md`](part-02-api-stream.md)，负责说明测试行为和断言；本文件只记录当前
已经落地的 GitHub Actions 配置，不承载尚未确定的后续 Gate 规划。

## 2. 当前 Workflows

- 文件：`.github/workflows/pr-smoke-gate.yml`
- workflow 名称：`PR Smoke Gate`
- job id：`smoke-blocking`
- GitHub Checks 显示名称：`Smoke Blocking Gate`
- runner：`ubuntu-latest`
- job timeout：20 分钟
- permissions：`contents: read`

### 2.1 触发条件

| 事件 | 条件 | 用途 |
|---|---|---|
| `pull_request` | 目标分支为 `main` 或 `master` | 验证待合并变更 |
| `push` | 推送到 `main` | 验证主分支提交 |
| `workflow_dispatch` | 手动触发 | 手动复现或诊断 |

`push` 成功只说明主分支上的这次 workflow 运行通过。只有 `pull_request` 事件配合 Branch
Protection required check，才能形成“失败时禁止合并”的 PR 强制门禁。

### 2.2 执行步骤

当前 job 按以下顺序执行：

```text
checkout repository
  -> setup Python 3.11
  -> setup uv
  -> uv sync --frozen --group test
  -> uv run python -m pytest tests/smoke -m "smoke and blocking" -q
       --junitxml=tests/artifacts/closed_loop_v1/junit-smoke.xml
  -> 无论 pytest 成功或失败都上传 suite/run/attempt 唯一的 JUnit Artifact
  -> pytest 非零退出码仍决定 job failure
```

各步骤职责：

1. `actions/checkout`
   - 将当前 commit 或 PR merge ref 检出到 runner。
2. `actions/setup-python`
   - 提供 Python 3.11，与项目支持版本保持一致。
3. `astral-sh/setup-uv`
   - 安装 uv。
4. `uv sync --frozen --group test`
   - 严格按 lock file 安装项目和 test dependency group。
   - lock file 与项目声明不一致时应失败，避免 CI 静默解析出不同依赖。
5. pytest
   - 只收集 `tests/smoke` 下同时带 `smoke` 和 `blocking` marker 的测试。
   - marker 描述测试属性；是否在 PR 阶段执行由 workflow 决定。
   - 任意测试失败或 fixture setup 失败都会让 job 返回失败。
   - 同时写出 `tests/artifacts/closed_loop_v1/junit-smoke.xml`，供机器读取 testcase、失败与错误明细。
6. JUnit Artifact 上传
   - `if: always()` 保证 pytest 失败后仍尝试保存诊断证据。
   - `if-no-files-found: error` 把“承诺生成报告但文件缺失”识别为 CI 基础设施错误。
   - 上传成功不会覆盖 pytest 的失败结果；pytest assertion 和退出码仍是 blocking truth。

### 2.3 Stream Contract Gate（远端 PR 运行已验证）

- 文件：`.github/workflows/pr-stream-contract-gate.yml`
- workflow 名称：`PR Stream Contract Gate`
- job id：`stream-contract`
- GitHub Checks 显示名称：`Stream Contract Gate`
- runner：`ubuntu-latest`
- job timeout：20 分钟
- permissions：`contents: read`
- concurrency：按 Git ref 分组，`cancel-in-progress: true`

触发条件与 Smoke workflow 一致：面向 `main` / `master` 的 pull request、推送到 `main`，以及
`workflow_dispatch` 手动触发。

该 job 执行：

```text
checkout repository
  -> setup Python 3.11
  -> setup uv
  -> uv sync --frozen --group test
  -> uv run python -m pytest tests/integration/chat_stream/test_resilience.py
       -m "integration and blocking and not real_llm" -q
       --junitxml=tests/artifacts/closed_loop_v1/junit-stream-contract.xml
  -> 无论 pytest 成功或失败都上传 suite/run/attempt 唯一的 JUnit Artifact
  -> pytest 非零退出码仍决定 job failure
```

当前 selection 精确包含两条已评审 SSE 契约，不包含 user-stop `xfail`、real LLM 或其他未评审
case。用例使用真实 `/chat/stream` route、可控 fake loop 与 persistence spy，不调用真实外部 LLM。

2026-08-10 的 Draft PR 证据确认：

| 字段 | 证据 |
|---|---|
| 触发事件 | `pull_request` |
| Head branch | `codex/verify-stream-contract-gate` |
| Head commit | `44a0af58d56e9b872ee064a36b1a193d3a7f353c` |
| Workflow / Check | `PR Stream Contract Gate / Stream Contract Gate` |
| GitHub job 结果 | `Successful`，PR 汇总页显示约 22 秒 |
| 实际 pytest 结果 | `2 passed, 6 deselected, 3 warnings in 2.61s` |
| Selection 边界 | 只执行两条 `integration and blocking and not real_llm` SSE 契约 |
| Required 状态 | PR 页面未显示 `Required`，当前归类为 `NON_BLOCKING` |

该证据证明 Stream Contract workflow 已经在真实 PR 事件中完成远端接线和成功执行。后续 C0-4
已通过 [Draft PR #2](https://github.com/tsukiyomu/NagaAgent-main/pull/2) 补齐真实负向红灯与恢复绿色；
它仍不证明失败会阻止合并，是否设置为 Required Check 属于 C0-6。

### 2.4 JUnit Artifact 发布契约

| Suite | Runner 文件 | Artifact 名称 | 上传条件 | 保留期 | 当前证据状态 |
|---|---|---|---|---|---|
| Smoke | `tests/artifacts/closed_loop_v1/junit-smoke.xml` | `closed-loop-v1-smoke-junit-${{ github.run_id }}-${{ github.run_attempt }}` | `if: always()`；缺失文件时报错 | 14 天 | workflow 与远端 success upload `VERIFIED`；未单独执行 Smoke failed-run probe |
| Stream Contract | `tests/artifacts/closed_loop_v1/junit-stream-contract.xml` | `closed-loop-v1-stream-contract-junit-${{ github.run_id }}-${{ github.run_attempt }}` | `if: always()`；缺失文件时报错 | 14 天 | success 与真实 failed-run upload/download/parse 均 `VERIFIED` |

Artifact 名称中的 suite 区分测试层，`github.run_id` 关联 workflow run，`github.run_attempt` 区分同一
run 的重试。`actions/upload-artifact@v4` 使用不可变 artifact 语义，因此每次 attempt 使用唯一名称，
不依赖覆盖旧证据。14 天是短期 PR review / triage 生命周期，不把 JUnit 当作永久审计档案。

本地失败探针已验证 pytest 在 assertion failure 时仍写出包含 testcase、失败消息和源代码位置的
JUnit XML；这证明报告格式可承载失败归因。2026-08-22 的 hosted success runs 进一步证明 GitHub
runner 能执行两个 upload step 并建立带 revision、digest 和 expiry 的 artifact：

| Suite | Run / Job | Artifact | Metadata evidence |
|---|---|---|---|
| Smoke | [run `32568350661`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/32568350661) / job `97020157953` | `closed-loop-v1-smoke-junit-32568350661-1`，id `9474671380` | 390 bytes；digest `sha256:0a9155...b25f`；expires `2026-09-05T10:43:33Z` |
| Stream Contract | [run `32568350679`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/32568350679) / job `97020157697` | `closed-loop-v1-stream-contract-junit-32568350679-1`，id `9474672187` | 717 bytes；digest `sha256:2f5de8...b6a`；expires `2026-09-05T10:43:37Z` |

两个 run 均为 `main@533d4a3...`、`push`、attempt 1、结论 `success`，其 test 与 upload step 都为
`success`。用户已人工检查远端结果；2026-08-23 的未认证 archive download 曾返回 HTTP `401`，所以
当时只记录 metadata，没有夸大为 Agent 已解析托管 ZIP。2026-08-31 的 C0-3 托管失败路径复核已补齐
内容下载证据：

| Run / revision | Test / upload | Artifact | 下载解析结果 |
|---|---|---|---|
| [failure run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451) / `07ee89cbc1124c4430bbacdc213845fd73f78181` | pytest `failure`；upload `success` | `closed-loop-v1-stream-contract-junit-33392294451-1`；id `9757933428`；1542 bytes；digest `sha256:956e2a20c218ff9f2b9fc434accc7823680663039dccba701c9be77ec984d437`；expires `2026-09-14T12:33:13Z` | ZIP digest 匹配；仅含 `junit-stream-contract.xml`；`tests=2 / failures=1 / errors=0 / skipped=0`；可定位 baseline nodeid、故障 assertion、`assert 1 == 2` |
| [restored run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083) / `d6553a96f6987c5f58fdafddb99fc28e19c72eb0` | pytest `success`；upload `success` | `closed-loop-v1-stream-contract-junit-33392789083-1`；id `9758123014`；716 bytes；digest `sha256:58d5dd7ec563da411d4a2ace0aa0d11484743ee638f31a835030a7ffdd3fc048` | ZIP digest 匹配；JUnit `tests=2 / failures=0 / errors=0 / skipped=0`；故障断言已恢复 |

认证下载最初仍得到 `401`，原因是客户端把 GitHub API 的认证头转发给了对象存储重定向目标。改为
先读取 GitHub `302 Location`，再不携带 GitHub 认证头请求签名 URL 后下载成功；凭据未输出或落盘。
这先关闭 C0-3 的真实 failed-run Artifact 缺口；用户后续明确继续后，同一组不可变 run/artifact
证据与三次稳定性结果一起用于 C0-4 正式验收。

### 2.5 C0-4 稳定性与负向检测结论

| 验收阶段 | 结果 | 证据 |
|---|---|---|
| 本地重复稳定性 | 三次均 `2 passed, 6 deselected`，nodeid 集合一致 | `13.19s / 13.30s / 11.63s`；无 flaky、XPASS、setup error 或 selection 漂移 |
| 初始远端绿色 | `Success` | [run `33392018497`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392018497) / revision `958b66b...` |
| 确定性故障红灯 | `Failure` / process exit `1` | [run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451) / revision `07ee89c...` |
| 失败证据保存 | failure ZIP digest 匹配，JUnit `tests=2 / failures=1` | Artifact id `9757933428`；可定位 nodeid、assertion、source、run、revision |
| 恢复绿色 | `Success`，JUnit `tests=2 / failures=0` | [run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083) / revision `d6553a9...` |
| 当前源码/回归 | diff 只有 remote-memory fixture 隔离；full resilience `7 passed, 1 xfailed` | 当前 branch/remote head `d6553a96...`；故障断言已恢复为 `round_end == 1` |

C0-4 因此为 `DONE`。PR #2 是包含 intentional-red 历史的专用 Draft 证据 PR，不应按普通 merge
进入 `main`；当前 Stream Check 仍为 `NON_BLOCKING`。

JUnit 是执行证据和诊断输入，不是第二套 Gate 判定器。Smoke 与 Stream Contract 仍分别由其 pytest
assertion 和退出码决定 Check 成败；当前 Quality Gate JSON / Markdown 也未被接入这两个 job。

### 2.6 C0-5 Traceability / Gate Record 结论

[`C0-5 Gate Record`](../reports/closed-loop-v1-c0-5-2026-09-01.md) 已把 C0-1～C0-4 的分散证据
整理成“风险 -> test/nodeid -> CI -> JUnit Artifact -> failure classification -> 当前决定”的单一入口。
该同步不新增 workflow，也不改变任何现有 job outcome 或 Gate 配置。

| Pipeline / review stage | Observed result | C0-5 status | Evidence boundary |
|---|---|---|---|
| Marker selection | 当前限定文件精确收集 `2/8`，其余 `6 deselected` | `PASS` | 只覆盖两条 blocking SSE case |
| Current local execution | `2 passed, 6 deselected, 3 warnings in 12.59s`；JUnit `2/0/0/0` | `PASS` | real route + fake loop + persistence spy；不证明外部服务 |
| Initial GitHub green | run `33392018497` 为 `Success` | `PASS` | 单次 green 不独立证明稳定性 |
| Intentional negative probe | run `33392294451` 的 GitHub conclusion 为 `Failure` / exit `1` | `PASS`（预期红灯被观察到） | controlled assertion mismatch，不是产品 defect |
| Failure evidence upload | 红色 pytest step 后 upload `success`，failure JUnit 可定位 `assert 1 == 2` | `PASS` | Artifact 仅保留 14 天，长期依赖 metadata/report |
| Restored GitHub green | run `33392789083` 为 `Success`，JUnit `tests=2 / failures=0` | `PASS` | 证据 PR 历史仍含 intentional-red commit |
| Required enforcement review | C0-5 没有 Owner 决定或 Ruleset 直接证据 | `SKIPPED`（C0-6 scope） | Stream 继续 `NON_BLOCKING` |

C0-5 记录状态是 `VERIFIED_LOCAL_RECORD`：风险和证据链在 shared workspace 中可复核，但仓库的
`.gitignore` 当前排除 `/docs/`，所以不能宣称这份 Gate Record 已作为 Git/GitHub 版本化审计档案发布。

### 2.7 C0-6 Owner gate decision

Repository Owner 于 2026-09-01 选择 `A — DEFER_REQUIRED_PROMOTION`：

| Decision item | Result | Boundary |
|---|---|---|
| Closed Loop V1 evidence-and-decision loop | `VERIFIED` | 表示技术证据和人类决定已闭环，不表示 merge blocking |
| `Stream Contract Gate` | `NON_BLOCKING` | 未修改 Branch Protection / Ruleset，不能写成 `PR_BLOCKING` |
| Remote memory in the two SSE contract cases | `ISOLATED` on evidence branch | `get_remote_memory_client -> None`，让失败可归因于 SSE 契约 |
| Real remote-memory integration coverage | `DELAYED` | 当前 JUnit 不证明认证、云端查询、网络或回退行为 |
| Required reconsideration | `PENDING_CLEAN_LANDING` | 先将隔离用干净 PR 落入 `main` 并复跑，再读取已认证平台规则 |

本轮复核为 `2 passed, 6 deselected, 3 warnings in 12.66s`、JUnit `2/0/0/0`；完整 resilience
文件为 `7 passed, 1 xfailed, 3 warnings in 13.54s`。完整决定见
[`C0-6 Owner Decision Record`](../reports/closed-loop-v1-c0-6-2026-09-01.md)。

## 3. 当前实际门禁范围

当前 PR 配置并验证了两个分离的确定性检查：

| 测试集合 | 当前 CI 是否执行 | Gate 状态 | 当前定位 |
|---|---|---|---|
| `tests/smoke -m "smoke and blocking"` | 是；`pull_request` 成功证据为 `3 passed` | `PR_BLOCKING`；该 Draft PR 显示 `Required` | PR 快速确定性门禁 |
| `test_resilience.py -m "integration and blocking and not real_llm"` | 是；`pull_request` 成功证据为 `2 passed, 6 deselected` | `NON_BLOCKING`；未显示 `Required` | SSE 正常/异常终止契约检查 |

因此 GitHub 页面显示对应 Check 为 Success 时，只能得出该 Check 所选择的确定性集合在该 revision
通过。`Smoke Blocking Gate` 不证明 integration；`Stream Contract Gate` 不证明真实 LLM、真实持久化
或完整 Agent Workflow。

不能据此得出：

1. 未被对应 marker selection 选中的 unit、golden、user-stop 或 real LLM 已运行。
2. 真实 LLM、MCP、Neo4j、memory 已联通。
3. Branch Protection 已配置为禁止失败 PR 合并。

## 4. Branch Protection

workflow YAML 负责“产生 check”，Branch Protection 或 Repository Ruleset 负责“要求 check
必须通过后才能合并”。这是两个独立配置。

要形成真正的 PR required gate，需要在 GitHub 仓库设置中：

1. 对 `main`（以及实际使用的目标分支）启用 branch protection/ruleset。
2. 启用 require status checks before merging。
3. 根据仓库 Owner 的评审结论，将 `Smoke Blocking Gate` 和/或 `Stream Contract Gate` 选为
   required status check。
4. 根据团队策略决定是否要求分支与目标分支保持最新。

仓库中的 YAML 无法单独证明以上设置已经启用，应在 GitHub Repository Settings 中确认。

2026-08-10 的 Draft PR 页面提供了当前规则的运行时证据：`Smoke Blocking Gate` 带有 `Required`
标识，而 `Stream Contract Gate` 没有。因此，对该 PR 适用的准确结论是 Smoke 为
`PR_BLOCKING`、Stream 为 `NON_BLOCKING`。页面上的 Merge 按钮不可用还受到 Draft 状态影响，
不能用来证明 Stream 失败会阻止合并。

## 5. 本地复现

当前 GitHub Actions 的等价测试命令：

```bash
uv sync --frozen --group test
uv run python -m pytest tests/smoke -m "smoke and blocking" -q \
  --junitxml=tests/artifacts/closed_loop_v1/junit-smoke.xml
uv run python -m pytest tests/integration/chat_stream/test_resilience.py \
  -m "integration and blocking and not real_llm" -q \
  --junitxml=tests/artifacts/closed_loop_v1/junit-stream-contract.xml
```

## 6. 当前结论

- PR Smoke workflow 已在 GitHub Actions 运行成功。
- Stream Contract workflow 已在真实 `pull_request` 事件中运行成功，commit 为
  `44a0af58d56e9b872ee064a36b1a193d3a7f353c`，结果为
  `2 passed, 6 deselected, 3 warnings in 2.61s`。
- 两个 workflow 分别通过 pytest 退出码判定 Smoke 与 SSE Contract 集合，不使用当前 Quality Gate
  diagnostic 结果决定 job 成败。
- 两个 workflow 已分别生成并通过 `if: always()` 上传 suite/run/attempt 唯一的 JUnit，保留期为
  14 天；本地已验证 success 与 assertion failure JUnit 内容，真实 GitHub success runs 已验证
  upload step、artifact identity/digest 和 14 天 expiry；Stream 的真实 failed-run Artifact 已下载并
  解析为包含明确 nodeid/assertion 的失败 JUnit，C0-3 为 `DONE`。
- 当前 PR 页面证明 `Smoke Blocking Gate` 是 `Required`；`Stream Contract Gate` 未显示 Required，
  因此当前仅作为 `NON_BLOCKING` PR Check，不得宣称它已经阻止不合格 PR 合并。
- C0-2 已证明绿色 PR 接线；C0-3 已完成本地实现、远端 success artifact 及真实 failed-run Artifact
  下载解析；C0-4 已完成三次稳定绿色、真实红灯、failure Artifact 与恢复绿色；C0-5 已形成风险到
  Gate 的单一 Traceability / Gate Record；C0-6 已由 Owner 决定暂缓 Required 晋升，因此 Stream
  继续为 `NON_BLOCKING`，真实 remote-memory profile 为 `DELAYED`。
