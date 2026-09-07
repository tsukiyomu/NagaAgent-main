# NagaAgent Final Testing Plan

## 1. 文档定位

- 文档状态：`READY_FOR_REENTRY — P3-0 未启动`
- 计划类型：`Final / Consolidated Plan（NagaAgent Basic Agent Workflow Understanding + Testing）`
- 制定日期：`2026-09-03`
- 修订日期：`2026-09-07（MIG-3/MIG-4 完成本地迁移验收；未启动 P3）`
- 当前迁移分支：`codex/upstream-langfuse-sync`
- 当前 upstream revision：`c2caa9079b9eb48129f550c43a5485231d404d3b`
- 当前本地测试基线：`981821be7b971c4123c8f41d7a77f176970cd872`，见 [MIG-4 报告](../reports/upstream-migration-mig-4-execution-journal.md)
- 本计划原证据 revision：`d6553a96f6987c5f58fdafddb99fc28e19c72eb0`
- 迁移前置条件：[`upstream-migration-plan.md`](upstream-migration-plan.md) MIG-1～MIG-4 已完成，已形成新本地测试基线
- 原始需求来源：`D:\platform\入り禁止\Artificial intelligence\NagaAgent\NagaAgentAbout.docx` 中的 `plan3 / final / Final after final`
- 当前状态真相源：[`../CURRENT_PROGRESS.md`](../CURRENT_PROGRESS.md)
- 价值与决策分析：[`../reports/final-testing-plan-analyze.md`](../reports/final-testing-plan-analyze.md)
- 已完成前置计划：[`closed-loop-v1-implementation-plan.md`](closed-loop-v1-implementation-plan.md)
- 测试架构入口：[`../architecture/overview.md`](../architecture/overview.md)
- 当前迁移边界：[`../MIGRATION_STATUS.md`](../MIGRATION_STATUS.md)

> 新分支已完成本地回归，P3-0 可以重新进入，但本次 MIG-3/MIG-4 不执行 P3 单元。
> 旧 GitHub Gate 状态不自动继承；新 revision 的远端 CI、Langfuse runtime 和真实外部服务仍未验证。

这里的 `Final` 表示：在暂不另建新计划的阶段，本文件是 NagaAgent 测试工作的唯一后续路线图，
后续新增范围优先作为本计划的工作单元或延期项维护。它不表示 P3-0～P3-9 已全部完成，也不表示
未来出现重大产品边界变化时永远不能建立新计划。

本文不是把 DOCX 中所有 Plan3 设想原样搬入仓库，而是结合当前已经完成的 Closed Loop V1、
两个 executable `xfail`、基于 NagaAgent 代码理解基础 Agent workflow 的学习目标和求职展示价值，
筛选下一阶段最值得执行的工作。

本文不重新打开 C0-1～C0-6。Closed Loop V1 已证明一条有限 SSE 契约可以完成：

```text
deterministic test
  -> CI Check
  -> pytest exit code
  -> success/failure JUnit Artifact
  -> failure classification
  -> restored verification
  -> human Gate decision
```

下一阶段先基于真实代码理解一个基础 Agent workflow 如何接收请求、组织上下文、调用模型、执行工具、
回注结果、继续或停止，再把 Closed Loop 方法应用到这些 Agent 特有风险；不扩建无关工具平台。

## 2. Plan3 原始价值与当前取舍

### 2.1 保留为当前主线

1. 基于 Route、Loop、LLM、Tool、Context、Queue 和 Finalize 画出可对应源码的基础 Agent workflow。
2. Agent Loop 状态转移、硬断言、收敛规则与 `failure_stage`。
3. Golden Cases 的版本化场景、规则型 oracle 和 baseline regression。
4. Quality Gate 的 JSON / Markdown / terminal summary，而不是另建 dashboard。
5. `/chat/stream` Route、真实 Agent Loop 和 scripted LLM 之间的跨层韧性验证。
6. 最小 Replay Bundle，使失败 run 能回放到本地。
7. 少量真实 staging E2E，用来补 deterministic profile 无法证明的真实依赖问题。
8. 轻量并发与故障注入，但放在核心 workflow 和 replay 完成之后。

### 2.2 根据当前状况调整

- DOCX 原建议先完成 5 条 Tool Loop 用例；当前仓库已超过该起点，因此不再把“新增同类 loop 单测”列为主线。
- DOCX 建议 Golden Cases 先做到约 10 条；当前已有 5 条可执行 stub cases。当前优先让已有 case 进入可观察的 CI 与 baseline，再根据真实 badcase 扩展，而不是先凑数量。
- Jaeger 与 NagaAgent 本计划没有实现或学习依赖。本计划的学习目标是利用现有代码和测试理解基础 Agent workflow；现有 telemetry/Langfuse 只作为仓库中的相邻边界，不要求接入、替换或扩建。
- Remote Memory 是产品能力，但认证和真实环境尚未确认；继续标为 `DELAYED`，不阻塞本地 deterministic loop，也不把隔离后的绿色结果写成真实 Remote Memory 验证。
- Stream Contract 已完成证据闭环，但 Owner 选择暂缓 Required 晋升；本计划不自动改变 Branch Protection 或 Gate 等级。

### 2.3 当前不优先

- 继续重构同一层测试 helper，而没有新增可证明的业务或 workflow 契约。
- 大量语义重复的 Tool Loop 单测。
- 新建与理解 NagaAgent workflow 无关的可观测平台或 dashboard。
- 直接把真实 LLM、MCP、Remote Memory、DB 全部塞进每个 PR 的硬门禁。
- 只扩写文档，但不能把流程说明映射到真实代码、代表测试、执行结果或 Gate Decision。
- 在部署目标尚未确定时，为了形式完整提前搭建复杂 CD。

## 3. 当前证据基线

### 3.1 2026-09-03 本地执行

| 范围 | 命令 | 结果 | 当前含义 |
|---|---|---|---|
| 完整 pytest | `uv run python -m pytest -q` | `90 passed, 1 skipped, 2 xfailed, 8 subtests passed` | 当前 deterministic 基线绿色；仍有两个明确契约缺口 |
| Golden Cases | `uv run python -m pytest tests/golden_cases -q` | `5 passed` | 5 条 stub workflow case 可执行 |
| Agent Tool Loop | `uv run python -m pytest tests/unit/agentic_tool_loop -q` | `19 passed, 1 xfailed` | 收敛、dispatch、回注、compression、归因已有较完整本地覆盖 |
| Quality Gate Unit | `uv run python -m pytest tests/unit/test_quality_gate_summary.py -q` | `5 passed` | 报告和 baseline 判定逻辑自身通过 |

### 3.2 当前 CI/Gate

| Suite/Profile | 实现状态 | Gate 状态 | 当前证据 | 证明边界 |
|---|---|---|---|---|
| API Smoke | `LANDED` | `PR_BLOCKING`（已有历史 Required 证据） | `PR Smoke Gate` + JUnit Artifact | 最小 API 可用；不证明完整 Agent Workflow |
| Stream Contract | `LANDED` | `NON_BLOCKING` | `PR Stream Contract Gate` + green/red/restored-green JUnit | real route + fake loop 的 SSE lifecycle；不证明真实 Loop/LLM |
| Real Route + Real Loop + Scripted LLM | `PARTIAL` | `NOT_WIRED` | 本地 integration case | Route/Loop 协作；不证明真实模型和外部工具 |
| Agent Tool Loop | `LANDED` | `NOT_WIRED` | 本地 `19 passed, 1 xfailed` | 真实 Loop 状态转移；邻接依赖受控 |
| Golden Cases | `PARTIAL` | `NOT_WIRED` | 5 条 stub cases 本地通过 | 规则型 workflow regression；无真实模型质量结论 |
| Quality Gate | `LANDED/PARTIAL` | `NOT_WIRED` | 生成逻辑与 unit tests 存在，默认需 `--quality-gate` | 目前是 diagnostic，不影响 GitHub job exit code |
| Real LLM Smoke | `PARTIAL` | `OPT_IN` | 完整执行中因凭据/config skip | 未形成 staging 证据 |
| Remote Memory | 产品能力 `LANDED` | 真实测试 `DELAYED` | 目标 SSE fixture 中隔离 | 当前不能宣称真实认证/query/fallback 正常 |

### 3.3 当前已知 executable gaps

1. `test_chat_stream_user_stop_contract_gap`：运行时没有显式 user-stop contract。
2. `test_duplicate_tool_call_id_is_deduplicated_across_rounds`：跨轮重复 `tool_call_id` 尚未去重。

### 3.4 当前未发现实现证据

- 测试或 CI 中没有标准 Replay Bundle。
- 测试、代码入口和状态变化之间还没有统一的 workflow ownership / evidence mapping。
- 没有 20/50 session 并发回归。
- Golden Cases 和 `--quality-gate` 没有出现在 GitHub workflow。

## 4. 目标形态

```text
Basic Agent Workflow Understanding and Regression
  ├─ Understanding Layer
  │    ├─ source-code ownership map
  │    ├─ request-to-finalize sequence
  │    └─ round/message/state transitions
  ├─ Deterministic Contract Layer
  │    ├─ API/SSE lifecycle
  │    ├─ Tool Loop state transitions
  │    ├─ Context boundary
  │    └─ Golden Cases rule-based oracle
  ├─ Evidence Layer
  │    ├─ JUnit
  │    ├─ Quality Gate JSON/Markdown
  │    ├─ failure_stage
  │    └─ Replay Bundle
  ├─ Authenticity Layer
  │    └─ 1～3 条 staging E2E
  └─ Human Gate Decision
       └─ non-blocking -> reviewed -> required/release-before
```

核心边界：

- pytest assertion 和进程退出码继续作为 deterministic CI 的 blocking truth。
- Workflow 图、执行日志和代码阅读记录用于解释“系统怎样工作”，不替代 pytest 对正确性的判断。
- Quality Gate 在没有稳定 baseline 和 Owner 评审前先作为 `NON_BLOCKING` signal。
- 真实 LLM/外部服务 profile 默认是 `OPT_IN`、`STAGING`、`NIGHTLY` 或 release-before，不直接成为每个 PR 的 required check。

## 5. 推荐执行顺序

| 顺序 | 工作单元 | 当前状态 | 主要价值 | 建议 Gate |
|---:|---|---|---|---|
| 0 | P3-0 收口当前基线 | `NEXT` | 避免在证据分支上继续堆叠新能力 | 保持现状 |
| 1 | P3-1 Basic Agent Workflow Understanding | `PLANNED` | 基于现有代码理解 Route、Loop、Tool 与 Finalize | 学习/验证记录，不设 Gate |
| 2 | P3-2 Duplicate Tool Call ID Contract | `XFAIL_GAP` | 关闭幂等与重复执行风险 | 本地 deterministic，评审后再入 CI |
| 3 | P3-3 User Stop / Cancel Finalization | `XFAIL_GAP` | 关闭真实用户流式取消缺口 | integration non-blocking 起步 |
| 4 | P3-4 Agent Workflow Non-blocking CI | `PLANNED` | 让 Tool Loop + Golden + Quality Artifact 进入真实 PR | `NON_BLOCKING` |
| 5 | P3-5 Replay Bundle | `PLANNED` | 让 CI/线上 badcase 可复盘和回放 | Artifact/diagnostic |
| 6 | P3-6 Context Boundary Completion | `PARTIAL` | 补 assembly、budget/timeout 边界 | integration non-blocking |
| 7 | P3-7 Staging E2E | `PLANNED/DELAYED` | 验证真实模型、持久化和必要外部依赖 | `STAGING` / release-before |
| 8 | P3-8 Concurrency & Fault Injection | `BACKLOG` | 从流程测试升级到可靠性与隔离性测试 | scheduled/manual |
| 9 | P3-9 CD Quality Handoff | `BACKLOG` | 将测试证据接入部署、健康检查和回滚 | release gate |

当前推荐只承诺 P3-0～P3-4。P3-5 之后根据 workflow 学习结果、部署平台和真实 badcase 再逐项启动。

## 6. Work Units

### P3-0：收口当前基线

- 状态：`[ ] [NEXT]`
- 目的：把 Closed Loop V1 的证据分支、主分支和文档状态整理成稳定起点，避免后续 workflow 学习和测试工作与故障注入历史混杂。
- 主要动作：
  1. 确认 PR #2 最终处理方式。
  2. 用干净变更把两行 Remote Memory fixture 隔离落入目标分支，或记录明确的不合并决定。
  3. 在目标分支重新执行完整 pytest、Smoke 和 Stream Contract。
  4. 更新 `CURRENT_PROGRESS.md` 的当前计划和 Architecture `PARTIAL` 项。
- 完成证据：目标分支 revision、完整 pytest 结果、两条 CI run、JUnit Artifact、Owner 决定。
- 不包含：Required Check 晋升、真实 Remote Memory 测试、任何新可观测平台接入。
- 面试价值：能够解释为什么先冻结可信 baseline，再开始新的 workflow 理解与测试工作。

### P3-1：建立 NagaAgent Basic Agent Workflow 理解与验证记录

- 状态：`[ ] [PLANNED]`
- 目的：把 NagaAgent 当作真实案例，理解一个基础 tool-using Agent workflow 的入口、状态变化、循环条件、工具边界和结束语义。
- 当前需要理解的主链路：

  ```text
  /chat/stream request
    -> create/restore session
    -> build messages + context supplement + tool schemas
    -> run_agentic_loop(...)
         -> LLM round
         -> no actionable tool -> final answer / stop
         -> tool call -> normalize -> dispatch -> result
         -> assistant/tool messages injected into next round
         -> queue/compression may update next-round context
         -> repeated failure or max_rounds -> tools=None summary
    -> route consumes SSE events
    -> save / notify / active-state cleanup / terminal outcome
  ```

- 主要动作：
  1. 从 `apiserver/routes/chat.py::chat_stream` 追到 `apiserver/agentic_tool_loop.py::run_agentic_loop` 和 `execute_tool_calls`。
  2. 标出每个阶段的输入、输出、message 变化、side effect 和 owner。
  3. 分别走读三条代表路径：无工具直接结束、一轮工具调用后继续、连续失败或 max rounds 后 summary。
  4. 把每个关键状态映射到已有代表测试和硬断言；缺口继续标为 `XFAIL_GAP` 或 `PLANNED`。
  5. 执行最窄的代表测试，并形成一份可以用自己的话复述的 workflow 学习记录或时序图。
- 完成证据：源码/符号映射、三条 workflow 时序、消息与状态变化表、代表测试命令和结果、proof boundary，以及用户 teach-back。
- 不包含：Jaeger、OpenTelemetry 或 Langfuse 接入；新增 exporter/dashboard；真实 LLM/Remote Memory 验证；把文档理解误写成运行时覆盖。
- 学习价值：能解释基础 Agent 为什么需要 loop、tool result 为什么要回注、何时继续或停止、Route 与 Loop 分别负责什么。
- 面试价值：能从真实代码解释 Agent workflow 和测试切面，而不是只展示测试框架或工具名称。

### P3-2：关闭 Duplicate Tool Call ID executable gap

- 状态：`[ ] [XFAIL_GAP]`
- 目的：防止跨轮重复 `tool_call_id` 导致工具重复执行、结果重复回注或副作用放大。
- 主要动作：
  1. 明确重复 ID 的产品契约：dedupe、fail gracefully 或按 provider/session 范围处理。
  2. 实现最小运行时状态，不让测试侧自行吞掉重复 ID。
  3. 让现有 `xfail` 先暴露 XPASS/行为变化，再移除 `xfail`。
  4. 增加执行次数、回注次数、final status 和 failure stage 断言。
- 完成标准：
  - 重复工具调用不产生不可控重复副作用。
  - `execute_tool_calls_called_expected_times` 满足契约。
  - `tool_results_injected_once == true`。
  - 无 unhandled exception，最终状态可解释。
- 完成证据：修复前 `xfail`、修复 diff、修复后 green、必要时 intentional regression red。
- 不包含：所有外部工具自身的幂等实现。
- 面试价值：状态机、幂等性和副作用控制，比新增普通 happy-path 用例更有工程难度。

### P3-3：关闭 User Stop / Cancel Finalization executable gap

- 状态：`[ ] [XFAIL_GAP]`
- 目的：定义用户停止、客户端断开和内部异常的不同终止语义，保证 Route 最终清理一致。
- 主要动作：
  1. 明确 cancel signal 从客户端到 Route/Loop 的传播方式。
  2. 定义 `cancelled`、`degraded`、`failed` 和正常 `[DONE]` 的事件契约。
  3. 断言 partial content 后只有一个 terminal outcome。
  4. 断言 persistence、notify、telemetry 和 active flag 的预期行为。
  5. 移除现有 user-stop `xfail` 并执行重复稳定性检查。
- 完成标准：取消后不继续工具调用；terminal 不重复；active flag 为 false；保存策略符合产品决定。
- 完成证据：协议决定、测试 nodeid、green/red/restored evidence、JUnit。
- 不包含：所有浏览器/移动端的网络断连行为；后者应由独立 E2E profile 验证。
- 面试价值：展示对流式系统“HTTP 已 200 但业务生命周期未结束”的理解。

### P3-4：建立 Agent Workflow Non-blocking CI 与 Quality Artifact

- 状态：`[ ] [PLANNED]`
- 目的：复用现有 Tool Loop、5 条 Golden Cases 和 Quality Gate producer，先形成真实 PR signal，而不是先继续增加 case 数量。
- 推荐初始 selection：
  - `tests/unit/agentic_tool_loop`
  - `tests/golden_cases`
  - `--quality-gate --quality-gate-profile stub`
- 主要动作：
  1. 新建独立 `Agent Workflow Regression` workflow/job，避免与 Smoke/Stream 归因混杂。
  2. 生成 JUnit、`agent_quality_report.json` 和 `agent_quality_summary.md`。
  3. 使用 `if: always()` 上传失败证据，并用 `if-no-files-found: error` 暴露 evidence pipeline 缺陷。
  4. 首阶段 Quality Gate 仅作为 diagnostic/non-blocking signal；pytest assertion 仍决定测试 job 成败。
  5. 连续积累稳定 run 和 baseline delta，再由 Owner 决定是否晋升 Required。
- 完成标准：真实 PR 上可看到独立 Check；成功和失败 run 均有可下载 Artifact；report 能定位 case、final status、failure stage 和 baseline delta。
- 不包含：把真实 LLM 作为 PR blocking；自动修改 Branch Protection；LLM judge 硬门禁。
- 面试价值：从“本地框架存在”升级为“变更进入 PR 时自动形成质量反馈”。

### P3-5：建立最小 Replay Bundle

- 状态：`[ ] [PLANNED]`
- 目的：把一次 workflow failure 的必要输入与状态保存为可在本地重放的最小证据包。
- 建议内容：

  ```text
  manifest.json
  messages.normalized.json
  tools.schema.json
  tool_calls.json
  tool_results.normalized.json
  final.json
  execution-reference.json
  ```

- `final.json` 最小字段：`case_id/nodeid`、`final_status`、`failure_stage`、`rounds`、`tool_call_count`、`summary_triggered`、`unhandled_exception`。
- 安全要求：默认脱敏；不保存 token/secret；真实用户 prompt、工具返回和 Memory 内容必须经过允许和 scrub。
- 主要动作：
  1. 先支持 deterministic Golden Case failure。
  2. 再关联 CI run、revision、Artifact、case_id/nodeid 和必要的现有执行标识。
  3. 提供单一 replay command，并验证回放结果可重复。
- 完成标准：一个失败 case 能由 Artifact 下载后在本地复现相同 failure stage 或明确报告环境差异。
- 不包含：完整生产流量录制平台。
- 面试价值：把 workflow 理解、CI evidence 和 deterministic regression 连接成可复盘工程链路。

### P3-6：补齐 Context Boundary，而不是在 SSE 中重测全部 Context Engineering

- 状态：`[ ] [PARTIAL]`
- 目的：确认 Context 边界异常不会拖死 Stream，同时把排序、召回、budgeting 细节留给 Context 模块测试。
- 建议只补 2～3 条跨层契约：
  1. `build_context_supplement` 异常 -> error/fallback -> finalize。
  2. `compress_context` 异常 -> fallback -> terminal + active false。
  3. budget overflow/timeout -> 可解释 final status，不能无限等待。
- 不在本工作单元验证：Memory 排序最优、RAG 召回质量、每段 Prompt 精确文本、Tool Schema 排序。
- 完成证据：Route/Loop profile、断言、运行结果、failure_stage、proof boundary。
- 面试价值：体现“最低充分测试层”和架构 ownership，而不是把所有问题都堆到 E2E。

### P3-7：建立 1～3 条受控 Staging E2E

- 状态：`[ ] [PLANNED]`；Remote Memory 子项 `DELAYED`
- 目的：补充 deterministic profile 无法证明的真实组装、真实模型、真实持久化和必要外部依赖问题。
- 推荐路径：
  1. 普通单轮对话：真实 Route + Context + Loop + Test LLM + Persistence。
  2. 多轮对话：历史上下文继续回答并可回读。
  3. 一条 Tool 路径；Remote Memory 只在认证、数据和 cleanup 契约确认后加入。
- 执行频率：manual、nightly、staging 或 release-before；默认不作为每个 PR 的 Required Check。
- 安全要求：测试账号、预算上限、超时、数据命名空间、清理、secret 管理和失败重跑策略必须显式。
- 完成证据：部署 revision、环境、真实/受控组件表、run、执行日志、测试报告、落库回读和 cleanup。
- 不包含：生产流量验证；不能从一条 real LLM smoke 推断完整 E2E。
- 面试价值：能够诚实解释确定性测试和真实环境验证为什么互补。

### P3-8：轻量并发、隔离性与故障注入

- 状态：`[ ] [BACKLOG]`
- 前置条件：P3-1 workflow model、P3-5 Replay 和至少一条 staging path 已稳定。
- 建议范围：
  - 20/50 并发 session；messages、queue、session state、tool result 不串线。
  - MCP 慢响应、429、timeout。
  - logging/telemetry 等观察侧路不可用或 flush 失败。
  - Queue 突增。
  - 连续工具失败后仍能按规则收敛。
  - Tool whitelist/auth/agent permission 和异常 tool call 边界。
- 完成标准：有明确 SLO/阈值、测试环境、数据隔离、failure classification 和可复现报告。
- 不包含：没有基线的“大压测数字展示”。
- 面试价值：从功能闭环进一步升级到可靠性、隔离性和风险控制。

### P3-9：CD Quality Handoff

- 状态：`[ ] [BACKLOG]`
- 前置条件：已选择真实部署平台和环境模型。
- 目的：把已验证的 CI evidence 接入构建、部署、部署后 Smoke 和回滚，而不是把 GitHub Release packaging 直接描述成完整 CD。
- 最小链路：

  ```text
  versioned build
    -> immutable artifact/image
    -> environment approval
    -> deploy
    -> readiness/health
    -> post-deploy smoke/staging E2E
    -> promote or rollback
    -> deployment evidence
  ```

- 完成证据：部署 revision/版本、环境、health、smoke、rollback drill、日志与 Artifact。
- 面试价值：把测试平台与真实交付平台连接起来，同时能解释 CI、release packaging 和 CD 的证据差异。

## 7. 统一断言与报告字段

### 7.1 Deterministic hard assertions

- `rounds <= max_rounds + 1`
- `duplicate_tool_call_id == false` 或符合 Owner 确认的 graceful-failure contract
- `tool_results_injected_once == true`
- `execute_tool_calls_called_expected_times`
- `final_status in [success, degraded, summary, cancelled, failed]`，并与场景预期一致
- `unhandled_exception == false`，除非测试目标就是验证异常外泄
- `summary_round_triggered_when_expected == true`
- `terminal_event_count == 1`
- `active_cleaned == true`

### 7.2 Diagnostic metrics

- `ttfb_ms`：必须说明是真实网络 TTFB 还是进程内 first-chunk latency。
- `total_latency_ms`
- `tool_rounds` / `tool_call_count`
- `retry_count` / `workflow_timeout_count`
- `fallback_rate` / `summary_rate`
- `save_call_count`
- `baseline_delta`

Diagnostic 字段存在不等于已经影响 Gate。只有 CI workflow、退出码或显式 enforce 逻辑接线并经 Owner 评审后，才能宣称它是 blocking rule。

### 7.3 Failure stages

- `llm_output_parse`
- `tool_call_normalize`
- `tool_dispatch`
- `tool_result_injection`
- `context_assembly`
- `summary_round`
- `finalize`
- `persistence`
- `telemetry`
- `cancel`

P3-1 应复核这些 stage 是否能对应到真实代码分支和可观察的状态变化；不要为了字段完整而制造实际代码无法区分的 stage。

## 8. Gate 晋升规则

一个 suite 从 `NOT_WIRED` 或 `NON_BLOCKING` 晋升为 Required/Release Gate 前，至少满足：

1. 用例和断言经过人工评审，能说明业务/工程风险。
2. 真实性边界明确，失败可以归因到受测变更。
3. 多次执行 selection 稳定，无 selection drift、XPASS 或隐式真实网络依赖。
4. 有真实 intentional-red 或历史真实缺陷证明负向检测能力。
5. 失败时 Artifact、执行日志或 Replay 足以支持 triage。
6. 执行时长、费用、数据和 secret 风险适合目标 Gate。
7. Owner 明确批准 Branch Protection、Ruleset 或 Release Policy 变更。

初始 Golden/Quality 规则建议保持简单：

- blocking case 必须 100% 通过；但当前先作为 report，不立即 enforce。
- overall pass rate 不低于人工批准 baseline 的容忍区间。
- avg rounds、P95 latency 和 fallback/summary rate 仅在真实测量语义稳定后参与 Gate。
- `unhandled_exception == 0`。
- LLM judge、一次性人工观感和未审查自动修复不得直接作为 blocking truth。

## 9. 每个工作单元的最小证据包

1. Work unit ID、目标契约和 non-goals。
2. Branch、完整 revision、操作系统和 runtime/profile。
3. 精确 nodeid/selection 与执行命令。
4. real/replaced/controlled dependency matrix。
5. pytest exit code 和摘要。
6. JUnit、Quality Report、执行日志或 Replay Artifact。
7. 失败时的 assertion、failure_stage 和直接日志。
8. 修复后的 restored verification。
9. Gate 状态和 Owner 决定。
10. 对应 Architecture/Current Progress 同步位置。

## 10. 执行纪律

- 每次只执行一个明确工作单元；完成、Review Needed 或 Blocked 后停止。
- 先执行最窄范围，再根据 blast radius 扩展完整 pytest。
- 不自动运行真实 LLM、外部 MCP、Remote Memory、staging、付费或可能产生副作用的测试。
- 不自动修改 Branch Protection、Required Check、发布策略或部署环境。
- 不为通过测试而削弱业务断言或在测试侧吞掉产品错误。
- 不把流程图、日志、JUnit 或 Quality Report 单独当作第二套业务真相源。
- 文档、测试、CI 和远端运行状态冲突时，以当前代码、当前 workflow 和最新执行证据为准，并记录冲突。

## 11. 近期推荐里程碑

### Milestone A：可信基线 + Basic Agent Workflow 理解

- P3-0 完成。
- P3-1 完成无工具、工具调用和 summary 三条代表路径的源码走读。
- Workflow 记录能连接 Route、Context、Loop、Tool、Result Injection 与 Finalization，并映射到代表测试。

### Milestone B：关闭两个已知状态机缺口

- Duplicate `tool_call_id` 不再是 `xfail`。
- User Stop 有明确 terminal/finalization 契约，不再是 `xfail`。
- 完整 pytest 无 XPASS/未知 skip。

### Milestone C：Agent Workflow CI Signal

- Tool Loop + 5 条 Golden Cases 在真实 PR 中执行。
- JUnit + Quality JSON/Markdown 在成功和失败 run 中可下载。
- 首阶段保持 `NON_BLOCKING`，积累 baseline 与稳定性证据。

完成 Milestone C 后，才能较稳妥地描述：

> NagaAgent 已从单一 SSE Closed Loop 扩展为可在 PR 中运行、可归因、可回放的 Agent Workflow Regression Signal。

若要描述“Agent Workflow Release Gate”，还必须完成 Owner 晋升决定、至少一条 staging E2E 和发布前接线。

## 12. 延后项与重新启动条件

| 延后项 | 当前原因 | 重新启动条件 |
|---|---|---|
| 真实 Remote Memory | 认证、环境、测试数据和 cleanup 未确认 | 确认测试账号/token、数据命名空间、成本与销毁策略 |
| Real LLM Gate | 当前只有 opt-in smoke，模型输出和成本不适合 PR 硬门禁 | 明确测试模型、预算、oracle、超时、重试和运行频率 |
| 20/50 并发 | 当前 workflow model/replay 尚未形成，失败难以归因 | P3-1、P3-5 与 staging baseline 稳定 |
| Prompt Injection/权限系统测试 | 缺少明确权限模型和工具白名单契约 | 产品 Owner 确认授权边界和 expected denial |
| 完整 CD | NagaAgent 当前只有 Build/GitHub Release，未确认部署平台 | 选择 staging/production 平台和 rollback 模型 |

## 13. 面试价值映射

| 工作单元 | 能展示的能力 |
|---|---|
| P3-0 | 基线治理、证据收口、主分支纪律 |
| P3-1 | Agent workflow 架构理解、源码走读、状态与测试映射 |
| P3-2 | 状态机、幂等、副作用控制 |
| P3-3 | SSE cancellation、异步资源清理、最终一致性 |
| P3-4 | GitHub Actions、测试分层、Quality Artifact 与 Gate 演进 |
| P3-5 | Failure replay、workflow evidence correlation、数据安全 |
| P3-6 | Context ownership、降级边界与最低充分测试层 |
| P3-7 | Deterministic regression 与真实 staging E2E 的互补设计 |
| P3-8 | 并发隔离、故障注入和可靠性工程 |
| P3-9 | CI、release packaging、CD、health 与 rollback 的完整区分 |

## 14. 完成定义

### 14.1 Final Plan 的完成条件

满足以下条件时，可以认为当前 `Final Plan` 的核心范围完成：

1. P3-0～P3-7 均有明确完成或 Owner 接受的延期决定。
2. 两个现有 `xfail` 已关闭或被新的明确产品决定取代。
3. Tool Loop + Golden Cases + Quality Artifact 已在真实 PR 中运行。
4. 至少一份可复核的 workflow 记录能把 request、context、round、tool、result injection、finalization 与代表测试连接起来。
5. 至少一条受控 staging E2E 验证真实 Route、Context、Loop、LLM 和 Persistence；Remote Memory 可以继续作为独立 `DELAYED` 子项，但不得被误报为已覆盖。
6. 每项都能回答：测试层、真实性、证明内容、不证明内容、失败含义和 Gate 状态。

### 14.2 Final after final（同一计划内的长期扩展）

P3-8、P3-9、权限/Prompt Injection、更多真实依赖和 Release Gate 属于 `Final after final`。它们继续保留在同一份 Final Plan 中作为长期方向，不需要现在再创建一份新计划，也不是理解基础 Agent workflow 的前置条件。

## 15. Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| FTA-CORR-1 | 2026-09-04 | 移除 Final Plan 与 Jaeger 的错误关联，将 P3-1 改为基于 NagaAgent 的 Basic Agent Workflow 学习 | `DONE` | 仓库代码/配置搜索未发现 Jaeger 实现；P3-1、依赖项和分析文档已按现有 Route/Loop/Tool 代码边界修正 | P3-0 收口当前基线 |

最终原则：

> 不追求一次性完成所有测试平台能力。优先让每个新增业务/风险范围形成自己的 deterministic test、执行证据、failure attribution 和 Gate Decision；重复出现的基础能力再沉淀到平台层。
