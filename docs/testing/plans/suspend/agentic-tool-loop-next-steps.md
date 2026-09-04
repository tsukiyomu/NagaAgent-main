# 当前认为未落地的建议

> `SUSPENDED`（2026-08-18）：本文件作为 Tool Loop、Context/Memory 与 MCP 后续设计参考；当前执行顺序见 [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md)。

## 1. 真实 MCP / OpenClaw 联调：需要，但不是当前优先级

这个判断是：需要，但放后面。

MCP 官方定义里，Tools 是让模型调用外部系统的函数能力，Resources 是给模型使用的上下文和数据，Prompts 是模板化消息和工作流。
所以真实 MCP dispatcher 联调当然有价值，因为它能验证：

- tool schema 是否能真实暴露
- dispatcher 是否能真实调用
- auth / permission / timeout 是否能处理
- 工具返回结构是否能被 loop 消费
- tool error 是否能进入标准降级路径

但它不适合放到当前 `agentic_tool_loop unit gate`，原因是它太重：

- 依赖真实 MCP server
- 依赖 OpenClaw / 外部工具配置
- 可能有权限、网络、认证、限流
- 失败原因可能来自环境，不一定来自 loop 逻辑
- 不适合做稳定 baseline gate

所以它应该放在：

```text
integration / mcp_tools
staging / full workflow
```

而不是：

```text
unit / agentic_tool_loop
```

当前文档也已经承认：`mcp_tools` 还只到 tool error 事件边界，没有真实 dispatcher 联调；后续应把真实 dispatcher、工具失败、超时、幂等等边界放在 `integration / mcp_tools`，这个分层是对的。

### 建议处理方式

短期只做假的 dispatcher / stub tool：

```text
LLM output -> tool_calls -> execute_tool_calls stub -> normalized tool_results -> inject next round
```

后面再补一条真实 MCP smoke：

```text
real loop + real MCP dispatcher + one harmless tool
```

比如只测一个无副作用工具：

- `echo`
- `time`
- `health_check`
- `search mock server`
- `list_tools`

不要一开始测文件写入、浏览器操作、真实外部 API。

### 简历表达

不要写成：

> 完成真实 MCP / OpenClaw 全链路联调。

可以写：

> 预留 MCP / OpenClaw 真实 dispatcher 联调层，当前在 unit gate 中通过 stub dispatcher 验证 tool call 标准化、结果注入与失败收敛，后续在 staging 层验证真实工具链路。

## 2. context_assembly / memory 真实参与下的多轮回归：需要，而且比真实 MCP 更值得做，但不要混进 loop unit

这个判断是：需要，优先级中高，但放在 integration / golden cases。

原因是 context / memory 和最终效果关系更直接。Agent 很多质量问题不是 tool 调错，而是：

- 历史上下文没注入
- memory 召回了但没有被使用
- context 压缩丢了关键约束
- 多轮对话中前文约束丢失
- tool result 没进入下一轮
- RAG 返回了内容，但最终回答没引用
- prompt/context 改动导致任务质量退化

这部分已经很接近“评测层”。真实 context/memory 的参与很有价值，但它不是纯 loop unit。

为什么不该混进当前 loop unit：

因为 loop unit 要验证的是：

- 有无 tool call 时怎么停
- tool result 怎么注入
- repeated failure 怎么 summary
- max rounds 怎么处理
- message queue 什么时候 drain
- native tool call 和 text parsed tool call 是否归一

这些应该是确定性的状态机测试。`agentic_tool_loop` 是 orchestration layer，不是每个工具或 provider 的具体实现；具体执行在 `execute_tool_calls(...)` 和下游 helper，loop 负责协调这些调用。

context/memory 真实参与后，变量太多：

- 检索结果可能变化
- memory 数据可能污染
- prompt 拼装可能变化
- LLM 输出可能不稳定
- 失败原因不容易归到 loop 本身

所以它应该放在：

```text
integration / memory
golden cases / context usage regression
real_llm / staging profile
```

不是：

```text
unit / agentic_tool_loop
```

### 建议处理方式

先在 loop unit 里做假的 context：

```text
fixed messages + fixed tool result -> assert next-round messages contains injected result
```

后面再做真实 context/memory integration：

```text
memory retrieval -> context assembly -> run agent workflow -> assert context used / required points covered
```

可以先设计 3 条就够：

| Case | 目标 |
|---|---|
| `memory_hit` | 召回到历史偏好，回答中应使用 |
| `memory_empty` | 空召回时不应崩溃，正常降级 |
| `compressed_context` | 压缩后关键约束仍保留 |

### 简历表达

可以写：

> 在后续 golden cases 中引入 `context_assembly / memory` 真实参与的多轮回归，用于验证上下文召回、压缩、注入和最终回答使用情况；但 loop unit gate 仍保持 stub context，以保证状态机断言稳定可复现。

## 3. route finalize 和 loop 收敛的跨层联测：需要，但只做 1-2 条，不要扩散

这个判断是：需要，而且短期比真实 MCP 更适合补，但数量必须少。

它的价值是验证：

> loop 内部得出“该结束 / 该 summary / 该 degraded”之后，route 层是否能正确消费这些事件，并完成 SSE terminal、finalize、save、active flag cleanup。

当前文档已经把边界讲清楚了：`agentic_tool_loop` 决定 workflow 为什么继续或停止，而 `p2_api` 决定这些事件如何通过 SSE 暴露，以及 finalize 如何处理。
所以跨层联测是有必要的，因为它验证的是两个层之间的契约。

但是不要做太多。当前已经有很多 `/chat/stream` integration，用例已经能证明 route 能消费 loop 输出并做 finalize / cleanup。后续只需要补 1-2 条跨层 integration：

### Case A：loop natural convergence -> route finalize

```text
real route + real loop + fake LLM
LLM 第 1 轮输出 tool_call
stub tool 返回结果
LLM 第 2 轮输出 final answer
assert:
- SSE has tool_calls / tool_results / round_end
- final answer exists
- [DONE] exists
- save once
- active flag cleaned
```

### Case B：max rounds summary -> route finalize

```text
real route + real loop + fake LLM
LLM 每轮都输出 tool_call，直到 max_rounds
loop 进入 summary
assert:
- summary round happened
- final round_end(has_more=False)
- route finalize once
- active flag cleaned
```

这两条就够了。不要再做 10 条 route-level tool loop integration，不然又会回到“堆框架测试”的问题。

### 简历表达

可以写：

> 在 loop unit gate 之外保留少量 route + loop 跨层联测，验证 loop 收敛结果能被 `/chat/stream` 正确消费并完成 SSE terminal、finalize、落盘和 active 状态清理，避免只测内部状态机而漏掉出口语义。

## 4. 最终优先级建议

我会这样排：

| 计划 | 是否需要 | 放在哪层 | 当前优先级 | 价值 |
|---|---|---|---|---|
| 真实 MCP / OpenClaw 联调 | 需要，但后置 | `integration / mcp_tools` 或 `staging` | P3 | 中等，适合展示真实依赖联调 |
| context_assembly / memory 真实多轮回归 | 需要 | `integration / memory` + `golden cases` | P2 | 高，贴近 AI 工程质量 |
| route finalize + loop 收敛跨层联测 | 需要，但少量 | `integration / p2_api + loop` | P1.5 | 高，能补齐 unit 与 API 出口之间的缝 |
| agentic_tool_loop deterministic unit gate | 必须先做 | `unit / agentic_tool_loop` | P1 | 最高，是当前主线 |

也就是说，接下来最合理的顺序是：

```text
P1: agentic_tool_loop unit gate
   - no tool call stop
   - valid tool call continue
   - repeated failure -> summary
   - max rounds -> summary
   - result injection idempotence

P1.5: 1-2 条 route + loop cross-layer integration
   - natural convergence finalize
   - summary fallback finalize

P2: context_assembly / memory + golden cases
   - memory hit
   - empty retrieval fallback
   - compressed context key constraint preserved

P3: real MCP / OpenClaw staging smoke
   - list tools / echo / harmless tool
   - auth failure
   - timeout fallback
```

## 5. 在文档里怎么写最稳

可以在 `agentic_tool_loop` 后面加一个 `Out of Scope / Deferred Integration` 小节：

```markdown
### Deferred Integration Scope

The following items are intentionally not included in the first `agentic_tool_loop` unit gate.

#### Real MCP / OpenClaw Integration
This belongs to a higher-cost `mcp_tools` or `staging` integration layer. The first loop gate should use stub dispatchers to validate tool-call normalization, result injection, convergence, and failure handling deterministically.

#### Real context_assembly / memory Multi-turn Regression
This belongs to later `memory` integration and Agent Workflow Golden Cases. The loop unit gate should use fixed messages/context to avoid mixing retrieval quality, memory state, and model behavior into state-machine assertions.

#### Route Finalize + Loop Convergence Cross-layer Integration
This belongs to a small number of `p2_api + agentic_tool_loop` integration cases. It verifies that loop convergence is correctly exposed through SSE and route-level finalize/cleanup, but should not replace unit-level loop convergence tests.
```

这段很有必要。它会显得你不是没做，而是明确分层、主动控制范围。

## 6. 最直接结论

这三条判断都对，但可以再压实成：

1. 真实 MCP / OpenClaw 联调：要，但后置。
   放到 `mcp_tools integration / staging`，不进当前 loop unit gate。
2. context_assembly / memory 真实多轮回归：要，而且未来很有价值。
   放到 `memory integration / golden cases`，因为它更接近 AI 质量评测，不要污染 loop 状态机单测。
3. route finalize + loop 收敛跨层联测：要，但只做少量。
   放到 `p2_api + core loop integration`，用于验证 loop 结果能正确通过 SSE 出口收尾。

当前最该落地的仍然是：

> `agentic_tool_loop deterministic unit gate`：停止条件、工具结果注入、失败收敛、summary fallback、幂等等边界。

先把这个做实，后面再接真实 context、真实 MCP、跨层联测。这样项目不会散，也不会变成“什么都测一点，但没有主线”。
