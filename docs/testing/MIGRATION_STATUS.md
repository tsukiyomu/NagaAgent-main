# Testing Documentation Migration Status

> 当前目标分支：`codex/upstream-langfuse-sync`
> 上游基线：`upstream/main@c2caa9079b9eb48129f550c43a5485231d404d3b`
> 旧证据分支：`codex/c0-4-intentional-red@d6553a96f6987c5f58fdafddb99fc28e19c72eb0`
> 状态日期：`2026-09-07`

全体 `docs/` 的来源边界见 [`../MIGRATION_STATUS.md`](../MIGRATION_STATUS.md)。

## 1. 这次迁移做了什么

`docs/` 中的人工编写文档与图片已经迁入最新 upstream 基线所在的工作分支。
MIG-1 保存了知识、历史证据和后续计划。MIG-2 随后迁入 Langfuse adapter 与单元测试，
在 `c7122124` 上取得 58 cases 通过证据；其余旧 pytest/GitHub Actions 尚未迁移。

以下四类状态必须分开理解：

| 维度 | 当前状态 | 含义 |
|---|---|---|
| 文档文件 | `MIGRATED` | 文档已进入目标分支的 Git 变更范围 |
| 历史 C0 报告 | `VERIFIED_ON_SOURCE_REVISION` | 报告中的运行结果仍对其记录的旧 revision 有效 |
| Langfuse adapter/tests | `LANDED` / 本地 `VERIFIED` | 真实 adapter + fake SDK；58 cases 通过，运行时和 CI 仍 `NOT_WIRED` |
| 其余旧测试/CI 在目标分支 | `NOT_YET_MIGRATED` / `NOT_WIRED` | 不能用旧报告证明新 upstream 分支已经通过相同测试 |
| 架构与计划说明 | `REVIEW_NEEDED` | 已保留，但必须随 MIG-2/MIG-3 的真实代码和测试重新核对 |

## 2. 当前代码与证据边界

### 目标分支当前真实存在

- 最新 `RTGS2017/NagaAgent` 产品代码。
- upstream 原有的三个根级文档：`build-windows.md`、
  `naga-network-requirements.md`、`travel-exploration-system.md`。
- 本次迁移进入 Git 变更范围的测试架构、计划、报告、展示材料和图片。
- `apiserver/langfuse_integration.py` 与 `tests/unit/test_langfuse_integration.py`；
  source 的三个 helper 契约保留，并补入 context/cleanup 等回归测试。

### 目标分支当前尚未存在或尚未验证

- Langfuse 的运行时调用点与 SDK 依赖：旧保留 revision 也没有这些接线；MIG-2 未恢复，环境变量本身不能启用 trace。
- 旧分支的 pytest 分层资产、Golden Cases、Quality Gate 与 PR workflows；MIG-3 处理。
- 目标分支完整 pytest 回归与 CI 成功结果；MIG-4 确认。MIG-2 的局部 unit 结果不替代它们。
- 真实 Langfuse、LLM、Remote Memory、MCP、staging 或部署验证。

## 3. 阅读规则

1. `reports/closed-loop-*` 是历史执行证据。保留原 revision、run 和 Artifact 含义，
   不把它们改写为当前 upstream 结果。
2. `architecture/` 描述的是待迁移能力模型。模块只有在新分支找到对应实现并执行代表测试后，
   才能重新标记为目标分支上的 `LANDED/VERIFIED`。
3. `plans/nagaagent-final-testing-plan.md` 暂不继续 P3-0；先完成 upstream migration 的
   MIG-1～MIG-4。
4. GitHub Gate 状态按目标分支实际 workflow 判断。当前旧 Smoke/Stream Check 不能自动继承。
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
| 旧 Closed Loop 结果 | 历史报告中记录的 source revision、GitHub run 和 Artifact |
| 目标分支实现 | 当前 `codex/upstream-langfuse-sync` 代码树 |
| 目标分支测试/CI 状态 | MIG-2 局部 unit 证据；后续 MIG-3/MIG-4 的实际代码、命令和运行结果 |

## 6. 下一步

MIG-2 已按原定边界完成 adapter/tests 迁移与 upstream 调用点核对。
下一步 MIG-3 迁移兼容的测试基础设施和 CI 资产。若要启用真实 Langfuse，仍需明确恢复
chat/LLM/tool/lifecycle 接线、SDK 版本、数据策略和集成验收；这不由 MIG-3 自动开启。
