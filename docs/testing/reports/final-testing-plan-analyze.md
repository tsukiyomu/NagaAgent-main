# NagaAgent Final Testing Plan 价值与决策分析

## 1. 文档定位

- 分析对象：[NagaAgent Final Testing Plan](../plans/nagaagent-final-testing-plan.md)
- 创建日期：2026-09-03
- 修订日期：2026-09-04
- 分支：codex/c0-4-intentional-red
- Revision：d6553a96f6987c5f58fdafddb99fc28e19c72eb0
- 工作单元：FTA-1 / FTA-AUDIENCE-1 — 解释 Final Testing Plan 的依据、工程价值与简历价值，并改写为仓库新读者可独立理解的版本
- 工作结果：DONE
- 学习迁移：TEACH_BACK_PENDING
- 性质：基于当前仓库证据的职业价值判断，不是招聘市场统计，也不是新的实施计划
- 目标读者：理解测试、Python、CI 和 Agent 基本概念，但此前没有接触过 NagaAgent 仓库的软件工程师或 SDET
- 阅读约定：不重复讲解 pytest、mock、CI 等通用入门知识；仓库专用模块、测试替换边界和缩写必须在首次出现时解释

建议阅读路径：

- 第一次了解项目或准备面试：先读第 2、5、6、8、9 节。
- 需要核对测试事实和边界：再读第 4、11 节。
- 继续维护计划：最后读附录 A、附录 B；这些执行记录不属于简历叙事正文。

本文回答：

1. 当前测试工作分别属于 NagaAgent 运行机制、测试设计、CI 还是交付流程的哪一部分？
2. 为什么已有最小 Closed Loop 后还要继续？
3. 我依据什么判断一项工作值得做？
4. P3-0～P3-9 分别解决什么风险？
5. 哪些内容真正增强简历竞争力，哪些只是必要地基？
6. 做到什么程度可以停下来，转向更具体的业务模块测试或其他项目？

## 2. 先建立上下文：这些工作分别属于哪里

### 2.1 NagaAgent 中被测试的基本流程

对本文而言，NagaAgent 是一个能够进行多轮推理并调用工具的 Agent 应用。与测试直接相关的主链路可以先简化为：

~~~text
客户端发起 /chat/stream 请求
  -> API Route 接收请求并准备 session、messages、context 和可用工具
  -> Agent Loop 调用 LLM，判断是直接回答还是请求工具
  -> 如果请求工具：执行工具，把工具结果加入下一轮 messages
  -> 如果不再请求工具：形成最终回答
  -> Route 持续发送 SSE 事件，并负责保存、通知和清理 active 状态
~~~

本文不会假定读者预先知道 `chat.py` 或 `agentic_tool_loop.py`。后文出现代码名时，它们分别对应：

- `chat_stream`：HTTP/SSE 入口，属于 API 与流式生命周期层。
- `run_agentic_loop`：多轮 Agent 调度循环，属于 Agent runtime/orchestration 层。
- `execute_tool_calls`：工具调用分发入口，属于 Agent 与工具系统的边界。

### 2.2 五个层次：不要把它们混成一个“测试平台”

| 层次 | 在 NagaAgent 中指什么 | 当前工作属于什么 | 当前状态 |
|---|---|---|---|
| 1. 项目运行机制 | Route、Agent Loop、LLM、Tool、Persistence 怎样协作 | P3-1 用源码和测试理解已有实现 | 已有代码，理解记录仍是 `PARTIAL` |
| 2. 测试设计 | 选择测试层，并决定哪些组件执行真实实现、哪些由可控替身代替 | 现有 pytest、fixture、Golden Case、P3-2/P3-3/P3-6 | 已有基础，仍有两个 `XFAIL_GAP` |
| 3. CI 质量反馈 | PR 是否运行测试、失败是否让 Check 变红、证据是否可下载 | C0 Closed Loop、P3-4、P3-5 | 最小闭环已完成；Agent 回归尚未全部接线 |
| 4. Agent 专属可靠性 | 多轮收敛、重复工具调用、取消、上下文和跨 session 隔离 | P3-2、P3-3、P3-6、P3-8 | 部分已有测试，关键缺口待关闭 |
| 5. 真实交付环境 | 真实模型/外部依赖、staging、部署后 smoke、rollback | P3-7、P3-9 | 条件不足，暂未完成 |

因此，C0 的主要成果属于第 2～3 层：它建立了可信测试选择、CI 红绿状态和失败证据链。
它不是 NagaAgent 业务功能本身，也还不是生产级 CD。P3-1 属于第 1 层的“项目理解”；P3-2/P3-3
才开始把这套基础设施用于更有 Agent 特征的运行时风险。

### 2.3 仓库专用术语

| 术语 | 本文中的含义 | 它不代表什么 |
|---|---|---|
| real Route | 测试实际执行 NagaAgent 的生产 API handler `chat_stream` | 不代表 Agent Loop、LLM、数据库和外部服务也都是真实的 |
| real Loop | 测试实际执行生产调度函数 `run_agentic_loop` | 不代表调用了真实 LLM 或真实外部工具 |
| scripted LLM | 用预先规定的模型响应驱动每一轮，使测试结果可重复 | 不验证模型回答质量，也不是线上模型 |
| fake tool | 用内存函数或固定结果代替真实工具执行 | 不验证 MCP、网络、权限或外部副作用 |
| persistence spy | 不真正写数据库，只记录“是否保存、保存几次、保存了什么” | 不验证数据库 schema、事务或真实读写 |
| authenticity profile | 按组件记录哪些运行生产实现、哪些被替换或禁用 | 它不是测试层，也不是“越真实越好”的排名 |
| Gate | 测试结果是否会影响 PR 合并或发布 | workflow 中存在一个 job 不等于它已经是 Required Check |
| XFAIL_GAP | 已有一条预期失败的 pytest，用可执行断言记录尚未满足的契约 | 不等于功能已经修复，也不等于普通测试失败可以忽略 |
| LANDED / PARTIAL / PLANNED | 已实现且有证据 / 只完成一部分 / 仅计划尚未实现 | 三者不能互相替代；计划文档不是实现证据 |
| NOT_WIRED / NON_BLOCKING | 尚未接入 CI / 已接入但结果暂不阻止合并 | 都不同于 PR Required Check |
| Golden Case | 用稳定输入和归一化期望结果描述的代表场景 | 不自动等于端到端测试；仍要说明它绕过或替换了哪些组件 |
| Replay Bundle | 经过脱敏、可下载并能在本地重放失败场景的输入和状态集合 | 普通日志或 JUnit 文件本身通常不足以完成重放 |

这里的 `real` 只表示“执行了仓库中的生产实现”，不是“整条链路连接了生产环境”。真实性必须逐个组件说明。

### 2.4 两个现有测试配置，用普通语言解释

| 测试配置 | 实际执行了什么 | 能回答的问题 | 不能回答的问题 |
|---|---|---|---|
| Stream Contract：real Route + fake Loop | 执行真实 `chat_stream`；用可控事件生成器代替 Agent Loop | Route 能否正确消费正常/异常事件、结束 SSE、保存并清理状态 | 多轮推理、真实工具调用、模型质量和外部依赖是否正确 |
| Loop tests：bypassed Route + real Loop + scripted LLM + fake tool | 不经过 HTTP；直接执行 `run_agentic_loop`，用固定模型响应和假工具驱动多轮 | Loop 是否按预期继续/停止、注入工具结果、进入 summary，以及调用次数是否正确 | HTTP/SSE、真实模型、真实工具和数据库是否可用 |

所以“把陌生 Agent 项目拆成 real Route、real Loop、scripted LLM、fake tool、persistence spy”并不是成果结论本身。
它属于第 2 层的测试设计方法：根据风险选择最小但充分的真实边界，使失败尽量能归因到一个模块。

### 2.5 在上述上下文下，再看职业价值结论

当前成果已经可以写进简历，竞争力主要来自三点：

1. 阅读陌生 Agent 项目的 Route、Loop、Tool 和 Persistence 边界，并针对不同风险设计可归因的测试配置。
2. 在 GitHub Actions 中跑通“绿色—故意红色—失败 JUnit Artifact—恢复绿色—人工 Gate 决定”。
3. 明确说明每组测试证明什么、不证明什么；没有把隔离 Remote Memory 后的绿色冒充成真实远端验证。

当前不足也很明确：

- 单条代表测试的代码不复杂，亮点仍偏测试架构、CI 证据和工程取舍。
- duplicate `tool_call_id` 与 user stop 两个 Agent 特有风险仍是 `XFAIL_GAP`。
- Quality Gate 已有代码，但没有接入 GitHub Actions。
- 还缺一份把 Route、Loop、Tool、message 变化和 Finalize 连成整体的基础 workflow 学习记录，也没有可独立回放的 Replay Bundle。
- 没有受控 staging E2E，不能称为生产级 Agent Release Gate。

Final Plan 因此不是继续堆测试数量，而是补齐三类深度：

| 深度 | 所属层次 | 当前状态 | 需要补充 |
|---|---|---|---|
| Agent 运行时深度 | 项目运行机制 + Agent 专属可靠性 | 已有收敛和消息注入；仍有两个 executable gap | P3-2、P3-3、P3-6 |
| Workflow 理解与复现深度 | 项目理解 + CI 诊断 | 代码和分层测试存在，但缺少统一的代码—状态—测试映射 | P3-1、P3-5 |
| 真实交付深度 | CI 质量反馈 + 真实交付环境 | 已有 PR Check/Release Packaging；缺 Workflow CI、staging、平台 CD | P3-4、P3-7、P3-9 |

最值得形成简历主线的是两个组合：

> Agent 状态安全：重复调用幂等 + 流式取消/清理

> 从理解到验证：基础 Agent Workflow Map + CI 失败证据 + 可重放失败样本

只增加几十条相似 pytest、画一张不能对应源码的流程图，或新建没有真实部署目标的 CD YAML，
都不会自然形成同等竞争力。

## 3. 判断标准

| 维度 | 关键问题 | 高价值表现 | 低价值表现 |
|---|---|---|---|
| Agent 特异性 | 是否来自多轮 LLM、工具、流式状态或上下文？ | tool_call_id 幂等、summary 收敛、取消、跨轮消息变化 | 普通 CRUD happy path |
| 风险后果 | 失败会造成什么？ | 重复副作用、假成功、状态泄漏、无限循环 | 仅格式不美观 |
| 跨边界难度 | 是否要理解多个模块？ | Route—Loop—Tool—Persistence—Telemetry | 单函数输入输出 |
| 确定性 | 能否用硬断言判断？ | 次数、顺序、唯一终态、状态清理 | “回答看起来不错” |
| 负向证据 | 是否证明能发现错误？ | xfail、intentional red、失败 Artifact、恢复绿色 | 只有一次 green |
| 可诊断/复现 | 别人能否独立定位或回放？ | nodeid、revision、round、message state、replay manifest | 只有截图 |
| 交付真实性 | 是否进入真实研发流程？ | PR Check、Artifact、staging、release decision | 仅本地脚本 |
| 可讲解性 | 能否解释取舍与边界？ | 为什么 mock、为什么不 Required、何时推翻设计 | 只会念工具名 |

复杂度不等于代码行数。duplicate tool_call_id 的修复可能不长，但必须决定去重范围、状态归属、
重复副作用、assistant/tool message 一致性和失败结果。面试价值来自这些决策和证据。

## 4. 当前仓库证据

### 4.1 静态盘点

2026-09-03 使用 inventory 工具得到：

| 项目 | 事实 |
|---|---|
| 测试文件 | 16 |
| 静态测试定义 | 85 |
| Fixtures | 6 |
| 使用 monkeypatch fixture 的测试 | 13 |
| 配置 | pyproject.toml、pytest.ini |
| CI 测试 workflow | PR Smoke Gate、PR Stream Contract Gate |

静态数量不等于覆盖率，也不会因 case 数量增加而自动提高项目价值。

### 4.2 本轮执行

| 范围 | 结果 | 证明 | 不证明 |
|---|---|---|---|
| Agent Loop + Golden + Quality Gate unit | 29 passed, 1 xfailed, 4 warnings in 17.02s | 相关 deterministic 资产在当前 revision 可执行 | 真实 LLM/工具/Memory、Route 或 CI |
| 两条 Stream Contract 精确 nodeid | 2 passed, 3 warnings in 12.38s | 真实执行 Route、用替身隔离 Loop 时，正常/异常终止契约通过 | 真实 Agent Loop 和外部依赖 |

本轮 Loop xfail：

- tests/unit/agentic_tool_loop/test_loop_message_injection.py::test_duplicate_tool_call_id_is_deduplicated_across_rounds

另一个已知 executable gap：

- tests/integration/chat_stream/test_resilience.py::TestChatStreamRouteWithFakeLoop::test_chat_stream_user_stop_contract_gap

### 4.3 能力边界

| 能力 | 状态 | 证据 | 边界 |
|---|---|---|---|
| Loop 收敛 | LANDED | run_agentic_loop、test_loop_convergence.py | LLM/工具/queue/compression 多为替身 |
| 重复 tool_call_id | XFAIL_GAP | test_loop_message_injection.py:337 | 目标断言已存在，runtime 未满足 |
| User stop | XFAIL_GAP | test_resilience.py:593 | 提前关闭 TestClient 只是近似，协议未定义 |
| Stream lifecycle | LANDED | 两条 blocking Stream cases | 真实执行 Route；Agent Loop 被可控替身代替 |
| Golden Cases | PARTIAL / NOT_WIRED | 5 个 YAML case，本轮 5 条通过 | bypass Route/Persistence/Memory |
| Quality Gate | LANDED/PARTIAL / NOT_WIRED | quality_gate.py、5 条 unit tests | 当前不驱动 GitHub Check |
| CI 失败证据 | VERIFIED | pytest + if: always() JUnit；历史红绿 run | Stream 仍为 NON_BLOCKING |
| Remote Memory | 产品 LANDED；真实测试 DELAYED | Route 会查询；fixture 替换为 None | 绿色不证明认证/query/fallback |
| Basic Agent Workflow Model | PARTIAL | Route、Loop 和代表测试均已存在 | 尚缺统一的代码 ownership、状态变化和测试映射记录 |
| Replay Bundle | PLANNED | 未发现可回放实现 | Langfuse helper 的 replay/debug 文案不等于回放包 |
| CD | PARTIAL | build-release.yml 构建三平台并发布 Release | 没有 deploy/health/rollback |

范围纠正：Jaeger 与 NagaAgent 项目没有实现或计划依赖。本报告不再把 Jaeger 当作 P3-1 的目标；
如果以后单独学习 Jaeger，应放在另一个项目或独立学习记录中。

## 5. 为什么 Closed Loop 完成后仍值得继续

Closed Loop V1 证明的是测量与治理链路：

~~~text
测试选择
  -> pytest assertion
  -> GitHub Check 红/绿
  -> 失败仍上传 JUnit
  -> nodeid/assertion/run/revision 可定位
  -> 恢复绿色
  -> 人工决定 Gate
~~~

它证明“测试和证据链会工作”，还没有充分证明“复杂 Agent workflow 在关键风险下会正确工作”。

- C0-1～C0-6：建设可信测量仪器和使用规范。
- P3-2/P3-3/P3-6：用它解决 Agent 运行时问题。
- P3-1：先把基础 Agent workflow 从真实代码讲清楚；P3-5 再让多轮失败可复现。
- P3-4/P3-7/P3-9：把结果逐步带入真实交付环境。

现在停止，可以讲“测试框架与 CI 闭环”；完成高价值 P3 单元后，才更接近
“Agent workflow reliability engineering”。

## 6. 每个工作单元的依据和价值

先按所属层次定位，再阅读各单元的技术细节：

| 工作单元 | 主要所属层次 | 要解决的问题 | 预期产物 | 在简历叙事中的角色 |
|---|---|---|---|---|
| P3-0 | 工程治理 | 清除证据分支与目标基线混杂 | 干净 revision、回归结果、Owner 决定 | 必要地基，不单独作为主 bullet |
| P3-1 | 项目运行机制理解 | 让仓库新读者理解一次 Agent 请求怎样运行 | 源码入口、时序、状态变化与代表测试映射 | 面试讲解基础，不单独包装成平台成果 |
| P3-2 | Agent 专属可靠性 | 防止重复工具调用造成重复副作用 | 幂等契约、修复、负向与回归证据 | 核心竞争力 bullet |
| P3-3 | API 生命周期 + Agent 可靠性 | 明确用户停止后如何取消、保存和清理 | cancel/finalize 契约与集成测试 | 核心竞争力 bullet |
| P3-4 | CI 质量反馈 | 让 Agent 回归在 PR 中自动执行和报告 | non-blocking Check 与 Quality Artifact | CI/测试开发能力的支撑 bullet |
| P3-5 | 失败诊断与回归资产 | 把一次多轮失败变成可脱敏重放的样本 | Replay Bundle、manifest、replay command | 差异化能力 bullet |
| P3-6 | Context 组件边界 | 验证上下文组装、预算和降级行为 | 组件测试与 Route/Loop 边界测试 | 绑定具体 Context 风险后作为补强 |
| P3-7 | 真实交付环境验证 | 补足 fake 无法证明的认证、网络和部署配置 | 少量受控 staging E2E 证据 | 有真实环境证据时可作为主 bullet |
| P3-8 | 可靠性工程 | 验证并发隔离和故障下的收敛 | 隔离 invariant、阈值和可复现报告 | 前置充分时可成为高级补强 |
| P3-9 | CD/发布工程 | 将测试结果用于部署、健康检查和回滚 | 部署后的 smoke、promotion/rollback 证据 | 只有真实部署平台存在时才值得写 |

### 6.1 P3-0：收口当前基线

所属层次：工程治理；它整理测试工作的起点，不新增 Agent 功能。

依据：

- 当前仍在 intentional-red 证据分支。
- PR #2 含故障注入历史，不能按普通功能 PR 描述。
- Remote Memory 隔离需要在目标分支干净处理。

判断：

- 工程必要性：高。
- 单独简历价值：低。
- 面试辅助价值：中，可展示 baseline、证据分支和主分支纪律。

它是地基，不应占简历主 bullet，但必须防止后续 workflow 学习、幂等和取消工作建立在混杂 revision 上。

### 6.2 P3-1：Basic Agent Workflow Understanding

所属层次：项目运行机制理解；它先回答“NagaAgent 怎样工作”，再支持后续测试设计。

依据：

- chat_stream 负责请求、session、messages/context/tools 准备、SSE 消费和最终清理。
- run_agentic_loop 负责 round、LLM、tool normalize/dispatch、result injection、queue/compression 和 summary。
- 当前这些知识散落在生产代码、测试和多份文档中，容易知道“有这些模块”却讲不清状态如何实际流动。

价值：

- 理解一个基础 tool-using Agent 为什么需要多轮 loop。
- 解释无工具直接结束、有工具继续下一轮、连续失败/max_rounds 进入 summary 三条路径。
- 解释 tool result 为什么必须以 assistant/tool message 回注，Route 与 Loop 为什么不能混为一层。
- 把每个状态、数据变化和 side effect 映射到真实代码及代表测试。

学习价值：很高。它是后续判断“该在哪一层测试、该保留什么真实、失败意味着什么”的前提。

单独简历价值：中等。只画流程图不是成果；能够把源码、状态变化、测试断言和两个真实 gap 连起来，
才可作为架构理解和测试设计能力来讲。

完成形态：

1. 三条代表 workflow 的时序与 message/state 变化表。
2. 精确代码入口：chat_stream、run_agentic_loop、execute_tool_calls、result injection、finalize。
3. 每个关键节点对应的代表测试、断言、真实性 profile 和 proof boundary。
4. 用户能用自己的话解释流程；不要求引入任何新可观测平台。

### 6.3 P3-2：Duplicate Tool Call ID

所属层次：Agent 专属可靠性；核心是跨轮幂等和副作用控制。

依据：

- Runtime 将调用 ID 写入 _tool_call_id，用于 assistant/tool message 回注。
- 现有 xfail 构造两个 round 重复返回 dup-id。
- 目标断言要求 tool message 和 assistant call reference 各只保留一次。

风险：

- 有副作用工具可能重复执行。
- 重复 tool result 会使下一轮决策失真。
- 保存、通知、扣费或外部写操作可能被放大。

简历价值：很高。它体现状态机、幂等、side-effect safety 和跨轮协议一致性。

完成证据至少应包括：去重作用域决定、执行次数断言、消息一致性、修复前失败、修复后 green 和完整回归。

### 6.4 P3-3：User Stop / Cancel Finalization

所属层次：API 流式生命周期与 Agent 专属可靠性的交界。

依据：

- Stream 正常/中途异常可 finalize，但显式停止没有产品契约。
- 现有 xfail 只用 TestClient 提前关闭近似 disconnect。
- chat.py 有 finally 清理 active flag，没有明确 cancel/abort 状态传播。

风险：

- 客户端停止后 Agent 仍调用工具或付费模型。
- partial answer 被当作正常完成保存。
- active 状态残留或 terminal 重复。
- cancel、异常和成功无法区分。

简历价值：很高。它连接 SSE、async generator cancellation、Loop 中断、持久化和资源清理。

实现前必须决定：是否保存 partial content、终态事件、通知语义和工具停止策略。没有产品决定，
测试只能锁住猜测。

### 6.5 P3-4：Agent Workflow Non-blocking CI

所属层次：CI 质量反馈；它负责自动执行与发布证据，不负责定义 Agent 业务正确性。

依据：

- Tool Loop、Golden、Quality Gate 本地可运行，未进入 GitHub workflow。
- 现有 Stream workflow 只选择两条“真实执行 Route、用替身隔离 Agent Loop”的 case。
- Quality Gate 的 pass/warn/fail 当前不影响 job。

价值：

- 把 Agent 回归从“仓库里有”变成“每个 PR 有反馈”。
- 同时留存 JUnit、Quality JSON/Markdown。
- 先 NON_BLOCKING 积累稳定性，再由人决定晋升。

简历价值：中高。因为 C0 已做过 CI 接线，单纯复制 YAML 增量有限。只有 selection 真正覆盖
Agent Loop/Golden、报告能定位 failure stage/baseline delta，并具备成功和失败证据时，才是新亮点。

### 6.6 P3-5：Replay Bundle

所属层次：失败诊断与可复现回归资产；它连接 CI 失败和本地调试。

依据：

- JUnit 能定位断言，不能重建多轮 messages/tool calls/tool results。
- 代码走读和日志可以解释时序，但它们通常不是可执行的确定性测试输入。
- Agent badcase 常依赖多轮上下文和外部返回。

价值：

- 将失败现场转换为最小、脱敏、版本化的可执行输入。
- 连接 Artifact、revision、case_id/nodeid、round/message state 和 replay command。
- 将诊断最终沉淀为 deterministic regression。

简历价值：很高，也是明显差异化能力。P3-1 + P3-5 的组合链路：

~~~text
CI/Test failure
  -> failure_stage + round/message evidence
  -> workflow model 定位失败阶段
  -> 下载脱敏 Replay Bundle
  -> 本地重放
  -> 修复并固化 regression
~~~

难点还包括安全裁剪：不能保存 token、私人 prompt、真实 Memory 和无限制工具结果。

### 6.7 P3-6：Context Boundary

所属层次：Context 组件及其与 Route/Loop 的集成边界。

依据：

- Loop 已测 compression 时机和替换后的 messages。
- Stream 已测 compression exception 的降级。
- 真实 assembly、budget/timeout、硬约束保持仍不完整。

简历价值：中；绑定真实业务后可以升高。只增加 monkeypatch exception 会与现有 resilience 重复。
更有价值的是长上下文后保留硬约束、assembly timeout 的明确降级、当前指令与历史/Memory 的优先级。

Context 模块负责内容与预算，Route/Loop integration 只验证异常不会拖死 Stream。

### 6.8 P3-7：受控 Staging E2E

所属层次：真实交付环境验证；它补充确定性测试无法覆盖的环境风险。

依据：

- 使用替身的确定性测试容易归因，但不能证明认证、网络、部署配置和真实模型组装。
- Remote Memory 401 已实际展示 stub 无法发现的环境问题。

简历价值：高，但依赖环境。一到三条可靠 E2E 比几十条不稳定 real-LLM case 更有价值。

必须记录 revision、环境、真实性矩阵、secret/预算/timeout、数据命名空间、cleanup、执行日志和回读。
Remote Memory 可以继续 DELAYED；认证和清理未确定时强行加入只会破坏归因。

### 6.9 P3-8：并发与故障注入

所属层次：可靠性工程；它在基本功能契约稳定后验证隔离性和降级能力。

依据：session、queue、tool result 和状态都可能串线；MCP、telemetry side channel、queue 也可能慢、429 或不可用。

简历价值：条件性高。只有先有 workflow model、Replay、隔离 invariant 和阈值时才值得做。
比“跑了 50 并发”更重要的是证明 session 不串线、故障按契约 degrade/stop、观察侧路不影响业务，
并且失败可复现。

### 6.10 P3-9：CD Quality Handoff

所属层次：CD/发布工程；它关注测试结果如何影响部署、健康检查和回滚。

依据：build-release.yml 已构建三平台并创建 GitHub Release，但没有 staging/production、health 或 rollback。

简历价值取决于真实平台。再写一个名为 deploy 的 workflow 不构成 CD。只有不可变产物、环境审批、
部署、post-deploy smoke、promotion/rollback 和部署证据形成闭环后才值得宣传。

## 7. 工程顺序与简历价值顺序

### 7.1 工程顺序

~~~text
P3-0 基线收口
  -> P3-1 Basic Agent Workflow 理解
  -> P3-2 幂等
  -> P3-3 取消
  -> P3-4 Agent Workflow CI
  -> P3-5 Replay
  -> P3-6/P3-7 补强
  -> P3-8/P3-9 条件性扩展
~~~

P3-1 先做是因为不先理解 Route、Loop、Tool 和 Finalize 的职责，就无法可靠判断 P3-2/P3-3
该改哪一层、测什么状态。它必须控制在代码走读、状态模型和代表测试验证范围内。

### 7.2 简历价值顺序

| 层级 | 工作 | 原因 |
|---|---|---|
| S | P3-2 + P3-3 | Agent 状态机、幂等、副作用和异步生命周期 |
| A | P3-5 | 多轮失败可下载、可回放并转成 regression |
| A | P3-4 | Agent regression 进入真实 PR 协作 |
| A | P3-7 | 补真实环境证据 |
| B | P3-6 | 绑定真实 Context 契约时价值更高 |
| 学习地基 | P3-1 | 理解基础 Agent workflow，并为后续测试和面试深问建立代码模型 |
| 基础 | P3-0 | 必须做，但不是主成果 |
| 条件性 | P3-8/P3-9 | 前置或真实平台不足时易变成展示性工程 |

S/A/B 是本项目内部的职业价值排序，不是行业统一标准。

## 8. 建议完成线

### 8.1 现在已经可以写

> 分析 NagaAgent 的 HTTP/SSE Route、Agent Loop、工具调用与持久化边界，针对不同风险设计分层 pytest；
> 将 Smoke/Stream Contract 接入 GitHub Actions，以 pytest exit code 驱动 Check，并通过故障注入、
> 失败 JUnit Artifact 和恢复绿色验证 CI 质量闭环。

当前面试深挖会主要落在测试切面、mock 边界和 CI 证据，而不是复杂业务算法。

### 8.2 推荐“竞争力完成线”

不必等 P3-0～P3-9 全部完成：

1. P3-0 收口干净基线。
2. P3-1 完成基础 Agent workflow 的代码、状态和测试映射，并能够 teach-back。
3. P3-2 或 P3-3 至少关闭一个真实 Agent gap；最好两个。
4. P3-4 将 deterministic Agent regression 作为 NON_BLOCKING PR signal。
5. P3-5 再把一条多轮失败关联到本地 Replay；它是强增强项，但不是理解基础 workflow 的前置条件。

届时可以升级为：

> 基于 NagaAgent 的生产 Route、Agent Loop 和工具分发代码建立可追溯的 workflow 模型；针对重复工具调用
> 和流式取消建立确定性契约，并通过 Failure Replay 与非阻塞 PR Quality Signal，使多轮 Agent 风险能够
> 被解释、检测、归因和复现。

### 8.3 更强但非当前必要

- P3-7：一到三条安全、可清理的 staging E2E。
- P3-8：基于 session isolation invariant 的轻量并发/故障注入。
- P3-9：真实平台上的 post-deploy smoke 和 rollback evidence。

这些会增强生产相邻经验，但不应阻塞你转向更具体的业务模块测试。

## 9. 面试深挖链

### 9.1 Duplicate tool_call_id

应能解释：重复 ID 为什么放大副作用、状态归谁、为何不能只删 tool message、assistant/tool 协议如何一致、
以及 xfail 如何转为修复后的 regression evidence。

### 9.2 User stop

应能解释：HTTP 200 与业务完成的区别；disconnect/stop/timeout/exception 的差异；cancel 如何传播；
partial content 是否保存；finally cleanup 为什么不等于完整取消协议。

### 9.3 Basic Agent Workflow + Replay

应能解释：Route、Loop、LLM、Tool、Result Injection、Finalize 各自负责什么；三条主要结束路径；
代码走读为什么不能代替 assertion；Replay 保存什么以及如何脱敏；怎样把 CI failure 固化为 regression。

## 10. 不建议作为主线

| 做法 | 原因 |
|---|---|
| 大量相似 Tool Loop happy path | 数量增加，风险和设计深度不增加 |
| 所有 PR 都调用 real LLM/MCP/Memory | 慢、贵、波动，失败难归因 |
| 为本项目先引入无关可观测平台 | 偏离“理解基础 Agent workflow”的目标 |
| LLM-as-a-Judge 直接阻塞 PR | 非确定，缺稳定 oracle 和人工认可 |
| 自动覆盖 baseline | 会把回归吸收为“正常” |
| 无平台时补“完整 CD” | 无法验证 deploy/health/rollback |
| 为绿色报告削弱 assertion | 丢失负向检测能力 |

## 11. 事实与职业判断边界

已确认事实：

- 16 个测试文件、85 个静态测试定义。
- 本轮 Agent Loop + Golden + Quality Gate 为 29 passed, 1 xfailed。
- 本轮两条 Stream Contract 为 2 passed。
- duplicate tool_call_id 和 user stop 是 executable xfail。
- Smoke/Stream workflow 生成 JUnit，并使用 if: always() 上传。
- Golden/Quality Gate 未接入 GitHub workflow。
- Jaeger 不是 NagaAgent 本计划的依赖或目标；P3-1 只基于现有代码和测试学习 workflow。
- Remote Memory 在目标 deterministic fixture 中显式隔离。

职业判断：

- P3-2/P3-3 比继续增加普通 happy path 更有价值。
- P3-1 的价值是建立真实代码模型；P3-5 的价值是把该模型用于失败复现，不能互相替代。
- P3-8/P3-9 在缺少前置或真实平台时投入产出低。
- 达到“竞争力完成线”后，可以把更多精力转向业务测试或其他项目。

目标岗位会改变权重：测试开发更看 CI/fixture/data/stability；Agent/后端更看 Loop/取消/幂等；
SRE/平台更看可观测性、Replay、并发、staging 和 rollback。

## 12. 面向读者的理解自检

读完后，尝试不用文档回答：

1. C0 Closed Loop 主要属于哪两个工程层次？为什么它不等于生产级 Agent Workflow Gate？
2. `real Route + fake Loop` 实际执行和替换了什么？它能证明什么、不能证明什么？
3. P3-2 代码可能不长，为什么价值仍高？
4. 代码走读、pytest assertion、Replay Bundle 分别解决什么？
5. 为什么 P3-0 必须先做，却不占简历主 bullet？
6. 如果只完成三个能力，你选哪些，依据是什么？

能把答案与具体代码、测试、CI run 或 failure evidence 对应后，再将学习状态更新为 MASTERED。

## 附录 A：维护者 / Agent 工作单元记录（首次阅读可跳过）

### A.1 方案比较

| 方案 | 优点 | 风险 | 决定 |
|---|---|---|---|
| 逐条复述 Final Plan | 容易 | 仍回答不了为什么和价值 | 拒绝 |
| 只给简历 bullet | 快 | 无法支持深问 | 拒绝 |
| 仓库证据 + 风险 + 职业价值 | 可验证、可学习、可取舍 | 文档较长 | 采用 |

Guided-learning checkpoint：不需要。本单元只创建分析记录，不修改产品契约或 Gate；在看到完整依据前
要求用户先选优先级会造成无意义暂停。学习状态保持 TEACH_BACK_PENDING，不能因文档完成而标为 MASTERED。

### A.2 变更边界

| 项目 | 结果 |
|---|---|
| 新建 | docs/testing/reports/final-testing-plan-analyze.md |
| 产品/测试代码 | 未修改 |
| CI/Gate | 未修改 |
| Final Plan | P3-0 仍为 NEXT；本分析不算 P3 实施完成 |
| Git | docs/ 被 .gitignore 忽略，文档当前仅在共享 workspace |

### A.3 执行偏差

首次尝试在当前 Windows command wrapper 中直接传递带空格的 marker 表达式，被拆成路径参数，
pytest exit code 4、未执行测试。随后改用两条精确 nodeid，结果为 2 passed。该错误属于命令封装，
不是测试或产品失败。

### A.4 2026-09-04 范围纠正

| 初始判断 | 用户纠正 | 修订结果 |
|---|---|---|
| 把 Jaeger 接入当作 P3-1 学习路径 | Jaeger 与 NagaAgent 无关；目标是基于 NagaAgent 理解基础 Agent workflow | 删除 Jaeger/OTel 接入目标；P3-1 改为 Route—Loop—Tool—Finalize 源码、状态与测试映射 |

这次纠正也说明：技术工具不能仅因“有学习价值”就自动进入项目计划；必须先证明它属于项目目标或实现边界。

### A.5 2026-09-04 目标读者纠正

| 原问题 | 对陌生工程师的影响 | 修订结果 |
|---|---|---|
| 开头直接使用 real Route、real Loop、scripted LLM、persistence spy 等内部 shorthand | 读者知道测试概念，却不知道这些词在 NagaAgent 中对应哪些代码和边界 | 先增加基础运行链路、五层归属图、仓库术语表和两种测试配置示例 |
| 职业价值、仓库事实和后续计划混在同一层叙述 | 难以判断某项成果属于产品 runtime、测试架构、CI 还是 CD | 为 P3-0～P3-9 增加“主要所属层次”和预期产物 |
| 简历 bullet 假定面试官已了解仓库 | 容易变成工具名堆叠，无法独立表达问题与成果 | 改为先说明 NagaAgent 边界，再说明测试设计、CI 行为和证据 |

本次改写不把读者当作编程初学者；它只补足理解本仓库所需的上下文，并保留可供面试深问的代码标识。

## 附录 B：当前计划接续点（面向维护者）

Final Plan 的下一工作单元仍是 P3-0。本分析没有启动 P3-0，也没有执行产品修复、
真实 Remote Memory、staging 或 CD。

P3-0 完成后，再按同一方法开始 P3-1：从 chat_stream 追到 run_agentic_loop 和 execute_tool_calls，
画出三条代表路径的 messages/state 变化，并用已有测试核对理解；不引入新的可观测平台。
