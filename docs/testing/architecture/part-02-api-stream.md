# P2 API Testing

> **当前迁移状态（2026-09-07）**：Smoke / SSE 资产已迁入 `981821be` 并在独立环境复验。
> Smoke 3 passed；resilience 7 passed + user-stop 1 xfailed；两个 workflow 的精确选测各通过三次。
> 真实 route、受控 Loop/LLM、保存 spy 与 Remote Memory 隔离的边界仍成立。
> 新 revision 的远端 CI/Required 未验证；下文旧 PR 和运行记录只属于 source revision。
> 当前证据见 [MIG-4 报告](../reports/upstream-migration-mig-4-execution-journal.md)，
> 全局基座适配见 [新测试基线](upstream-testing-baseline.md)。未逐行重新认证本文所有历史设计细节。
>
> 对应 [`overview.md`](overview.md) 第 2 章。

## 2.1 文档定位、模块职责与范围

### 2.1.1 与 Agent Workflow PR CI Gate 总目标的关系

当前 `part-02-api-stream.md` 不是完整的 Agent Workflow 测试总文档，而是 Agent Workflow 分层回归体系中属于 P2 API Layer 的说明文档。更高层的总体目标是：基于 NagaAgent 构建面向 Agent Workflow 的 Pytest 分层回归体系与 PR CI Gate，将 API 冒烟、流式响应、工具调用链路、上下文注入、任务级 golden cases 和质量报告前置到 CI / PR 阶段，降低 prompt / tool / context 相关变更破坏核心 AI 工作流的风险。

在这个总体目标中，`p2_api` 只承载其中与 API 入口和流式入口外显行为相关的部分，主要包括：

1. API 冒烟：验证 `/health`、`/chat`、`/chat/stream` 这些 P2 暴露的最小入口是否可用。
2. 流式响应一致性：验证 `/chat/stream` 是否能建立 SSE 连接，并按应用层契约输出 `session_id -> status+ -> content+ -> round_end -> [DONE]`；异常路径则以唯一、末尾的 `error` 事件结束。
3. 路由级流式韧性：验证异常中断、tool error event、compression failure、side-channel failure、empty output 等情况下，`/chat/stream` 是否仍然可以 finalize、清理 active flag，并以可诊断方式结束。
4. P2 质量门禁数据：从 `/chat/stream` 运行结果中提取 `ttfb_ms`、`total_latency_ms`、`event_count`、`done_seen`、`finalize_called`、`save_call_count`、`active_cleaned` 等最小报告字段，供后续 quality gate 聚合。

因此，`p2_api` 文档不会承载完整的工具调用工作流回归、完整上下文注入质量评测、完整 memory / RAG 评测或任务级 golden cases。那些内容属于更高层的 Agent Workflow Regression Gate，后续应分别放到 runtime、tool、context、memory 或 golden cases 的专项文档中。当前 `p2_api` 的重点是：先从 P2 API 入口视角保障系统最小可用性和 `/chat/stream` thick gateway 的收尾语义，确保核心入口不会被改挂。





- 这个模块测的是 P2 统一 HTTP 入口层最小闭环与流式入口治理。
- 对应业务 Part 主要是：
1. Part 2 API Layer
2. Part 3 Runtime 的入口边界
3. Part 6 / Part 7 的外显边界语义
- 当前先从这里入手，是因为 P2 是最先暴露给外部的入口，最适合做“是否被改挂”的门禁。
- 当前最难的点集中在 `/chat/stream`：
1. SSE 长连接是否能终止
2. 异常路径是否还能 finalize
3. active 状态是否能回落

## 2.2 当前已落地的 P2 范围

当前 `p2_api` 已落地范围对应 Agent Workflow PR CI Gate 总目标中的两个 P2 子目标：

1. API 冒烟
2. `/chat/stream` 流式入口一致性与 route-level resilience

其中，API 冒烟直接归属于 P2 API Layer；流式入口一致性虽然会触达 Part 3 Runtime、Part 6 Tool、Part 7 / Part 8 side-channel 的边界，但测试入口和外显断言仍然落在 `/chat/stream`，因此当前仍归在 `p2_api` 下说明。

### 2.2.1 smoke / p2_api
- 文件：`tests/smoke/test_api_smoke.py`
- 当前覆盖接口：
1. `/health`
2. `/chat`
3. `/chat/stream`

这一层的目标是验证 P2 最小 API surface 没有被改挂。它只确认服务可用、路由可访问、基础响应结构可读、流式接口至少能建连并出现终止事件。它不验证真实 LLM 语义、不验证真实 memory / RAG、不验证真实 MCP / tool workflow，也不验证完整 Agent 任务完成质量。

#### 2.2.1.1 `/health` 的职责与测试语义

`GET /health` 是 P2 API Layer 暴露的快速存活检查入口，代码位于
`apiserver/routes/system.py::health_check`。它的职责是用一个低成本、无外部服务依赖的
请求确认 FastAPI 应用已经成功加载、system router 已注册，并且事件循环能够正常处理
请求。

当前接口返回的核心字段包括：

1. `status`
   - 当前约定值为 `"healthy"`。
   - 表示 P2 API 进程能够正常响应该健康检查，而不是所有下游组件都已经健康。
2. `agent_ready`
   - 当前实现固定返回 `True`，属于 API 响应契约字段。
   - 它目前不能证明真实 LLM、Agent Server、memory、Neo4j、MCP 或 OpenClaw 已经就绪。
   - smoke 只检查字段存在，避免把轻量健康检查误写成完整依赖诊断。
3. `websocket_connections`
   - 来自 `apiserver.websocket_manager.get_stats()`。
   - 这使 `/health` 在实现上触达 Part 7 的 WebSocket 状态边界，但接口所有权和测试归类
     仍然属于 Part 2。
4. `timestamp`
   - 来自当前 asyncio event loop。
   - 用于提供本次健康响应的运行时信息，smoke 不对具体数值做固定断言。

因此，`test_health_smoke` 实际证明的是：

```text
FastAPI app 可加载
  -> system router 已注册
  -> GET /health 可访问
  -> 返回 HTTP 200
  -> 基础健康 JSON 契约仍然成立
```

它不证明以下事项：

1. 真实 LLM provider 可访问。
2. Agent Server 已启动。
3. Neo4j、memory 或 RAG 后端可用。
4. MCP / OpenClaw 工具可调用。
5. WebSocket 客户端可以完成真实端到端通信。
6. 完整 Agent Workflow 可以成功执行。

这些真实运行依赖不应塞进 PR smoke。跨进程和跨模块健康检查应由
`GET /health/full` 的 integration 或 staging 测试承担。两者的边界是：

| 接口 | 测试定位 | 外部依赖 | 当前 PR blocking |
|---|---|---|---|
| `/health` | P2 快速入口健康契约 | 不需要 | 是 |
| `/health/full` | 多 Part 真实运行状态诊断 | Agent Server 及其他内部服务 | 否 |

从架构映射看，`/health` 的入口所有权属于 Part 2；其
`websocket_connections` 字段读取了 Part 7 的本地状态。测试仍归入 `p2_api`，因为断言
关注的是 P2 对外暴露的 HTTP 契约，而不是 Part 7 WebSocket 功能本身。

### 2.2.2 stream resilience / p2_api

- 文件：`tests/integration/chat_stream/test_resilience.py`

- 对应总目标中的：AI 流式响应一致性回归

- 当前已落地的是

  ```
  SSE 异常可收尾回归（V1）
  ```

  ，按两组组织为 7 条 + 1 条

  ```
  xfail
  ```

   contract gap：

  1. `real route + fake loop`
  2. `real route + real loop + fake LLM`

这一层的目标是验证 `/chat/stream` 作为 P2 thick gateway 时，在正常路径和异常路径下是否仍能正确收尾。它关注的是 SSE 事件序列、`[DONE]` 或 error terminal、finalize、active flag 回落、side-channel failure 不阻塞主链路、compression failure 不打崩流式输出，以及必要时对 persistence 调用次数进行 spy 观察。

这层虽然命名上属于 `p2_api`，但它不是单纯的 endpoint status check，而是 P2 入口视角下的跨层边界测试。它只验证 Part 3 / Part 6 / Part 7 / Part 8 的失败是否会破坏 `/chat/stream` 的外显行为，不替代这些 Part 的专项测试。

#### 2.2.2.1 P1 SSE 协议工作单元状态（更新至 2026-08-10）

| 工作项 | 所有权 / 边界 | 测试层与真实性 | 实现状态 | Gate 状态 | 当前证据 |
|---|---|---|---|---|---|
| 固定 SSE 事件顺序和终止协议 | Part 2 API 为协议所有者；Part 3 loop 为被消费边界 | integration；real app + real route + fake loop + persistence spy | `LANDED` | `NON_BLOCKING` PR Check | `Stream Contract Gate` 在 `pull_request` 上成功，`2 passed, 6 deselected` |
| 验证首个及多个增量 `content`、完整拼接和终止 | Part 2 API 的 SSE 输出与保存调用边界 | integration；real app + real route + scripted SSE loop + persistence spy | `LANDED` | `NON_BLOCKING` PR Check | 三段 `content` 精确拼接为 `baseline-stream-ok` 并与保存入参一致；远端目标用例通过 |
| 用户 stop / 客户端断开收尾 | Part 2 前端取消传播与 route generator cleanup 边界 | executable gap | `XFAIL_GAP` | `NOT_WIRED` | `test_chat_stream_user_stop_contract_gap` 仍为预期失败 |

本工作单元的完整 resilience 复跑结果为 `7 passed, 1 xfailed`。唯一 `xfail` 是上表中的 user-stop 缺口，不应计入已落地的前两项。这里的完成状态只证明应用层 SSE 事件契约，不证明独立进程、代理服务器或真实网络上的 HTTP 分包与 TTFB。

### 2.2.3 real_llm / p2_api

- 文件：`tests/integration/chat_stream/test_real_llm_smoke.py`

- 对应总目标中的：真实模型路径的最薄 happy-path 验证

- 当前已落地的是 1 条 opt-in、non-blocking 的

  ```
  real_llm normal stream smoke
  ```

  ：

  1. `real route + real loop + real LLM + patched side effects`

这一层用于验证真实 LLM 路径在最薄 happy path 下不会出现明显初始化、鉴权、stream 消费或 route/loop 协同问题。由于它依赖真实模型服务、网络、密钥和模型输出稳定性，因此当前不建议作为 PR required check，而更适合作为 opt-in、non-blocking、nightly 或 staging 前置检查。



## 2.3 当前主流程定义

### 2.3.1 smoke 主流程
- `/health`
1. API 进程可用
2. 路由可访问
3. 基础健康字段可读
- `/chat`
1. 请求进入非流式主链路
2. 会话创建或复用
3. LLM 路径被 stub 固定
4. 返回标准 JSON 响应
- `/chat/stream`
1. 建立 SSE 连接
2. 输出 `session_id`
3. 输出业务事件
4. 存在终止事件 `[DONE]`

### 2.3.2 integration 主流程
- `/chat/stream` 在 integration 层当前测的不是“回答质量”，而是“异常下还能不能正确收尾”。
- 当前关注链路按两组组织：
1. `real route + fake loop`
2. `real route + real loop + fake LLM`
- 共同关注点：
1. 设置 conversation active
2. 进入正常或故障注入后的流式分支
3. 正常路径或 `finally` 路径执行 finalize
4. active flag 回落
5. SSE 事件序列仍然可收尾
6. side-channel / compression failure 不阻塞主链路结束
7. 必要时观察 persistence 调用次数

### 2.3.3 current run modes in `p2_api`
- 当前 `p2_api` 已经同时存在 3 种运行模式语义：
1. `stub`
2. `real_llm`
3. `staging`（仅规划）
- `stub`
1. `tests/smoke/test_api_smoke.py`
2. `tests/integration/chat_stream/test_resilience.py`
- `real_llm`
1. `tests/integration/chat_stream/test_real_llm_smoke.py`
- `staging`
1. 当前只有设计目标，没有现成用例

### 2.3.4 PR Gate 选择依据

当前 `p2_api` 在 PR 上使用两个分离的确定性 Check：

1. `Smoke Blocking Gate`：执行 3 条 `smoke and blocking` API 冒烟；当前 PR 页面显示为
   `Required`，Gate 状态为 `PR_BLOCKING`。
2. `Stream Contract Gate`：执行 2 条 `integration and blocking and not real_llm` SSE 契约；
   已在真实 `pull_request` 事件中通过，但当前未显示 `Required`，Gate 状态为 `NON_BLOCKING`。

两者共同优先保障 P2 外部入口最小可用和 `/chat/stream` 正常/异常终止协议。P2 API Layer 是用户
请求进入系统的第一层入口；`/health`、`/chat` 或 `/chat/stream` 的基础协议一旦失效，系统会直接
表现为不可用。

`smoke` 用来验证最小基础功能没有被改挂。它只覆盖 `/health`、`/chat` 和 `/chat/stream` 三个最小入口，目标是确认 API 进程可用、非流式主链路可以返回标准响应、流式链路至少可以建立 SSE 连接并产生终止事件。`smoke` 不验证真实 LLM 语义，不验证真实 tool loop，也不验证 memory / RAG / MCP 的完整效果。它的设计目标是快、稳、离线可跑，适合作为 PR 的第一道 blocking check。

`tests/integration/chat_stream/test_resilience.py` 中只有以下两条经过评审并增加 `blocking` marker 的
用例进入 Stream PR Check：

1. `test_chat_stream_resilience_baseline_finishes_and_cleans_state`
2. `test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state`

同文件其余 6 条用例仍被 marker selection 排除；其中 user-stop 仍是 `XFAIL_GAP`。这避免把尚未
评审的场景、真实 LLM 或完整 resilience 文件整体误纳入 PR Check。

当前 PR Gate 选择原则只有：

1. 用例必须快速、稳定、完全离线。
2. 失败必须能明确归因于本次代码变更。
3. 不依赖真实 LLM、MCP、Neo4j、memory 或其他外部服务。

### 2.3.5 Test Profile 真实性边界说明

当前 `p2_api` 测试中，“real” 不表示所有依赖都是真实的，而是表示某一层核心路径被保留下来。为了避免误解，当前 profile 的真实性边界定义如下。

#### 2.3.5.1 `smoke`

`smoke` 的目标是验证最小入口可用性。

- 真实部分：
  1. FastAPI app
  2. `/health`
  3. `/chat`
  4. `/chat/stream` route entry
- 替换部分：
  1. LLM
  2. tool loop
  3. context / prompt 的高波动分支
  4. persistence
  5. telemetry
  6. remote notify
- 适合回答的问题：
  1. API 服务是否可用
  2. 基础路由是否还能访问
  3. 非流式响应结构是否被改坏
  4. 流式接口是否至少能建连并输出终止事件
- 不适合回答的问题：
  1. 真实 LLM 回答质量是否正确
  2. 真实 tool workflow 是否完整收敛
  3. memory / RAG 是否召回正确
  4. staging 环境是否真实可用

#### 2.3.5.2 `stream resilience: real route + fake loop`

`real route + fake loop` 的目标是验证 `/chat/stream` 路由层的 SSE 协议、finalize 和 active cleanup。

- 真实部分：
  1. FastAPI app
  2. `TestClient(app)` 进程内请求链路
  3. `/chat/stream` route
  4. route 内部的 SSE 响应消费逻辑
  5. route 内部的 `finally` / finalize 路径
  6. queue active flag 回落逻辑
- 替换部分：
  1. `run_agentic_loop(...)`
  2. LLM
  3. tools / MCP
  4. persistence，使用 spy 观察调用次数
  5. telemetry
  6. remote notify
- 适合回答的问题：
  1. route 是否能正确消费 loop 输出
  2. 正常流是否满足 `session_id -> status+ -> content+ -> round_end -> [DONE]`
  3. `[DONE]` 或 `error` 是否唯一且位于事件序列末尾
  4. 多个 `content` 事件是否保持顺序、完整拼接并传给保存边界
  5. midstream exception 后是否可诊断结束
  6. tool error 事件是否会阻塞流式收尾
  7. notify failure 是否会影响主链路 finalize
  8. empty output 是否仍能触发收尾
- 不适合回答的问题：
  1. 真实 `run_agentic_loop(...)` 是否完整收敛
  2. 真实 tool execution 是否成功
  3. tool result 是否被真实注入下一轮
  4. 真实 LLM 是否能生成合理回答
  5. `TestClient.iter_text()` 次数是否等于真实网络分包次数
  6. 独立进程、反向代理和真实网络下的 TTFB 是否满足性能目标

#### 2.3.5.3 `stream resilience: real route + real loop + fake LLM`

`real route + real loop + fake LLM` 的目标是验证 route 与 `run_agentic_loop(...)` 的协同，而不是验证完整真实 Agent workflow。

- 真实部分：
  1. FastAPI app
  2. `/chat/stream` route
  3. `run_agentic_loop(...)` orchestration shell
  4. 每轮 loop 的基础控制流
  5. compression 调用分支
  6. LLM stream chunks 的消费与事件解析
  7. `round_end(has_more=False)` 分支
  8. route 对 loop 输出的消费、finalize 和 active cleanup
- 替换部分：
  1. `get_llm_service()`，使用 fake streaming LLM 控制模型输出
  2. 真实 tool execution
  3. 真实 MCP dispatcher
  4. 真实 tool-result reinjection
  5. 真实 queue injection
  6. 真实 memory / RAG
  7. persistence / telemetry / remote notify
- 适合回答的问题：
  1. route 和真实 loop 外壳是否能协同
  2. fake LLM 输出能否被真实 loop 正确消费
  3. loop 是否能走到 `round_end`
  4. compression failure 是否不会把流式主链路打崩
  5. route 是否能在真实 loop 输出后完成 `[DONE]`、finalize 和 active cleanup
- 不适合回答的问题：
  1. 完整多轮 tool workflow 是否收敛
  2. `execute_tool_calls(...)` 是否真实执行成功
  3. tool result 是否真实进入下一轮 messages
  4. repeated failure 是否进入 summary round
  5. `max_rounds` exhausted 后是否完整触发 summary round
  6. memory recall 和 context assembly 的真实质量是否正确

因此，当前文档中提到的 `real loop` 更准确地说是 `real orchestration shell + fake model output + partial workflow coverage`。它证明的是 route/loop 协作和部分 runtime 分支稳定性，不等价于 full workflow。

#### 2.3.5.4 `real_llm`

`real_llm` 的目标是保留真实模型路径的最薄 happy-path smoke。

- 真实部分：
  1. `/chat/stream` route
  2. `run_agentic_loop(...)`
  3. `get_llm_service()`
  4. 真实 LLM stream
- 仍然建议替换或稳定化的部分：
  1. persistence
  2. telemetry
  3. remote notify
  4. prompt / context 中与当前断言目标无关的高波动分支
- 适合回答的问题：
  1. 真实模型服务是否能被 loop 正常调用
  2. 真实 stream 是否能产生可消费输出
  3. happy path 是否不会出现明显初始化失败、鉴权失败或本地模型路径错误
  4. route 是否能在真实模型路径下执行 ended / save spy
- 不适合作为 PR blocking gate 的原因：
  1. 依赖 API key 或本地模型环境
  2. 可能受网络和模型服务状态影响
  3. 模型输出存在随机性
  4. 成本和耗时高于 stubbed stream resilience
  5. 失败不一定代表本次 PR 改坏了代码

因此，`real_llm` 当前应保持 opt-in、non-blocking 或 nightly，不建议作为每个 PR 必须通过的 required check。

#### 2.3.5.5 `staging`

`staging` 的目标是验证更接近生产配置的完整链路。

- 真实部分：
  1. 真实 API 服务
  2. 真实 route
  3. 真实 agent loop
  4. 真实 LLM
  5. 真实 memory / RAG
  6. 真实 tool / MCP
  7. 真实 persistence
  8. 真实 side-channel
- 适合回答的问题：
  1. 本地 stub / fake 无法覆盖的环境问题
  2. 多依赖联动是否稳定
  3. 真实配置下是否能完整流式返回
  4. 真实工具和记忆路径是否可用
  5. 发布前是否存在明显回归
- 不适合作为每个 PR blocking gate 的原因：
  1. 执行慢
  2. 依赖多
  3. flaky 风险高
  4. 失败归因范围大
  5. 更适合 nightly、release 前或手动触发

### 2.3.6 P2 测试与 GitHub Actions 的关系

GitHub Actions 的完整配置和 required check 策略统一记录在
[`ci-pr-gate.md`](ci-pr-gate.md)。本节只说明 `p2_api` 向 CI 提供哪些测试集合。

#### 2.3.6.1 当前已经接入 CI 的部分

当前两个 workflow 分别执行：

```bash
uv run python -m pytest tests/smoke -m "smoke and blocking" -q

uv run python -m pytest tests/integration/chat_stream/test_resilience.py \
  -m "integration and blocking and not real_llm" -q
```

GitHub Check `Smoke Blocking Gate` 覆盖：

1. `test_health_smoke`
2. `test_chat_non_stream_smoke`
3. `test_chat_stream_smoke_has_terminal_event`

GitHub Check `Stream Contract Gate` 覆盖：

1. `test_chat_stream_resilience_baseline_finishes_and_cleans_state`
2. `test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state`

2026-08-10 的 Draft PR 证据显示两个 Check 均由 `pull_request` 触发并成功：Smoke 用时约 24 秒，
Stream 用时约 22 秒；Stream pytest 日志为 `2 passed, 6 deselected, 3 warnings in 2.61s`。Smoke
显示 `Required`，Stream 未显示 `Required`。

这证明 P2 最小入口 smoke 和两条受控 SSE 契约在该 revision 通过，不证明真实 LLM、真实 Agent
Workflow、真实持久化、user-stop 或外部服务已经运行。

## 2.4 用例与断言

### 2.4.1 `tests/smoke/test_api_smoke.py`

#### 2.4.1.1 `test_health_smoke`
- 目标：验证 API 本地可用性和基础健康契约没有被改挂。
- 覆盖流程：`GET /health -> JSON 解析 -> 基础健康字段断言`
- 关键断言：
  1. `status_code == 200`
  2. `status == "healthy"`
  3. `agent_ready` 字段存在
- 当前非目标：
  1. 不验证 `/health/full`
  2. 不验证 `agentserver` 跨进程依赖

#### 2.4.1.2 `test_chat_non_stream_smoke`
- 目标：验证非流式主链路可以形成最小闭环。
- 覆盖流程：`POST /chat -> 会话创建 -> LLM stub 返回 -> JSON 封装`
- 关键断言：
  1. `status_code == 200`
  2. `status == "success"`
  3. `response == "smoke-chat-ok"`
  4. `session_id` 存在
- 当前非目标：
  1. 不验证真实 LLM 语义
  2. 不验证 RAG / memory 质量

#### 2.4.1.3 `test_chat_stream_smoke_has_terminal_event`
- 目标：验证流式主链路至少能建立连接并存在终止事件。
- 覆盖流程：`POST /chat/stream -> SSE 建连 -> content -> round_end -> [DONE]`
- 关键断言：
  1. `status_code == 200`
  2. `content-type == text/event-stream`
  3. `session_id` 存在
  4. `[DONE]` 存在
- 当前非目标：
  1. 不验证真实 tool loop
  2. 不验证真实 side-channel 协同

### 2.4.2 `tests/integration/chat_stream/test_resilience.py`

#### 2.4.2.1 `test_chat_stream_resilience_baseline_finishes_and_cleans_state`
- 所属组：`real route + fake loop`
- 实现状态：`LANDED`
- Gate 状态：`NON_BLOCKING`；已接入 `Stream Contract Gate` 并在 `pull_request` 上验证通过
- 核心目标：固定正常流的应用层 SSE 顺序、多增量拼接、唯一终止和保存边界
- 关键断言：
  1. 首个事件为 `session_id`，首个 `content` 前只允许一个或多个 `status`
  2. 三个 `content.text` 依次为 `baseline-`、`stream-`、`ok`，首个增量非空
  3. 从首个 `content` 起的尾部序列精确为 `content -> content -> content -> round_end -> done`
  4. `[DONE]` 是唯一 terminal，且之后不存在任何 SSE 事件
  5. 三段内容拼接为 `baseline-stream-ok`
  6. persistence spy 调用 1 次，保存的响应文本等于完整拼接结果
  7. `started` / `ended` 生命周期事件各出现一次，queue active flag 回落
- 证明范围：证明真实 route 对受控 loop SSE 输出的顺序消费、聚合、保存调用和正常收尾；不证明真实 loop、真实 LLM、真实持久化落盘或网络分包。
- 失败含义：优先指向 route SSE 协议顺序、内容聚合、terminal 唯一性、保存边界或 finalize 行为发生回归。

#### 2.4.2.2 `test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state`
- 所属组：`real route + fake loop`
- 实现状态：`LANDED`
- Gate 状态：`NON_BLOCKING`；已接入 `Stream Contract Gate` 并在 `pull_request` 上验证通过
- 核心目标：midstream 抛错后仍然可诊断地结束
- 关键断言：
  1. 首个事件为 `session_id`，部分 `content` 前只允许 `status` 事件
  2. 尾部序列精确为 `content -> error`
  3. `error` 是唯一 terminal、位于末尾，且不得再出现 `[DONE]`
  4. 错误前部分内容为 `partial-before-error`，error payload 为 `midstream boom`
  5. queue active flag 回落，persistence spy 调用 0 次
- 证明范围：证明 route 能把受控 loop 的中途异常转成唯一、可诊断的 SSE error terminal 并清理 active state；不证明重试、部分响应保存或 user-stop 语义。
- 失败含义：优先指向异常终止协议、terminal 重复/乱序、异常后错误保存或 generator cleanup 回归。

#### 2.4.2.3 `test_chat_stream_resilience_tool_error_event_still_terminates`
- 所属组：`real route + fake loop`
- 核心目标：tool error 事件不阻塞 SSE 收尾
- 关键断言：
  1. 存在 `tool_results`
  2. 存在 `status=error`
  3. 存在 `[DONE]`
  4. queue active flag 回落
  5. persistence spy 调用 1 次

#### 2.4.2.4 `test_chat_stream_real_loop_with_fake_llm_finishes_and_cleans_state`
- 所属组：`real route + real loop + fake LLM`
- 核心目标：保留真实 `run_agentic_loop`，只替换 LLM，验证主路径收尾
- 关键断言：
  1. 存在 `real-loop-safe-ok`
  2. 存在 `round_end`
  3. 存在 `[DONE]`
  4. queue active flag 回落
  5. persistence spy 调用 1 次

#### 2.4.2.5 `test_chat_stream_resilience_compress_failure_does_not_break_stream`
- 所属组：`real route + real loop + fake LLM`
- 核心目标：compression failure 不崩流
- 关键断言：
  1. 存在 `compress-safe-ok`
  2. 存在 `round_end`
  3. 存在 `[DONE]`
  4. queue active flag 回落
  5. persistence spy 调用 1 次

#### 2.4.2.6 `test_chat_stream_resilience_notify_failure_does_not_block_finalization`
- 所属组：`real route + fake loop`
- 核心目标：通知 side-channel 失败不阻塞 finalize
- 关键断言：
  1. 存在 `notify-failure-safe`
  2. 存在 `[DONE]`
  3. queue active flag 回落
  4. persistence spy 调用 1 次

#### 2.4.2.7 `test_chat_stream_resilience_empty_output_still_finalizes`
- 所属组：`real route + fake loop`
- 核心目标：空输出不是挂死理由，仍然必须收尾
- 关键断言：
  1. 存在 `session_id`
  2. 存在 `[DONE]`
  3. `finalize_called == 1`
  4. `save_call_count == 1`
  5. 保存的 `response_text` 允许为空字符串
  6. queue active flag 回落

#### 2.4.2.8 当前缺口：`user stop`
- 当前已经补了一条 `xfail` 形式的 executable gap，用来固定未来目标契约：
  1. `test_chat_stream_user_stop_contract_gap`
- 原因不是测试没写，而是主代码还缺少明确的 stop/cancel 语义边界：
  1. 没有单独的 `/chat/stop`
  2. 也没有显式的 `request.is_disconnected()` / `CancelledError` 收口语义
- 因此这条当前先以 `xfail` gap 形式存在，而不是伪装成“已覆盖通过”的正式回归。

### 2.4.3 `tests/integration/chat_stream/test_real_llm_smoke.py`

#### 2.4.3.1 `test_chat_stream_real_llm_normal_smoke`
- 所属组：`real route + real loop + real LLM`
- 运行模式：`real_llm`
- 核心目标：保留真实模型路径的最薄 happy-path smoke
- 关键断言：
  1. 存在 `session_id`
  2. 存在 `round_end`
  3. 不出现 `auth_expired`
  4. 不出现 `data: error:`
  5. 不出现明显的本地 LLM 初始化失败文案
  6. `ended` 生命周期事件出现 1 次
  7. `save_call_count == 1`

## 2.5 测试执行链路

### 2.5.1 smoke 执行链路
`pytest -> tests/conftest.py -> client fixture -> monkeypatch chat_routes / agentic_tool_loop -> 调 /health /chat /chat/stream -> 断言`

### 2.5.2 integration 执行链路
- `real route + fake loop`
`pytest -> stream_env fixture -> patch fake run_agentic_loop -> 调 /chat/stream -> 按 data block 解析有序 SSE 事件 -> 断言顺序 / terminal / 拼接 / finalize / save_calls`
- `real route + real loop + fake LLM`
`pytest -> stream_env fixture -> 保留真实 run_agentic_loop -> patch fake stream LLM 或 compression failure -> 调 /chat/stream -> 断言 round_end / [DONE] / save_calls / active flag`
- `real route + real loop + real LLM`
`pytest -> real_llm_stream_env fixture -> 保留真实 get_llm_service + real run_agentic_loop -> 调 /chat/stream -> 断言 round_end / no error / save_calls / active flag`
- 这里的 `real route` 指的是：
1. 真实 `TestClient(app)` 把请求送进真实 FastAPI 应用
2. 真实执行 `/chat/stream` 路由函数及其内部主流程
3. 不是先启动独立 `uvicorn` 进程再从外部打 HTTP

### 2.5.3 与真实业务流程映射
| 测试点 | 被测业务 Part | 代码入口 / 关键文件 | 当前边界 |
|---|---|---|---|
| `test_health_smoke` | Part 2 + Part 7 | `tests/smoke/test_api_smoke.py`、`apiserver/routes/system.py`、`apiserver/websocket_manager.py` | 只验证本地健康契约，不验证 `/health/full` |
| `test_chat_non_stream_smoke` | Part 2 + Part 3 | `tests/smoke/test_api_smoke.py`、`tests/conftest.py`、`apiserver/routes/chat.py` | LLM 为固定 stub，不验证真实语义 |
| `test_chat_stream_smoke_has_terminal_event` | Part 2 + Part 3 | `tests/smoke/test_api_smoke.py`、`tests/conftest.py`、`apiserver/routes/chat.py`、`apiserver/agentic_tool_loop.py` | 只验证最小终止语义，不验证真实工具编排 |
| `test_chat_stream_resilience_baseline_finishes_and_cleans_state` | Part 2 owner + Part 3 boundary | `tests/integration/chat_stream/test_resilience.py`、`apiserver/routes/chat.py`、`apiserver/message_queue.py` | 验证正常 SSE 顺序、三段增量拼接、唯一 `[DONE]`、保存 spy 和 active 回落；不验证真实 LLM/MCP/磁盘落盘/网络分包 |
| `test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state` | Part 2 owner + Part 3 boundary | `tests/integration/chat_stream/test_resilience.py`、`apiserver/routes/chat.py`、`apiserver/agentic_tool_loop.py` | 验证部分内容后以唯一末尾 `error` 收尾且无 `[DONE]`；不验证真实重试、部分保存和 user stop |
| `test_chat_stream_resilience_tool_error_event_still_terminates` | Part 2 + Part 3 + Part 6 边界 | `tests/integration/chat_stream/test_resilience.py`、`apiserver/routes/chat.py`、`apiserver/agentic_tool_loop.py` | 只到 tool error 事件级别，不触发真实 MCP dispatcher |
| `test_chat_stream_real_loop_with_fake_llm_finishes_and_cleans_state` | Part 2 + Part 3 | `tests/integration/chat_stream/test_resilience.py`、`apiserver/routes/chat.py`、`apiserver/agentic_tool_loop.py`、`apiserver/llm_service.py` | 保留真实 loop，只替换 LLM，验证主路径收尾 |
| `test_chat_stream_resilience_compress_failure_does_not_break_stream` | Part 3 + Part 2 | `tests/integration/chat_stream/test_resilience.py`、`apiserver/context_compressor.py`、`apiserver/agentic_tool_loop.py`、`apiserver/routes/chat.py` | 只验证 compression failure fallback，不验证真实压缩效果 |
| `test_chat_stream_resilience_notify_failure_does_not_block_finalization` | Part 2 + Part 7/8 边界 | `tests/integration/chat_stream/test_resilience.py`、`apiserver/routes/chat.py`、`apiserver/api_server.py` | 只验证 conversation lifecycle notify 失败不阻塞 finalize，不验证真实 websocket / remote notify E2E |

### 2.5.4 SSE 协议契约表
| invariant | 实现状态 | 说明 |
|---|---|---|
| HTTP 200 + `text/event-stream` | `LANDED` | smoke 与 integration 都断言 |
| `session_id` 是首个应用层 SSE 事件 | `LANDED` | 正常流和 midstream exception 用结构化事件序列断言 |
| 首个 `content` 前只出现 `status` | `LANDED` | 两条核心契约用例均固定此前缀顺序 |
| 多个 `content` 事件按序到达 | `LANDED` | 正常流断言三个 SSE `content` 事件及各自文本；不以 HTTP transport chunk 数量作为证据 |
| `content` 拼接结果与保存边界一致 | `LANDED` | `baseline-stream-ok` 与 persistence spy 的响应入参完全一致 |
| happy path 以唯一、末尾 `[DONE]` 终止 | `LANDED` | 正常流尾部精确为 `content x3 -> round_end -> done` |
| 异常路径以唯一、末尾 `error` 终止且无 `[DONE]` | `LANDED` | midstream exception 尾部精确为 `content -> error` |
| finalize 只执行一次 | `PARTIAL` | 当前通过 `ended` 次数和 save spy 近似观察，尚未覆盖所有取消/重复 finalize 分支 |
| save 调用次数符合路径预期 | `LANDED` | 当前 resilience 用例已覆盖 0 次 / 1 次分支 |
| active flag 最终回落 | `LANDED` | 当前所有 resilience case 都断言 |
| `user stop` 收尾一致性 | `XFAIL_GAP` | 已有 executable gap，等待 `AbortSignal` 与 generator cleanup 契约落地 |
| `empty output` 仍收尾 | `LANDED` | 当前已补空输出回归 |

## 2.6 依赖替换与故障注入

### 2.6.1 smoke 的依赖替换矩阵
- 当前 smoke 的替换由 `tests/conftest.py::client` 统一提供。
- 替换目标分为 3 类：
1. prompt / context assembly 稳定化
2. model / tool path 稳定化
3. side effect 隔离

### 2.6.2 integration 的故障注入方式
- 当前 integration 不是“全链路真实依赖”，而是“真实路由主流程 + 最小故障注入”。
- `stream_env` 先做一层 route-adjacent 稳定化：
1. 固定 prompt / supplement
2. 屏蔽 telemetry
3. 把通知事件改为本地 `events` 账本
4. 把 `_save_conversation_and_logs` 改为 `save_calls` spy
- 每条用例再按组做最小注入：
1. `real route + fake loop`：替换 `run_agentic_loop`
2. `real route + real loop + fake LLM`：保留真实 loop，只替换 `get_llm_service`
3. `compression failure`：在真实 loop 下额外替换 `compress_context`

### 2.6.3 为什么替这些，不替哪些
- 当前替换的是高波动、强外部依赖、与当前断言目标无关的点：
1. LLM
2. 外部 tool 行为
3. persistence
4. telemetry
5. 远程通知
- 当前不替换的，是我们真正想验证的核心：
1. 真实 FastAPI app
2. 真实 `/chat/stream` 路由
3. route 内 finalize / `finally` 路径
4. queue active flag 的回落逻辑

### 2.6.4 Current `real_loop` Coverage
- In the current `real route + real loop + fake LLM` cases, `run_agentic_loop(...)` is real, but model output is still controlled by a fake streaming LLM.
- What is real in the current coverage:
1. the real `/chat/stream` route consumes loop output and performs real finalize / cleanup
2. the real loop enters per-round `compress_context(...)` handling
3. the real loop consumes LLM stream chunks and parses event types
4. the real loop reaches the `no actionable tool call -> round_end(has_more=False) -> stop` branch
- What is not yet covered by the current real-loop cases:
1. actual tool execution via `execute_tool_calls(...)`
2. tool-result reinjection into later rounds
3. queue injection via `message_queue.drain()`
4. repeated-failure convergence and early summary
5. `max_rounds` exhausted -> summary round
- In other words, the current real-loop coverage proves real route/loop cooperation and compression-failure fallback, but it does not yet prove full multi-round tool convergence.

### 2.6.5 Stub 与真实路径切换边界
- 当前不应该被随意替换掉的核心路径：
1. `FastAPI app`
2. `/chat/stream` route
3. `finally` / finalize / active flag 回落
4. `TestClient(app)` 进程内请求链路
- 在 `stub` 模式下可以替换：
1. `get_llm_service`
2. `run_agentic_loop`
3. `build_system_prompt`
4. `build_context_supplement`
5. `_notify_conversation_event`
6. `_save_conversation_and_logs`（替换成 spy）
7. `emit_telemetry`
- 在 `real_llm` 模式下仍然建议替换：
1. `_notify_conversation_event`
2. `_save_conversation_and_logs`（spy）
3. `emit_telemetry`
4. prompt/context 稳定化分支（避免无关波动）
- 在 `real_llm` 模式下不应替换：
1. `get_llm_service`
2. `run_agentic_loop`
- 在 `staging` 模式下进一步收紧：
1. 尽量不 patch side-channel
2. 尽量保持真实配置和真实依赖
3. 只在安全或成本需要时保留最小 spy

### 2.6.6 最小报告字段
- 当前 SSE 回归需要统一一组最小报告字段，避免每个测试只断言字符串而缺少观测面。
- 协议断言现由 `_parse_sse_events(...)` 按 SSE `data:` block 解析；`event_count` 使用解析后的应用层事件数，而不是 `TestClient.iter_text()` 返回次数。
- 推荐最小字段：
1. `ttfb_ms`
2. `total_latency_ms`
3. `event_count`
4. `done_seen`
5. `finalize_called`
6. `save_call_count`
7. `active_cleaned`
- 当前实现状态：
1. `tests/integration/chat_stream/test_resilience.py` 已有 `_stream_run(...)`
2. 同文件已补 `_build_stream_report(...)`
3. 这些字段当前主要用于 resilience 套件与后续 `real_llm` / `staging` 扩展

### 2.6.7 `_publish_quality_gate_case(...)` 的作用
- `_publish_quality_gate_case(...)` 不是业务逻辑的一部分，而是测试侧的结构化上报 helper。
- 它当前主要出现在：
  1. `tests/integration/chat_stream/test_resilience.py`
  2. `tests/integration/chat_stream/test_real_llm_smoke.py`
- 它做的事情不是改写测试结果，而是把当前 case 的附加语义写入 `request.node.user_properties`，键名固定为 `quality_gate_case`。
- 当前上报的核心字段包括：
  1. `case_id`
  2. `feature`
  3. `story`
  4. `blocking / non_blocking`
  5. `final_status`
  6. `failure_stage`
  7. `metrics`
- 其中：
  1. `_build_stream_report(...)` 负责 route / SSE 层的最小观测字段
  2. `build_failure_attribution(...)` 负责把运行现象投影成 `final_status / failure_stage / rounds / tool_call_count`
  3. `_publish_quality_gate_case(...)` 负责把这两类信息合成一份可聚合的 case record
- 这样做的目的不是替代断言，而是让一条测试除了 `pass / fail` 之外，还能被后续 gate 聚合器理解为：
  1. 这是 correctness、stability 还是 performance case
  2. 这是 blocking 还是 non-blocking case
  3. 失败时更像是哪一个阶段出了问题
  4. 这条 case 应该贡献哪些性能或 workflow 指标
- 当前不是每条测试都必须补这个 helper。
- 没补的测试仍然会有 pytest 原生的 `passed / failed / skipped` 结果，但不会贡献细粒度的 `failure_stage`、`ttfb_ms`、`tool_rounds` 等 gate 字段。

### 2.6.8 `p2_api` 到 Quality Gate 的数据流
- 当前 `p2_api` 测试接入 quality gate 的最短链路是：
`test body -> _stream_run / _build_stream_report -> build_failure_attribution -> _publish_quality_gate_case -> pytest hook -> quality gate aggregator`
- 具体分成 5 步：
  1. 测试先跑真实 route 或受控依赖下的 `/chat/stream`
  2. `_stream_run(...)` 与 `_build_stream_report(...)` 产出最小 stream report
  3. 需要 workflow 语义时，再调用 `build_failure_attribution(...)`
  4. `_publish_quality_gate_case(...)` 把这些字段写入 `request.node.user_properties`
  5. `tests/conftest.py` 在 `pytest_runtest_makereport(...)` / `pytest_terminal_summary(...)` 里收集并汇总
- 和性能相关的两个时间字段，当前单 case 口径是：
  1. `ttfb_ms`：当前代码字段名尚未迁移；在进程内 `TestClient` profile 中实际表示从发起请求到收到首个非空 transport chunk 的 `first_chunk_ms` 语义，不能作为真实网络 TTFB 证据
  2. `total_latency_ms`：从发起请求到整个 stream 完成并退出 `client.stream(...)` 的总时间
  3. 这两个字段先作为单 case metrics 上报，后续才会在 quality gate 中聚合成 `ttfb_p95_ms` 和 `total_latency_p95_ms`
- 汇总后由 `tests/support/quality_gate.py` 做：
  1. case 标准化
  2. 指标聚合
  3. baseline 对比
  4. `pass / warn / fail` 判级
  5. 输出 `agent_quality_report.json`、`agent_quality_summary.md` 与 terminal summary
- 当前边界要明确：
  1. `--quality-gate` 不开启时，这套上报不会生效
  2. 当前实现重点是统一判级与报告输出
  3. 当前 `gate_result=fail` 主要表示规则层判级失败；它本身不是另一套业务逻辑，只是给本地和 CI 的质量门禁消费

### 2.6.9 本次执行证据与 Quality Gate 边界（2026-08-01）

1. 两条 SSE 顺序/增量核心用例定向执行：`2 passed`。
2. 完整 `tests/integration/chat_stream/test_resilience.py -q`：`7 passed, 1 xfailed`。
3. 带 `--quality-gate` 的诊断执行没有功能用例失败，但报告为 `gate_result=fail`；直接原因是 `ttfb_p95_ms` 和 `total_latency_p95_ms` 相对现有 baseline 超过 severe regression 阈值。
4. 该 Gate 结果不能改写前两项 SSE 功能契约已经 `LANDED` 的事实；在 2026-08-01 时 integration profile 仍为 `NOT_WIRED`。后续 C0-2 只把两条经评审的确定性契约接入 PR，不使用该 performance diagnostic 决定 CI 成败。

### 2.6.10 C0-2 Stream Contract PR Check 证据（2026-08-10）

1. Head branch：`codex/verify-stream-contract-gate`。
2. Head commit：`44a0af58d56e9b872ee064a36b1a193d3a7f353c`。
3. PR 汇总页显示两个 `pull_request` Check 成功：
   - `PR Smoke Gate / Smoke Blocking Gate`：约 24 秒，显示 `Required`。
   - `PR Stream Contract Gate / Stream Contract Gate`：约 22 秒，未显示 `Required`。
4. Stream job 执行命令为：

   ```bash
   uv run python -m pytest tests/integration/chat_stream/test_resilience.py \
     -m "integration and blocking and not real_llm" -q
   ```

5. GitHub runner 结果为 `2 passed, 6 deselected, 3 warnings in 2.61s`。
6. 当前准确分类：两条目标 SSE 契约为 `LANDED + NON_BLOCKING PR Check`；user-stop、real LLM
   和其余未评审 resilience case 没有进入该 selection。
7. 该证据证明绿色 PR 接线，不证明失败会阻止合并或 Stream Check 已被设为 Required；Required
   决策属于 C0-6。C0-3 已在 workflow 中加入 JUnit 生成和 `if: always()` artifact 上传，并在
   本地验证 success/failure JUnit 内容。
8. commit `533d4a3...` 的 [Stream push run `32568350679`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/32568350679)
   和 upload step 均为 `success`；artifact `closed-loop-v1-stream-contract-junit-32568350679-1` 已具备
   id `9474672187`、digest 和 14 天 expiry。该证据验证 success upload。

### 2.6.11 C0-3 真实 failure Artifact 证据（2026-08-31）

1. [Stream failure run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451)
   在 revision `07ee89cbc1124c4430bbacdc213845fd73f78181` 上由确定性 pytest assertion 失败变红；
   test step 为 `failure`，`if: always()` upload step 为 `success`。
2. Artifact `closed-loop-v1-stream-contract-junit-33392294451-1`（id `9757933428`）为 1542 bytes，
   digest 为 `sha256:956e2a20c218ff9f2b9fc434accc7823680663039dccba701c9be77ec984d437`，服务端到期时间为
   `2026-09-14T12:33:13Z`。
3. Agent 已通过认证 API 下载 ZIP；本地 SHA256 与 GitHub digest 一致。包内只有
   `junit-stream-contract.xml`，解析为 `tests=2 / failures=1 / errors=0 / skipped=0`，可定位
   baseline nodeid、故障 assertion、`assert 1 == 2`、run 和 revision。
4. [恢复 run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083)
   在 revision `d6553a96f6987c5f58fdafddb99fc28e19c72eb0` 上重新成功；下载后的 JUnit 为
   `tests=2 / failures=0 / errors=0 / skipped=0`，当前代码已恢复 `round_end == 1`。
5. 该证据先关闭 C0-3 的真实 failed-run Artifact 缺口；用户后续明确继续后，与三次稳定绿色结果
   一起复用于 C0-4 正式验收。

### 2.6.12 C0-4 稳定性与恢复结论（2026-08-31）

1. 独立 Python 3.11 frozen test 环境中，目标 selection 连续三次均为
   `2 passed, 6 deselected`，nodeid 集合一致，无 flaky、XPASS、setup error 或选择漂移。
2. [Draft PR #2](https://github.com/tsukiyomu/NagaAgent-main/pull/2) 依次保留 isolation、intentional-red
   与 restore 三个证据 commit；初始 run `33392018497` 绿色、故障 run `33392294451` 红色、恢复 run
   `33392789083` 重新绿色。
3. 当前 branch/remote head 为 `d6553a96...`，源码断言已恢复为 `round_end == 1`；相对 `main` 只剩
   remote-memory fixture 隔离。当前完整 resilience suite 为 `7 passed, 1 xfailed`。
4. C0-4 为 `DONE`，但 Stream 继续是 `NON_BLOCKING`；PR #2 包含故障 commit 历史，保持 Draft，
   不应按普通 merge 进入 `main`。

### 2.6.13 C0-5 Traceability / Gate Record（2026-09-01）

1. [`C0-5 Gate Record`](../reports/closed-loop-v1-c0-5-2026-09-01.md) 已把本模块的两条 blocking
   SSE 风险连接到精确 nodeid、关键断言、真实/受控依赖、revision、GitHub run、JUnit Artifact、
   failure classification、恢复证据和当前 Gate 决定。
2. baseline case 对应正常 stream 的 content 顺序、单一 `round_end`、唯一 done、保存、finalize 与
   active cleanup；midstream case 对应部分输出后唯一 error terminal、无 done、不保存与 cleanup。
3. 分类边界已经固定：remote-memory `401` 是 `TEST_DEFECT` 类型的 fixture isolation gap；
   `assert 1 == 2` 是 controlled failure probe，不是产品缺陷；通过的 `degraded/tool_dispatch` 是
   expected midstream degradation，不应被报告层判成失败。
4. C0-5 当前 revision 复核仍精确收集 `2/8`；定向执行为
   `2 passed, 6 deselected, 3 warnings in 12.59s`，JUnit 为
   `tests=2 / failures=0 / errors=0 / skipped=0`。该本地结果没有重新定义既有 GitHub
   green/red/restored 证据。
5. C0-5 的结论是 decision material ready，而不是 merge enforcement ready；Stream 继续为
   `NON_BLOCKING`，Required status context 与 Owner 风险接受属于 C0-6。
6. `/docs/` 当前受 `.gitignore` 排除；本记录已同步到 shared workspace，但未自然发布为 GitHub
   仓库文档。

### 2.6.14 C0-6 remote-memory isolation decision（2026-09-01）

1. Repository Owner 选择 `A — DEFER_REQUIRED_PROMOTION`；`Stream Contract Gate` 保持
   `NON_BLOCKING`，Branch Protection / Ruleset 未修改。
2. remote memory 是 `/chat/stream` 回答前 RAG 召回路径的一部分，产品实现保持 `LANDED`；两条
   blocking SSE case 只在 fixture 中令 `get_remote_memory_client()` 返回 `None`，从而把失败含义限定为
   SSE lifecycle / protocol contract，而不是认证、网络或云服务状态。
3. 真实 remote-memory authentication、query 和 fallback 覆盖标为 `DELAYED`，未来由独立
   opt-in/integration 或 staging profile 负责；当前 Stream JUnit 不证明真实 memory 联通。
4. 当前证据分支复核为 `2 passed, 6 deselected, 3 warnings in 12.66s`，JUnit `2/0/0/0`；完整
   resilience 文件为 `7 passed, 1 xfailed, 3 warnings in 13.54s`。隔离尚需通过不含
   intentional-red 历史的干净 PR 进入 `main`。
5. Owner Decision Record 见
   [`closed-loop-v1-c0-6-2026-09-01.md`](../reports/closed-loop-v1-c0-6-2026-09-01.md)。

## 2.7 当前边界与非目标
- 当前为什么选 `/health` 而不是 `/health/full`
1. `/health` 符合 smoke 的“快、稳、离线可跑”
2. `/health/full` 会联动 `agentserver` 和多 Part 诊断链路，属于 integration
- 当前不覆盖：
1. `/health/full`
2. 真实 LLM 语义
3. 真实 tool loop 质量
4. 真实 telemetry / 落盘
5. 真实 websocket 端到端行为
6. 真实 MCP dispatcher 联调
7. 明确的 `user stop` 契约

## 2.8 后续扩展
- `p2_api` 后续最自然的扩展顺序：
1. 为前端 `chatStream` 接入 `AbortSignal`，并补齐 route generator cleanup 与 user-stop 回归
2. 将进程内性能字段迁移为 `first_chunk_ms`，真实网络 profile 才使用 `ttfb_ms`
3. `/health/full` integration
4. 更接近真实配置的协议兼容性验证
5. websocket / side-channel 更真实的收尾联调

## 2.9 业务 / mapping 解析
- `2.3.2` 里提到的 “side-channel / compression failure 不阻塞主链路结束”，本质上是在区分：
1. 主回答链路
2. 辅助治理或旁路协同链路
- 当前 `/chat/stream` 的主回答链路是：
1. 请求进入 `/chat/stream`
2. route 建立 SSE 响应并设置 conversation active
3. route 调用 `run_agentic_loop(...)`
4. loop 产出 `content / reasoning / tool_calls / tool_results / round_end`
5. route 消费这些事件并最终保存、finalize、回落 active flag
- 这条主链路的核心代码入口是：
1. `apiserver/routes/chat.py`
2. `apiserver/agentic_tool_loop.py`

### 2.9.1 什么是 `compression failure`
- `compression` 不属于 P2 路由本体，而属于 Part 3 Runtime 里的上下文治理。
- 具体是每轮 loop 开始前尝试执行 `compress_context(...)`。
- 业务含义：
1. 当上下文太大时，先压缩再继续本轮推理/工具调用
2. 如果压缩失败，不应该把整个 `/chat/stream` 主链路打崩
- 所以 `test_chat_stream_resilience_compress_failure_does_not_break_stream` 测到的是：
1. Part 3 Runtime 的 context orchestration failure
2. 经过 P2 route 外显为“流还能正常结束”

### 2.9.2 什么是 `side-channel`
- `side-channel` 不是主回答链路本身，而是围绕主链路附带发生的旁路动作、外部通知或副作用。
- 在当前项目里，至少可以分成 4 类：

| side-channel 类型 | 代码位置 | 对应业务功能 | 架构归属 |
|---|---|---|---|
| conversation lifecycle notify | `apiserver/routes/chat.py`、`apiserver/api_server.py` | 通知外部 `agent_server` 对话 started / ended | Part 2 出口治理，边界上触到 Part 7/8 |
| telemetry | `apiserver/routes/chat.py` | 首包、结束、错误埋点 | Part 8 Infra / Engineering |
| TTS / voice integration | `apiserver/routes/chat.py` | 流式文本转语音、轮次 flush | Part 7 Frontend / Voice |
| persistence | `apiserver/routes/chat.py` | 保存完整对话与日志 | Part 3/8 交界的副作用落盘 |

### 2.9.3 当前测试到底测了哪一个 `side-channel`
- 当前 resilience suite 里，“side-channel failure” 主要落地的是：
1. conversation lifecycle notify failure
- 对应用例：
1. `test_chat_stream_resilience_notify_failure_does_not_block_finalization`
- 这条用例的业务目标不是验证 notify 成功发到了远端，而是验证：
1. 就算 `_notify_conversation_event(...)` 失败
2. `/chat/stream` 仍然要 finalize
3. active flag 仍然要回落
4. 不应该把用户看到的主流式回复卡死

### 2.9.4 为什么这类测试仍然放在 `p2_api`
- 因为这些 failure 最终都是通过 `/chat/stream` 这个入口和出口语义暴露给用户的：
1. 流有没有断干净
2. finalize 有没有跑
3. 状态有没有收尾
- 所以虽然 `compression` 本体属于 Part 3，`telemetry` 属于 Part 8，`voice` 属于 Part 7，
  但它们一旦影响到“流有没有正常结束”，测试入口仍然最自然地落在 `p2_api`。

### 2.9.5 `fake loop` / `real loop` / `full workflow` 的区别
- 当前 testing 文档里的 `real_loop` 容易被误解成“真实 agentic tool workflow 全部跑通”，但实际上不是。
- 这 3 层更准确的区别如下：

| 层级 | 当前是否已落地 | 什么是真的 | 什么是假的/未覆盖 | 适合回答什么问题 |
|---|---|---|---|---|
| `fake loop` | yes | real app、real route、real finalize | `run_agentic_loop(...)` 整体被 fake/stub；不跑真实 loop 编排 | `/chat/stream` 最小协议面和 finalize 会不会被改挂 |
| `real loop` | yes | real `run_agentic_loop(...)` orchestration 外壳、real compression 分支、real route/loop 协同 | LLM 仍可 fake；真实 tool execution、真实 tool reinjection、真实 queue injection、真实 summary round 还没全覆盖 | route 和 loop 协同是否稳定；compression failure 是否会把流打崩 |
| `full workflow` | no | real route、real loop、real LLM、real tool path、真实多轮收敛 | 当前尚未系统落地为稳定测试层 | prompt / tool / context 变更会不会破坏完整 agent workflow |

- `real loop` 里的 `real` 主要指：
1. `run_agentic_loop(...)` 本身没有被 stub 掉
2. 轮次控制、停止条件、`round_end` 发射、上下文压缩调用这些 orchestration 控制流是真实代码
- `real loop` 里的 `not fully real` 主要指：
1. `get_llm_service()` 当前仍然可以被 fake
2. `execute_tool_calls(...)` 还没有作为完整 workflow 被系统覆盖
3. tool result reinjection、queue injection、连续失败收敛、`max_rounds` 后 summary round 也还没有作为完整主线测试闭环
- 所以当前 `real loop + fake LLM` 更准确的定位不是“真实 agentic tool workflow”，而是：
1. real orchestration shell
2. fake model output
3. partial workflow coverage
- 这也是为什么后续文档里，`agentic_tool_loop` 的主体建议仍然是 unit 层，而不是继续无限堆更多 route-level SSE 用例。
