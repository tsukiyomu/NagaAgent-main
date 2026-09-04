# NagaAgent 测试工程与 CI/CD 面试介绍大纲

> 文档状态：`持续完善`  
> 当前事实快照：2026-09-03，分支 `codex/c0-4-intentional-red`，Revision `d6553a96f6987c5f58fdafddb99fc28e19c72eb0`  
> 使用方式：这是一份面试叙述骨架，不是逐字背诵稿。每次项目状态变化后，应重新核对代码、测试结果和 GitHub Actions 证据。

## 0. 状态标记

- `[当前可讲]`：已有代码、执行结果或 CI 证据支持。
- `[待完善]`：方向成立，但还需要补实现、证据或个人复盘。
- `[可能深问]`：面试官可能继续追问，至少要能解释因果关系。
- `[不能宣称]`：当前证据不足，不能作为已完成成果介绍。

## 1. 一句话项目定位

### 1.1 当前可讲

> 我围绕 NagaAgent 的流式对话和多轮工具调用链路，借助 Codex 盘点并理解陌生代码库，建立了分层 pytest 测试、依赖隔离、GitHub Actions 检查和失败 Artifact 留存机制，完成了一条从测试设计、执行、CI 红绿验证到人工 Gate Decision 的最小可验证闭环。

### 1.2 表述边界

- `[当前可讲]` 这是 AI Agent workflow 的测试基础设施与 CI 证据闭环。
- `[当前可讲]` 测试代码的算法难度不高，主要难点是架构理解、测试切面、依赖真实性和失败证据设计。
- `[不能宣称]` 已完成复杂业务模块的全面测试。
- `[不能宣称]` 已完成生产级 Agent Release Gate。
- `[不能宣称]` 已完成真实 LLM、MCP、Remote Memory 和部署环境的全链路 E2E。
- `[待完善]` 完成 CD 后，再把“一直到部署、健康检查和回滚”的内容加入一句话定位。

## 2. 30 秒版本

### 2.1 当前可讲

> NagaAgent 是一个包含 SSE 流式响应、多轮 LLM 推理、工具调用、Context Compression 和 Queue 注入的 Agent 项目。我先借助 Codex 从 `/chat/stream` 入口反向梳理到 `run_agentic_loop`，再按 Smoke、API/Integration、Agent Loop Unit 和 Golden Case 分层测试。为了保证测试可重复，我保留真实 Route 或真实 Loop，同时用 scripted LLM、fake tools 和 spy 隔离不稳定外部依赖。最后将 Smoke 和两条 Stream Contract 接入 GitHub Actions，通过一次真实 assertion 错误注入证明检查会变红，并用 `if: always()` 在失败时继续保存 JUnit Artifact，形成了最小的测试—CI—证据—决策闭环。

### 2.2 待完善

- `[待完善]` 将上面内容压缩成自己的自然表达，避免逐字背诵。
- `[待完善]` 准备一个能够在 30 秒内画出的简化架构图。
- `[待完善]` CD 完成后补充部署目标、部署验证和回滚证据。

## 3. 两分钟介绍主线

1. 项目是什么：带有流式响应和工具调用的 AI Agent 系统。
2. 原问题是什么：测试资产存在，但分层、真实性边界、CI Gate 和失败证据不够清楚。
3. 如何理解架构：从 Route 追踪 Agent Loop、LLM、Tool、Context、Queue 和 Finalization。
4. 如何选择测试层：使用最低但足以证明目标契约的测试层。
5. 如何控制外部依赖：不同 profile 保留不同真实组件，避免所有测试访问真实服务。
6. 如何接入 CI：Smoke 与 Stream Contract 由 GitHub Actions 自动执行。
7. 如何证明闭环有效：稳定绿灯、错误注入红灯、失败 Artifact、恢复绿灯。
8. 当前结果和边界：最小 Closed Loop 已验证，综合 Agent Gate、真实 staging 和 CD 仍待完善。

### 3.1 待完善

- `[待完善]` 为每一步准备一个真实文件、测试名或 GitHub Run 作为证据。
- `[待完善]` 练习在两分钟结束时主动说明边界，而不是等面试官指出夸大。

## 4. NagaAgent 架构理解

### 4.1 核心执行链

```text
HTTP /chat/stream
  -> FastAPI route 解析请求并建立 SSE response
  -> run_agentic_loop(messages, session_id, tools, max_rounds)
  -> 每轮检查 context compression
  -> LLM 流式输出 content/reasoning/tool_calls
  -> 解析并执行 MCP/OpenClaw/local tool
  -> tool result 回注 messages
  -> queue 侧路消息在下一轮前注入
  -> 无工具调用时正常收敛
  -> 连续失败或 max_rounds 时进入 summary round
  -> route finalize / cleanup / persistence / terminal event
```

### 4.2 面试时应能解释的模块

| 模块/边界 | 当前理解重点 | 主要代码入口 | 状态 |
|---|---|---|---|
| HTTP/SSE Route | 请求进入、事件转发、结束和状态清理 | `apiserver/routes/chat.py` | `[当前可讲]` |
| Agent Loop | 轮次、收敛、工具执行、回注、summary | `apiserver/agentic_tool_loop.py::run_agentic_loop` | `[当前可讲]` |
| LLM Boundary | 流式 chunk、原生 tool call、真实/替身模型 | `apiserver/llm_service.py` | `[可能深问]` |
| Tool Dispatch | MCP/OpenClaw/local tool 分发及错误归一化 | `execute_tool_calls(...)` | `[当前可讲]` |
| Context | 每轮压缩及压缩失败降级 | `apiserver/context_compressor.py` | `[可能深问]` |
| Message Queue | 工具执行后、下一轮前注入且避免重复 | `apiserver/message_queue.py` | `[当前可讲]` |
| Persistence/Finalize | 保存、通知、active flag、唯一 terminal event | Route finalize path | `[可能深问]` |
| Remote Memory | 产品能力；当前特定 SSE 契约内隔离 | fixture/route boundary | `[待完善]` |

### 4.3 可能深问

- `[可能深问]` 为什么工具结果必须回注下一轮 messages，而不是直接返回给用户？
- `[可能深问]` `round_end.has_more`、`[DONE]` 和最终保存之间是什么关系？
- `[可能深问]` 为什么 Queue 消息要合并到最后一条 user-semantic message？
- `[可能深问]` Context Compression 失败为什么可以降级，而不能直接让整个流失败？
- `[可能深问]` 连续工具失败和 `max_rounds` 为什么需要 summary round？
- `[待完善]` 阅读并准备 Route 层 persistence/finalize 的完整正常和异常路径。
- `[待完善]` 补充一张包含真实数据对象变化的时序图。

## 5. 如何从 0 借助 Codex 构建测试框架

### 5.1 工作方法

1. 盘点仓库：测试文件、pytest 配置、fixtures、GitHub workflows 和生产入口。
2. 建立架构模型：从公开入口沿调用链定位状态所有者和依赖边界。
3. 建立风险地图：先选择高价值、稳定、可归因的 Smoke 和 SSE lifecycle。
4. 划分独立维度：测试层、真实性 profile、实现状态和 Gate 状态不能混为一谈。
5. 建设公共能力：marker、fixture、scripted LLM、queue stub、SSE parser、failure attribution。
6. 先跑最窄测试，再扩展到完整回归。
7. 接入 GitHub Actions 并保存 JUnit Artifact。
8. 用真实 assertion failure 验证负向检测能力，再恢复绿色契约。
9. 记录当前证据、未覆盖边界和人工 Gate Decision。

### 5.2 Codex 与人的职责

#### Codex 辅助内容

- 快速检索和梳理陌生代码。
- 生成候选测试、fixture、辅助函数和文档草稿。
- 执行 pytest、读取输出、收集 CI/Artifact 证据。
- 对照架构同步测试文档和 Current Progress。

#### 人负责的决定

- 决定什么行为具有业务或工程风险。
- 决定在哪一层验证，哪些组件保留真实。
- 复核断言是否真的代表目标契约。
- 决定测试能否进入 blocking gate。
- 对真实服务、成本、凭据和发布风险作最终判断。

### 5.3 可能深问与待完善

- `[可能深问]` 如何避免直接相信 Codex 生成的测试？
- `[当前可讲]` 回答方向：读生产入口、核对替身位置、执行测试、进行错误注入，并只声明证据实际证明的内容。
- `[可能深问]` Codex 生成测试通过，是否可能只是在验证 mock？
- `[当前可讲]` 回答方向：可能，因此每个 profile 都要说明 real/replaced/controlled 组件和 proof boundary。
- `[待完善]` 选择 2～3 次有代表性的 Codex 决策过程，保存原始需求、候选方案、人工修改和最终证据。
- `[待完善]` 准备一次 Codex 建议不合适、自己根据代码证据修正方向的例子。

## 6. 测试分层与真实性设计

| 测试组 | 测试层 | 真实性 profile | 当前 Gate | 当前状态 | 能证明 | 不能证明 |
|---|---|---|---|---|---|---|
| API Smoke | Smoke/API | real route + controlled downstream | GitHub workflow；marker 为 blocking | `LANDED` | 关键接口最小可用和终止事件 | 真实 LLM/MCP/Memory 可用性 |
| Stream Contract baseline/failure | Integration/API | real route + fake loop | 当前 Stream 决策为 `NON_BLOCKING` | `LANDED` | Route 消费 SSE、terminal、cleanup、异常 finalization | 真实 Agent Loop 和模型质量 |
| Stream real-loop profile | Integration | real route + real loop + scripted LLM | 未作为独立 PR gate | `LANDED/PARTIAL` | Route 与 Loop 的编排协作 | 真实模型和外部工具质量 |
| Agent Tool Loop | Unit/Component | real loop + scripted LLM + fake tools/queue/compression | `NOT_WIRED` | `LANDED` | 收敛、timeout、max rounds、回注和 failure stage | 真实工具和跨服务可用性 |
| Golden Cases | Golden case | real loop + stub LLM/tools | `NOT_WIRED` | `PARTIAL` | 5 条确定性场景的结构化回归 | 真实模型质量和发布环境表现 |
| Real LLM Smoke | Integration/opt-in | real route + real loop + real LLM，侧路受控 | `OPT_IN` | `PARTIAL` | 有凭据环境下的真实模型主路径 | 完整 staging/E2E |
| Quality Gate | Reporting/Governance | 聚合测试记录和 baseline | `NOT_WIRED` | `LANDED/PARTIAL` | 生成 PASS/WARN/FAIL 及 JSON/Markdown | 当前不会自动阻塞 GitHub PR |

### 6.1 可能深问

- `[可能深问]` Unit、Component、API、Integration、Golden Case 是如何划分的？
- `[可能深问]` `integration` 为什么不等于 `real_llm`？
- `[可能深问]` 为什么 PR blocking 测试优先离线、快速和可归因？
- `[可能深问]` 为什么只有两条 Stream Contract 候选进入 blocking marker？
- `[待完善]` 为每个 profile 准备一条代表测试的逐行讲解。
- `[待完善]` 增加真实 persistence 和 staging profile 后更新此表。

## 7. 代表性技术问题

### 7.1 SSE lifecycle

#### 当前可讲

- 不能只断言 HTTP 200，需要检查事件顺序、增量内容、唯一 terminal event、finalization 和 active state 清理。
- 中途异常可能发生在已经发送部分内容之后，因此需要验证错误事件和最终清理是否仍然执行。
- Route 测试使用真实 FastAPI 路由，Loop 根据目标选择 fake 或 real。

#### 可能深问

- `[可能深问]` 为什么 TestClient 得到 200 仍可能是业务失败？
- `[可能深问]` 如何断言 `[DONE]` 只能出现一次？
- `[可能深问]` 客户端断开和用户显式停止有什么区别？
- `[待完善]` `user-stop` 当前仍是 executable `xfail`，完成真实契约后补充红绿证据。

### 7.2 Agent Loop 收敛

#### 当前可讲

- 没有工具调用时停止循环。
- 连续工具失败达到阈值时进入 summary。
- `max_rounds` 用尽后使用 `tools=None` 强制最终总结，避免无限工具循环。
- Tool Result 和 Queue 消息必须以正确时序、正确次数进入下一轮 context。

#### 可能深问

- `[可能深问]` 如何证明 summary round 禁止再次调用工具？
- `[可能深问]` 为什么重复 tool result 会造成问题？
- `[待完善]` `duplicate tool_call_id` 去重当前仍是 executable `xfail`。
- `[待完善]` 补多会话隔离和无限循环保护的更高层验证。

### 7.3 Golden Cases 与 Quality Gate

#### 当前可讲

- Golden Case 使用结构化 YAML 描述输入、工具脚本、预期工具、轮次、答案要点和 Gate 元数据。
- Stub profile 通过 scripted LLM 和 fake tools 运行真实 Agent Loop，适合确定性回归。
- Quality Gate 可以聚合 correctness、stability、TTFB、latency、tool rounds 等字段，输出 JSON/Markdown，并与 baseline 比较。

#### 可能深问

- `[可能深问]` Golden Case 与普通单元测试有什么区别？
- `[可能深问]` 为什么不能把 LLM-as-a-judge 直接作为 blocking signal？
- `[可能深问]` baseline 如何避免把一次偶然结果固化为标准？
- `[待完善]` 当前只有 5 条 stub Golden Cases，应扩展场景并经过人工审核。
- `[待完善]` Quality Gate 尚未接入 GitHub Actions，不得称为当前 PR Gate。

## 8. GitHub Actions、结果留存和 Closed Loop

### 8.1 当前 Pipeline

```text
pull_request / main push / workflow_dispatch
  -> checkout
  -> Python 3.11
  -> uv sync --frozen --group test
  -> pytest selected profile
  -> process exit code drives GitHub Check result
  -> if: always() uploads JUnit Artifact
```

### 8.2 当前可讲

- `PR Smoke Gate` 执行 `tests/smoke -m "smoke and blocking"`。
- `PR Stream Contract Gate` 执行两条 `integration and blocking and not real_llm` 用例。
- 两个 workflow 都生成 JUnit XML，并在 pytest 失败时继续上传 Artifact。
- 错误注入分支真实产生过 pytest assertion failure 和红色 GitHub Check，随后恢复绿色。
- Closed Loop V1 当前是“证据 + 人类决定”闭环；Owner 选择 Stream 保持 `NON_BLOCKING`。

### 8.3 红绿验证 STAR 大纲

- Situation：绿色 CI 只能证明当前输入通过，不能证明测试能检测真实回归。
- Task：验证 pytest failure 能传递成 GitHub Check failure，并且失败证据不会因 step 中断而丢失。
- Action：在独立分支注入最小 assertion failure；触发 workflow；核对红色 Check 和 JUnit Artifact；恢复契约并重新执行。
- Result：证明了测试具备负向检测能力，也证明失败 Artifact 能定位 nodeid、assertion、run 和 revision。

### 8.4 可能深问与待完善

- `[可能深问]` `if: always()` 是否会让失败的 workflow 变绿？
- `[当前可讲]` 不会；pytest step 仍返回非零，`always()` 只保证后续上传步骤继续运行。
- `[可能深问]` workflow 运行失败是否一定会阻止 PR 合并？
- `[当前可讲]` 不一定；还取决于 branch protection/required checks。当前 Stream 是 `NON_BLOCKING` 决策。
- `[待完善]` 保存并整理 green run、red run、restored-green run 的固定 URL 和截图。
- `[待完善]` 将 Artifact 下载后的 JUnit 关键字段整理为一页证据说明。
- `[待完善]` 明确最终 branch protection required checks 配置。

## 9. Remote Memory 401 与依赖真实性

### 9.1 当前可讲 STAR 大纲

- Situation：首次运行 SSE fixture 时意外访问真实 Remote Memory，返回 HTTP 401。
- Task：判断这是产品缺陷、测试缺陷还是环境/认证依赖，并防止不稳定远端服务污染 PR 契约。
- Action：沿 fixture 和 Route 调用链定位隐式远端访问；在目标 SSE lifecycle profile 中显式隔离 Remote Memory；保留产品能力，不删除真实集成路径。
- Result：离线测试恢复稳定绿色；真实 Remote Memory 集成被明确标记为 `DELAYED`，没有用 stub 结果冒充远端验证。

### 9.2 可能深问与待完善

- `[可能深问]` 为什么不是直接配置一个 token？
- `[当前可讲]` PR blocking 契约应优先稳定、低成本、可归因；真实认证属于独立 integration/staging profile。
- `[可能深问]` 隔离后是否还能证明 Remote Memory 正常？
- `[当前可讲]` 不能；当前只证明目标 SSE lifecycle 不依赖真实 Remote Memory。
- `[待完善]` 确认 Remote Memory 的认证方式、测试环境、测试数据和清理策略。
- `[待完善]` 建立独立 opt-in/staging 契约后，再更新为真实集成证据。

## 10. 当前结果快照

### 10.1 代码与执行事实

| 项目 | 当前事实 | 口径 |
|---|---|---|
| 测试盘点 | 16 个测试文件、85 个静态测试定义、6 个 fixtures | inventory 工具结果；参数化不会在静态数量中完全展开 |
| 最近完整执行 | `90 passed, 1 skipped, 2 xfailed, 8 subtests passed` | Windows 本地、当前分支；需在面试前重新执行更新 |
| Real LLM | 1 条 opt-in smoke 被 skip | 需要可用凭据/config，不等于 staging 已完成 |
| User Stop | 1 条 `xfail` | `XFAIL_GAP` |
| Duplicate Tool Call ID | 1 条 `xfail` | `XFAIL_GAP` |
| Smoke CI | workflow 已存在并上传 JUnit | `LANDED` |
| Stream CI | workflow 已存在；技术检查可执行 | `LANDED`，但 Owner gate decision 为 `NON_BLOCKING` |
| Golden Cases | 5 条 stub cases 本地通过 | `PARTIAL`、`NOT_WIRED` |
| Quality Gate | 逻辑及自身测试存在 | `LANDED/PARTIAL`、默认关闭、`NOT_WIRED` |
| Remote Memory | 目标 SSE profile 中已隔离 | 真实集成 `DELAYED` |
| CD | Build & Release 有打包发布 workflow | `[待完善]` 尚不能等同于生产部署验证 |

### 10.2 待完善

- `[待完善]` 每次正式面试前重新记录 branch、commit、完整 pytest 输出和 GitHub 最新 runs。
- `[待完善]` 补充覆盖率数据前，不要回答具体 coverage 百分比。
- `[待完善]` 将当前三条 evidence branch commits 合并或完成正式收口。

## 11. CD 完成后应该补充什么

> 当前不要把 Build & Release 打包直接描述成完整生产 CD。

### 11.1 待完善清单

- `[待完善]` 部署目标：服务器、容器平台或托管平台。
- `[待完善]` 触发方式：tag、main merge、手动审批或环境 promotion。
- `[待完善]` Secret 和 environment protection 管理。
- `[待完善]` 构建产物、版本号、镜像或安装包的可追溯关系。
- `[待完善]` 部署后 health check 和 smoke test。
- `[待完善]` 失败回滚或上一版本恢复机制。
- `[待完善]` 部署日志、release metadata 和执行 Artifact 留存。
- `[待完善]` 说明哪些测试阻止发布、哪些只产生 warning。

### 11.2 CD 完成后的表达模板

> 在 PR 阶段由 Smoke/Contract tests 提供快速反馈，在发布阶段构建版本化产物并部署到目标环境，部署后执行 health check 和关键路径 smoke；失败时停止 promotion 或回滚，并保留构建、部署和测试日志，形成从代码提交到部署验证的可追溯链路。

## 12. 高频面试问题

### 12.1 测试代码看起来不复杂，项目难点是什么？

回答骨架：

> 单条测试主要使用 pytest、monkeypatch 和普通断言，算法并不复杂。难点是把带有流式输出、多轮状态和外部依赖的 Agent workflow 拆成可验证边界，并决定 Route、Loop、LLM、Tool、Persistence 中哪些保留真实。错误的 mock 位置可能让测试变绿但没有证明业务契约。

- `[待完善]` 准备一个“错误 mock 会造成假通过”的具体例子。

### 12.2 为什么不全部使用真实依赖？

回答骨架：

> PR 测试需要快速、稳定、低成本和可归因。真实 LLM、MCP 和 Remote Memory 应放在 opt-in 或 staging profile；本地确定性 profile 用来锁定状态机和协议契约。两类测试互补，不能互相替代。

- `[待完善]` 补真实 staging profile 后准备成本、频率和数据安全说明。

### 12.3 如何证明不是只测试了 mock？

回答骨架：

> 我没有统一 mock 整个系统，而是使用多个真实性 profile：real route + fake loop 验证 Route lifecycle；real route + real loop + scripted LLM 验证跨层编排；未来再用少量 staging E2E 验证真实依赖。

- `[待完善]` 准备两条测试代码的现场对比讲解。

### 12.4 为什么保留 xfail？

回答骨架：

> `xfail` 把已知缺口变成可执行契约，避免文档里的 TODO 与代码脱节。它不能算通过覆盖；功能修复后应移除 `xfail`，先看到 XPASS/失败变化，再转为正常回归测试。

### 12.5 如何验证 Codex 生成的代码可信？

回答骨架：

> 生成结果只是候选。我会核对真实生产入口、检查 fixture 替换范围、执行最窄与完整测试、检查失败含义，并对关键 Gate 做负向错误注入。没有执行证据的代码不会被当作已完成测试能力。

- `[待完善]` 准备一次发现 Codex 假设与真实代码不一致的案例。

### 12.6 CI 与 CD 的区别是什么？

回答骨架：

> 当前 GitHub workflow 已覆盖依赖安装、pytest 检查和 Artifact 上传，属于 CI；Build & Release 可以生成多平台产物，但在部署目标、部署后验证和回滚没有完成前，我不会把它描述成完整生产 CD。

### 12.7 如果测试偶发失败怎么办？

回答骨架：

> 先按产品缺陷、测试缺陷、环境依赖、数据污染和 flaky timing 分类。阻塞门禁前必须验证重复性、隔离性、执行时长和失败归因。不能仅通过自动重试把不稳定问题隐藏起来。

- `[待完善]` 准备一套实际 flaky triage 示例。

## 13. 现场代码讲解路线

### 路线 A：5～10 分钟

1. `apiserver/agentic_tool_loop.py::run_agentic_loop`：解释状态机和外部边界。
2. `tests/unit/agentic_tool_loop/test_loop_convergence.py`：解释 scripted LLM 和 max rounds summary。
3. `tests/integration/chat_stream/test_resilience.py`：解释 real route + fake/real loop 两种 profile。
4. `.github/workflows/pr-stream-contract-gate.yml`：解释 marker、pytest exit code 和 JUnit Artifact。
5. `docs/testing/CURRENT_PROGRESS.md`：解释技术证据与人工 Gate Decision 的区别。

### 路线 B：如果面试官关注测试平台

1. `tests/conftest.py`：公共 fixture、离线网络约束和 pytest hook。
2. `tests/support/agentic_tool_loop_helpers.py`：scripted LLM、queue stub、SSE parser。
3. `tests/support/golden_cases.py`：schema、runner 和 deterministic assertions。
4. `tests/support/quality_gate.py`：聚合、baseline、PASS/WARN/FAIL 和 Artifact。

### 待完善

- `[待完善]` 为每条路线准备本地可运行命令。
- `[待完善]` 练习只讲关键 20～40 行，避免从头滚动大型文件。
- `[待完善]` 准备没有 IDE 和没有网络时的白板版本。

## 14. 简历表述候选

### 14.1 当前可用版本

- 围绕 NagaAgent 的 SSE 流式响应与多轮工具调用链路，借助 Codex 完成代码盘点和测试边界设计，建立 Smoke、API/Integration、Agent Loop Unit 与 Golden Case 分层 pytest 体系。
- 设计 `real route + fake loop`、`real loop + scripted LLM` 等真实性 profile，覆盖流式终止、异常清理、工具超时、最大轮次、结果/Queue 注入和 Failure Stage 归因，同时隔离真实 LLM 与 Remote Memory 等不稳定依赖。
- 将 Smoke 与 Stream Contract 接入 GitHub Actions，使用 pytest exit code 驱动 Check 状态，并通过 `if: always()` 在失败时留存 JUnit Artifact；以真实 assertion 错误注入验证红灯检测和恢复绿色的证据闭环。
- 建立 YAML Golden Cases 和 Quality Gate 原型，支持结构化场景、baseline、TTFB/latency/tool rounds 等指标及 JSON/Markdown 输出；明确区分已落地、`xfail`、opt-in 与未接入 CI 的能力。

### 14.2 待完善后才能使用

- `[待完善]` “建立生产级 PR/Release Agent Workflow Gate”。
- `[待完善]` “完成真实 LLM/MCP/Remote Memory 全链路 E2E”。
- `[待完善]` “完成持续部署、部署后验证和自动回滚”。
- `[待完善]` “完成并发、性能和故障注入平台”。

## 15. 最终复习清单

### 架构

- [ ] 能在白板上画出 Route → Loop → LLM → Tool → Result Injection → Finalize。
- [ ] 能解释 Context、Queue、Persistence 在 workflow 中的位置。
- [ ] 能解释正常收敛、连续失败和 max rounds 三条结束路径。

### 测试

- [ ] 能区分测试层、真实性 profile、实现状态和 Gate 状态。
- [ ] 能逐行讲解一条 SSE 测试和一条 Agent Loop 测试。
- [ ] 能解释每条代表测试“证明什么”和“不证明什么”。
- [ ] 能解释两个当前 `xfail`。

### CI/CD 与证据

- [ ] 能解释 pytest exit code 如何影响 GitHub Check。
- [ ] 能解释 `if: always()` 和 JUnit Artifact。
- [ ] 能讲清错误注入红灯与恢复绿色过程。
- [ ] 能区分 workflow check、required check、release packaging 和完整 CD。
- [ ] 面试前更新 branch、commit、pytest 和 GitHub Run 证据。

### Codex 协作

- [ ] 能说明 Codex 加速了什么、人工判断负责什么。
- [ ] 能举出至少一个验证或修正 Codex 结果的实例。
- [ ] 不把“生成过”描述成“已经验证”。

### 后续建设

- [ ] 完成 user-stop 契约。
- [ ] 完成 duplicate tool_call_id 去重契约。
- [ ] Golden/Quality 先以 non-blocking CI 运行并积累 baseline。
- [ ] 补 1～3 条安全、受控的 staging E2E。
- [ ] 基于 NagaAgent 真实代码完成 Route → Loop → Tool → Result Injection → Finalize 的基础 Agent workflow 走读，并把关键状态变化映射到代表测试。
- [ ] 完成 Replay Bundle。
- [ ] 完成 CD、部署后 smoke 和回滚证据后更新本文。

## 16. 证据入口

- 当前进度：`docs/testing/CURRENT_PROGRESS.md`
- 测试架构总览：`docs/testing/architecture/overview.md`
- API/SSE 测试说明：`docs/testing/architecture/part-02-api-stream.md`
- Agent Loop 测试说明：`docs/testing/architecture/part-04-agentic-tool-loop.md`
- Golden Cases：`docs/testing/architecture/part-11-golden-cases.md`
- CI Gate：`docs/testing/architecture/ci-pr-gate.md`
- Smoke workflow：`.github/workflows/pr-smoke-gate.yml`
- Stream workflow：`.github/workflows/pr-stream-contract-gate.yml`
- Build & Release：`.github/workflows/build-release.yml`
- pytest 配置：`pytest.ini`、`pyproject.toml`

> `[待完善]` 后续每完成一个工作单元，只更新相关章节和事实快照；不要为了让文档看起来“完整”而提前删除缺口标记。
