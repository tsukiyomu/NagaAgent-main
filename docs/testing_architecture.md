# NagaAgent Testing Architecture

## 1. 测试目标与范围

### 1.1 需求/问题
- 当前仓库此前缺少可执行的 `tests/` 基础骨架，PR 缺少最小回归门禁。
- P2（统一 HTTP 接口层）是系统稳定性的第一入口，最容易被“功能改动顺带破坏”。
- 对 Agent 系统来说，`/chat/stream` 的终止与收尾最容易出问题（无结束事件、连接不收敛、请求悬挂）。

### 1.2 功能目标
- 建立第一版可落地的 PR 阻塞门禁（smoke 级别）。
- 在不改业务内部实现的前提下，覆盖 3 条最小闭环：
1. `/health`：服务可用底线。
2. `/chat`：非流式主链路可返回。
3. `/chat/stream`：流式存在终止事件，且连接可收尾。

### 1.3 核心策略
- 黑盒优先：只通过 P2 HTTP 接口验证，不进入内部模块重构。
- 稳定优先：测试中替换外部依赖（LLM、远程事件通知、工具 loop）为确定性 stub。
- 分层优先：先做 `smoke + blocking`，再扩展 `integration` 和 `unit`。
- 低侵入优先：仅新增测试与文档，不改变生产接口行为。

## 2. 测试组织方式

### 2.1 分层原则
- `smoke`：最小可用与门禁用例，必须离线可跑，优先覆盖系统“是否会被改挂”。
- `integration`：需要真实依赖或进程协同的验证（如 `agentserver`、真实 memory/RAG、真实工具执行）。
- `unit`：模块内逻辑单测（纯函数、状态机、编排分支、异常分支）。
- `fixtures`：跨层复用的样例、工厂、假对象与测试数据。

### 2.2 模块归属原则
- `p2_api`：HTTP 入口、响应协议、SSE 行为与路由门禁。
- `core_service`：会话管理、上下文装配、服务编排与基础中间层逻辑。
- `memory`：RAG 与记忆读写链路、召回策略与容错行为。
- `mcp_tools`：工具协议、工具发现、工具调度与调用结果处理。

### 2.3 运行分层与门禁关系
- PR blocking：`smoke and blocking`（离线、确定性、快速）。
- 独立流水线：`integration`（允许真实依赖，成本更高）。
- 本地快速回归：优先 `tests/smoke`，必要时按模块补跑指定 `unit`。

## 3. 当前实现快照

### 3.1 已落地范围总览
- 已实现层级：`smoke`（阻塞门禁）。
- 已覆盖模块：`p2_api`。
- 已落地文件：
1. `pytest.ini`
2. `tests/conftest.py`
3. `tests/smoke/test_p2_smoke.py`
- 当前重点：
1. 保证离线可执行与可重复。
2. 保证 `/chat/stream` 存在终止事件 `[DONE]`。
3. 保证 smoke 不引入真实外部副作用（LLM、远程通知、落盘、遥测）。

### 3.2 按层级 + 模块的当前状态

#### 3.2.1 smoke / p2_api
- 当前状态：`done`。
- 当前覆盖接口：`/health`、`/chat`、`/chat/stream`。
- 当前主流程定义：入口级最小闭环（服务可用、非流式返回、流式可收尾）。
- 当前断言重点：状态码、响应结构、`session_id`、SSE 终止事件 `[DONE]`。

#### 3.2.2 integration / p2_api
- 当前状态：`planned`。
- 目标内容：
1. `/health/full` 与 `agentserver` 联动。
2. 流式异常中断/超时下的 finalize 行为。
3. 接近真实配置下的协议兼容性验证。

#### 3.2.3 integration / memory
- 当前状态：`planned`。
- 目标内容：
1. 真实 RAG/memory 召回链路联调。
2. 召回失败、空召回、降级路径验证。
3. 记忆相关上下文拼装稳定性。

#### 3.2.4 unit / core_service
- 当前状态：`planned`。
- 目标内容：
1. 会话管理与消息装配分支单测。
2. 输入边界与异常处理单测。
3. 关键纯函数行为锁定。

#### 3.2.5 unit / agentic_tool_loop
- 当前状态：`planned`。
- 目标内容：
1. `max_rounds`、停止条件、失败收敛。
2. 工具结果格式化与注入逻辑。
3. 关键异常分支与幂等边界。

## 4. 当前主流程与覆盖边界

### 4.1 当前 smoke 的“主流程”定义
- 当前 smoke 覆盖的是 P2 入口层最小主流程闭环：
1. `/health`：服务可用底线。
2. `/chat`：非流式主链路可返回。
3. `/chat/stream`：流式存在终止事件且连接可收尾。

### 4.2 为什么当前选择 `/health` 而不是 `/health/full`
- `/health` 只验证 API 进程本地可用性与基础路由可访问，符合 smoke 的“快速、稳定、离线可跑”要求。
- `/health/full` 会联动 `agentserver` full health，依赖跨进程/外部协同，不适合作为 V1 阻塞门禁。
- 因此 `/health/full` 归入 integration 层。

### 4.3 当前覆盖到的链路层级
- 已覆盖：HTTP 入口可达、基础请求处理、最小协议返回、流式终止语义。
- 未覆盖：真实外部依赖参与下的完整业务全链路。

### 4.4 当前明确不覆盖的内容
- 不测 `/health/full`（依赖 `agentserver`）。
- 不测真实 LLM 语义质量。
- 不测真实 tool loop 多轮工具编排正确性。
- 不测真实落盘与 telemetry 上报。

## 5. 当前执行路径

### 5.1 测试执行链路
`pytest -> conftest.py -> client fixture -> monkeypatch -> 调接口 -> 断言`

### 5.2 当前执行路径与业务流程映射
- `/health`
1. `TestClient` 发起 GET。
2. 断言进程可用与基础健康字段存在。
- `/chat`
1. `client.post("/chat")` 进入非流式主链路。
2. `get_llm_service` 被替换为 `_DummyLLMService`，固定返回 `smoke-chat-ok`。
3. 断言 `status=success`、`response` 固定值、`session_id` 存在。
- `/chat/stream`
1. `client.stream("POST", "/chat/stream")` 建立 SSE。
2. `run_agentic_loop` 被替换为 `_fake_run_agentic_loop`，固定输出 `content -> round_end -> [DONE]`。
3. 断言流式 `content-type`、存在 `session_id`、存在终止事件 `[DONE]`。

## 6. 运行与筛选规则

### 6.1 Marker 规则
- `smoke`：最小门禁测试。
- `blocking`：PR 阻塞级测试，默认必须通过。
- `integration`：依赖真实外部服务/进程，可在独立流水线或手动触发执行。

### 6.2 本地运行方式
```bash
# 运行阻塞 smoke
python -m pytest tests/smoke -m "smoke and blocking" -q

# 运行全部 smoke
python -m pytest tests/smoke -m "smoke" -q
```

### 6.3 CI 阻塞范围
- 目标阻塞范围：`smoke and blocking`。
- 质量目标：确保 P2 入口基础可用与流式可收尾。
- 当前状态：已接入 PR 门禁 workflow（`.github/workflows/pr-smoke-gate.yml`），默认执行 `smoke and blocking`。
- 阻塞生效前提：在仓库分支保护规则中，将该 workflow 对应检查设置为 required check。

### 6.4 依赖策略
- `smoke/blocking`：必须离线可跑，不依赖真实 LLM、真实 memory、真实 agentserver。
- `integration`：允许真实依赖，单独分层执行，不阻塞基础开发流。

### 6.5 PR CI Gate 如何起作用
- workflow 文件：`.github/workflows/pr-smoke-gate.yml`。
- 触发时机：
1. `pull_request` 到 `main/master`。
2. `push` 到 `main`（用于主分支持续验证）。
3. `workflow_dispatch`（手动触发）。
- 收敛机制：
1. 使用 `concurrency`，同一分支新提交会取消旧任务，避免重复排队。
2. 这样 PR 上显示的始终是“最新提交”的门禁结果。
- 任务执行链路：
1. `actions/checkout@v4` 拉取代码。
2. `actions/setup-python@v5` 固定 Python 3.11。
3. `astral-sh/setup-uv@v4` 安装 `uv`。
4. `uv sync --frozen --group test` 安装锁定依赖（含测试依赖组）。
5. `uv run python -m pytest tests/smoke -m "smoke and blocking" -q` 执行阻塞门禁测试。
- 判定逻辑：
1. 只要任一步失败（安装失败/测试失败），job 状态即 `failed`。
2. job 成功时状态为 `success`，代表当前 PR 在 smoke 粒度通过门禁。
- 与分层测试策略的关系：
1. CI 门禁只跑 `smoke and blocking`，保证速度和稳定性。
2. `integration` 保留给独立流水线，避免把高成本依赖引入 PR 快速回路。

### 6.6 门禁失败时怎么看
- 先看失败阶段：
1. 依赖安装阶段失败：优先检查 `uv.lock`、测试依赖组、Python 版本。
2. pytest 阶段失败：优先看 `tests/smoke/test_p2_smoke.py` 三条用例哪条失败。
- 常见失败归因：
1. `/health` 失败：应用启动或路由注册问题。
2. `/chat` 失败：`conftest.py` 的 LLM stub 替换失效或响应结构变化。
3. `/chat/stream` 失败：SSE 协议格式变化、终止事件 `[DONE]` 缺失、`run_agentic_loop` patch 失效。
- 定位建议：
1. 先本地执行同一命令复现：`python -m pytest tests/smoke -m "smoke and blocking" -q`。
2. 再比对 `tests/conftest.py` 中 patch 目标符号是否仍与生产代码引用路径一致。

## 7. 覆盖矩阵

### 7.1 当前覆盖矩阵
| 测试层级 | 模块 | 用例 | 覆盖流程 | 当前断言 | 非目标 |
|---|---|---|---|---|---|
| smoke | p2_api | `test_health_smoke` | API 进程可用 -> 路由可访问 -> 健康状态可读 | `200`、`status=healthy`、`agent_ready` 存在 | 不验证 `agentserver` 深层依赖 |
| smoke | p2_api | `test_chat_non_stream_smoke` | 请求入站 -> 会话创建 -> 非流式响应封装 | `200`、`status=success`、固定回复、`session_id` 存在 | 不验证真实 LLM 语义与 RAG 质量 |
| smoke | p2_api | `test_chat_stream_smoke_has_terminal_event` | SSE 建连 -> 事件输出 -> 终止收尾 | `200`、`content-type=text/event-stream`、包含 `session_id`、包含 `[DONE]` | 不验证真实多轮工具编排与实时语音行为 |

### 7.2 后续扩展矩阵预留
| 测试层级 | 模块 | 状态 | 计划覆盖 |
|---|---|---|---|
| integration | p2_api | planned | `/health/full` 联动、流式异常 finalize、一致性回归 |
| integration | memory | planned | 真实召回链路、降级路径、稳定性回归 |
| unit | core_service | planned | 会话/上下文装配关键分支与异常路径 |
| unit | agentic_tool_loop | planned | 收敛逻辑、停止条件、工具失败幂等边界 |

## 8. 测试基座实现说明

### 8.1 `tests/conftest.py` 的职责
- 提供共享 `client` fixture 作为 smoke 统一入口。
- 通过 `monkeypatch` 将高波动依赖替换为确定性实现。
- 保证 smoke 离线、稳定、可重复执行。

### 8.2 共享 client fixture
- `client(monkeypatch)` 在每个测试开始时构建 `TestClient(app)`。
- `with TestClient(app)` 确保 FastAPI 生命周期正确启动与回收。
- `yield test_client` 将统一客户端交给各 smoke 用例复用。

### 8.3 依赖替换矩阵
| 被替换对象 | 替身实现 | 影响接口 | 目的 |
|---|---|---|---|
| `_build_agent_prompt_context` | `lambda -> None` | `/chat`、`/chat/stream` | 移除 agent 特定上下文分支，降低环境差异 |
| `build_system_prompt` | 固定字符串 `SMOKE_SYSTEM_PROMPT` | `/chat`、`/chat/stream` | 固定系统提示词，避免内容漂移 |
| `build_context_supplement` | 固定字符串 `SMOKE_SUPPLEMENT` | `/chat`、`/chat/stream` | 固定补充上下文，降低抖动 |
| `_supports_function_calling` | `lambda -> False` | `/chat`、`/chat/stream` | 固定到非原生 FC 路径，避免动态 schema 影响 |
| `get_llm_service` | `_DummyLLMService` | `/chat` | 固定非流式回复 |
| `run_agentic_loop` | `_fake_run_agentic_loop` | `/chat/stream` | 固定 SSE 协议链路 |
| `_update_proactive_activity_silent` | `_noop_async` | `/chat`、`/chat/stream` | 去掉后台外部副作用 |
| `_notify_conversation_event` | `_noop_async` | `/chat/stream` | 去掉远程事件副作用 |
| `_save_conversation_and_logs` | `lambda: None` | `/chat`、`/chat/stream` | 避免真实落盘 |
| `emit_telemetry` | `lambda: None` | `/chat`、`/chat/stream` | 避免遥测副作用 |

### 8.4 Stub 行为定义
- `_DummyLLMService`：
1. 保持与生产代码一致的方法签名：`chat_with_context_and_reasoning(...)`。
2. 固定返回 `LLMResponse(content="smoke-chat-ok", reasoning_content="")`。
3. 目标是让 `/chat` 断言稳定且不依赖真实模型。
- `_fake_run_agentic_loop`：
1. 保持与真实 `run_agentic_loop(...)` 一致的入参签名。
2. 固定输出三段 SSE：`content -> round_end -> [DONE]`。
3. 目标是最小化验证 `/chat/stream` 的终止语义与可收尾性。

### 8.5 隔离与清理语义
- `monkeypatch` 仅在测试生命周期内生效，测试结束自动恢复原函数。
- `TestClient` 上下文关闭时自动执行应用清理，避免跨用例污染。
- smoke 请求默认采用 `temporary=true`（在测试请求中指定），降低持久化状态影响。
- 通过 patch `chat_routes` 命名空间中的符号，确保命中路由模块实际引用对象，而不是只修改定义源头。

## 9. 后续扩展路线

### 9.1 integration 扩展
- 增加 `/health/full` 与 `agentserver` 联动测试。
- 增加真实 memory/RAG 联调验证。
- 增加真实 tool loop（最小可执行工具链）联调测试。

### 9.2 unit 扩展
- 对 `message_manager`、context assembly、agentic loop 分支做模块级单测。
- 引入更细粒度异常分支和退化路径验证（超时、空返回、工具失败重试等）。

### 9.3 deeper integration 扩展
- 将覆盖矩阵扩展到 `integration + memory`、`unit + agentic_tool_loop` 等组合。
- 引入流式异常注入回归（中断、慢响应、最终收尾一致性）。
- 逐步接入性能/成本回归指标（如 TTFB、P95、token cost）的自动报告与门禁。

## 10. 模块级说明索引

### 10.1 p2_api
- `docs/testing/p2_api.md`（待补充）

### 10.2 conftest / fixtures
- `docs/testing/conftest_notes.md`（待补充）

### 10.3 memory
- `docs/testing/integration_memory.md`（待补充）

### 10.4 agentic_tool_loop
- `docs/testing/unit_agentic_loop.md`（待补充）
