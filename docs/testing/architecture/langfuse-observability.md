# Langfuse 接入说明

> **当前迁移状态（2026-09-07）**：MIG-2 已将 adapter/tests 从 `d6553a96...` 迁入
> upstream-based 分支，代码/测试 commit 为 `c7122124`，58 个 unit cases 已通过。
> **运行时仍未接线**：`LLMService`、tool dispatcher、chat route 和 API lifecycle 没有调用
> adapter，依赖清单也没有 Langfuse。因此，仅配置环境变量不会自动产生 trace。
> 详见 [迁移状态](../MIGRATION_STATUS.md) 与 [MIG-2 执行记录](../reports/upstream-migration-mig-2-execution-journal.md)。

## MIG-2 已验证的部分

Adapter 是应用与观测 SDK 之间的转换层，负责把应用字段变成 observation 参数，并隔离 SDK 的普通异常。
它属于可观测性模块：记录 LLM/工具发生了什么，不负责执行 LLM/工具，也不负责决定 pytest 是否通过。
本轮迁移该模块及其测试，没有恢复历史运行时接线；旧记录中的 `4e6fd1d` 移除接线状态在保留 revision
`d6553a96...` 上仍存在，不能根据历史章节推断 MIG-2 已运行完整 trace。

测试入口为 [`test_langfuse_integration.py`](../../../tests/unit/test_langfuse_integration.py)：
20 个测试函数通过参数化展开为 58 个 cases，不代表 58 个 Agent 业务场景。

| 验证组 | 对应 adapter 职责与断言 | 失败含义 |
|---|---|---|
| 原有三个 helper 契约 | generation 输入/输出、usage、tool count；工具名称、session 参数、error 状态 | 应用字段转换给 SDK 的契约变化 |
| 配置与 no-op | 缺任一凭据、缺 SDK、初始化失败时返回 None；dotenv 不覆盖进程环境；初始化结果缓存 | 可选观测依赖变成必需条件或重复初始化 |
| Context 生命周期 | SDK 创建、进入、退出失败不改变调用方正常结果；调用方异常、取消、生成器关闭保留原异常对象 | 观测层污染业务控制流或掩盖业务失败 |
| Payload 与 update | 字符串、深度、集合截断；原输入不变；update 失败不外抛 | 已覆盖输入形状的适配/上报隔离失效 |
| Flush / shutdown | 只使用已创建 client；shutdown 仅清理一次；flush 失败仍尝试 shutdown | 清理阶段意外初始化、重复清理或遗漏清理 |

真实性边界：真实 adapter 源文件；fake SDK client/context/observation 和环境变量；API 启动、LLM、工具、
Remote Memory、真实 Langfuse 均不参与正式隔离测试。由于 `apiserver/__init__.py` 会立即导入完整 API，
测试用文件加载方式直接执行 adapter，而不是导入整个 package。原三个 helper 测试仍有 helper 级替换；
新增生命周期测试通过真实 `start_observation` / `propagate_langfuse_attributes` 验证 fake SDK 边界。

因此这些测试不证明 HTTP/SSE 协议、真实 SDK 兼容性、trace 上传、父子关联或 Langfuse UI 可见性。
CI 分类为 `NOT_WIRED`：当前 workflow 没有调用本文件；本轮没有迁移全局 pytest marker/fixture 配置。

## 当前 upstream 的接线核对（尚未实施）

| 未来调用点 | 已查看的代码事实 | 恢复时要保留的语义 |
|---|---|---|
| LLM | `LLMService` 有三处 `acompletion`，流式调用位于最多三次的 retry 循环内 | observation 按实际调用/attempt 记录，不合并掉重试；不改变 SSE 输出 |
| Tool | `execute_tool_calls` 为四类分支创建任务，随后 `asyncio.gather(..., return_exceptions=True)` | 包住单个任务并保留并发和原错误归一化；当前未知 agentType 会跳过，不能照搬旧示例改成 error result |
| Chat | `/chat` 返回非流式响应，`/chat/stream` 返回 `StreamingResponse` | root observation 需要覆盖流的实际消费周期，不只覆盖 response 对象创建 |
| Lifecycle | `api_server.lifespan` 管理启动和 finally 清理 | flush/shutdown 为同步函数，接线前需设计 off-loop 执行与有界退出 |

仍需解决：SDK 版本与安装方式、真实 SDK 验证、runtime wiring、trace/session 父子关系与数据策略。
`compact_langfuse_payload` 只截断，不脱敏，也不承诺总字节上限；prompt、工具结果和错误字符串仍可能含敏感信息。
`shutdown_langfuse` 隔离异常但没有超时保证。上述边界不能因本地 unit 通过就消失。

## 0. 后续恢复方案（未实施）

### 0.1 是否会让项目代码变复杂

如果 Langfuse 只用于观察每次聊天、LLM 调用、工具调用和 Live2D 动作，请求链路仍然可以保持清晰，
整体属于低到中等复杂度，不需要让业务代码直接调用 Langfuse REST API。

推荐依赖关系是：

```text
业务代码
  -> 本地 Langfuse adapter
    -> Langfuse Python SDK
      -> Langfuse server
```

业务代码只调用本地 adapter 提供的 `start / update / propagate / flush / shutdown` helper。SDK 不可用、
缺少凭据或上报失败时，adapter 必须自动降级为 no-op，不能改变聊天、LLM 或工具执行结果。

复杂度主要不在“连接 Langfuse API”，而在以下运行时语义：

1. 流式输出结束后，正确聚合 `content / reasoning_content / tool_calls / usage`
2. 多轮 agentic loop 和重试之间保持正确的父子 observation 关系
3. 并发工具调用各自拥有独立 tool observation
4. 后台 Live2D 任务在 root chat trace 结束前完成或显式关联
5. 对 prompt、工具参数和工具结果进行截断、脱敏与数据边界控制

### 0.2 推荐的 Trace 层级

如果目标是观察“每次聊天调用了什么工具、执行了什么动作”，建议采用以下结构：

```text
chat.request
├── llm.generation.round_1
├── tool.<service>.<tool_name>
│   ├── input / normalized dispatch contract
│   ├── output / normalized result
│   ├── duration
│   └── success / error
├── motion.live2d.<action>
│   ├── requested
│   ├── dispatched
│   └── acknowledged / failed
└── llm.generation.round_2
```

标识语义必须明确区分：

1. `session_id`：一整个对话，可包含多次用户消息
2. `trace_id`：一次具体的用户消息或 chat request
3. observation：该次请求中的某一轮 LLM、某一次工具调用或某一个动作

因此，不应只使用 `chat:{session_id}` 作为所有消息共用的 root trace 标识。每次 `/chat` 或
`/chat/stream` 请求应创建唯一 `request_id / trace_id`，再用相同 `session_id` 将多次请求分组到同一会话。

### 0.3 当前代码中的四个接入点

当前架构已经提供集中式边界，恢复接入不需要在大量业务分支中散布 SDK 调用：

1. Chat root trace
   - [`routes/chat.py`](../../../apiserver/routes/chat.py)
   - 非流式 `/chat`：包住一次完整请求
   - 流式 `/chat/stream`：必须在异步生成器内部包住完整消费周期，直到成功、异常或客户端断开
2. LLM generation
   - [`llm_service.py`](../../../apiserver/llm_service.py)
   - 在每次真实 `acompletion(...)` 外层创建 generation observation
   - 流式场景在消费结束后一次性回写聚合结果，不需要记录每个 SSE chunk
3. Tool observation
   - [`agentic_tool_loop.py`](../../../apiserver/agentic_tool_loop.py)
   - 在 `execute_tool_calls(...)` 的单个 dispatch item 外层创建 observation
   - 并发工具分别记录，不把整个 `asyncio.gather(...)` 合并成一个无法定位的 observation
4. Live2D motion observation
   - [`agentic_tool_loop.py`](../../../apiserver/agentic_tool_loop.py)
   - 在 `_send_live2d_actions(...)` 中为每个动作记录独立 observation

最后在 [`api_server.py`](../../../apiserver/api_server.py) 中恢复初始化与 shutdown，在请求结束或适当的批处理
边界进行 best-effort flush。应用入口只负责生命周期，不应承担 trace 业务字段组装。

### 0.4 Live2D 动作的关键边界

当前 Live2D 动作通过 `asyncio.create_task(_send_live2d_actions(...))` fire-and-forget 发送，并且
`_send_live2d_actions(...)` 没有检查 HTTP 状态，内部异常也会被忽略。基于当前行为，Langfuse 最多只能可靠说明：

- 模型请求了哪个动作
- 后端尝试发送了哪个动作

它不能证明 UI 已经实际执行该动作。

如果只需要观察“模型选择了什么表情”，记录 `requested / dispatched` 就足够，接入仍然简单。如果需要确认
“动作确实播放”，应增加 `action_id` 和 UI acknowledgement，并记录以下状态：

```text
requested -> dispatched -> acknowledged
                        -> failed
```

此外，后台 motion task 可能晚于 root chat trace 结束。要保持正确父子关系，可选择以下任一方案：

1. 在 trace 结束前等待 motion dispatch 完成
2. 向后台任务显式传递 trace context
3. 将 UI acknowledgement 作为带 `action_id` 的关联 observation/event

不要把 `requested` 误标为 `performed`。

### 0.5 复杂度分级

| 目标 | 复杂度 | 说明 |
| --- | --- | --- |
| 记录 chat、LLM、tool 和 motion request | 低到中 | 四个集中式接入点即可完成 |
| 正确处理 streaming、retry、并发 tool 与父子关系 | 中 | 需要明确 observation 生命周期和聚合语义 |
| 证明 Live2D 动作已在 UI 播放 | 中 | 需要 action acknowledgement，而不只是后端发送 |
| 接入 score、dataset、experiment、prompt management | 高于基础观测 | 属于后续平台化能力，不应和第一阶段混做 |

推荐第一阶段只恢复 root chat trace、generation、tool、motion request 和 no-op 降级；第二阶段再增加 UI
acknowledgement。Langfuse 应继续作为运行时 observability layer，不作为 pytest、Golden Cases 或 CI gate 的真值来源。

## 历史实现参考

以下章节记录 `4e6fd1d` 之前的 generation/tool 接入。章节中的“当前”指历史接入版本，不代表
`codex/upstream-langfuse-sync` 已启用 Langfuse。第 0 节仍是推荐恢复设计，不是 MIG-2 的已实现范围。

## 1. 功能概述

当前项目对 Langfuse 的接入，定位是 **Agent Runtime 可观测层**，不是完整的 Langfuse 平台化接入。

当前已经实际接入的能力主要有：

1. `LLM generation observation`
   - 非流式 `llm.chat_with_context`
   - 流式 `llm.stream_chat_with_context`
2. `tool observation`
   - `agentic_tool_loop` 中每个标准化后的 tool call
3. `input / output / usage / error` 记录
   - 输入 `messages`
   - 输出 `content / reasoning_content / tool_calls`
   - provider usage
   - error status
4. `startup / shutdown` 生命周期接入
   - 启动阶段检查是否启用
   - 退出阶段执行 `flush()` / `shutdown()`
5. `session` 传播
   - 通过 `propagate_attributes(session_id=...)` 传播到 LLM / tool observations
6. 请求结束显式 `flush`
   - `/chat`
   - `/chat/stream`

当前还没有显式接入的更高层能力包括：

1. `user`
2. 显式 root chat trace
3. 独立 `trace` 生命周期管理
4. `score / dataset / experiment / prompt management`
5. Allure / CI / quality report 直接打通

## 2. 接入目标与使用场景

当前接入目标主要有三类：

1. 观察一次完整的 LLM 调用
   - 看输入 `messages`
   - 看输出 `content`
   - 看是否产出 `tool_calls`
   - 看 usage
2. 观察一次完整的 tool call 执行
   - 看标准化后的 dispatch contract
   - 看工具结果是否成功
   - 看错误信息是什么
3. 在不影响主业务链路的前提下提供可回溯 trace
   - Langfuse 不可用时自动降级
   - 不阻断 chat/tool 运行

## 3. 在测试体系中的定位

Langfuse 在当前测试体系里，不是 gate truth，也不是核心判定器。

它的定位更接近：

1. `observability layer`
2. `trace / debug` 辅助层
3. `quality analysis` 辅助信息来源

它当前不承担：

1. CI gate 真值判定
2. deterministic regression contract
3. quality gate baseline 的唯一数据源

相关文档：

- [测试架构总设计](../../testing_architecture.md)
- [Quality Gate Summary](part-08-quality-gate-summary.md)
- [Agent Workflow Gate Strategy（暂停）](../plans/suspend/agent-workflow-gate-strategy.md)

## 4. 功能拆解

当前 [`langfuse_integration.py`](../../../apiserver/langfuse_integration.py) 主要承担这些工作：

1. 凭据加载
2. 启用判断
3. 共享 client 初始化
4. no-op 降级
5. payload 压缩与截断
6. generation observation helper
7. tool observation helper
8. error status 回写
9. trace/session 属性传播
10. request-end flush
11. shutdown 清理

## 5. 核心流程

```text
API 启动
  ↓
检查 Langfuse 是否可用
  ↓
按请求/执行上下文传播 `session_id`
  ↓
LLM 调用前开始 generation observation
  ↓
真实调用 LLM
  ↓
LLM 输出完成后写回 output / usage / error
  ↓
若触发 tool call，则为每个 tool call 包 tool observation
  ↓
请求结束时显式 flush
  ↓
API 退出时 flush / shutdown
```

## 6. 代码实现解析

### 6.1 Langfuse Client 初始化

负责文件：

- [`langfuse_integration.py`](../../../apiserver/langfuse_integration.py)

这一层负责：

1. 从项目根目录 `.env` 读取：
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
   - `LANGFUSE_BASE_URL`
2. 惰性初始化共享 client
3. 若缺配置或 SDK 初始化失败，则降级为 `None`

相关接口：

- `get_langfuse_client()`
- `is_langfuse_enabled()`

### 6.2 Trace / Session 语义

当前接入需要区分三个概念：

1. `session_id`
   - 代表一整个聊天会话，例如 `chat-session-001`
   - 用于把多次请求分组到同一个 Langfuse Session
2. `trace`
   - 代表一次具体执行链路
   - 当前项目里通常对应一次 generation observation 或某个 tool observation 所在链路
3. `messages`
   - 是单次 LLM 调用的完整上下文
   - 它可能包含多轮历史 `user/assistant` 消息

这意味着：

1. Langfuse 页面里如果在某个 generation input 中看到多轮历史消息，不代表多个请求共用了同一个 trace
2. 更常见的情况是：
   - 每次请求都有自己的 trace
   - 但 trace 的 generation input 里带着完整对话历史

当前 `session` 的接入方式不是给 `start_as_current_observation(...)` 直接传 `session_id`，而是使用：

```python
with propagate_langfuse_attributes(session_id=session_id):
    with start_llm_generation_observation(...) as observation:
        ...
```

原因是当前项目使用的 Python SDK 版本里，Langfuse 官方推荐 `session` 通过 `propagate_attributes(...)` 传播，而不是通过 observation 构造参数直接传入。

### 6.3 LLM 调用埋点

负责文件：

- [`llm_service.py`](../../../apiserver/llm_service.py)

非流式 generation：

```python
# 先传播 session 级属性，再开启 generation observation。
with propagate_langfuse_attributes(session_id=session_id):
    with start_llm_generation_observation(
        name="llm.chat_with_context",
        messages=messages,
        model=model_name,
        metadata={
            "session_id": session_id,
            "provider_hint": provider_hint,
            "model_override": model_override,
            "api_base_override": api_base_override,
        },
        temperature=normalized_temperature,
        max_tokens=max_tokens,
        stream=False,
    ) as observation:
        response = await acompletion(...)
        message = response.choices[0].message
        complete_llm_generation_observation(
            observation,
            content=message.content or "",
            reasoning_content=getattr(message, "reasoning_content", None),
            response=response,
        )
```

流式 generation：

```python
with propagate_langfuse_attributes(session_id=session_id):
    with start_llm_generation_observation(
        name="llm.stream_chat_with_context",
        messages=messages,
        model=model_name,
        metadata={
            "session_id": session_id,
            "attempt": attempt,
            "model_override": model_override,
            "api_base": llm_params.get("api_base"),
            "tools_enabled": bool(tools),
        },
        temperature=normalized_temperature,
        max_tokens=call_params.get("max_tokens"),
        stream=True,
        tools=tools,
    ) as observation:
        response = await acompletion(**call_params)
        ...
        complete_llm_generation_observation(
            observation,
            content=output_payload["content"],
            reasoning_content=output_payload["reasoning_content"],
            tool_calls=output_payload.get("tool_calls"),
        )
```

当前这一层记录的核心内容包括：

1. `messages`
   - 注意：这里是完整对话上下文，不只是“本轮用户问题”
2. `model`
3. `temperature / max_tokens / stream`
4. `tool_count`
5. `content / reasoning_content / tool_calls`
6. `usage_details`
7. `error status`
8. `session_id`（通过 propagate 传播，metadata 中也保留）

### 6.4 Tool Call 埋点

负责文件：

- [`agentic_tool_loop.py`](../../../apiserver/agentic_tool_loop.py)

tool observation 包装层：

```python
async def _execute_tool_call_with_observation(
    call: Dict[str, Any],
    session_id: str,
    source_agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    agent_type = call.get("agentType", "")
    observation = None

    # 先传播 session，再开始 tool observation。
    with start_tool_observation(
        call,
        session_id=session_id,
        source_agent_id=source_agent_id,
    ) as observation:
        # 下面这些分支才是真正的工具执行逻辑，不是 Langfuse 本身。
        if agent_type == "mcp":
            result = await _execute_mcp_call(call, source_agent_id=source_agent_id)
        elif agent_type == "openclaw":
            result = await _execute_openclaw_call(call, session_id)
        elif agent_type in ("tool", "openclaw_tool"):
            result = await _execute_openclaw_tool_call(call, source_agent_id=source_agent_id)
        elif agent_type == "naga_control":
            result = await _execute_naga_control(call)
        else:
            result = {
                "tool_call": call,
                "result": f"未知agentType: {agent_type}",
                "status": "error",
                "service_name": "unknown",
                "tool_name": "unknown",
            }

        # 工具执行结束后，把标准化结果写回 Langfuse observation。
        complete_tool_observation(observation, result)
        return result
```

当前这一层记录的核心内容包括：

1. 标准化后的 tool dispatch contract
2. `service_name / tool_name / agentType`
3. `session_id / source_agent_id`
4. 标准化后的 tool result
5. error status

### 6.5 Request-End Flush

负责文件：

- [`chat.py`](../../../apiserver/routes/chat.py)

为了避免交互式请求结束后 Langfuse UI 中短时间“看不到 trace / observation”，当前在以下位置增加了显式 flush：

1. `/chat` 成功结束
2. `/chat` 异常结束
3. `/chat/stream` 成功结束
4. `/chat/stream` 异常结束

对应 helper：

- `flush_langfuse()`

这一层的目标不是改变 trace 结构，而是提升交互式调试时的数据可见性。

### 6.6 SSE / Streaming 指标埋点

当前流式链路已经做的是：

1. 保持原始 SSE 输出给前端
2. 在流式消费完成后，把聚合后的：
   - `content`
   - `reasoning_content`
   - `tool_calls`
   写回 generation observation

也就是说，当前是：

- `stream result aggregation`

而不是：

- `per-chunk Langfuse metrics`

### 6.7 测试用例与 trace_id 绑定

### 6.8 Allure 报告关联

### 6.9 CI Summary / Quality Gate 结果输出

## 7. 关键数据结构与指标

当前 Langfuse 侧实际涉及的关键结构主要有：

1. generation input
   - `messages`
2. generation metadata
   - `model`
   - `temperature`
   - `max_tokens`
   - `stream`
   - `tool_count`
   - `provider_hint / model_override / api_base_override / attempt`
3. generation output
   - `content`
   - `reasoning_content`
   - `tool_calls`
4. generation usage
   - `input`
   - `output`
   - `total`
5. tool observation metadata
   - `session_id`
   - `source_agent_id`
   - `agent_type`
6. request-level visibility control
   - request-end `flush`
7. tool observation output
   - 标准化后的 `result`
   - `status`
   - `service_name`
   - `tool_name`

## 8. 与测试体系的关系

### 8.1 与 pytest 的关系

当前有显式单元测试覆盖：

- [`test_langfuse_integration.py`](../../../tests/unit/test_langfuse_integration.py)

这个测试文件验证的是：

1. generation observation 是否按预期开始
2. output / usage 是否按预期写回
3. stream helper 场景下是否保留 tool count 与聚合 output 字段（不证明真实 SSE 语义）
4. tool observation 命名和错误写回是否正确

### 8.2 与 Allure 的关系

### 8.3 与 Langfuse Trace 的关系

当前 generation / tool observation 会出现在 Langfuse trace 视图中。

它们的关系是：

1. `llm_service.py` 负责 generation observation
2. `agentic_tool_loop.py` 负责 tool observation
3. `langfuse_integration.py` 负责统一的 start / update / propagate / flush / shutdown 适配

需要注意：

1. 当前还没有显式 root chat span
2. 因此 Langfuse 上的主可见对象仍然以 generation / tool observation 为主
3. 若某个 generation input 中看到了多轮历史消息，通常是因为 `messages` 记录的是完整上下文，而不是多个请求共享了同一个 trace

### 8.4 与 metrics.json / agent_quality_report.json 的关系

### 8.5 与 CI Gate 的关系

当前 Langfuse 不是 CI gate 的真值来源。

当前 gate 体系更依赖：

1. deterministic unit / integration tests
2. golden cases
3. baseline regression
4. quality gate summary

Langfuse 在这里更偏：

- trace / debug / analysis 辅助层

## 9. 验证设计

### 9.1 接入正确性验证

本机已验证：

1. `.env` 中 `LANGFUSE_PUBLIC_KEY / SECRET_KEY / BASE_URL` 存在
2. `get_langfuse_client()` 返回真实 `Langfuse` 客户端对象
3. `auth_check()` 返回 `True`
4. 通过最小 `start_observation(...)` 调用可生成有效 `trace_id`
5. 通过最小 generation observation 调用可生成有效 observation

### 9.2 Trace 数据完整性验证

当前通过单元测试验证：

1. generation output 是否写回
2. usage 是否写回
3. stream 场景下 tool_calls 是否写回
4. tool observation 的 metadata / error status 是否写回
5. `session_id` 是否通过 `propagate_langfuse_attributes(...)` 正确传播

### 9.3 测试报告关联验证

### 9.4 降级与异常验证

当前接入层的核心降级语义是：

1. 缺少凭据 -> `None`
2. SDK 初始化失败 -> `None`
3. `start_observation(...)` 失败 -> `nullcontext(None)`
4. `update_observation(...)` 失败 -> 吞掉异常
5. `shutdown_langfuse()` 失败 -> 仅记录 debug，不阻断退出

也就是说，Langfuse 当前必须满足：

- 可以失效
- 但不能影响主业务

### 9.5 不影响原业务验证

这一点的设计原则已经写在封装语义里：

1. 业务代码不直接依赖 Langfuse SDK 细节
2. 无 Langfuse 时业务链路仍可运行
3. Langfuse 只作为 around wrapper，不替代 LLM/tool 主逻辑

## 10. 异常与边界

当前已知边界包括：

1. 未显式接入 Langfuse `user`
2. 已接入 `session`，但尚未接入 `user`
3. 未显式实现 root-level `chat trace`
4. 未接入 `score / dataset / experiment / prompt management`
5. 未接入 `GRAG / Neo4j / memory query` 这类链路
6. 未做 per-SSE-chunk Langfuse metrics
7. 不作为 CI gate truth

## 11. 历史实现总结

在 `4e6fd1d` 移除运行时接线之前，项目曾实际接入 Langfuse，且接入范围是收敛的。

当前真正已落地的是：

1. `LLM generation observation`
2. `tool observation`
3. `input/output/usage/error` 记录
4. `session` 传播
5. request-end `flush`
6. `startup/shutdown` 生命周期接入

而还没有显式接入的是：

1. `user`
2. root `chat trace`
3. 更明确的独立 `trace` 管理
4. `score / dataset / experiment`
5. 与 Allure / metrics.json / CI Summary 的直接打通

对该历史版本，最准确的表述不是“项目已经完整接入 Langfuse 平台”，而是：

> 历史版本曾把 Langfuse 作为 Agent Runtime 的 generation/tool 可观测层接入，并补上 session 传播与请求结束 flush；但当时尚未显式接入 root chat trace、Live2D motion observation、user、score、dataset、experiment 等更高层能力。当前 `main` 已移除运行时接线，仅保留 adapter 与测试作为恢复参考。

## 12. 历史版本面试表达

如果明确说明是在描述历史版本，可以这样说：

> 历史版本里，我曾把 Langfuse 接到 Agent Runtime 的核心执行链路，覆盖 `LLMService` 的流式/非流式 generation observation，以及 `agentic_tool_loop` 中每个标准化 tool call 的 tool observation；同时通过 `propagate_attributes(session_id=...)` 做会话传播，并在请求结束时显式 `flush()`。适配层采用 no-op 降级和 payload compact，确保观测失败不影响主业务。当前 `main` 已暂时移除运行时接线；下一阶段若恢复，将补充每次用户消息的 root chat trace 与 Live2D motion observation，并把 UI acknowledgement 与单纯 motion request 区分开。
