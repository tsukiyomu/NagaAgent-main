# Testing Documentation Migration Status

> 当前目标分支：`codex/upstream-langfuse-sync`
> 上游基线：`upstream/main@c2caa9079b9eb48129f550c43a5485231d404d3b`
> 旧证据分支：`codex/c0-4-intentional-red@d6553a96f6987c5f58fdafddb99fc28e19c72eb0`
> 状态日期：`2026-09-11`（MIG 历史保留；追加 P3-0 验收结果）

全体 `docs/` 的来源边界见 [`../MIGRATION_STATUS.md`](../MIGRATION_STATUS.md)。

## 1. 这次迁移做了什么

`docs/` 中的人工编写文档与图片已经迁入最新 upstream 基线所在的工作分支。
MIG-1 保存了知识、历史证据和后续计划；MIG-2 迁入 Langfuse adapter 与单元测试。
MIG-3 随后迁入兼容测试/CI 资产，MIG-4 在 `981821be` 完成本地回归并形成新测试基线。
MIG-0～MIG-4 的本地迁移范围已完成；用户追加的 MIG-5 在 `7c88065c` 恢复 Langfuse runtime，
通过原 LAN 服务的合成 trace 上传/读回。9 月 11 日 P3-0 将 `357a8a6f` 发布到
`tsukiyomu/NagaAgent-main` 的迁移分支，完成两条 CI 与 JUnit 下载解析；main 未合并。

以下四类状态必须分开理解：

| 维度 | 当前状态 | 含义 |
|---|---|---|
| 文档文件 | `MIGRATED` | 文档已进入目标分支的 Git 变更范围 |
| 历史 C0 报告 | `VERIFIED_ON_SOURCE_REVISION` | 报告中的运行结果仍对其记录的旧 revision 有效 |
| Langfuse runtime/tests | `LANDED` / `VERIFIED_SYNTHETIC_LAN` | SDK/chat/LLM/tool/lifecycle 接线完成；58 adapter cases + 9 runtime cases + 1 wiring case；提交后 LAN 2 traces / 7 observations；CI 仍 `NOT_WIRED` |
| 测试基座 | `LANDED` / 本地 `VERIFIED` | MIG-5 全套 189 passed、2 skipped、2 xfailed，另有 12 subtests passed |
| Smoke / Stream CI | `LANDED` / `VERIFIED_ON_TARGET` | P3-0 在 `357a8a6f` 的 manual CI 为 Smoke 3 / Stream 2 passed，JUnit 已下载解析；Required 未重新验证或更改 |
| 报告链路 | 本地 `VERIFIED` | JUnit、Allure 原始结果、32 条子集的 Quality 摘要；未晋升性能基线 |
| 架构与计划说明 | `PARTIAL` | 新基线、CI/Langfuse 当前边界、状态入口已同步；其余历史模块说明未逐行重新认证 |

## 2. 当前代码与证据边界

### 目标分支当前真实存在

- 已固定的 `RTGS2017/NagaAgent@c2caa907...` 产品代码，迁移没有覆盖其实现。
- upstream 原有的三个根级文档：`build-windows.md`、
  `naga-network-requirements.md`、`travel-exploration-system.md`。
- 本次迁移进入 Git 变更范围的测试架构、计划、报告、展示材料和图片。
- `apiserver/langfuse_integration.py` 与 `tests/unit/test_langfuse_integration.py`；
  source 的三个 helper 契约保留，并补入 context/cleanup 等回归测试。
- Smoke、SSE、Loop、Golden、归因/Quality helpers、pytest marker/fixture、两个 PR workflows。
- collection-time offline bootstrap；产品配置逻辑保留，测试使用临时 home / 受控配置和连接护栏。
- 独立 frozen-lock 环境的本地回归、预期失败探针和可核对的 JUnit / Allure / Quality 产物。
- MIG-5 的 `langfuse_runtime.py`、SDK 4.15.1、真实调用点和显式 LAN 验收脚本；默认正文禁用，现有 `.env` 保留。

### 目标分支当前尚未存在或尚未验证

- 新 revision 的 Required enforcement、PR merge-ref 验证和 main 合并；P3-0 只完成分支发布与 manual CI / JUnit，没有变更规则。
- user-stop 与跨轮重复 tool id 去重；仍为两个原有 xfail，不计作已实现。
- 当前版本的可信性能基线；旧 JSON 仅保留来源数值，本次独立 advisory bootstrap 不作晋升。
- 真实 LLM、Remote Memory、MCP、staging、持久化回读和部署验证；Langfuse UI 浏览器交互及 motion acknowledgement 也未验收。

## 3. 阅读规则

1. `reports/closed-loop-*` 是历史执行证据。保留原 revision、run 和 Artifact 含义，
   不把它们改写为当前 upstream 结果。
2. 当前已核对范围以 [`architecture/upstream-testing-baseline.md`](architecture/upstream-testing-baseline.md)
   为入口。旧 Part 文档仍可帮助理解断言，但旧运行/优先级/Required 事实不能无条件继承。
3. `plans/nagaagent-final-testing-plan.md` 的 P3-0 已于 9 月 11 日完成；P3-1 workflow 学习尚未启动。
4. workflow 文件只证明配置存在，远端执行和 Required 必须分别取证，不能自动继承旧 Check 状态。
5. Langfuse 是 observability side channel，不是 pytest assertion 或 CI gate truth。

## 4. 文档迁移选择

- 迁移：Markdown、图片、测试架构、计划、报告、展示和模板资料。
- 不纳入 Git：四个 `Typora_Hook_Log.txt`。它们是生成的本地编辑器日志，已由 MIG-0 ZIP 备份。
- 不纳入本单元：根目录的历史 docs backup 文件夹、Allure/Test artifacts 和未跟踪的
  `NagaAgent System Prompt Assembly Analysis.md`；它们没有被删除。

## 5. 当前真相源

| 问题 | 当前真相源 |
|---|---|
| 迁移进度 | [`plans/upstream-migration-plan.md`](plans/upstream-migration-plan.md) |
| MIG-1 决策与证据 | [`reports/upstream-migration-mig-1-execution-journal.md`](reports/upstream-migration-mig-1-execution-journal.md) |
| MIG-2 决策与证据 | [`reports/upstream-migration-mig-2-execution-journal.md`](reports/upstream-migration-mig-2-execution-journal.md) |
| MIG-3 迁移与隔离理由 | [`reports/upstream-migration-mig-3-execution-journal.md`](reports/upstream-migration-mig-3-execution-journal.md) |
| MIG-4 回归与新基线 | [`reports/upstream-migration-mig-4-execution-journal.md`](reports/upstream-migration-mig-4-execution-journal.md) / [机器清单](reports/upstream-migration-mig-4-baseline.json) |
| MIG-5 Langfuse 可用性与更新基线 | [journal](reports/upstream-migration-mig-5-execution-journal.md) / [机器清单](reports/upstream-migration-mig-5-evidence.json) |
| P3-0 基线收口与 Owner 决定 | [journal](reports/p3-0-execution-journal.md) / [机器清单](reports/p3-0-baseline-evidence.json)；PR #2 已关闭未合并、证据分支保留 |
| 旧 Closed Loop 结果 | 历史报告中记录的 source revision、GitHub run 和 Artifact |
| 目标分支实现 | 当前 `codex/upstream-langfuse-sync` 代码树 |
| 目标分支测试/CI 状态 | P3-0 同 revision 本地与远端验收；Langfuse LAN 保留 MIG-5 证据，Allure/Quality 保留 MIG-4 边界；[CI 当前结论](architecture/ci-pr-gate.md#0-当前-upstream-分支结论) |

## 6. 下一步

下一工作单元为 P3-1 基础 Agent workflow 理解；本轮没有启动。P3-0 已在 Owner 明确选择后完成远端验收。
Langfuse 的正文状态和已知风险以 [当前测试基线](architecture/upstream-testing-baseline.md#6-未完成范围与阅读规则) 为准，
不能把 MIG-5 初始“默认禁用 / 需重启”当成此后所有活动进程的状态，也不能把本次 CI 绿色当作这些风险已修复。
