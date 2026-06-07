# NagaAgent Testing Architecture

## 0. 文档定位

### 0.1 本文档解决什么问题

本文档定义 NagaAgent 测试体系的架构边界：为什么需要分层测试、每一层验证什么、不同模块的测试责任如何划分，以及 Quality Gate、Langfuse、Allure、JSON report 在测试体系中的位置。

它关注的是测试架构本身，而不是某一个测试文件的逐行说明。读完本文档后，应该能回答以下问题：

- 哪些测试应该阻塞 PR，哪些测试只作为回归或观测参考。
- p2_api、agentic_tool_loop、memory、mcp_tools、observability 等模块分别应该在哪一层被验证。
- 外部依赖如 LLM、Langfuse、MCP tool、存储、记忆系统应该如何替换和隔离。
- Quality Gate 的判断依据来自哪里，哪些系统只负责展示或观测。

### 0.2 本文档不解决什么问题

本文档不描述具体测试用例的完整清单，也不替代模块级测试文档。

以下内容应放在其他文档或测试代码中维护：

- 某一个接口的完整输入输出样例。
- 某一个 fixture、fake、stub 的具体实现细节。
- 某一个 Allure 报表字段或 Langfuse trace 字段的截图级说明。
- 临时问题排查记录和一次性实验结论。

### 0.3 与 testing_overview.md 的关系

`docs/testing/testing_overview.md` 是面向阅读入口的测试总览，重点说明当前已有测试、如何运行、结果在哪里看。

`docs/testing_architecture.md` 是面向架构判断的设计文档，重点说明为什么这样分层、为什么这样替换依赖、为什么这样设置 gate。两者关系是：

- `testing_architecture.md` 定义测试体系的结构和边界。
- `testing_overview.md` 汇总当前测试资产和日常使用方式。
- 当新增测试层、模块边界或 gate 策略时，应优先更新本文档。
- 当新增具体测试命令、测试文件或阅读入口时，应同步更新 `testing_overview.md`。

## 1. 架构目标与设计原则

### 1.1 架构目标

NagaAgent 的测试体系目标不是追求所有路径都通过真实外部服务跑一遍，而是把不同风险放到合适的层级验证。

核心目标包括：

- 用低成本、确定性的 smoke 测试守住 PR 基线。
- 用 unit 测试锁定 agentic loop、Langfuse adapter 等关键控制流。
- 用 integration 测试验证 FastAPI route、SSE、会话生命周期和持久化边界。
- 用 real_llm 测试验证真实模型接入的最小可用性，但不把模型语义质量作为阻塞条件。
- 为 memory、mcp_tools、staging full-chain 等后续能力预留清晰扩展点。

### 1.2 设计原则

测试体系遵循以下原则：

- 控制流优先：优先验证请求如何进入系统、如何被调度、如何结束，而不是只验证某个返回字符串。
- 确定性优先：PR 阻塞测试必须可重复、离线、低波动。
- 外部依赖可替换：LLM、Langfuse、MCP、数据库、记忆系统默认应通过 fake、stub 或 monkeypatch 隔离。
- 真实链路按需开启：真实 LLM、真实 Langfuse、staging 环境只进入非阻塞或手动 profile。
- 观测系统不参与判定：Langfuse 和 Allure 负责观测与展示，不作为 gate truth。
- 模块边界清晰：每个测试层只验证自己负责的边界，不把所有模块耦合在一个大测试里。

### 1.3 核心风险假设

当前测试架构基于以下风险假设设计：

- Agentic loop 的轮次控制、工具调用、消息注入、上下文压缩和失败归因是高风险核心逻辑。
- `/chat/stream` 的 SSE 输出、active 状态清理、finalize 和异常恢复直接影响用户体验。
- Langfuse 属于观测链路，失败时不应影响主业务请求成功。
- 真实 LLM 输出不可完全确定，因此只能验证协议级和最小可用性，不能作为稳定语义断言。
- memory、mcp_tools、GraphRAG/GRAG 等能力未来会扩大系统状态面，因此需要提前保留模块化测试边界。

## 2. 测试分层架构

### 2.1 分层总览

NagaAgent 测试体系按执行成本、依赖真实度和阻塞级别分为五层：

| 层级 | 目标 | 外部依赖 | 是否阻塞 PR |
| --- | --- | --- | --- |
| smoke | 验证最小 HTTP 可用性和关键入口不崩 | 全部替换 | 是 |
| unit | 验证模块内部控制流和边界契约 | 全部替换 | 可作为本地/CI 基线 |
| integration | 验证模块协作和 API 生命周期 | 关键依赖替换 | 通常不阻塞或按 profile 配置 |
| real_llm | 验证真实模型接入最小可用性 | 使用真实 LLM | 否 |
| staging | 验证接近生产的全链路行为 | 使用真实服务 | 否，适合发布前或定时回归 |

### 2.2 smoke 层定位

smoke 层是 PR Blocking Gate 的主要来源，目标是以最小成本发现基础接口不可用、路由崩溃、SSE 协议中断等问题。

当前代表测试包括 `tests/smoke/test_p2_smoke.py`，覆盖：

- `/health` 基础健康检查。
- `/chat` 非流式入口。
- `/chat/stream` 流式入口。
- session id、基础响应结构和 `[DONE]` 结束信号。

smoke 层不应依赖真实 LLM、真实 Langfuse、真实 MCP 服务或真实数据库。

### 2.3 unit 层定位

unit 层验证单一模块内部控制流是否符合契约。它应该尽量使用 fake LLM、stub 工具、内存队列和 monkeypatch，避免引入 HTTP、网络和真实模型。

当前重点是 `agentic_tool_loop`：

- 收敛与最大轮次控制。
- 工具解析和分发。
- 工具结果注入。
- 上下文压缩。
- 失败归因和错误输出。

另一个 unit 重点是 Langfuse helper：

- generation / tool observation 的创建边界。
- session id 传播。
- Langfuse 不可用时主流程不被阻断。

### 2.4 integration 层定位

integration 层验证多个模块之间的协作边界，尤其是 API route 与 loop、持久化、状态清理、SSE 输出之间的组合行为。

当前代表测试包括 `tests/integration/p2_api/test_chat_stream_resilience.py`，重点覆盖：

- `/chat/stream` route 的异常恢复。
- 流式输出完成后的 finalize。
- active session 状态清理。
- 消息保存和错误路径的边界。

integration 层允许使用真实 FastAPI route，但外部 LLM、Langfuse、MCP 和远程服务仍应被替换。

### 2.5 real_llm 层定位

real_llm 层用于确认真实模型配置、协议兼容性和最小调用链路没有断裂。

当前代表测试包括 `tests/integration/p2_api/test_chat_stream_real_llm_smoke.py`。这一层的判断重点是：

- 能否通过真实 LLM provider 完成一次最小流式响应。
- SSE 协议是否仍然完整。
- 系统是否能在真实模型延迟和输出形态下完成请求。

real_llm 层不适合作为 PR 阻塞条件，因为真实模型存在网络、限流、延迟、输出不确定和供应商波动。

### 2.6 staging 层定位

staging 层面向接近生产的全链路验证，适合覆盖真实服务组合后的风险。

staging 层未来应覆盖：

- 真实 LLM。
- 真实 Langfuse。
- 真实 memory / database。
- 真实 MCP tools。
- 完整 chat session 多轮链路。

staging 层不应替代 smoke、unit、integration。它负责发现环境集成问题，而不是负责精确定位模块级回归。

## 3. 模块边界设计

### 3.1 模块划分总览

当前测试架构按以下模块划分责任：

| 模块 | 测试关注点 | 主要测试层 |
| --- | --- | --- |
| p2_api | HTTP route、SSE、session lifecycle、finalize | smoke / integration |
| agentic_tool_loop | loop 控制流、工具调度、上下文压缩、失败归因 | unit |
| core_service | 会话上下文组装、业务服务编排 | unit / integration |
| memory | 记忆检索、RAG/GraphRAG 边界、召回降级 | unit / integration |
| mcp_tools | 工具注册、schema、dispatch、结果契约 | unit / integration |
| observability | Langfuse trace/session/observation、flush、降级 | unit / integration |
| quality_gate_summary | 测试结果聚合、报告输出、gate 分类 | unit / smoke-adjacent |

### 3.2 p2_api 边界

p2_api 负责 HTTP 入口，不负责 LLM 语义质量。

测试应验证：

- route 是否能接收请求并返回合法响应。
- `/chat/stream` 是否按 SSE 约定输出事件。
- 请求结束、异常、客户端断开时是否正确清理 active 状态。
- finalize 是否被触发，消息是否按预期保存。
- route 是否正确调用下游 loop 或 service。

测试不应在 p2_api 层验证：

- 模型回答是否“聪明”。
- 工具内部业务逻辑是否正确。
- memory 检索排序是否最优。

### 3.3 agentic_tool_loop 边界

agentic_tool_loop 是多轮智能体控制流核心，测试重点是确定性的 orchestration。

测试应验证：

- LLM 输出如何被解析成工具调用或最终回答。
- 工具调用如何被 dispatch。
- 工具结果如何注入下一轮消息。
- 最大轮次、收敛、重复调用和失败路径如何处理。
- 上下文压缩是否在正确时机触发。
- 错误是否归因到 LLM、tool、parser 或 loop 控制流。

测试不应依赖真实工具后端或真实 LLM 输出。

### 3.4 core_service 边界

core_service 负责业务服务层编排，位于 API route 和底层能力之间。

未来测试应覆盖：

- session 上下文如何构建。
- 用户消息、系统提示、记忆片段和工具配置如何组合。
- route 参数如何转换为 loop 输入。
- 服务层异常如何转化为 API 可处理的错误。

core_service 的测试应优先使用 unit 和 integration，不应直接连接真实外部服务。

### 3.5 memory 边界

memory 模块负责长期记忆、检索增强和未来 GraphRAG/GRAG 能力。

测试应区分三类风险：

- 检索接口契约：输入 query、session、user 后是否返回结构化 memory item。
- 降级行为：memory 不可用、空结果、超时时主流程是否继续。
- 图谱或 RAG 策略：GraphRAG/GRAG 的节点、边、片段、排序和引用关系是否符合预期。

memory 测试不应把真实 embedding、真实向量库或真实图数据库放进 PR blocking gate。真实后端适合 staging 或专门的 integration profile。

### 3.6 mcp_tools 边界

mcp_tools 负责工具发现、schema 管理、调用分发和结果标准化。

测试应验证：

- 工具 schema 是否能被稳定注册。
- loop 发出的 tool call 是否能被正确路由。
- 工具成功、失败、超时、非法参数是否返回统一结果结构。
- MCP 服务不可用时是否有明确错误和降级路径。

mcp_tools 的内部真实工具效果不属于 agentic_tool_loop unit 的责任，应放到 mcp_tools 自己的 unit 或 integration 测试中。

### 3.7 observability 边界

observability 负责把业务运行过程投递到 Langfuse 等观测系统。

测试应验证：

- 每次用户请求是否能形成独立 trace。
- 同一个会话的多次请求是否通过 session id 关联。
- generation、tool observation、metadata、usage 等字段是否在 helper 层正确传递。
- Langfuse client 异常、网络失败或 flush 失败时是否不影响主业务响应。

observability 不负责判断请求是否成功，也不作为 Quality Gate 的 truth source。

### 3.8 quality_gate_summary 边界

quality_gate_summary 负责测试结果汇总和 gate 分类，不负责重新执行业务逻辑。

测试应验证：

- pytest 结果和 user_properties 是否能被正确聚合。
- blocking、non-blocking、warning 等分类是否准确。
- JSON、Markdown、terminal summary、Allure attachment 是否能从同一组结果派生。
- 生成报告失败时是否不会掩盖 pytest 原始失败。

quality_gate_summary 的 truth source 应来自 pytest 结果，而不是 Allure 页面或 Langfuse trace。

## 4. 测试执行架构

### 4.1 总体执行链路

总体执行链路如下：

```text
pytest
  -> test profile / marker selection
  -> fixture setup
  -> dependency replacement
  -> module or route under test
  -> assertion
  -> pytest result
  -> quality gate summary
  -> JSON / Markdown / Terminal / Allure presentation
```

这个链路中，pytest assertion 是判定源头。后续 report 和 observability 只能展示或辅助排查，不能反向改变测试结论。

### 4.2 smoke 执行链路

smoke 层执行链路如下：

```text
pytest smoke
  -> FastAPI TestClient
  -> patched route dependencies
  -> /health or /chat or /chat/stream
  -> response / SSE chunks
  -> status, session_id, [DONE] assertions
```

smoke 的核心要求是快、稳定、离线。它应该尽早发现“服务入口不可用”，但不承担深度业务验证。

### 4.3 agentic_tool_loop unit 执行链路

agentic_tool_loop unit 执行链路如下：

```text
pytest unit
  -> scripted fake LLM stream
  -> fake tool dispatcher / parser / compression boundary
  -> run_agentic_loop
  -> collected SSE events or loop outputs
  -> rounds, dispatch, injection, compression, failure assertions
```

这一层测试应该尽量靠近真实 loop 控制流，只替换不可确定或外部依赖部分。不能为了方便断言而绕过 loop 主路径。

### 4.4 p2_api integration 执行链路

p2_api integration 执行链路如下：

```text
pytest integration
  -> FastAPI route
  -> controlled fake loop or fake LLM
  -> route lifecycle
  -> SSE streaming / finalize / save / cleanup
  -> API-level assertions
```

这一层验证 route 与下游协作是否正确，尤其关注异常恢复和请求生命周期。它不验证真实模型语义，也不验证工具后端业务效果。

### 4.5 quality gate 汇总链路

quality gate 汇总链路如下：

```text
pytest result
  -> test metadata / user_properties
  -> quality_gate_summary collector
  -> gate classification
  -> JSON report
  -> Markdown summary
  -> terminal summary
  -> optional Allure attachment
```

gate 汇总不能吞掉 pytest 失败，也不能用展示层结果覆盖测试原始结论。

## 5. 依赖替换与隔离架构

### 5.1 为什么需要替换依赖

NagaAgent 依赖真实 LLM、Langfuse、MCP、数据库、记忆系统、网络和时间等不稳定因素。若 PR 阻塞测试直接依赖这些组件，会导致失败原因不可定位、执行成本过高、结果不可重复。

因此测试架构要求：

- 控制流测试替换外部依赖。
- 集成边界测试只保留被测模块协作所需的最小真实度。
- 真实外部服务测试进入 real_llm、staging 或手动 profile。

### 5.2 依赖替换原则

依赖替换遵循以下原则：

- 替换不可控依赖，不替换被测控制流。
- fake 应表达行为，stub 应表达固定返回，monkeypatch 只作为注入手段。
- 替换点应靠近模块边界，而不是散落在业务逻辑内部。
- 每个测试应清楚说明自己替换了什么、保留了什么。
- 替换后的输出结构应尽量贴近真实组件契约。

### 5.3 替换对象分类

常见替换对象包括：

| 替换对象 | 默认策略 | 原因 |
| --- | --- | --- |
| LLM | fake stream / scripted response | 输出不确定、成本高、网络不稳定 |
| Langfuse | fake client / no-op helper | 观测链路不应影响业务断言 |
| MCP tools | fake dispatcher / stub result | 工具后端不属于 loop unit 范围 |
| database | in-memory fake / monkeypatch save | 避免持久状态污染 |
| memory | stub recall / fake retriever | 检索结果和后端状态不可控 |
| time / uuid | fixed value / monkeypatch | 保证断言稳定 |
| network notify | no-op stub | 避免测试外部副作用 |

### 5.4 fake / stub / monkeypatch 的职责边界

fake、stub、monkeypatch 的职责不同：

- fake 用于模拟一个有行为的替身，例如 scripted LLM 按轮次输出工具调用和最终回答。
- stub 用于返回固定值或 no-op，例如禁用远程通知、固定保存返回。
- monkeypatch 用于把 fake 或 stub 注入到被测模块，不应成为业务断言本身。

如果一个测试大量 monkeypatch 内部函数并绕过主控制流，说明它更像实现细节测试，应该重新评估测试边界。

### 5.5 隔离与清理原则

隔离和清理是测试稳定性的基础。

测试应确保：

- 不向真实用户数据、真实 Langfuse 项目、真实数据库写入 PR 测试数据。
- 每个测试结束后清理 active sessions、临时状态和 monkeypatch。
- fake 的内部状态只在单个测试内有效。
- 异常路径同样验证清理逻辑。
- 并发或流式测试不依赖测试执行顺序。

## 6. Quality Gate 架构定位

### 6.1 Gate 分层

Quality Gate 按阻塞能力分为三类：

| Gate | 作用 | 典型来源 |
| --- | --- | --- |
| PR Blocking Gate | 阻止明显不可合并变更 | smoke |
| Non-blocking Regression Gate | 暴露回归风险但不立即阻塞 | integration / real_llm |
| Quality Summary Gate | 汇总质量状态和趋势 | pytest metadata / report |

### 6.2 PR Blocking Gate 定位

PR Blocking Gate 的职责是快速、稳定地判断基础功能是否仍然可用。

它应该满足：

- 离线可运行。
- 不依赖真实 LLM 和真实外部服务。
- 失败原因明确。
- 执行时间短。
- 覆盖最关键入口。

当前 smoke 层是 PR Blocking Gate 的主要输入。

### 6.3 Non-blocking Regression Gate 定位

Non-blocking Regression Gate 用于发现更复杂的集成风险，但不直接阻塞常规 PR。

适合放入这一层的测试包括：

- p2_api resilience integration。
- real_llm smoke。
- 未来 memory integration。
- 未来 mcp_tools integration。
- staging full-chain。

这一层的失败需要被记录和观察，但是否阻塞合并应由项目阶段和 CI profile 决定。

### 6.4 Quality Summary Gate 定位

Quality Summary Gate 是对 pytest 结果的结构化汇总。

它负责：

- 聚合各测试层结果。
- 标记 blocking 与 non-blocking。
- 输出 JSON、Markdown、terminal summary。
- 给 Allure 提供附件或展示数据。

它不负责替代 pytest 的断言，也不负责根据 Langfuse trace 反推测试成功。

### 6.5 Gate Truth Source 定位

Gate truth source 必须来自可重复的测试断言和结构化测试结果。

优先级如下：

1. pytest assertion result。
2. pytest metadata / user_properties。
3. quality gate JSON summary。
4. Markdown / terminal / Allure 展示结果。
5. Langfuse trace 仅作为排查辅助。

因此，Langfuse 和 Allure 都不应作为 gate truth source。

## 7. Observability / Report / Allure 分工

### 7.1 Langfuse 的定位

Langfuse 是运行时 observability 系统，负责观察真实或接近真实请求中的 LLM、tool、trace、session 关系。

在 NagaAgent 测试体系中，Langfuse 适合用于：

- 调试一次请求中的 LLM generation。
- 观察 tool observation。
- 检查 session id 是否把多次 trace 关联到同一个会话。
- 排查真实环境中的延迟、错误和 token 使用。

Langfuse 不适合用于：

- 判断 PR 是否通过。
- 作为唯一测试报告。
- 替代 pytest assertion。
- 存放测试基线。

### 7.2 Allure 的定位

Allure 是测试报告展示层，负责让测试结果更容易阅读、筛选和追踪。

Allure 适合展示：

- 测试层级和模块分类。
- smoke、unit、integration、real_llm 的结果。
- Quality Gate summary 附件。
- 失败用例的上下文信息。

Allure 不应承载 gate 规则本身。即使 Allure 报告生成失败，也不应改变 pytest 的原始测试结论。

### 7.3 JSON / Markdown / Terminal Summary 的定位

JSON、Markdown、Terminal Summary 是 Quality Gate 的主要报告出口：

- JSON 面向机器读取和后续自动化处理。
- Markdown 面向 PR comment、文档化记录和人工 review。
- Terminal Summary 面向本地开发和 CI 日志快速判断。

这些报告应从同一个 quality gate 数据模型派生，避免多个报告之间出现口径不一致。

### 7.4 为什么 Langfuse 和 Allure 不作为 gate truth

Langfuse 和 Allure 不作为 gate truth，原因是它们的职责是观测和展示，不是判定。

主要原因包括：

- Langfuse 依赖网络、项目配置和异步 flush，天然不适合作为确定性 gate。
- Langfuse trace 可能用于真实请求，一个 trace 是否完整不等于测试断言是否通过。
- Allure 是 pytest 结果的展示层，不应反向定义测试是否成功。
- gate truth 需要稳定、可重复、可机器读取，pytest 和 JSON summary 更适合承担这一职责。

## 8. 可扩展架构

### 8.1 向 memory testing 扩展

memory testing 应沿用现有分层：

- unit 层验证 retriever、ranker、fallback、memory item schema。
- integration 层验证 p2_api 或 core_service 如何注入 memory 上下文。
- staging 层验证真实数据库、向量库或图数据库。

如果引入 GraphRAG/GRAG，应把图谱构建、图查询、片段引用和回答上下文注入拆开测试，避免把所有风险压进一个端到端测试。

### 8.2 向 mcp_tools testing 扩展

mcp_tools testing 应重点验证工具契约，而不是只验证某个工具偶然可用。

建议扩展方向：

- schema registration unit tests。
- tool dispatch contract tests。
- success / failure / timeout result normalization tests。
- agentic_tool_loop 与 mcp_tools 的 integration tests。
- staging profile 下的真实 MCP service tests。

### 8.3 向 golden cases 扩展

golden cases 适合沉淀稳定业务场景，但需要避免把真实 LLM 文本逐字匹配作为 gate。

建议策略：

- 对结构化输出做精确断言。
- 对工具调用链路做步骤级断言。
- 对自然语言回答只做关键事实、引用、格式或 rubric 级判断。
- 将高波动 golden cases 放入 non-blocking 或人工 review profile。

### 8.4 向 staging full-chain 扩展

staging full-chain 应作为发布前或定时回归能力，而不是替代本地 deterministic tests。

未来 staging 应覆盖：

- 真实 API server。
- 真实 LLM provider。
- 真实 Langfuse。
- 真实 memory backend。
- 真实 MCP tools。
- 多轮 session。

staging 失败通常说明环境组合或配置存在问题，需要结合 Langfuse、日志、Allure 和 JSON summary 共同排查。

## 9. 文档分工与阅读关系

### 9.1 architecture 与 overview 的区别

`docs/testing_architecture.md` 回答“测试体系为什么这样设计”。

`docs/testing/testing_overview.md` 回答“现在有哪些测试、怎么运行、从哪里开始看”。

当两者内容冲突时，应以本文档作为架构意图来源，以 overview 作为当前资产入口来源，并同步修正过期部分。

### 9.2 architecture 与模块测试文档的区别

模块测试文档负责说明具体模块的测试目标、文件分布和运行方式。

当前相关文档包括：

- `docs/testing/testing_p2_api_2.md`：p2_api 测试目标、route 边界和 stream 测试说明。
- `docs/testing/testing_agentic_tool_loop_4.md`：agentic_tool_loop 的 loop 控制流测试说明。
- `docs/testing/langfuse-integration.md`：Langfuse trace、session、generation、tool observation 接入说明。
- `docs/testing/testing_quality_gate_summary_8.md`：Quality Gate summary 的输出和使用说明。
- `docs/testing/Allure_gateway_plan.md`：Allure 展示层和 gateway 规划。
- `docs/testing/agent_workflow_golden_cases_plan.md`：golden cases 的规划方向。

### 9.3 推荐阅读顺序

推荐阅读顺序如下：

1. `docs/testing_architecture.md`：先理解测试体系的架构边界。
2. `docs/testing/testing_overview.md`：再了解当前测试资产和运行入口。
3. `docs/testing/testing_p2_api_2.md`：理解 API 与 SSE 测试。
4. `docs/testing/testing_agentic_tool_loop_4.md`：理解 agentic loop 单元测试。
5. `docs/testing/langfuse-integration.md`：理解 Langfuse trace 与 session 接入。
6. `docs/testing/testing_quality_gate_summary_8.md`：理解 gate summary 如何生成和使用。
7. `docs/testing/Allure_gateway_plan.md`：理解展示层如何承接测试结果。
8. `docs/testing/agent_workflow_golden_cases_plan.md`：理解后续 golden cases 扩展方向。
