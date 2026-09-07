# NagaAgent Testing Architecture

> **Migration status（2026-09-07）：当前测试基线已复验，历史细节仍 `PARTIAL`。**
> `981821be` 完成 MIG-3/MIG-4：179 passed、1 skipped、2 xfailed，另有 12 subtests passed；
> Smoke / Stream 本地各通过三次。当前模块映射、配置隔离、报告和 CD 边界见
> [新测试基线](upstream-testing-baseline.md)，当前 CI 事实见 [CI 第 0 节](ci-pr-gate.md#0-当前-upstream-分支结论)。
> 下方原模块说明保留供查阅；旧运行时长、PR Required、C0 结果及实施优先级仍属于原 revision，
> 未宣布全部历史架构逐行核验完成。Langfuse runtime 未接回，远端新 CI 未验证。

## 0. 阅读说明

### 0.1 文档定位
- 这是测试体系的总览文档，用于定义范围、分层、门禁、当前已落地内容与后续扩展方向。
- 当前文档以“已落地能力 + 当前 gaps + 后续扩展”三部分组织，而不是执行前计划稿。

### 0.2 阅读顺序
1. 先读 `1. 全局测试原则`。
2. 再读 `2. p2_api 模块`（当前优先模块）。
3. 如果要看 `p2_api` 的详细用例、执行链路和业务映射，再读 [`part-02-api-stream.md`](part-02-api-stream.md)。
4. 如果要继续补 loop 工作流门禁，再读 [`part-04-agentic-tool-loop.md`](part-04-agentic-tool-loop.md)。
5. 如果要看 Langfuse / observability 的当前接入和测试边界，再读 [`langfuse-observability.md`](langfuse-observability.md)。
6. 如果要看 `Quality Gate Summary` 的正式模块说明，再读 [`part-08-quality-gate-summary.md`](part-08-quality-gate-summary.md)。
7. 如果要看 Agent Workflow Golden Cases 的任务契约和业务 mapping，再读 [`part-11-golden-cases.md`](part-11-golden-cases.md)；后续计划见 [`../plans/nagaagent-final-testing-plan.md`](../plans/nagaagent-final-testing-plan.md)，历史 Golden 计划保存在 [`../plans/suspend/golden-cases-implementation.md`](../plans/suspend/golden-cases-implementation.md)。
8. 如果只想快速知道 Closed Loop V1 现在做到哪里，再读 [`../CURRENT_PROGRESS.md`](../CURRENT_PROGRESS.md)。
9. 如果要看当前 GitHub Actions 和 PR required check，再读 [`ci-pr-gate.md`](ci-pr-gate.md)。
10. 如果要从 SSE 风险追踪到 nodeid、run、Artifact、failure classification 和当前决定，再读 [`../reports/closed-loop-v1-c0-5-2026-09-01.md`](../reports/closed-loop-v1-c0-5-2026-09-01.md)。
11. 如果要看 C0-6 Owner 的暂缓晋升决定与 remote-memory `DELAYED` 边界，再读 [`../reports/closed-loop-v1-c0-6-2026-09-01.md`](../reports/closed-loop-v1-c0-6-2026-09-01.md)。
12. 如果要面向简历、面试或开源作品展示，再读 [`../showcase/portfolio-summary.md`](../showcase/portfolio-summary.md)。
13. 最后看 `8. CI / PR Gate` 与 `9. 覆盖总表`。

### 0.3 当前已落地模块概览
- P0 可复现基线已完成：测试依赖、失效 monkeypatch、marker、artifact 边界和干净环境执行均已收口；2026-07-28 Run Record 由用户临时确认 `VERIFIED`，但不代表当前 revision 已复验。
- 已有基础：`smoke / p2_api`。
- 已新增：`integration / p2_api` 的 SSE resilience 回归；P1 已固定正常/异常 SSE 顺序、唯一 terminal、三段 `content` 拼接与保存 spy 一致性；user stop 仍为 `XFAIL_GAP`。
- 已新增：独立 `Stream Contract Gate`，在真实 `pull_request` 上执行两条经评审的确定性 SSE 契约；当前为 `NON_BLOCKING` PR Check。
- 已完成：Closed Loop V1 C0-1～C0-6；Owner 选择暂缓 Required 晋升，Stream 保持 `NON_BLOCKING`。remote memory 仍是产品能力，在两条 SSE lifecycle 契约内隔离，真实集成验证标为 `DELAYED`。
- 已新增：1 条 opt-in 的 `real_llm` stream smoke。
- 已新增：`unit / agentic_tool_loop` 的首批工作流单测，已覆盖收敛、dispatch、compression、message injection、failure attribution。
- 已新增：`unit / observability` 的 Langfuse helper 单测，已覆盖 generation / tool / session 传播边界。
- 已新增：`quality_gate_summary` v1，已通过 pytest hook 聚合 `quality_gate_case` payload，输出 JSON / Markdown / terminal summary，并支持 baseline compare 与 Allure 展示边界。
- 规划中：`core_service`、`memory`、`mcp_tools`，以及更真实的 `staging` 运行模式。

## 1. 全局测试原则

### 1.1 测试目标与范围
- 建立面向 Agent Workflow 的 Pytest 分层回归体系。
- 建立 PR CI Gate，先守住 `/health`、`/chat`、`/chat/stream` 的可用性底线。
- 优先防止流式链路回归：卡死、不收尾、重复 finalize、不落库。
- 在 `p2_api` 基础闭环之外，把当前已经成为系统稳定性关键点的两条链路正式纳入测试目标：
1. `agentic_tool_loop`
   - 收敛逻辑
   - dispatch contract
   - 消息注入
   - 上下文压缩
   - failure attribution
2. `observability / Langfuse`
   - generation observation 写回
   - tool observation 写回
   - `session_id` 传播
   - side-channel 失败不阻断主链路

### 1.2 分层原则
- `smoke`：最小可用与阻塞门禁，必须离线可跑。
- `integration`：真实路由 + 可控替身，验证流程协作与协议一致性。
- `unit`：模块内状态机、分支与收敛逻辑。
- `fixtures`：跨层复用的 client、stub、故障注入与清理。

### 1.3 门禁与运行原则
- PR blocking 当前只跑同时带 `smoke` 和 `blocking` marker 的测试；Draft PR 页面显示 `Smoke Blocking Gate` 为 `Required`。
- integration 中两条经评审的 SSE 契约通过独立 `Stream Contract Gate` 在 PR 上运行，但当前为 `NON_BLOCKING`。
- unit 作为快速反馈层，优先覆盖收敛与边界逻辑。

### 1.4 通用测试基座
- `pytest.ini`：统一入口、marker、筛选。
- `tests/conftest.py`：共享 `TestClient(app)` 与基础 monkeypatch。
- `tests/support/*`：跨模块复用的测试辅助函数、fake、stub 与归因工具。
- 规则：先稳可重复，再逐步提高真实性。

## 2. p2_api 模块

- 这一节保留测试总纲级定义；`2.1-2.9` 的详细展开已单独抽到 [`part-02-api-stream.md`](part-02-api-stream.md)。

### 2.1 模块职责与范围
- 目标业务：Part 2 API Layer（统一 HTTP 接口 + streaming 入口）。
- 主风险点：`/chat/stream` 的 SSE 协议与 finalize 生命周期。

### 2.2 当前已落地范围

#### 2.2.1 smoke / p2_api
- `/health`
- `/chat`
- `/chat/stream`

#### 2.2.2 integration / p2_api
- 当前已落地首批 `/chat/stream` resilience 回归，覆盖：
1. 正常流满足 `session_id -> status+ -> content+ -> round_end -> [DONE]`，且 `[DONE]` 唯一、位于末尾。
2. 三个有序 `content` 事件可以精确拼接，并与 persistence spy 的保存入参一致。
3. midstream exception 以唯一、末尾 `error` 可诊断结束，且不再出现 `[DONE]`。
4. tool error 事件不阻塞流式终止。
5. notify failure / compression failure 不阻塞 finalize。
6. empty output 仍然收尾。
7. user stop 已有 `xfail` executable contract，但取消传播和 cleanup 契约尚未实现。

### 2.3 当前主流程定义

#### 2.3.1 smoke 主流程
- `pytest -> conftest -> TestClient(app) -> 调 /health /chat /chat/stream -> 断言`

#### 2.3.2 integration 主流程
- `real /chat/stream route`
- `+ fake/stub loop 或 fake LLM`
- `+ SSE 协议事件序列断言`
- `+ finalize 清理断言`
- `+ 必要的 save 调用次数观察`

### 2.4 用例与断言
- `test_health_smoke`：服务可用底线。
- `test_chat_non_stream_smoke`：非流式主链路可返回。
- `test_chat_stream_smoke_has_terminal_event`：流式必须可收尾。
- SSE 回归：正常顺序、多 `content` 拼接、midstream exception、tool error、compression failure、notify failure、empty output；user stop 仍为 `XFAIL_GAP`，整体 timeout 尚未落地。

### 2.5 测试执行链路
- smoke：离线稳定、快速门禁。
- integration：路由真实、依赖可控、关注协议与生命周期。

### 2.6 依赖替换与故障注入
- 可替：LLM、tool dispatch、telemetry、notify、save（根据测试目标分层替换）。
- 不替：P2 路由核心控制流、SSE 输出通道、finalize 主路径。

### 2.7 当前边界与非目标
- 暂不把 `/health/full` 放入 blocking。
- 暂不验证真实 LLM 语义质量。
- 暂不在 P2 测试中做完整工具生态 E2E。

### 2.8 当前剩余未落地项
- P1 前两项已经 `LANDED`，当前剩余：
1. 前端 `AbortSignal` 与服务端 generator cleanup。
2. `final_status=cancelled`、finalize/cleanup 幂等和部分响应保存规则。
3. timeout、重复 finalize、客户端断开等生命周期矩阵。
4. 进程内 `first_chunk_ms` 与真实网络 `ttfb_ms` 的指标口径分离。
- 当前优先级和后续状态以 [`../plans/sop-compiler-runtime-practical-roadmap.md`](../plans/sop-compiler-runtime-practical-roadmap.md) 为准；历史进度表保存在 [`../plans/suspend/`](../plans/suspend/README.md)。

### 2.9 业务映射说明
- Side-channel 指：通知、遥测、持久化、压缩等旁路能力。
- 测试目标：side-channel 失败不能阻塞主链路收尾。
- real loop 指：走真实 `run_agentic_loop` 编排路径；不等于真实外部工具全量联调。

## 3. core_service 模块

### 3.1 模块职责与范围
- 会话管理、消息装配、上下文注入、基础服务编排。

### 3.2 当前状态
- `planned`

### 3.3 计划覆盖点
- 输入边界与异常处理。
- message/context 组装稳定性。
- 关键纯函数行为锁定。

### 3.4 预期测试层级
- `unit` 为主，必要时 `integration` 补链路。

## 4. agentic_tool_loop 模块

### 4.1 模块职责与范围
- 多轮循环收敛、停止条件、工具失败降级、summary 回合。
- 这一节源自现已暂停的 [`../plans/suspend/agent-workflow-gate-strategy.md`](../plans/suspend/agent-workflow-gate-strategy.md) 第 1 个计划：`Tool Loop State Regression / 状态机门禁`；当前优先级由 active roadmap 管理。
- `Golden Cases` 与 `Quality Gate Report` 属于后两个计划，不在这个模块里展开。

### 4.2 当前状态
- `implemented (with executable gaps tracked in tests/docs)`
- 当前已落地文件：
1. `tests/unit/agentic_tool_loop/test_loop_convergence.py`
2. `tests/unit/agentic_tool_loop/test_loop_message_injection.py`
3. `tests/unit/agentic_tool_loop/test_loop_tool_dispatch.py`
4. `tests/unit/agentic_tool_loop/test_loop_failure_attribution.py`
5. `tests/unit/agentic_tool_loop/test_loop_context_compression.py`
- 当前共享 support：
1. `tests/support/agentic_tool_loop_helpers.py`
2. `tests/support/failure_attribution.py`
- 当前策略：直接跑真实 `run_agentic_loop(...)` 编排路径，但把 LLM、queue、compression、具体工具执行替换为可控替身。

### 4.3 当前覆盖与后续覆盖点
- 当前已覆盖：
1. `max_rounds`、停止条件、失败收敛。
2. tool timeout/error 结果下的 summary 收敛。
3. 工具调用/结果注入幂等性。
4. text tool-call 与 native function-call 两条路径的 dispatch contract 对齐。
5. `mcp` / `openclaw` / `tool` / `naga_control` 四类 dispatch 分支路由。
6. queue message 注入时机与“只注入一次”的稳定性。
7. compression SSE 事件透传，以及 summary round 之前的第二次 compression pass。
8. duplicate `tool_call_id` 跨轮去重已形成可执行 gap（`xfail`），等待 runtime 显式支持。
9. 最小 failure attribution contract 与显式 stage override。
10. loop 内 `tool_call_normalize`、`tool_result_injection` stage override 回归。
- 当前仍未覆盖：
1. 真实 MCP / OpenClaw 工具联调。
2. 更真实的 context assembly / memory 参与下的多轮行为。
3. route 层 finalize 与 loop 层状态联动。
- 当前明确需要做的门禁项：
1. 把 loop 工作流测试正式收口成“状态机门禁”，而不是继续堆工具观测。
2. 继续补更完整的 deterministic failure-stage regression（超出现有 override 样例）。
3. 在文档中固定状态转移表、硬断言集合和 failure attribution 最小 schema，作为后续回归补点基线。
4. 保持 `real tool integration`、`memory/context`、`route-finalize` 跨层问题仍在后续 integration 范围，不混入当前 stub gate。
5. 先补 deterministic 的 loop contract，再考虑 route+loop 跨层联测；不要直接跳到真实 MCP / OpenClaw 联调。

### 4.4 状态转移测试（已部分落地）
- 当前已落地的状态转移断言围绕 `round_start -> tool_dispatch -> tool_result_injected -> next/stop/summary` 展开，具体包括：
1. 无可执行 tool call 时立即停止，不进入 dispatch。
2. 连续两轮全失败时，提前进入 summary round，而不是一直等到 `max_rounds`。
3. 到达 `max_rounds` 后若仍有 tool call，下一轮必须进入 `tools=None` 的 summary round。
4. 工具 timeout 结果必须被标准化为 error，并最终收敛到 summary round。
5. native tool result 注入后，下一轮 messages 中 assistant/tool 成对出现且仅出现一次。
6. queue message 必须在下一轮 LLM 调用前注入，并且只注入一次。
7. 多轮 tool result 注入时，每个唯一 `tool_call_id` 都会在后续 history 中保留且只保留一份。
8. compression 事件会在 round 前透传，summary round 前会再执行一次 compression。
9. duplicate `tool_call_id` 跨轮去重当前仍是 `xfail` executable gap，用例先保留契约。
- 需要继续固定成门禁的状态转移表见：[`part-04-agentic-tool-loop.md`](part-04-agentic-tool-loop.md)。

### 4.5 失败归因字段（已部分落地）
- 归因字段定义仍保持为：`llm_output_parse` / `tool_call_normalize` / `tool_dispatch` / `tool_result_injection` / `context_assembly` / `summary_round` / `finalize`。
- `tests/support/agentic_tool_loop_helpers.py` 的作用可以简单理解为：
1. 提供 loop 单测共享的 fake LLM、queue stub 与 SSE 编解码 helper。
2. 把重复的测试脚手架沉到 `tests/support`，避免在每个 loop 用例文件里重复定义。
- 这层 helper 不改变被测语义，只负责让测试输入更稳定、断言更集中。
- `tests/support/failure_attribution.py` 的两个核心函数可以简单理解为：
1. `build_failure_attribution`：把测试现象（例如 stream 文本、finalize/save/active 等观察值）整理成标准归因报告。
2. `assert_failure_attribution_shape`：检查这份归因报告是否满足统一 schema（字段齐全、结构合法、可比较）。
- 这些 `tests/support` 能力都不绑定单一模块；当前已同时服务于 `p2_api` 与 `agentic_tool_loop` 回归。
- 当前已新增最小归因辅助：
1. `tests/support/failure_attribution.py`：构造稳定的 `case_id / final_status / failure_stage / rounds / tool_call_count / summary_triggered / unhandled_exception` 结构。
2. `test_loop_failure_attribution.py`：验证 success、dispatch error、summary round 三类 loop 输出都能投影成稳定归因记录。
3. `tests/unit/p2_api/test_failure_attribution.py`：验证 `llm_output_parse`、`tool_result_injection`、`context_assembly`、`summary_round` 等显式 stage override 的 schema 稳定性。
4. `test_loop_failure_attribution.py`：新增 `tool_call_normalize`、`tool_result_injection` 的 loop 级 stage override 回归。
- 当前目的不是接外部 tracing 平台，而是先把 CI 可比对的最小 failure attribution contract 固定下来。
- 推荐的后续方向不是接 Langfuse 式平台，而是继续补 deterministic 的 failure-stage regression cases。
- 当前建议的优先级是：
1. 先补更多 loop 内 deterministic failure-stage case（现有已覆盖 `tool_call_normalize`、`tool_result_injection`）。
2. 再补 1-2 条 route + loop 跨层联测，验证收敛结果能正确外显到 `/chat/stream`。
3. 最后才考虑真实 `MCP / OpenClaw` 联调与更重的 `memory/context` 参与路径。

## 5. memory 模块

### 5.1 模块职责与范围
- RAG 召回、记忆读写、空召回/降级路径。

### 5.2 当前状态
- `planned`

### 5.3 计划覆盖点
- integration 下真实召回链路。
- 召回失败与降级行为稳定性。

## 6. mcp_tools 模块

### 6.1 模块职责与范围
- tool schema、tool discover、dispatcher 调用、结果规范化。

### 6.2 当前状态
- `planned`

### 6.3 计划覆盖点
- 工具契约测试。
- dispatcher 返回结构一致性。
- 工具失败/超时/幂等边界。

## 7. conftest / fixtures 测试基座模块

### 7.1 基座职责
- 提供统一 `client fixture`。
- 提供跨用例稳定的 patch 层与清理语义。
- 提供 `tests/support` 下可跨文件复用的 helper / fake / stub。

### 7.2 共享 client fixture
- 使用 `TestClient(app)` 在测试进程内跑真实 FastAPI 路由，不启动独立 uvicorn 端口。

### 7.3 依赖替换矩阵（基线）
- `get_llm_service` -> 可控 fake。
- `run_agentic_loop` -> 可控 fake（或保留 real）。
- notify/telemetry/save -> 可观测替身。
- `tests/support/agentic_tool_loop_helpers.py` -> 共享 `ScriptedStreamLLM`、queue stub、SSE helper。

### 7.4 隔离与清理语义
- monkeypatch 仅在测试生命周期生效。
- queue active flag 在用例前后做清理，避免状态泄漏。

## 8. CI / PR Gate 模块

### 8.1 当前门禁目标
- 当前使用两个独立 workflow 运行离线、确定性测试：`smoke and blocking` 与两条
  `integration and blocking and not real_llm` SSE 契约。
- `Smoke Blocking Gate` 当前显示为 `Required`；`Stream Contract Gate` 已完成 PR 接线，但当前为
  `NON_BLOCKING`，是否升级为 Required 由后续人类评审决定。

### 8.2 workflow 触发条件
- `pull_request`：目标分支为 `main` 或 `master`。
- `push`：推送到 `main`。
- `workflow_dispatch`：手动触发。

### 8.3 执行链路
- `.github/workflows/pr-smoke-gate.yml`
- checkout -> Python 3.11 -> setup uv -> `uv sync --frozen --group test`
  -> `pytest tests/smoke -m "smoke and blocking"` -> 根据退出码判定 job 通过/失败。
- `.github/workflows/pr-stream-contract-gate.yml`
- checkout -> Python 3.11 -> setup uv -> `uv sync --frozen --group test`
  -> `pytest tests/integration/chat_stream/test_resilience.py -m "integration and blocking and not real_llm"`
  -> 根据退出码判定 job 通过/失败。

### 8.4 本地复现方式
- `uv run python -m pytest tests/smoke -m "smoke and blocking" -q`
- `uv run python -m pytest tests/integration/chat_stream/test_resilience.py -m "integration and blocking and not real_llm" -q`

### 8.5 与测试分层关系
- blocking 只放低成本高确定性用例。
- 当前只有两条经评审的 integration SSE 契约进入 PR Check，并且暂不阻塞 PR；同文件其他 6 条
  用例仍被 selection 排除。
- 2026-08-10 的 Draft PR 证据显示 Smoke 为 `Required`、Stream 为 `NON_BLOCKING`。绿色 job
  本身不自动证明 Stream 失败会阻止合并。
- 当前 workflow 和 Branch Protection 说明见
  [`ci-pr-gate.md`](ci-pr-gate.md)。

#### 8.5.1 C0-5 Traceability / Gate Record

- C0-5 已在 [`closed-loop-v1-c0-5-2026-09-01.md`](../reports/closed-loop-v1-c0-5-2026-09-01.md)
  建立单一追溯入口，把正常 SSE、midstream exception、remote-memory isolation 和 intentional-red
  分别连接到 nodeid、断言、dependency profile、revision、run、Artifact、classification 与当前决定。
- 当前技术结论是两条 SSE case 的稳定性、归因和失败证据已可供 Owner 评审；这不是 Required 授权。
- C0-5 没有修改 workflow、Branch Protection、Ruleset 或 PR 状态；Stream 继续为 `NON_BLOCKING`，
  C0-6 负责明确选择晋升 Required、保持 Non-blocking 或暂缓。
- 当前 `/docs/` 被 `.gitignore` 忽略，因此 Gate Record 与本 architecture 同步是 shared-workspace
  记录，尚未自然发布到 Git/GitHub；本状态不能被写成已经形成远端版本化审计档案。

#### 8.5.2 C0-6 Owner 决定与 remote-memory 边界

- Owner 于 2026-09-01 选择 `A — DEFER_REQUIRED_PROMOTION`；Closed Loop V1 的证据与人类决定闭环
  为 `VERIFIED`，但 Stream Gate 继续是 `NON_BLOCKING`，没有修改 GitHub Ruleset / Branch Protection。
- remote memory 是 NagaAgent 的正式 RAG/记忆能力，产品实现保持 `LANDED`；当前 fixture 隔离只服务于
  SSE 生命周期测试的确定性和失败归因，不代表删除或否定该能力。
- 真实 remote-memory 认证、云端查询与回退验证标为 `DELAYED`，未来应进入独立 opt-in/integration
  或 staging profile；不得把当前两条 SSE 契约的绿色结果写成真实 memory 联通证据。
- 完整 Owner Decision Record 见
  [`closed-loop-v1-c0-6-2026-09-01.md`](../reports/closed-loop-v1-c0-6-2026-09-01.md)。

### 8.6 Allure 展示层定位
- `Allure` 更适合作为测试体系的横切展示层，而不是某个单独 gate 模块的一部分。
- 它服务的对象不只包括 `quality gate summary`，还包括：
1. `p2_api` 的 smoke / resilience 结果
2. `agentic_tool_loop` 的 unit / failure attribution 结果
3. `real_llm` smoke 结果
4. 后续可能接入的 `golden cases` 或其他 integration 层结果
- 因此在测试体系里，`Allure` 的位置更接近：
1. 汇总展示入口
2. 测试结果浏览层
3. 报告附件承载层

### 8.7 Allure 当前边界
- `Allure` 当前不应承担：
1. baseline 存储中心
2. gate 规则定义中心
3. Langfuse 替代角色
4. 自定义 dashboard 平台
- 当前更合理的分工是：
1. `JSON / Markdown / terminal summary` 负责规则层真相源
2. `part-08-quality-gate-summary.md` 负责判级规则与报告契约
3. `Allure` 负责展示这些结果，而不是重新定义这些结果

## 8.8 找工作导向的最小闭环

当前测试体系可以对外收敛成 `Deterministic Agent Workflow Quality Gate for Tool-Using LLM Agents`。这不是完整线上 E2E 平台，而是一个以灰盒回归为主的最小质量闭环：

1. `PR Smoke Gate`：用离线、确定性的 `/health`、`/chat`、`/chat/stream` 守住 Required PR 基线。
2. `PR Stream Contract Gate`：保留真实 FastAPI route，用 fake loop 固定正常/异常 SSE 终止协议；当前是 `NON_BLOCKING` PR Check。
3. `SSE Resilience Integration`：继续承载未进入 PR selection 的 route/loop、compression、notify、empty output 与 user-stop gap。
4. `Agentic Loop State Gate`：保留真实 `run_agentic_loop(...)`，用 fake LLM / queue / tool / compression 锁定收敛、dispatch、message injection、context compression 和 failure stage。
5. `Quality Gate Summary`：消费 pytest 结果和 `quality_gate_case` payload，生成可对比 baseline 的 pass / warn / fail 报告。

这条闭环的展示重点是：把非确定性的 agent workflow 拉回到可复现、可归因、可门禁的软件质量体系。完整线上环境和真实外部服务只作为 `real_llm` 或未来 `staging` 的非阻塞补充，不作为当前主门禁。

## 9. 当前覆盖总表

### 9.1 按模块统计
- `p2_api`: `smoke` 已落地并作为 Required Check；`integration` 首批 resilience 已落地，其中两条 SSE 契约进入 non-blocking PR Check；`real_llm` seed 已落地。
- `agentic_tool_loop`: 已落地首批 `unit` 测试，覆盖收敛、消息注入、dispatch contract、compression、failure attribution。
- `quality_gate_summary`: `implemented v1`，当前已落地 pytest hook 收集、case 归一、metrics 聚合、baseline compare、pass / warn / fail 判级，以及 JSON / Markdown / terminal summary 输出。
- `core_service` / `memory` / `mcp_tools`: 计划中。

### 9.2 按层级统计
- `smoke`: 已落地。
- `integration`: 已部分落地，当前主要集中在 `p2_api` 的 `/chat/stream` resilience。
- `real_llm`: 已有 1 条 non-blocking seed case。
- `unit`: 已开始落地，当前主要集中在 `agentic_tool_loop`。
- `quality_gate`: 已有 v1 聚合链路，可覆盖 `p2_api`、`agentic_tool_loop`、`real_llm` 的结构化结果。

### 9.3 当前 gaps
- `p2_api` 的 smoke 和 P1 前两项 SSE 契约已落地；user stop、timeout、重复 finalize、真实持久化回读和指标口径迁移仍未完成。
- `agentic_tool_loop` 当前 gaps：
1. duplicate `tool_call_id` 跨轮去重仍为 `xfail` 契约，尚未落到 runtime。
2. 真实工具联调、context/memory 参与下的多轮回归、route-finalize 与 loop 收敛的跨层联测仍未覆盖。
- `quality_gate_summary` 当前 gaps：
1. CI 中目前只由 Smoke 作为 Required Check；Stream Contract 已作为 non-blocking PR Check，完整 `--quality-gate` 运行仍适合作为本地展示或后续独立 workflow。
2. baseline 更新策略仍应保持显式确认，不应每次运行自动覆盖健康线。

## 10. 架构映射与阅读顺序

### 10.1 模块到架构映射
- `p2_api` ↔ Part 2 / Part 3
- `core_service` ↔ Part 3
- `memory` ↔ Part 5
- `mcp_tools` ↔ Part 6

### 10.2 建议阅读顺序
1. `docs/architecture/NagaAgent_architecturev2.md`
2. `docs/architecture/p2_api.md`
3. 本文档（测试规划）
4. `docs/testing/architecture/part-02-api-stream.md`
5. `docs/testing/architecture/part-04-agentic-tool-loop.md`
6. `docs/testing/architecture/part-08-quality-gate-summary.md`
7. `docs/testing/architecture/part-11-golden-cases.md`
8. `docs/testing/plans/suspend/golden-cases-implementation.md`
9. `docs/testing/architecture/ci-pr-gate.md`
10. `docs/testing/showcase/portfolio-summary.md`
11. `tests/unit/agentic_tool_loop/test_loop_convergence.py`
12. `tests/unit/agentic_tool_loop/test_loop_message_injection.py`
13. `tests/unit/agentic_tool_loop/test_loop_tool_dispatch.py`
14. `tests/unit/agentic_tool_loop/test_loop_context_compression.py`
15. `tests/unit/agentic_tool_loop/test_loop_failure_attribution.py`
16. `tests/unit/p2_api/test_failure_attribution.py`

## 11. Agent Workflow Golden Cases 模块

### 11.1 模块职责与范围
- 从真实用户任务出发，验证 context、memory、Skill、tool loop、结果回注和最终回答组成的任务级业务闭环。
- 不重复 `p2_api` 的协议测试或 `agentic_tool_loop` 的内部状态机单测。

### 11.2 当前状态
- `implemented v1 / partial expansion`
- 当前已有 5 条 deterministic stub Golden Cases 并在 P0 clean environment 中通过；生产 prompt/schema/context assembly 与后续扩展仍未完成。详细边界见 [`part-11-golden-cases.md`](part-11-golden-cases.md)。

### 11.3 文档结构
- 旧版详细文档结构规则已归档到 [`../archive/document-structure-legacy.md`](../archive/document-structure-legacy.md)；当前分类与维护规则以 [`../README.md`](../README.md) 为准。
- `11.1-11.8` 描述职责、范围、流程、用例、执行链路、依赖替换、边界和扩展。
- `11.9 业务 / mapping 解析` 作为最后一章，负责把 Golden Cases 映射到真实 Agent 业务流程。
