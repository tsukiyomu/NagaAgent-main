# Upstream 迁移后的测试基线

> 核对日期：2026-09-07 · 代码 revision：`981821be7b971c4123c8f41d7a77f176970cd872`\
> 这是当前分支的测试事实入口。旧 C0 GitHub 结果仍只属于其原 revision。

## 1. 现在具备什么

新 upstream 产品代码与旧测试基座已能共同运行。完整本地回归为 179 passed、1 skipped、2 xfailed；
另有 12 个 subtests passed。迁移没有补齐所有业务缺口，也没有自动接通 Langfuse。
逐次证据、完整命令和环境在 [MIG-4 报告](../reports/upstream-migration-mig-4-execution-journal.md)，
当前进度见 [CURRENT_PROGRESS](../CURRENT_PROGRESS.md)。

测试中的“真实”按具体部件理解：**真实 route** 是执行仓库的 FastAPI 路由代码；
**真实 Loop** 是执行仓库的 `run_agentic_loop` 轮次控制、工具分派和停止逻辑。
它们都不自动表示模型、外部工具、记忆服务或数据库也是真实联通的。

## 2. 测试如何对应产品流程

| 流程位置 / 所有者 | 测试资产与已验证内容 | 受控依赖与明确不证明的内容 | CI 位置 |
|---|---|---|---|
| HTTP 入口 / API | [Smoke](../../../tests/smoke/test_api_smoke.py)：health、chat JSON、stream terminal，3 passed | 模型/Loop/prompt/副作用替换；不证明完整下游健康 | Smoke workflow 选这 3 条；本地三次通过，远端未验证 |
| SSE 输出与收尾 / chat route | [Resilience](../../../tests/integration/chat_stream/test_resilience.py)：正常与异常终止、active cleanup、save spy、notify/compression fallback，7 passed + 1 xfail | fake Loop 或真实 Loop + fake LLM；保存调用不等于持久化回读 | Stream workflow 只选正常/中途异常 2 条；本地三次通过 |
| 多轮编排 / Agentic Loop | [Loop unit](../../../tests/unit/agentic_tool_loop/)：停止/summary、dispatch、消息回注、压缩事件、归因，19 passed + 1 xfail | LLM、具体工具、queue/compression 按用例替换；不证明真实 MCP、Memory | 当前两个 workflow 都不选这一组 |
| 任务级受控回归 / Golden runner | [五个 YAML 场景](../../../tests/golden_cases/cases/)与 runner/schema：任务、工具结果回注和规则检查 | 固定模型输出、工具结果与上下文；不证明生产 prompt、真实回答质量或全链路 E2E | 本地执行；未接入当前两个 PR job |
| 观测适配边界 / Langfuse adapter | [58 cases](../../../tests/unit/test_langfuse_integration.py)：payload、异常隔离、cleanup | fake SDK；运行时调用点和 SDK 依赖未接回，不能产生 trace | 本地执行；`NOT_WIRED` to CI |
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

产品 Remote Memory 没有删除；SSE fixture 中的 client 固定为 None，真实认证、query、fallback
继续标为 `DELAYED`。真实 LLM 只有一个 opt-in case，本次 skipped。
`NAGA_ENABLE_REAL_LLM_TESTS=1` 会关闭全局离线 bootstrap，须另行规划真实依赖执行，不能用于普通 PR 回归。

## 4. CI、报告、基线是三件不同的事

- **CI 配置**：两个 workflow 已迁入，精确 selection、JUnit 与 always-upload 契约已核对。
  新 revision 尚未 push / 运行 GitHub Actions；Required 状态未知，未修改规则。
- **报告**：完整 JUnit 与 Allure 都有 182 条记录；两个 xfail 在这两者中记为 skipped。
  Quality Gate 只聚合 32 条 API/Loop 子集，不能用其 total 代表整个测试套件。
- **代码基线**：`981821be` 可用于后续开发和回归比较；不等于性能标准。
  旧 `tests/baseline/quality_gate/*.json` 是来源版本数据；默认 helper 仍会读取它们。
  MIG-4 显式使用独立 advisory 目录，`baseline_bootstrap=true`、delta=null，仅验证输出链路，没有晋升数值基线。

当前复现命令须禁用插件自动加载，显式启用 pytest-asyncio；报告模式再启用 Allure。
详见 [CI 本地复现](ci-pr-gate.md#5-本地复现) 和 [MIG-4 命令](../reports/upstream-migration-mig-4-execution-journal.md#9-复现与证据索引)。

## 5. 最小闭环和后续扩展

完整闭环是相对于声明的风险范围而言：定义风险 → 确定性断言 → 执行 → 保存证据 → 归因 → 恢复验证 → 人类决定。
旧 C0 已在 source revision 跑过这条链；新分支本次完成了本地测试与证据部分，远端 CI 仍需重新验证。

复杂业务先增加状态准备、fixture、数据清理、并发和断言难度；涉及真实数据库、服务、secret 或 staging 时，
还会增加 CI/CD 的环境与执行策略要求。这些测试基座可以复用，但不是所有后续业务都不再需要写数据脚本。

仓库 Build & Release 只说明存在打包/发布配置；本次没有执行。Personal Web 的 CD 是用户提供的独立经验，
不作为本项目部署证据。真实平台的部署、health、migration 和 rollback 需要独立验收，不能用本地 pytest 替代。

## 6. 未完成范围与阅读规则

user-stop 与跨轮 duplicate tool id 仍为两个 xfail；真实外部服务、完整 E2E、性能标准和 Langfuse runtime
仍待后续工作。P3-0 未启动，迁移前置条件已满足。

本页、CI 页当前状态和 Langfuse 当前边界已同步。各 Part 的断言/owner 可以继续查阅，
但旧运行时长、PR Required、实施优先级及产品整体架构仍须按原 revision 阅读；
**没有宣布全部历史 architecture 文档逐行核验完成**。更细的架构重整留在 P3-0。
