# Testing Current Progress

> 最后更新：`2026-09-04`  
> 当前计划：[`NagaAgent Upstream Migration Plan`](plans/upstream-migration-plan.md)  
> 迁移状态真相源：[`MIGRATION_STATUS.md`](MIGRATION_STATUS.md)  
> 暂停的后续测试计划：[`NagaAgent Final Testing Plan`](plans/nagaagent-final-testing-plan.md)  
> 已完成前置计划：[`Closed Loop V1 Implementation Plan`](plans/closed-loop-v1-implementation-plan.md)  
> 本页职责：只回答“现在做到哪里、为什么还没完成、下一步是什么”。详细调查和逐次运行记录保留在 `reports/`，不在这里重复。

## 1. 当前结论

| 项目 | 当前状态 |
|---|---|
| 总体阶段 | Upstream Migration：`IN_PROGRESS`；Closed Loop V1 只在 source revision 上保持历史 `VERIFIED` |
| 当前工作单元 | `MIG-1 — 建立 upstream 分支并迁移/reconcile docs` |
| 当前状态 | `DONE`；下一工作单元为 MIG-2，尚未启动 |
| 完成分布 | MIG-0～MIG-1 `DONE`；MIG-2～MIG-4 `TODO`；P3-0 暂停 |
| 已完成执行链 | `3x green -> intentional red -> failure Artifact -> restored green` |
| 当前证据 revision | 目标分支文档迁移 commit `0cd39102`（upstream base `c2caa907...`）；历史测试证据 `main@533d4a3...` 与隔离证据分支 `d6553a96...` |
| Gate 状态 | 目标分支：旧 Smoke/Stream workflows 尚未迁移，按 `NOT_WIRED` 处理；历史状态不自动继承 |
| 文档发布状态 | 54 个 authored/upstream docs 已进入目标分支版本范围；4 个 Typora logs 不纳入 Git；尚未 push/PR |
| Remote memory | 产品能力保持 `LANDED`；当前两条 SSE 契约内 `ISOLATED`；真实集成覆盖 `DELAYED` |
| 最小 Closed Loop 能力 | `VERIFIED`；现有 pytest/fixture/CI/Artifact/triage/Gate Record 骨架已实际完成一条 SSE 有限闭环，可复用于新的明确业务范围 |
| CD 定位 | 仓库已有跨平台 Build & GitHub Release；Personal Web 有用户提供的 CD 实践，但具体 staging/production 平台部署细节尚未在本项目验证，当前为次重点 |
| Architecture 同步 | `REVIEW_NEEDED`；旧架构文档已迁入，但必须随 MIG-2/MIG-3 的目标代码与测试重新核对 |

一句话判断：**MIG-1 已完成文档迁移与证据边界标记；旧 Closed Loop、Langfuse、pytest 和 CI 结论没有自动转移到新分支。MIG-2/MIG-3 才迁移实现与测试，MIG-4 才形成新 baseline。**

> 以下 C0 材料是 pre-migration history，证据含义仅绑定其记录的 source revision。

## 2. Closed Loop V1 任务板

| 工作单元 | 状态 | 已完成/当前缺口 |
|---|---|---|
| C0-1 冻结 Blocking 测试集合 | `DONE` | 两条 SSE 契约可被 marker 精确选择，不包含 user-stop、real LLM 或其他未评审 case。 |
| C0-2 建立 Stream Contract CI Check | `DONE` | 独立 `Stream Contract Gate` 已在真实 PR 事件中成功运行；当前仍是 `NON_BLOCKING`。 |
| C0-3 保存最小执行 Artifact | `DONE` | Success 与 failure JUnit 均已由真实 GitHub run 上传；failure ZIP 已下载并解析。 |
| C0-4 验证重复稳定性和负向阻断 | `DONE` | 三次目标 selection 一致通过；PR #2 完成绿色→红色→恢复绿色，failure/restored JUnit 均已下载验 hash 和解析。 |
| C0-5 形成 Traceability 与 Gate Record | `DONE` | 独立 Gate Record 已连接风险、两条 nodeid、断言、dependency profile、revision、CI run、Artifact、classification、恢复与当前决定；3 份 architecture 事实所有者文档已同步。 |
| C0-6 人类确认 Required Check | `DONE` | Owner 选择 `A — DEFER_REQUIRED_PROMOTION`；不修改 GitHub rules，Stream 保持 `NON_BLOCKING`，真实 remote-memory profile 标为 `DELAYED`。 |

## 3. C0-3～C0-6 闭环证据

- 本地独立环境连续三次目标 selection：均为 `2 passed, 6 deselected`，nodeid 集合一致。
- [初始绿色 run `33392018497`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392018497)：隔离 revision 上的 Stream Contract Gate 为 `Success`。
- [故意红色 run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451)：pytest step `failure`，upload step `success`；失败 Artifact 已下载且 digest 匹配，可定位 baseline nodeid、`assert 1 == 2`、run 和 revision。
- [恢复绿色 run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083)：pytest 与 upload step 均 `success`；下载的 JUnit 为 `2 tests / 0 failures`。
- Draft [PR #2](https://github.com/tsukiyomu/NagaAgent-main/pull/2) 当前 head 只保留 remote-memory 测试隔离，`round_end == 1` 已恢复；`main` 未接收故障提交。
- C0-4 当时的完整 resilience suite 复核：`7 passed, 1 xfailed, 3 warnings in 13.76s`；C0-6 当前复核见下方 `13.54s` 记录。
- [C0-5 Gate Record](reports/closed-loop-v1-c0-5-2026-09-01.md) 已把上述事实与两条测试的风险、断言、真实性边界、failure classification 和 Gate 决定连接为单一长期入口。
- C0-5 当前 revision 复核：collection 精确 `2/8`；定向执行 `2 passed, 6 deselected, 3 warnings in 12.59s`；JUnit 为 `tests=2 / failures=0 / errors=0 / skipped=0`。
- 2026-09-01 公开页面复核：PR #2 仍为 Draft、包含 3 个证据提交且无 review；因此不存在可当作 Required 授权的 Reviewer reference。
- `.gitignore:247` 的 `/docs/` 规则命中当前 Testing 文档；本轮没有改变 ignore policy 或 force-add，因此“C0-5 DONE”只表示共享 workspace 记录完成，不表示已经提交到 GitHub。
- Architecture consistency search 精确命中 `overview.md`、`part-02-api-stream.md` 和 `ci-pr-gate.md`；它们分别负责总体状态、SSE owner 语义和 CI/Gate 事实，其他 architecture 文件没有被无差别改写。
- [C0-6 Owner Decision Record](reports/closed-loop-v1-c0-6-2026-09-01.md) 已完成 blocking qualification：证据分支满足隔离要求，但 `main@533d4a3...` 尚未包含 remote-memory fixture 隔离，因此 Owner 决定暂缓晋升 Required。
- GitHub 公开只读探针中，repository rulesets endpoint 返回 `200 []`，classic `main` protection endpoint 返回 `401 Requires authentication`；所以平台 Required 状态仍为 `UNKNOWN`，不能标记为 `PR_BLOCKING`。
- 2026-09-01 Owner 明确选择 A：暂缓 Required 晋升；该决定关闭 C0-6 的人类治理检查点，但不声称 GitHub 已配置 merge blocking。
- 当前证据分支复核：`2 passed, 6 deselected, 3 warnings in 12.66s`，JUnit `tests=2 / failures=0 / errors=0 / skipped=0`；remote-memory client 在 fixture 中固定为 `None`。
- 完整 resilience 文件回归：`7 passed, 1 xfailed, 3 warnings in 13.54s`；唯一 `xfail` 是已知 user-stop contract gap。

## 4. C0-6 关闭决定

Repository Owner 已选择：

1. **暂缓晋升**：Stream 保持 `NON_BLOCKING`，GitHub Ruleset / Branch Protection 不变。
2. remote memory 仍是正式产品能力；当前只在两条 SSE lifecycle 契约中隔离，避免 HTTP/auth/network 让失败失去归因性。
3. 真实 remote-memory authentication、query 与 fallback 测试标为 `DELAYED`，未来由独立 opt-in/integration 或 staging profile 承担。
4. Required 复审前，先以干净 PR 将两行 fixture 隔离落入 `main` 并取得目标分支绿色 run。

Closed Loop V1 的“证据 + 人类决定”闭环因此为 `VERIFIED`；这不等于 Stream `PR_BLOCKING`。

## 5. 当前框架能力与 CD 定位

### 5.1 最小 Closed Loop 已具备复用基础

当前不是只完成了一组孤立测试，而是已经用真实证据跑通一套可以复用的最小工程骨架：

```text
有限业务风险 / 契约
  -> 可审查的测试 perimeter
  -> 确定性 fixture 与 assertion
  -> CI Check
  -> success / failure Artifact
  -> failure classification
  -> restored verification
  -> human Gate decision
```

“完整”是相对于声明范围而言：当前 SSE lifecycle loop 是完整的；remote-memory integration、real LLM
和完整 Agent E2E 仍应分别建立自己的 loop，不能因为共享同一套工程步骤就被算作已覆盖。

复杂业务通常首先增加测试侧的建模与实现成本，例如状态准备、fixture、stub/spy、数据清理、并发、故障
注入和断言；当真实性需要数据库、外部服务、secret、专用 runner 或 staging 时，复杂度才进一步扩散到
CI/CD 的环境、执行策略和 Gate 等级。不能把所有复杂度都归入测试代码，也不需要把所有 profile 塞进
同一个 PR workflow。

### 5.2 CD 是次重点，但不是未涉及

- 当前仓库的 [Build & Release workflow](../../.github/workflows/build-release.yml) 已实现 Windows/macOS/Linux
  构建、Artifact 汇总和 GitHub Release 发布；它证明 release packaging/publishing，不证明某个应用平台上的
  staging -> production 部署、health/readiness、migration 或 rollback。
- Personal Web 已有 CD 实践属于用户提供的经验事实；目标平台、运行时、secret、数据库和回滚机制不同，
  具体细节需要在真实项目平台确定后再验证，当前不能从本仓库推断。
- 对当前测试工程目标，优先级仍是继续用同一方法形成多个范围清晰、可归因的 Closed Loop；在没有明确
  部署目标前，不为了形式完整而扩建平台级 CD。
- 后续如选择部署平台，最小可信 CD 边界应至少包含：可复现构建、环境配置/secret、部署、health 或
  post-deploy smoke、失败回滚和部署证据。

### 5.3 Architecture 尚未同步的内容

截至 2026-09-02，C0-6 的执行事实已经同步到 `overview.md`、`part-02-api-stream.md` 和
`ci-pr-gate.md`；但本节新增的以下跨层结论仍只存在于 Current Progress：

1. Closed Loop 的完整性相对于业务/风险范围，而不是相对于整个产品。
2. 当前测试框架已经具备复用最小 Closed Loop 的基础。
3. 复杂业务主要增加测试设计与依赖控制，也可能扩散到 CI/CD 环境与 Gate 策略。
4. 当前仓库的 Build & Release、Personal Web CD 经验和未来平台部署验证属于三个不同证据层级。

预计事实所有者为 `architecture/overview.md`（全局 Closed Loop 模型）和
`architecture/ci-pr-gate.md`（CI、Release 与未来 platform CD 边界）。在完成该同步前，Architecture
状态保持 `PARTIAL`，不得写成上述新结论已经被完整架构化。

## 6. 当前证明边界

- `Smoke Blocking Gate` 当前有 Required 运行时证据；`Stream Contract Gate` 没有 Required 证据，继续分类为 `NON_BLOCKING`。
- Stream Contract 使用真实 `/chat/stream` route、可控 fake loop 和 persistence spy；它不证明真实 LLM、真实持久化回读或完整 Agent Workflow。
- pytest assertion 和退出码仍是 Check 成败的真相源；JUnit 是可下载执行证据，不是第二套 Gate 判定器。
- C0-3 已关闭 Artifact 证据生命周期，C0-4 已关闭稳定性与负向检测验收，C0-5 已形成完整追溯记录，C0-6 已保存 Owner 的 non-blocking 决定；它们不能互相替代。

## 7. 文档怎么读

| 想知道什么 | 阅读位置 |
|---|---|
| 现在做到哪里、下一步是什么 | 本页 `CURRENT_PROGRESS.md` |
| 当前唯一后续路线图、P3 工作单元与长期扩展 | [`plans/nagaagent-final-testing-plan.md`](plans/nagaagent-final-testing-plan.md) |
| 每个 C0 工作单元的目的、步骤与验收标准 | [`plans/closed-loop-v1-implementation-plan.md`](plans/closed-loop-v1-implementation-plan.md) |
| C0-3 的完整调查、设计和执行日志 | [`reports/closed-loop-v1-c0-3-2026-08-20.md`](reports/closed-loop-v1-c0-3-2026-08-20.md) |
| C0-4 的三绿、红灯、Artifact 与恢复报告 | [`reports/closed-loop-v1-c0-4-2026-08-31.md`](reports/closed-loop-v1-c0-4-2026-08-31.md) |
| C0-5 的风险到 Gate 决策追溯记录 | [`reports/closed-loop-v1-c0-5-2026-09-01.md`](reports/closed-loop-v1-c0-5-2026-09-01.md) |
| C0-6 的 blocking 资格与 Owner 决策记录 | [`reports/closed-loop-v1-c0-6-2026-09-01.md`](reports/closed-loop-v1-c0-6-2026-09-01.md) |
| GitHub Actions 当前真实执行与 Gate 边界 | [`architecture/ci-pr-gate.md`](architecture/ci-pr-gate.md) |
| 测试报告和运行产物应放在哪里 | [`reports/README.md`](reports/README.md) |

维护规则：每完成或复核一个工作单元，先更新实施计划与证据，再同步本页的当前任务、状态、缺口和下一步；本页不累积逐次运行日志。
