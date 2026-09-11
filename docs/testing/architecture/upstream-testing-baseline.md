# Upstream 迁移后的测试基线

> 核对日期：2026-09-10～11 · 已验收代码 revision：`357a8a6f553882fd68ac9c951b0ae92422ccae1c`\
> 这是当前分支的测试事实入口。旧 C0 GitHub 结果仍只属于其原 revision。

## 1. 现在具备什么

新 upstream 产品代码与旧测试基座已能共同运行。MIG-5 完整本地回归为 189 passed、2 skipped、2 xfailed；
另有 12 个 subtests passed。Langfuse runtime 已在原 LAN 实例完成合成上传/读回，详见
[MIG-5 journal](../reports/upstream-migration-mig-5-execution-journal.md)。这不代表所有业务缺口已补齐。
逐次证据、完整命令和环境在 [MIG-4 报告](../reports/upstream-migration-mig-4-execution-journal.md)，
当前进度见 [CURRENT_PROGRESS](../CURRENT_PROGRESS.md)。

P3-0 于 2026-09-10 在上述候选上重新执行：完整 189 passed / 2 skipped / 2 xfailed + 12 subtests，
Smoke 3 passed，Stream 2 passed / 6 deselected。当前应用、测试和 CI 文件未改动。
9 月 11 日同一 revision 已发布到 `tsukiyomu/NagaAgent-main`：Smoke / Stream GitHub CI 均通过，
JUnit ZIP 已下载验 hash 并解析。Owner 要求的 PR #2 关闭已完成，未合并且保留证据分支，P3-0 为 `DONE`。
[P3-0 journal](../reports/p3-0-execution-journal.md) 与 [机器证据](../reports/p3-0-baseline-evidence.json) 是本次执行入口。

测试中的“真实”按具体部件理解：**真实 route** 是执行仓库的 FastAPI 路由代码；
**真实 Loop** 是执行仓库的 `run_agentic_loop` 轮次控制、工具分派和停止逻辑。
它们都不自动表示模型、外部工具、记忆服务或数据库也是真实联通的。

## 2. 测试如何对应产品流程

| 流程位置 / 所有者 | 测试资产与已验证内容 | 受控依赖与明确不证明的内容 | CI 位置 |
|---|---|---|---|
| HTTP 入口 / API | [Smoke](../../../tests/smoke/test_api_smoke.py)：health、chat JSON、stream terminal，3 passed | 模型/Loop/prompt/副作用替换；不证明完整下游健康 | Smoke workflow 选这 3 条；9 月 11 日远端 3 passed，JUnit 已解析 |
| SSE 输出与收尾 / chat route | [Resilience](../../../tests/integration/chat_stream/test_resilience.py)：正常与异常终止、active cleanup、save spy、notify/compression fallback，7 passed + 1 xfail | fake Loop 或真实 Loop + fake LLM；保存调用不等于持久化回读 | Stream workflow 只选正常/中途异常 2 条；9 月 11 日远端 2 passed，JUnit 已解析 |
| 多轮编排 / Agentic Loop | [Loop unit](../../../tests/unit/agentic_tool_loop/)：停止/summary、dispatch、消息回注、压缩事件、归因，19 passed + 1 xfail | LLM、具体工具、queue/compression 按用例替换；不证明真实 MCP、Memory | 当前两个 workflow 都不选这一组 |
| 任务级受控回归 / Golden runner | [五个 YAML 场景](../../../tests/golden_cases/cases/)与 runner/schema：任务、工具结果回注和规则检查 | 固定模型输出、工具结果与上下文；不证明生产 prompt、真实回答质量或全链路 E2E | 本地执行；未接入当前两个 PR job |
| 观测适配与 runtime / Langfuse | [当前说明](langfuse-observability.md)：58 adapter cases、9 runtime cases、1 wiring case；LAN opt-in 另行通过 | adapter fake SDK / runtime 真 SDK 内存导出 / LAN 真服务分开验证；provider 和具体工具仍固定，Memory 禁用 | 离线本地 + LAN `OPT_IN`；CI `NOT_WIRED` |
| 上游现有单测 / 各模块 | config/tools、Live2D assets、updates/TTS 的原测试，56 passed + 12 subtests passed | 保留各文件原有单测边界，不扩张成 UI/音频/更新服务 E2E | 本地执行；未新增其 CI selection |
| 结果归因与展示 / testing support | [Quality helper](../../../tests/support/quality_gate.py)、JUnit、Allure 原始结果 | 32 条子集的诊断摘要；无有效历史性能比较、无 Allure HTML 验收 | pytest exit code 才决定现有 job；Quality/Allure 未接入两个 workflow |

## 3. 共用基座与依赖边界

[`tests/conftest.py`](../../../tests/conftest.py) 在导入 API 前安装
[`offline_bootstrap.py`](../../../tests/support/offline_bootstrap.py)。原因是上游配置会在导入期优先读取
项目 `config.json`，只在请求 fixture 中 patch 已经太晚。

离线 profile 使用临时 home / APPDATA、阻止真实项目配置被优先选择、禁止 dotenv 注入凭据，
并对已检查的 Python TCP 连接入口建立拒绝和记录机制。即使应用吞掉网络错误，teardown / session
仍让 pytest 失败。标准库 socketpair 的 Windows asyncio self-pipe 被单独放行。
这是测试依赖控制，不是进程级安全沙箱，也不保护未检查的任意 subprocess / native networking。
MIG-5 增加独立的 LAN opt-in：仅显式验收期间放行保存的私网 IP:port，其余 TCP 拒绝和吞异常检测保留；
没有用 real-LLM 开关绕过离线基座。

产品 Remote Memory 没有删除；SSE fixture 中的 client 固定为 None，真实认证、query、fallback
继续标为 `DELAYED`。真实 LLM 只有一个 opt-in case，本次 skipped。
`NAGA_ENABLE_REAL_LLM_TESTS=1` 会关闭全局离线 bootstrap，须另行规划真实依赖执行，不能用于普通 PR 回归。

## 4. CI、报告、基线是三件不同的事

- **CI 配置与运行**：两个 workflow 已迁入，精确 selection、JUnit 与 always-upload 契约已核对。
  `357a8a6f` 的两条 `workflow_dispatch` run 均 success，test/upload 与下载解析已验证；链接见 [CI 当前结论](ci-pr-gate.md#0-当前-upstream-分支结论)。Required 未重新验证，规则未改；本次未重做远端故障注入。
- **报告**：MIG-4 JUnit 与 Allure 都有 182 条记录；MIG-5 JUnit 有 193 条、其中 4 skipped（两个 opt-in + 两个 xfail）。MIG-5 没有重验 Allure。
  Quality Gate 只聚合 32 条 API/Loop 子集，不能用其 total 代表整个测试套件。
- **代码基线**：MIG-4 `981821be` 保留；当前 runtime 基线为 MIG-5 `7c88065c`，都不等于性能标准。
  P3-0 已验收代码为 `357a8a6f`（收口只改文档）；这是带已知风险的测试起点，不是生产发布或合并批准。
  旧 `tests/baseline/quality_gate/*.json` 是来源版本数据；默认 helper 仍会读取它们。
  MIG-4 显式使用独立 advisory 目录，`baseline_bootstrap=true`、delta=null，仅验证输出链路，没有晋升数值基线。

当前复现命令须禁用插件自动加载，显式启用 pytest-asyncio；报告模式再启用 Allure。
详见 [CI 本地复现](ci-pr-gate.md#5-本地复现) 和 [MIG-4 命令](../reports/upstream-migration-mig-4-execution-journal.md#9-复现与证据索引)。

## 5. 最小闭环和后续扩展

完整闭环是相对于声明的风险范围而言：定义风险 → 确定性断言 → 执行 → 保存证据 → 归因 → 恢复验证 → 人类决定。
旧 C0 已在 source revision 跑过这条链；新分支本次补齐同 revision 的本地回归、真实 CI、JUnit 与 Owner 决定。
旧红灯证据仍属于原 revision；新分支绿色不自动证明新版所有负向路径、Required 或完整 E2E。

复杂业务先增加状态准备、fixture、数据清理、并发和断言难度；涉及真实数据库、服务、secret 或 staging 时，
还会增加 CI/CD 的环境与执行策略要求。这些测试基座可以复用，但不是所有后续业务都不再需要写数据脚本。

仓库 Build & Release 只说明存在打包/发布配置；本次没有执行。Personal Web 的 CD 是用户提供的独立经验，
不作为本项目部署证据。真实平台的部署、health、migration 和 rollback 需要独立验收，不能用本地 pytest 替代。

## 6. 未完成范围与阅读规则

user-stop 与跨轮 duplicate tool id 仍为两个 xfail；真实模型/Memory/MCP、完整 E2E 和性能标准仍待后续工作。
Langfuse runtime 已可用；其当前真实 LLM 路径测试结束于 `round_end` / 迭代耗尽，并非旧 fake-loop 的 `[DONE]`。
该协议差异仍应在后续业务契约梳理中处理，MIG-5 没有修改产品 SSE；P3-0 也未修改协议。

9 月 8 日复核发现的下列风险仍在同一源码上，P3-0 只登记、不修复。原始合成探针见
[边界证据](../../../tests/artifacts/upstream_migration/mig-5/review-boundary-probes-2026-09-08.json)，本次未重跑该探针。

| 风险 | 直接证据与含义 | 后续边界 |
|---|---|---|
| 多轮 trace 正文漏记 | `langfuse_runtime.py::trace_chat_stream` 在 `content_clean` 时重置整段累计；三轮送达客户端，但根输出只保留后两轮 | 待独立修复与正式回归；不据此声称客户端丢字 |
| 提前关闭依赖后续清理 | `body_iterator.aclose()` 返回时 root 已结束、provider close=0；事件循环继续后 close=1、generation 结束 | 不是永不清理；确定性内层关闭尚不足，与 P3-3 的产品 user-stop 契约仍须分别验收 |
| JSON 字符串脱敏局限 | 结构化 password 被替换，JSON 字符串中的合成 password 未被替换 | 开启正文不是任意秘密/PII 清除保证；未发现或导出真实秘密 |

配置事实：9 月 8 日已确认重启后真实聊天的根/子 observation 均有正文；9 月 10 日根 `.env`
保存的 `LANGFUSE_CAPTURE_CONTENT=true`。这是本地显式选择；产品代码默认仍为 false，本轮未上传新 trace 或重验活动进程。

本页、CI 页当前状态和 Langfuse 当前边界已同步。各 Part 的断言/owner 可以继续查阅，
但旧运行时长、PR Required、实施优先级及产品整体架构仍须按原 revision 阅读；
**没有宣布全部历史 architecture 文档逐行核验完成**。本次同步当前入口、profile、命令、来源和风险；
Part 2/4/8/11 的逐项历史映射仍为 `PARTIAL`。完整 workflow 时序与 message/state ownership 属于 P3-1，
真实服务、取消、幂等与部署分别遵循后续工作单元，不能因为 P3-0 更新文档而视为已覆盖。
