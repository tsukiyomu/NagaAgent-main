# Agentic Tool Loop Testing

> **Migration status：`REVIEW_NEEDED`。** 对应测试尚未在 target branch 迁移/执行；旧断言与结果
> 仅绑定 source revision。详见 [`../MIGRATION_STATUS.md`](../MIGRATION_STATUS.md)。
>
> 对应 [`overview.md`](overview.md) 第 4 章。

## 4.1 模块职责与范围
- 该模块测试的不是 HTTP / SSE 协议本身，而是 `run_agentic_loop(...)` 背后的多轮编排。
- 关注点包括：
1. `round loop` 如何继续或停止
2. tool call 如何从 LLM 输出中解析、标准化并进入 dispatcher
3. tool result 如何注入下一轮 messages
4. 何时进入 `summary round`
5. queued message 与 compression 如何影响下一轮上下文
- 当前定位是：`workflow state-machine gate`，不是工具观测平台。
- 它对应现已暂停的 [`../plans/suspend/agent-workflow-gate-strategy.md`](../plans/suspend/agent-workflow-gate-strategy.md) 第 1 个计划：
1. `Tool Loop State Regression`
2. `状态转移`
3. `硬断言`
4. `收敛规则`
5. `失败归因`
- 它不承接另外两条总计划：
1. `Golden Cases / baseline regression`
2. `Quality Gate Report / pass-warn-fail gate`

## 4.2 当前已落地范围
- 当前已落地测试文件：
1. `tests/unit/agentic_tool_loop/test_loop_convergence.py`
2. `tests/unit/agentic_tool_loop/test_loop_message_injection.py`
3. `tests/unit/agentic_tool_loop/test_loop_tool_dispatch.py`
4. `tests/unit/agentic_tool_loop/test_loop_context_compression.py`
5. `tests/unit/agentic_tool_loop/test_loop_failure_attribution.py`
6. `tests/unit/p2_api/test_failure_attribution.py`
- 当前共享 support：
1. `tests/support/agentic_tool_loop_helpers.py`
2. `tests/support/failure_attribution.py`
- 当前已覆盖能力：
1. no tool call -> 直接停止
2. repeated failure -> early summary
3. `max_rounds` exhausted -> `tools=None` summary round
4. text tool-call 与 native function-call 的 dispatch contract 对齐
5. tool result 注入与 queue injection 的稳定性
6. duplicate `tool_call_id` 跨轮去重目前为 executable gap（`xfail`）
7. compression pass 与 `compress_info` 事件透传
8. 最小 failure attribution schema
- loop 级已补充的 failure-stage 回归：
1. `tool_call_normalize`
2. `tool_result_injection`
- 当前仍未真正落地：
1. 真实 MCP / OpenClaw 联调
2. memory / context assembly 深度参与下的多轮回归
3. route finalize 与 loop 收敛的跨层联测

## 4.3 当前主流程定义
- 当前主流程不是 route 层 `/chat/stream`，而是 loop 内部的状态机：
1. `round_start`
2. `parse / normalize tool calls`
3. `tool_dispatch`
4. `tool_result_injected`
5. `next round` 或 `stop`
6. 必要时进入 `summary_round`
- 推荐作为门禁固化的状态转移表：

| 当前状态 | 输入事件 | 预期状态 | 必须断言 |
|---|---|---|---|
| `round_start` | no tool call | `final_answer` | 不调用 `execute_tool_calls(...)` |
| `round_start` | valid tool call | `tool_dispatch` | `tool_name / args` 被标准化 |
| `tool_dispatch` | tool success | `tool_result_injected` | tool result 进入下一轮 `messages` |
| `tool_dispatch` | tool error | `failure_count + 1` | 单轮失败不直接打断整个 loop |
| `failure_count >= 2` | repeated failure | `summary_round` | 不继续无限 tool call |
| `round == max_rounds` | still has tool call | `summary_round` | summary round 必须 `tools=None` |
| `summary_round` | final output | `stop` | `round_end(has_more=False)` |

### 4.3.1 收敛规则
- 当前这个模块要锁住的不是“模型答得好不好”，而是 loop 在异常和边界下能不能收敛到可解释终态。
- 当前推荐固定的收敛规则是：
1. `no tool call -> final_answer -> stop`
2. `valid tool call -> dispatch -> inject result -> next round`
3. `single tool error` 只增加 failure count，不直接打断整个 loop
4. `failure_count >= 2` 时提前进入 `summary_round`
5. `round == max_rounds` 且仍有 tool call 时，必须进入 `tools=None` 的 summary round
6. `summary_round` 必须发出最终 `round_end(has_more=False)`，而不是继续进入下一轮
- 因此，这里的质量门禁首先是“为什么停、什么时候停、停成什么状态”，而不是“工具调用次数越多越好”。

## 4.4 用例与断言
- 当前 `agentic_tool_loop` 相关用例已落地 20 条（其中 1 条为 `xfail` executable gap：`duplicate tool_call_id`）。
- 下面改按“测试文件 -> 用例 -> 关键断言”展开，便于从代码文件直接映射到文档。

### 4.4.1 按测试文件分组总览
| 测试文件 | 主要关注面 | 当前用例数 |
|---|---|---|
| `tests/unit/agentic_tool_loop/test_loop_convergence.py` | loop 收敛、summary 进入条件、`max_rounds` 终止语义 | 4 |
| `tests/unit/agentic_tool_loop/test_loop_message_injection.py` | tool result 回注、queue 注入、跨轮幂等、重复 id gap | 4（含 1 条 `xfail`） |
| `tests/unit/agentic_tool_loop/test_loop_tool_dispatch.py` | dispatch contract、异常标准化、agent type 路由 | 5 |
| `tests/unit/agentic_tool_loop/test_loop_context_compression.py` | compression 调用时机、压缩结果是否进入下一轮输入 | 2 |
| `tests/unit/agentic_tool_loop/test_loop_failure_attribution.py` | loop 级 `final_status / failure_stage` 投影 | 4 |
| `tests/unit/p2_api/test_failure_attribution.py` | 通用 failure attribution schema 的跨层复用 | 1 组共享归因用例 |

### 4.4.2 `tests/unit/agentic_tool_loop/test_loop_convergence.py`
- 关注面：
  1. loop 在不同停止条件下能否收敛
  2. repeated failure 与 `max_rounds` 是否正确触发 summary
  3. summary round 是否强制 `tools=None`

- 本文件测试边界 / Real vs Stub：
  - Real：
    1. `run_agentic_loop(...)` 的真实多轮推进与停止逻辑。
    2. summary round 进入条件、`max_rounds` 处理与 `round_end` 终态。
  - Stub / Fake：
    1. `get_llm_service` -> fake `ScriptedStreamLLM`，避免真实模型输出波动。
    2. `compress_context` -> no-op passthrough，避免压缩逻辑干扰收敛断言。
    3. `get_message_queue` -> 空 queue stub，避免 queue 注入影响轮次判断。
    4. `execute_tool_calls` 或 `_execute_*` -> success / error / timeout doubles，用于精确构造收敛场景。
  - 不覆盖：
    1. 不测真实 compression 内容正确性。
    2. 不测真实 queue 注入语义细节。
    3. 不测真实 MCP / OpenClaw / 外部工具链路，应放到更高层 integration / staging。

- `test_loop_stops_when_no_actionable_tool_calls`
  - 目标：`round_start` 下无可执行 tool call 时直接停止。
  - 关键断言：
    1. `execute_tool_calls` 调用次数为 `0`。
    2. LLM 仅调用 1 轮。
    3. 仅出现 1 个 `round_end`，且 `has_more=False`。
    4. 不进入 `summary round`。

- `test_loop_repeated_all_failed_rounds_trigger_early_summary`
  - 目标：连续失败触发 early summary，而不是一直跑到 `max_rounds`。
  - 关键断言：
    1. dispatcher 被调用 2 次后进入 summary。
    2. summary 轮 LLM 调用时 `tools is None`。
    3. 存在 `summary=true` 的 `round_start`。
    4. 最终 `round_end` 为 `has_more=False`。

- `test_loop_max_rounds_exhausted_enters_summary_with_tools_disabled`
  - 目标：到达 `max_rounds` 且仍有 tool call 时，必须进入 `tools=None` 的 summary。
  - 关键断言：
    1. dispatcher 调用次数等于 `max_rounds` 轮数。
    2. summary 轮 LLM 调用显式 `tools is None`。
    3. summary 轮 `round_start` 与 `round_end` round 编号一致。
    4. 最终 `has_more=False`。

- `test_loop_tool_timeout_errors_still_converge_to_summary`
  - 目标：tool timeout 结果被标准化后仍可收敛到 summary。
  - 关键断言：
    1. tool timeout 结果出现在 `tool_results` 事件中。
    2. summary 轮触发且 `tools is None`。
    3. 最终 `round_end` 为终止态。

### 4.4.3 `tests/unit/agentic_tool_loop/test_loop_message_injection.py`
- 关注面：
  1. tool result 回注是否稳定进入下一轮 `messages`
  2. queue 侧路消息是否按时机注入且不重复
  3. 多轮回注是否保持幂等

- 本文件测试边界 / Real vs Stub：
  - Real：
    1. `run_agentic_loop(...)` 内部的 tool result 回注逻辑。
    2. queue `drain()` 后消息并入下一轮 `messages` 的真实时序。
    3. native/text 路径下的 history 增量追加行为。
  - Stub / Fake：
    1. `get_llm_service` -> fake `ScriptedStreamLLM`，精确控制每一轮是否产出 tool call。
    2. `compress_context` -> no-op passthrough，避免 compression 改写 messages 干扰注入断言。
    3. `get_message_queue` -> `EmptyQueueStub` / `OneShotQueuedMessageStub`，分别模拟“无排队消息”和“只注入一次消息”。
    4. `execute_tool_calls` -> success double，只构造规范化 tool result，不引入真实执行器波动。
  - 不覆盖：
    1. 不测真实 dispatcher 路由是否正确。
    2. 不测真实 compression 行为。
    3. 不测 route 层如何把 queue/tool result 事件对外暴露，应放到 `p2_api` integration。

- `test_native_result_injection_is_single_and_stable`
  - 目标：单轮 native tool result 注入只发生一次。
  - 关键断言：
    1. 第二轮 messages 中 assistant/tool 成对出现。
    2. `tool_call_id` 与内容匹配预期。
    3. 同一 `tool_call_id` 的 tool message 仅 1 条。
    4. 最终 `round_end.has_more=False`。

- `test_queue_injection_happens_before_next_round_and_once`
  - 目标：queue 消息在下一轮前注入且只注入一次。
  - 关键断言：
    1. queue `drain` 至少被调用。
    2. 下一轮 user 内容包含 queue 文本且仅出现一次。
    3. `queued_messages` 事件出现且 `count==1`。
    4. `sources` 字段符合预期。

- `test_multi_round_native_result_injection_stays_idempotent`
  - 目标：多轮注入保持幂等，不重复回注历史。
  - 关键断言：
    1. 第三轮中 `call-r1`、`call-r2` 各出现一次。
    2. assistant `tool_calls` 中两个 id 也各出现一次。
    3. 最终 `round_end.has_more=False`。

- `test_duplicate_tool_call_id_is_deduplicated_across_rounds`（`xfail`）
  - 目标：锁定“重复 `tool_call_id` 不应重复注入”的未来契约。
  - 当前状态：`xfail` executable gap（runtime 尚未显式实现去重）。
  - 关键断言（目标态）：
    1. 重复 id 的 tool message 应只保留一条。
    2. assistant 中重复 id 引用也应只保留一条。

### 4.4.4 `tests/unit/agentic_tool_loop/test_loop_tool_dispatch.py`
- 关注面：
  1. dispatch 输入输出 contract
  2. executor 异常与 timeout 结果的标准化
  3. 多种 `agentType` 的路由选择

- 本文件测试边界 / Real vs Stub：
  - Real：
    1. `execute_tool_calls(...)` 作为 dispatch 入口的真实分发逻辑。
    2. native/text 两条路径在进入 dispatcher 前的 contract 对齐。
    3. 异常 / timeout 结果的标准化输出 shape。
  - Stub / Fake：
    1. 各类 `_execute_*` 下游执行器 -> fake returns / raised exception，用于验证 dispatch 后的归一化结果。
    2. 不依赖真实 MCP / OpenClaw / tool backend，仅模拟其返回结构。
  - 不覆盖：
    1. 不测真实 `run_agentic_loop(...)` 多轮状态推进。
    2. 不测 tool result 注入到下一轮 `messages`。
    3. 不测真实外部工具可用性，应放到 `mcp_tools` integration 或 staging。

- `test_execute_tool_calls_empty_list_returns_empty`
  - 目标：空输入时 dispatch 返回空列表。
  - 关键断言：
    1. 返回值严格为 `[]`。

- `test_execute_tool_calls_normalizes_raised_exceptions`
  - 目标：executor 抛异常时统一标准化为 error 结果。
  - 关键断言：
    1. 成功分支结果结构保持正常。
    2. 异常分支被规范成 `status=error`。
    3. error 结果保留可诊断文本。

- `test_execute_tool_calls_preserves_executor_returned_timeout_error`
  - 目标：executor 已标准化的 timeout error 不被二次破坏。
  - 关键断言：
    1. `status=error` 保留。
    2. `service_name/tool_name` 保留。
    3. `result` 中保留 timeout 语义。

- `test_native_and_text_paths_share_dispatch_contract`
  - 目标：text 解析路径与 native 路径在 dispatch contract 上保持一致。
  - 关键断言：
    1. text 路径提取后不残留 tool fence。
    2. text/native 投影后的 dispatch shape 完全一致。

- `test_execute_tool_calls_dispatches_all_supported_agent_types`
  - 目标：`mcp/openclaw/tool/naga_control` 四分支都路由到正确 executor。
  - 关键断言：
    1. `calls_seen` 顺序与来源参数符合预期。
    2. 每条结果 `service_name/status` 正确。

### 4.4.5 `tests/unit/agentic_tool_loop/test_loop_context_compression.py`
- 关注面：
  1. compression 调用时机
  2. compression SSE 事件是否透传
  3. 压缩后的 `messages` 是否真正成为下一轮 LLM 输入

- 本文件测试边界 / Real vs Stub：
  - Real：
    1. `run_agentic_loop(...)` 在普通 round 前与 summary round 前调用 compression 的真实时机。
    2. compression 返回后，loop 是否透传 `compress_info` 事件、是否用压缩结果覆写 `messages`。
  - Stub / Fake：
    1. `compress_context` -> custom stub，分别模拟“替换 messages”和“只记录调用不替换”两类场景。
    2. `get_llm_service` -> fake `ScriptedStreamLLM`，用于观察压缩后真正传进 LLM 的 `messages`。
    3. `get_message_queue` -> 空 queue stub，避免 queue 注入干扰 compression 时序。
    4. `execute_tool_calls` -> success double，仅用于构造进入 summary 的路径。
  - 不覆盖：
    1. 不测真实 compression 算法如何裁剪上下文。
    2. 不测真实 token 统计与压缩质量。
    3. 不测 compression 与真实 route finalize 的联动，应放到更高层 integration。

- 本文件内非测试用例 helper 的作用：
  1. `_native_tool_call_chunk(...)`
     - 用来构造一条 native function-calling 形态的 `tool_calls_native` SSE chunk。
     - 作用不是测试 payload 拼装本身，而是让本文件可以走“真实 loop 解析 native tool call”这条路径。
  2. `_collect_loop_chunks(...)`
     - 负责运行真实 `run_agentic_loop(...)`，并把它 yield 出来的原始 SSE chunks 按顺序收集起来。
     - 这样测试可以先保留真实流式输出，再用 `extract_sse_json_events(...)` 做事件级断言。
  3. `compression_env`
     - 提供共享测试环境。
     - 主要职责是固定 `get_config()`，并把 queue 替换成空 stub，避免 queue 注入干扰 compression 断言。

- `test_loop_forwards_compress_events_and_uses_compressed_messages`
  - 目标：compression 事件透传且压缩后消息真正进入 LLM 输入。
  - 关键断言：
    1. `compress_info` 事件被透传。
    2. LLM 第一轮输入等于压缩后 messages。
    3. 最终 `round_end.has_more=False`。

- `test_loop_summary_round_runs_its_own_compression_pass`
  - 目标：summary round 前执行第二次 compression pass。
  - 关键断言：
    1. compression 调用次数为 2。
    2. `compress_info` phase 顺序为 `initial -> summary`。
    3. summary 轮 `tools is None`。
    4. 最终 `round_end` 正常终止。

### 4.4.6 `tests/unit/agentic_tool_loop/test_loop_failure_attribution.py`
- 关注面：
  1. loop 级 `final_status` 投影
  2. `failure_stage` 是否可稳定归因
  3. summary path 与 override path 是否满足统一 schema

- 本文件测试边界 / Real vs Stub：
  - Real：
    1. `run_agentic_loop(...)` 真实输出的事件流。
    2. loop 输出如何被投影成 `final_status / failure_stage / summary_triggered`。
  - Stub / Fake：
    1. `get_llm_service` -> fake `ScriptedStreamLLM`，构造 success / error / summary 三类稳定流。
    2. `compress_context` -> no-op passthrough，避免 compression 干扰归因。
    3. `get_message_queue` -> 空 queue stub，避免 queue 侧路消息影响归因报告。
    4. `execute_tool_calls` -> controlled success / error doubles，用于稳定命中特定 `failure_stage`。
  - 不覆盖：
    1. 不测 route 层 finalize/save/active cleanup 的真实执行。
    2. 不测 `build_failure_attribution(...)` 的跨模块完整矩阵，应与 `tests/unit/p2_api/test_failure_attribution.py` 配合看。
    3. 不测真实工具执行链路。

- `test_loop_failure_attribution_success_contract`
  - 目标：happy path 可稳定投影到 `final_status=success`。
  - 关键断言：
    1. `final_status=success`。
    2. `failure_stage=none`。
    3. schema 校验通过（`assert_failure_attribution_shape`）。

- `test_loop_failure_attribution_dispatch_error_contract`
  - 目标：error 事件可稳定投影到 `tool_dispatch` 归因。
  - 关键断言：
    1. `final_status=degraded`。
    2. `failure_stage=tool_dispatch`。
    3. schema 校验通过。

- `test_loop_failure_attribution_summary_round_contract`
  - 目标：summary 路径可被归因为 `summary_round`。
  - 关键断言：
    1. stream 中存在 `summary=true`。
    2. `summary_triggered=true`。
    3. `failure_stage=summary_round`。

- `test_loop_failure_attribution_accepts_loop_stage_overrides`
  - 目标：loop 级 failure-stage override 可稳定用于门禁归因。
  - 当前覆盖 stage：
    1. `tool_call_normalize`
    2. `tool_result_injection`
  - 关键断言：
    1. override 后 `failure_stage` 与输入一致。
    2. `final_status=degraded`。
    3. schema 校验通过。

### 4.4.7 `tests/unit/p2_api/test_failure_attribution.py`（共享归因能力）
- 关注面：
  1. `build_failure_attribution(...)`
  2. `assert_failure_attribution_shape(...)`
  3. loop 与 route 层共享的最小 failure attribution schema

- 本文件测试边界 / Real vs Stub：
  - Real：
    1. `tests/support/failure_attribution.py` 的归因构建与 schema 校验逻辑。
    2. 默认推断与显式 stage override 的字段规则。
  - Stub / Fake：
    1. 这里主要直接构造输入 payload / stream 文本，不依赖真实 loop 或真实 route。
    2. 目的是把归因工具本身与具体业务流程解耦开测。
  - 不覆盖：
    1. 不测真实 `run_agentic_loop(...)` 事件流。
    2. 不测真实 `/chat/stream` finalize 生命周期。
    3. 这些应分别由 `agentic_tool_loop` unit 与 `p2_api` integration 承担。

- 目标：验证通用归因工具在 `p2_api` 视角下的稳定性。
- 当前覆盖：
  1. success 默认归因。
  2. error 事件 -> `tool_dispatch` 归因。
  3. finalize 不完整 -> `failed/finalize` 归因。
  4. 显式 stage override：`llm_output_parse` / `tool_result_injection` / `context_assembly` / `summary_round`。
- 关键断言：
  1. `case_id/final_status/failure_stage/rounds/tool_call_count/summary_triggered/unhandled_exception` 字段齐全。
  2. 默认推断与显式 override 都满足 schema 规范。

### 4.4.8 硬门禁断言矩阵
| 断言 | 当前状态 | 说明 |
|---|---|---|
| `rounds <= max_rounds + 1` | landed | summary round 最多只允许额外 1 轮 |
| `execute_tool_calls_called_expected_times` | landed | 不该 dispatch 时不能误调 |
| `tool_results_injected_once == true` | landed | 结果注入不能重复写 history |
| `tool_result_message_count == expected` | landed | 注入条数需要和预期一致 |
| `summary_round_triggered_when_expected == true` | landed | repeated failure / max rounds 时必须进入 summary |
| `final_status in ["success", "degraded", "failed"]` | landed | 这里不用 `summary` 作为 final_status；summary 由独立字段表达 |
| `summary_triggered == true/false` | landed | 区分是否走过 summary path |
| `unhandled_exception == false` | landed | failure 需要被标准化，而不是直接炸出 loop |
| `duplicate_tool_call_id == false` | gap (xfail) | 跨轮重复 `tool_call_id` 目前仍可能重复回注，待 runtime 显式支持 |

### 4.4.9 `final_status` 与 `summary_triggered` 的职责分离
- 当前不建议把 `summary` 直接塞进 `final_status`。
- 更稳定的表达方式是：
1. `final_status`: `success / degraded / failed`
2. `summary_triggered`: `true / false`
- 原因是 `summary` 更像“路径/阶段”，而不是终态健康级别。

## 4.5 测试执行链路
- 当前 `unit / agentic_tool_loop` 的执行链路是：
`pytest -> fake llm / fake queue / fake compression / fake tool executor -> real run_agentic_loop(...) -> collect SSE chunks -> assert state transitions`
- 这里的核心边界是：
1. 保留真实 `run_agentic_loop(...)`
2. 替换高波动依赖
3. 只验证 deterministic workflow contract
- 这类测试不需要起独立服务，也不走真实网络端口。
- 这也是为什么这个模块不应该继续堆更多 SSE 用例：
1. SSE 协议已经由 `p2_api` 模块承担
2. 这里更适合做状态机级的收敛验证
3. route+loop 跨层问题只保留少量 integration case 即可

## 4.6 依赖替换与故障注入
- 当前主要替换点：
1. `get_llm_service` -> `_ScriptedStreamLLM`
2. `compress_context` -> passthrough / custom compress result / raise
3. `get_message_queue` -> deterministic queue stub
4. `execute_tool_calls` 或下游 `_execute_*` -> success / error / timeout doubles
- 当前共享 helper 来源：
1. `tests/support/agentic_tool_loop_helpers.py`：`ScriptedStreamLLM`、`EmptyQueueStub`、`OneShotQueuedMessageStub`、SSE helper
2. `tests/support/failure_attribution.py`：归因 payload 构建与 schema 断言
- 当前故障注入方式：
1. tool 全失败，验证 early summary
2. executor 返回 timeout-style error，验证 summary 收敛
3. compression path 注入额外 `compress_info`
4. duplicate `tool_call_id`，保留 executable gap（xfail）用于锁定未来 dedupe contract
- 当前不做的事情：
1. 不接真实 MCP server
2. 不接真实 OpenClaw 网关
3. 不把这层测试扩成 trace/observability 平台

### 4.6.1 为什么暂时不把真实 MCP / OpenClaw 联调放进这里
- 真实 `MCP / OpenClaw` 联调当然需要，但它不适合当前 `unit / agentic_tool_loop` gate。
- 原因是它会引入：
1. 真实网络和权限
2. 外部工具配置与认证
3. 失败归因混杂到环境层
4. 非确定性波动
- 因此更合理的落点是：
1. `integration / mcp_tools`
2. `staging / full workflow`
- 当前这个模块只需要通过 fake dispatcher / stub tool 验证：
1. tool call 标准化
2. dispatcher 调用契约
3. tool result 注入
4. repeated failure / summary 收敛

### 4.6.2 为什么 `context_assembly / memory` 很重要，但不该混进 loop unit
- `context/memory` 对最终任务质量影响很大，但它不属于纯 loop 状态机问题。
- 一旦把真实 context / memory 混进来，变量会明显增多：
1. 召回结果可能变化
2. prompt/context 组装可能变化
3. LLM 输出不再稳定
4. failure 不容易归因到 loop 本身
- 所以这里保留 stub context，更真实的验证应放到：
1. `integration / memory`
2. `golden cases / context usage regression`
3. `real_llm` 或 `staging` profile

## 4.7 当前边界与非目标
- 非目标：
1. 真实工具生态联调质量
2. 外部网络稳定性
3. route 层 streaming finalize 细节
4. LLM 语义回答质量
- 当前边界：
1. 这是 `run_agentic_loop(...)` 的 unit-style workflow gate
2. 不是 `/chat/stream` 的协议契约测试
3. 不是 staging / E2E
4. 不是 `Golden Cases` 或 baseline quality regression

### 4.7.1 当前最小 failure attribution schema
- 当前推荐固定的最小 failure attribution 结构是：

```json
{
  "case_id": "tool_loop_003",
  "final_status": "degraded",
  "failure_stage": "tool_dispatch",
  "rounds": 3,
  "tool_call_count": 2,
  "summary_triggered": true,
  "unhandled_exception": false
}
```

- 当前固定的 `failure_stage` 集合：
1. `llm_output_parse`
2. `tool_call_normalize`
3. `tool_dispatch`
4. `tool_result_injection`
5. `context_assembly`
6. `summary_round`
7. `finalize`
- 这个结构的目标是做 `CI gate / regression report`，不是做 trace 平台。

## 4.8 后续扩展
- 当前明确需要做的：
1. 把状态转移表对应到更完整的 deterministic hard assertions
2. 继续补 loop 级 failure-stage regression cases（在已覆盖 `tool_call_normalize`、`tool_result_injection` 基础上扩展）
- 当前可以后置的：
1. 真实 MCP / OpenClaw integration
2. context assembly / memory 深度参与
3. route-finalize 与 loop 收敛的跨层联测
- 当前不建议做的：
1. Langfuse 风格 trace 平台
2. 非确定性的“工具观测大盘”

### 4.8.1 推荐优先级
- 如果按工程收益排序，当前更合理的顺序是：

| 优先级 | 项目 | 推荐落点 | 原因 |
|---|---|---|---|
| P0 | loop 内 `failure_stage` regression cases（继续扩展） | `unit / agentic_tool_loop` | 在已固定 schema 基础上增强 CI 归因能力 |
| P1 | route + loop 跨层联测 1-2 条 | `integration / p2_api` | 验证 loop 收敛结果能正确外显到 `/chat/stream` |
| P2 | `context_assembly / memory` 真实参与 | `integration / memory` 或 `golden cases` | 更接近任务质量，但不适合混入 unit gate |
| P3 | 真实 `MCP / OpenClaw` 联调 | `integration / mcp_tools` 或 `staging` | 依赖最重，环境波动最大，不适合当前主门禁 |

### 4.8.2 route + loop 跨层联测建议只保留 1-2 条
- 这类联测需要，但数量必须少。
- 当前最值得补的只有两类：
1. `tool success -> final answer -> route finalize`
2. `max_rounds -> summary -> route finalize`
- 目的不是把 route-level integration 再堆成新平台，而是验证 loop 收敛结果能被 `/chat/stream` 正确消费并收尾。

## 4.9 业务 / mapping 解析
- 主要代码入口：
1. `apiserver/agentic_tool_loop.py::parse_tool_calls_from_text(...)`
2. `apiserver/agentic_tool_loop.py::_convert_native_to_dispatch(...)`
3. `apiserver/agentic_tool_loop.py::execute_tool_calls(...)`
4. `apiserver/agentic_tool_loop.py::run_agentic_loop(...)`
5. `tests/support/failure_attribution.py::build_failure_attribution(...)`
- 与主架构映射：
1. 主要属于 Part 3 Runtime 的多轮编排逻辑
2. tool call / result 边界触到 Part 6 MCP / Tool Integration
3. route 侧 SSE finalize 则仍属于 `p2_api` 模块测试
- 因此，这一层最合适的测试表达方式是：
1. state-machine gate
2. deterministic hard assertions
3. minimal failure attribution

### 4.9.1 loop 的输入 / 输出语义（业务视角）
- 输入（每轮）
1. 上一轮累积的 `messages`
2. 当前轮可用 `tools`
3. queue 注入内容（如有）
4. compression 后的 messages（如启用）

- 核心结论
  上面 4 项里，真正直接传给 LLM 的核心对象其实还是 `messages`；`queue` 与 `compression` 最终都会回落到“改写下一轮 messages”的过程。

- `messages` 是什么
  它不是“仅用户历史”，而是“当前轮完整对话状态”。

  组成通常包括：
  1. 初始历史消息：`system` / `user` / `assistant`
  2. route 层补入的上下文：system supplement / tool instructions / skills prompt / RAG context
  3. 前一轮回注内容：tool 调用痕迹与 tool result
  4. summary round 前补入的总结指令

  因此，“上一轮累积的 messages” 更准确地说，是“到本轮开始为止已经组装完成的整份 conversational state”，不是某个独立的 history snapshot。

  在当前项目里，`messages` 的外层格式就是 `list[dict]`，每条消息至少有：
  1. `role`
  2. `content`

  最常见的 message shape 类似：

  ```python
  {"role": "system", "content": "..."}
  {"role": "user", "content": "..."}
  {"role": "assistant", "content": "..."}
  ```

  需要注意的是：
  1. 外层 message object 是 JSON-like dict
  2. 但 `content` 大多数时候不是 JSON，而是一段自然语言文本 prompt
  3. 只有在 native function calling 回注时，`assistant` / `tool` message 才会带额外结构字段

  当前项目里，一个进入 loop 前的典型 `messages` 样例可以近似理解为：

  ```python
  [
      {
          "role": "system",
          "content": "<主 system prompt，来自 build_system_prompt()>",
      },
      {
          "role": "user",
          "content": "上一轮用户消息",
      },
      {
          "role": "assistant",
          "content": "上一轮助手回复",
      },
      {
          "role": "user",
          "content": "帮我搜一下 NagaAgent",
      },
      {
          "role": "system",
          "content": "<route 层 supplement，里面可能包含时间、技能、MCP、RAG、multi-agent context 等文本块>",
      },
  ]
  ```

  这个样例里几种角色的来源分别是：
  1. 第一条 `system`：来自 `build_system_prompt()`，属于主人格 / 基础系统提示词
  2. 中间历史 `user` / `assistant`：来自 session 持久化历史，由 `message_manager.build_conversation_messages(...)` 读出并拼回上下文
  3. 最后一条当前 `user`：来自本次请求的用户输入
  4. 末尾追加的第二条 `system`：来自 `build_context_supplement(...)`，属于 route 层运行时补充上下文

  换句话说，当前项目里的 `system` 通常不止一条：
  1. 一条是主 system prompt
  2. 一条是 route 层 append 的 supplement

  而 `assistant` 也不一定只来自“模型刚刚这一轮输出”，还可能来自：
  1. 历史会话里已经持久化过的助手回复
  2. loop 在 tool 调用后回注的 `assistant` function-call message

  如果本轮发生 native function calling，则下一轮前的 `messages` 还可能变成：

  ```python
  [
      {
          "role": "system",
          "content": "<主 system prompt>",
      },
      {
          "role": "user",
          "content": "帮我搜一下 NagaAgent",
      },
      {
          "role": "system",
          "content": "<supplement>",
      },
      {
          "role": "assistant",
          "content": None,
          "tool_calls": [
              {
                  "id": "call-r1",
                  "type": "function",
                  "function": {
                      "name": "tool__web_search",
                      "arguments": "{\"query\":\"NagaAgent\"}",
                  },
              }
          ],
      },
      {
          "role": "tool",
          "tool_call_id": "call-r1",
          "content": "搜索结果文本...",
      },
  ]
  ```

  这个阶段就能看出：
  1. `messages` 仍然是结构化数组
  2. 但只有 tool-call 相关消息会出现 `tool_calls`、`tool_call_id` 这类额外字段
  3. route 层补入的上下文本身依旧只是 `system.content` 里的长文本，而不是独立 JSON protocol

- `messages` 的回注形态
  native function calling 路径：
  1. 追加 1 条带 `tool_calls` 的 `assistant` 消息
  2. 再追加若干条 `role=tool` 的结果消息

  text-parsing 兼容路径：
  1. 追加 1 条 `assistant` 消息
  2. 再追加 1 条承载格式化 tool result 的 `user` 消息

- `tools` 是什么
  这里的 `tools` 特指传给模型的 OpenAI function-calling schema 列表，不是泛指“系统里所有可扩展能力”。

  它通常来自统一 schema 构建器，可映射到：
  1. 内建 `tool__*`
  2. `mcp__{service}__{tool}`
  3. `openclaw__*`
  4. `live2d__*`
  5. `naga_control__*`

  需要明确两件事：
  1. `tools` 可以覆盖 MCP，但不等于“已有 MCP 列表”
  2. `tools` 是“模型这一轮被允许调用的函数 schema 集合”

- `tools` 和 skill 的关系
  1. skill 主要通过 system prompt / supplement / instructions 影响模型行为
  2. skill 本身通常不会作为 loop 的 `tools` 参数直接传入
  3. 某个 skill 可以间接引导模型去调用某些 tool / MCP schema

- `queue` 是什么
  `queue` 指的是运行时消息队列中的侧路消息，不是抽象概念，也不是新的独立上下文层。

  它承载的通常是“对话进行中，从外部源异步送来的消息”，例如：
  1. user 中途补充
  2. scheduler / heartbeat / screen-monitor 一类 side-channel 输入

  loop 不会把 queue 作为单独结构传给 LLM，而是在“本轮工具执行结束、下一轮 LLM 调用前”执行 `drain()`，把队列内容合并进最后一条 user-semantic message。

  所以测试里的 `queue injection` 更准确地是在验证：
  1. queue 是否在正确时机被 drain
  2. drain 出来的消息是否只被合并一次
  3. 合并后的文本是否真的进入下一轮 `messages`

- `compression` 是什么
  `compression` 不是和 `messages` 并列的长期输入槽位，而是对当前 `messages` 做一次上下文治理变换。

  它的语义应理解为：
  1. 先拿当前累计的 `messages` 做压缩判断
  2. 如需压缩，则用压缩结果覆盖原 `messages`
  3. 然后把压缩后的 `messages` 作为下一轮真实 LLM 输入

  因此，“compression 后的 messages” 更准确的含义是“进入本轮 LLM 前的最终 messages 视图”，而不是另一份独立于 `messages` 存在的输入副本。

- 输入装配链
  如果按代码执行链把“每轮输入如何装配出来”写得更具体，可以概括为：

  1. `routes/chat.py` 先完成基础 `messages` 组装，并补入 system supplement、tool instructions、skills prompt、RAG/context 等外围上下文
  2. 若当前模型支持 native function calling，则由 `tool_schemas.py` 生成 `tools` schema 列表；否则 `tools=None`，后续走文本解析兼容路径
  3. `run_agentic_loop(...)` 接收这份初始 `messages` 和当前轮可用 `tools`，作为 loop 的起点状态
  4. 每轮真正调用 LLM 之前，loop 先执行一次 `compress_context(messages)`；如果发生压缩，则直接覆写当前 `messages`
  5. LLM 调用时真正拿到的输入只有两类核心对象：`messages` 与 `tools`
  6. 如果本轮产生 tool call，loop 会先执行 dispatcher，再把 tool call 与 tool result 回注进 `messages`
  7. tool result 回注完成后，loop 会调用 `message_queue.drain()`；如有 queued message，则把它继续合并进“下一轮要发送给 LLM 的最后一条 user-semantic message”
  8. 下一轮开始时，LLM 看到的不是“初始 messages + queue + compression 的并列输入”，而是“已经被 tool result、queue、compression 共同改写过的新 messages”
  9. 如果进入 summary round，则 loop 还会再补 1 条“不要再调用工具、请基于已有结果直接总结”的 user 指令，并强制 `tools=None`

- 简化表达
  从状态机角度看，下一轮 LLM 的真实输入更接近：

  `final_messages_for_this_round = compress(inject_queue(inject_tool_results(accumulated_messages))))`

  这里的 `tools` 则是与 `final_messages_for_this_round` 并列传入模型的“可调用函数集合”，而不是被拼进 message 文本里的上下文。

- 对测试边界的影响
  1. `agentic_tool_loop` 单测主要验证的是这条装配链在 loop 内是否按顺序发生
  2. 它不需要证明 `chat.py` 里所有 supplement 文案都正确，只需要承认这些内容会先于 loop 进入初始 `messages`
  3. 它也不需要证明某个具体 MCP/skill 的业务能力，只需要证明这些能力若被投影成 `tools` 或 prompt context，loop 能稳定消费并收敛

- 输出（每轮）
1. `content/reasoning` 等模型事件
2. `tool_calls` / `tool_results` 事件
3. `round_end`（是否继续的显式信号）
4. 终止时 `[DONE]`（在 route 层被最终消费）

- 业务意义
1. loop 不是“直接给最终答案”的单步函数，而是“每轮推进 + 条件收敛”的状态机执行器
2. 当前门禁核心是“状态是否正确推进并可解释结束”，而不是“回答文案是否更像人”

### 4.9.2 状态机阶段与代码入口映射
| 状态机阶段 | 关键代码入口 | 业务问题 | 当前测试覆盖 |
|---|---|---|---|
| `round_start` | `run_agentic_loop(...)` | 当前轮要不要继续、是否进入 summary | `test_loop_stops_when_no_actionable_tool_calls`、`test_loop_repeated_all_failed_rounds_trigger_early_summary` |
| `tool_call_parse` | `parse_tool_calls_from_text(...)`、`_convert_native_to_dispatch(...)` | 模型输出能否转成可执行 tool call | `test_native_and_text_paths_share_dispatch_contract` |
| `tool_dispatch` | `execute_tool_calls(...)` 与 `_execute_*` 分支 | 不同 agentType 是否走对执行器、错误是否标准化 | `test_execute_tool_calls_dispatches_all_supported_agent_types`、`test_execute_tool_calls_normalizes_raised_exceptions` |
| `tool_result_injected` | `run_agentic_loop(...)` 内部回注逻辑 | tool result 是否正确进入下一轮 messages | `test_native_result_injection_is_single_and_stable`、`test_multi_round_native_result_injection_stays_idempotent` |
| `queue_injected` | `message_queue.drain()` + loop 内合并逻辑 | 队列消息是否在正确时机注入且不重复 | `test_queue_injection_happens_before_next_round_and_once` |
| `summary_round` | `run_agentic_loop(...)` 的 failure/max_rounds 分支 | 何时降级、降级后是否关闭 tools | `test_loop_max_rounds_exhausted_enters_summary_with_tools_disabled` |
| `stop/final_status` | `round_end` + 归因构建 | 是否可解释结束、失败阶段是否可归因 | `test_loop_failure_attribution_*`、`tests/unit/p2_api/test_failure_attribution.py` |

### 4.9.2.1 `dispatcher` / `executor` / `tool result injection` 的关系
- 在当前项目里，`dispatcher` 可以理解为：
  1. LLM 已经产出 tool call 之后
  2. loop 先把 tool call 解析并标准化
  3. 再交给一层“分发执行”的入口
  4. 由它决定把这条调用路由给哪个具体执行器

- 对应到当前代码与测试表达，更接近：
  1. `execute_tool_calls(...)`：dispatch 入口
  2. `_execute_*` 分支：具体 executor

- 也就是说，这一层的职责不是“让模型决定调用什么工具”，而是：
  1. 根据标准化后的 tool call 判断来源或类型
  2. 选择正确执行器
  3. 执行后把返回值标准化成统一 tool result

- 简化链路可以理解为：

  `LLM output -> parse/normalize tool_call -> dispatcher(execute_tool_calls) -> executor(_execute_*) -> normalized tool_result -> inject next-round messages`

- 这也是为什么当前 `tool_dispatch` 阶段测的重点不是回答文案，而是：
  1. route 到哪个 executor
  2. `agentType / tool_name / args` 是否保持一致
  3. error / timeout 是否被标准化
  4. 返回结果能否进入后续 `tool_result_injected`

- 因此，从业务视角说：
  1. LLM 负责“提出工具调用意图”
  2. dispatcher 负责“把调用请求交给正确执行器”
  3. loop 负责“把执行结果回注到下一轮上下文并继续收敛”

### 4.9.3 为什么会“继续”或“停止”
- 继续的典型条件：
1. 本轮存在可执行 tool call，且尚未触发收敛阈值。
2. tool result 已回注，需要下一轮让模型消费工具结果。
- 停止的典型条件：
1. 无可执行 tool call，直接 `round_end(has_more=False)`。
2. 连续失败达到策略阈值，进入 summary 并停止。
3. 达到 `max_rounds` 且仍有 tool call，进入 `tools=None` 的 summary 后停止。
- 对应测试上的硬断言核心：
1. `round_end` 终止语义。
2. `summary` 是否在预期条件触发。
3. summary 轮 `tools is None`。

### 4.9.4 与 `p2_api` 的边界（避免职责重叠）
- `agentic_tool_loop` 负责：
1. 轮次推进逻辑。
2. tool 解析/执行/回注。
3. 收敛与降级策略。
- `p2_api` 负责：
1. HTTP/SSE 入口契约。
2. route 级 finalize、active flag 回落。
3. side-channel 失败下的流式收尾。
- 所以“error/summary”在两层的含义不同：
1. loop 关注“状态机是否收敛”。
2. p2 关注“用户可见流是否正确结束”。

### 4.9.5 与另外两个总计划的边界
- 这个模块解决的是：
1. workflow 为什么继续
2. workflow 为什么停止
3. workflow 在失败下是否收敛
- 它不直接解决的是：
1. 最终回答质量是否低于 baseline
2. 整套 agent workflow 的 pass / warn / fail gate summary
- 也就是说：
1. `agentic_tool_loop` 提供第 1 层状态机门禁
2. `golden cases` 承接第 2 层任务质量回归
3. `quality gate report` 负责第 3 层门禁汇总
