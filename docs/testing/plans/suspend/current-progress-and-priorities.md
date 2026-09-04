# NagaAgent 当前测试框架进度与 Chat Stream 后续优先级

> `SUSPENDED`（2026-08-18）：本文件保留历史状态与执行台账，不再作为当前优先级真相源。当前路线见 [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md)。

## 1. 文档定位

- 文档状态：`Living Candidate`
- 主线工作流：`POST /chat/stream`
- 目标：形成可扩展的 Pytest 分层回归、确定性 PR Quality Gate，以及一条可追溯的 Agent Workflow 测试闭环。
- 当前阶段：P0 技术项已完成并获得临时 `VERIFIED` 快照；P1 前两项已完成，其余检查项仍按各自状态执行。文档中的 `[x] / [~] / [!] / [ ]` 必须结合证据和 Gate 状态理解。
- 人工责任：`Reviewed`、`Executable`、`Verified`、`PR_BLOCKING` 仍需由人类 Owner / Reviewer 根据代码、执行证据和仓库设置确认。
- 最近同步日期：`2026-08-01`
- revision 边界：P0 `VERIFIED` 绑定 Run Record 中的 HEAD `70f781f6d3e46ecdded15eb92c133a6ce9a47e40` 加当时 dirty working tree；当前仓库 HEAD 为 `01090ce1c60492c411624d057afd10517b504666`，尚未在该 revision 上重新完成 P0 干净环境验收。

## 2. 目标闭环

```text
/chat/stream 请求
  -> system prompt / context assembly
  -> run_agentic_loop
  -> tool call normalize / dispatch
  -> tool result injection
  -> next round / degraded answer / summary
  -> SSE terminal state
  -> finalize / active cleanup
  -> conversation persistence
  -> quality report
  -> PR gate decision
```

## 3. 当前测试框架进度

### 3.1 总体判断

| 目标 | 当前结论 | 说明 |
|---|---|---|
| 可扩展 Pytest 分层框架 | `PARTIAL` | smoke、unit、integration、golden case、fixture/support、测试依赖和 quality report 骨架均已落地；P0 的依赖与失效 fixture 漂移已收口，但完整 PR Gate、扩展模板和当前 revision 干净环境复验仍未完成。 |
| PR 测试框架 | `PARTIAL` | GitHub Actions 已运行 3 条 deterministic smoke，且用户提供的 workflow run 为成功；完整 deterministic suites 尚未接入，Branch Protection Required Check 状态仍为 `UNKNOWN`。 |
| Chat Stream 功能闭环 | `PARTIAL` | P1 的 SSE 顺序/唯一终止和多 `content` 拼接契约已 `LANDED`；user stop、真实持久化回读、完整 context assembly 和指标重命名仍有缺口。 |
| Agent Tool Workflow | `PARTIAL` | 状态机、dispatch、超时、max rounds、message injection、compression 和 failure attribution 已落地；duplicate `tool_call_id` 仍为 `XFAIL_GAP`。 |
| Golden Cases | `PARTIAL` | 5 条 deterministic stub cases 当前通过，但 runner 仍预设工具调用和最终回答，尚不能证明生产 prompt/tool schema/context assembly 质量。 |
| Quality Gate | `PARTIAL` | 本地聚合、baseline compare、JSON/Markdown/terminal 输出及 pass/warn/fail 单测已存在；PR 未启用 enforce 和 artifact publication。 |
| 可交接性与 SOP 闭环 | `PARTIAL` | 测试文档较丰富，但当前状态声明存在滞后，尚无完整的风险到 Gate Record 的 Verified pilot 链。 |

当前成熟度定位：**P0 基线已形成可复现快照、P1 已开始收口协议契约的测试工程试点；尚不是完整、可交接的 PR Blocking 测试平台。**

### 3.2 资产清单

| 项目 | 当前数量/状态 |
|---|---|
| 测试文件 | 16 |
| 测试函数/参数化测试节点 | 85 |
| 显式 fixtures | 6 |
| 直接使用 monkeypatch 的测试 | 13 |
| smoke + blocking tests | 3 |
| executable xfail gaps | 2 |
| Golden YAML cases | 5 |
| CI pytest 命令 | 1 条，仅运行 `tests/smoke -m "smoke and blocking"` |

### 3.3 当前可核对执行证据

| Suite | 精确命令 | 当前结果 | 实现状态 | Gate 状态 |
|---|---|---|---|---|
| API smoke | `uv run python -m pytest tests/smoke -m "smoke and blocking" -q` | P0 clean env：`3 passed`；用户提供的 GitHub workflow run：Success | `LANDED` | workflow 已调用且成功；Required Check `UNKNOWN` |
| 全部 unit | `uv run python -m pytest tests/unit -m "unit" -q` | P0 clean env：`48 passed, 1 xfailed` | `PARTIAL`；duplicate ID 为 `XFAIL_GAP` | `NOT_WIRED` |
| Tool Loop unit | `.venv\\Scripts\\python.exe -m pytest tests/unit/agentic_tool_loop -q` | `19 passed, 1 xfailed` | `PARTIAL`；duplicate ID 为 `XFAIL_GAP` | `NOT_WIRED` |
| Stream resilience | `.venv\\Scripts\\python.exe -m pytest tests/integration/chat_stream/test_resilience.py -q` | P1 最新复跑：`7 passed, 1 xfailed`；SSE 两条核心契约定向 `2 passed` | `PARTIAL`；前两项 `LANDED`，user stop 为 `XFAIL_GAP` | `NOT_WIRED` |
| Stub golden | `uv run python -m pytest tests/golden_cases -m "golden_case" -q` | P0 clean env：`5 passed` | `PARTIAL`；确定性 workflow contract 已落地 | `NOT_WIRED` |
| Quality Gate unit | `.venv\\Scripts\\python.exe -m pytest tests/unit/test_quality_gate_summary.py -q` | `5 passed` | 本地判级逻辑 `LANDED`，CI enforcement `PLANNED` | `NOT_WIRED` |

未执行：真实 LLM、真实 MCP/OpenClaw、真实 RAG、staging、网络 TTFB；这些 profile 不属于当前默认 PR Blocking 范围。

### 3.4 当前测试层与真实性边界

| 能力 | Test layer | 当前真实性 | 当前能证明 | 当前不能证明 |
|---|---|---|---|---|
| API smoke | Smoke/API | real FastAPI app/route；LLM、loop、memory、persistence、telemetry 为替身 | 路由和最小响应契约 | 真实模型、工具、数据库和外部服务 |
| Stream resilience | Integration/API | real route；部分 case 使用 fake loop，部分使用 real loop + scripted LLM；save 为 spy | SSE 收尾、异常外显、cleanup、save 调用次数 | 真实网络 TTFB、用户 stop 完整语义、真实落盘一致性 |
| Tool Loop | Unit/Component | real `run_agentic_loop`；scripted LLM、fake queue/tools/compressor | 状态机、dispatch、收敛、注入和归因 | 模型是否会选择正确工具、真实工具可用性 |
| Stub golden | Golden case | real loop；scripted LLM 和 fake tools；测试专用 prompt/schema | 固定脚本下的 workflow contract | 生产 prompt/schema/context 变化后的真实任务质量 |
| Quality Gate | Unit/Observability | real report builder；输入为测试记录 | 聚合、baseline compare、pass/warn/fail 规则 | CI 是否真正阻断 PR、指标是否全部来自真实运行 |

## 4. 当前已知缺口

- PR workflow 当前只执行 API smoke，没有覆盖完整 deterministic Agent Workflow 回归。
- 当前 HEAD `01090ce...` 尚未重新执行完整 P0 干净环境验收；现有 `VERIFIED` 只适用于已记录快照。
- 用户 stop 仍为 `XFAIL_GAP`。
- 重复 `tool_call_id` 跨轮去重仍为 `XFAIL_GAP`。
- stream resilience 当前主要验证 save 调用，不证明真实磁盘持久化和重新加载一致性。
- 现有 stub golden cases 由脚本预设工具调用和最终回答，不能独立证明生产 prompt / tool schema / context assembly 的质量。
- Quality Gate 已能生成报告，但尚未作为完整 PR Blocking 执行并强制非零退出。

## 5. 接下来应该做什么及优先级

### 5.1 优先级总表

| 优先级 | 工作包 | 原因 | 完成后的直接价值 |
|---|---|---|---|
| `已完成` | P0 修复依赖、fixture 和 smoke 基线 | 已形成干净环境 Run Record，并由用户临时确认 `VERIFIED` | 为后续 P1-P5 提供可复现基线；当前 revision 变化后仍需复验 |
| `S1-当前` | P1 Chat Stream 生命周期 | SSE 顺序与多增量已完成，user stop、timeout、重复 finalize 和指标语义仍是闭环缺口 | 完成 API/SSE 生命周期闭环 |
| `S1-高` | P2 Tool、Context、真实持久化 | 决定能否把“调用一致性”升级为真正的垂直工作流证据 | 完成 route -> loop -> context -> disk 闭环 |
| `S2-中` | P3 Golden Cases 升级 | 当前 stub 不能证明生产 prompt/schema/context 回归 | 获得可信的 deterministic task contract |
| `S2-中` | P4 PR Gate、完整指标、enforce 和 artifacts | 当前只有 Smoke workflow 与本地 Quality Gate 骨架，integration/golden 尚未接线 | 形成可诊断、可下载、可阻断的 CI 结果 |
| `S3-收口` | P5 扩展指南与 SOP Pilot | 应基于实际实现和执行证据收口，避免先写出过度设计 | 达到可交接、可展示和可复用目标 |

推荐执行队列：`P0 DONE -> P1 IN_PROGRESS -> P2 -> P3 -> P4 -> P5`。当前先完成 Chat Stream 功能闭环，再扩展生产级 Gate 接线。

状态符号：`[x]` 已落地；`[~]` 部分落地；`[!]` 当前失败或阻塞；`[ ]` 待实现。

### P0：修复可复现测试基线（`S0-立即`）

- [x] [DONE] 在 test dependency group 显式声明 `pytest`、`pytest-asyncio` 及测试运行必需依赖。
  - 目的：让测试环境直接声明自己需要的 runner、异步插件和报告插件，不依赖其他包偶然带入测试依赖。
  - 作用：保证 `uv sync --frozen --group test` 在新机器和 CI 中可以重建相同环境，避免出现本地能运行、干净环境缺少 `pytest` 或插件版本漂移的问题。
  - 完成记录：`p0-dependencies-001` 已显式声明 `pytest`、`pytest-asyncio`、`allure-pytest`，保留 `google-genai`，并更新 `uv.lock`。
  - 验证证据：`uv lock --check` 和 `uv sync --frozen --group test` 均以退出码 `0` 完成；Golden schema/runner 定向测试为 `14 passed`。
- [x] [DONE] 修复 `flush_langfuse`、`start_llm_generation_observation` 等失效 monkeypatch。
  - 目的：让测试替身始终指向当前生产代码真实存在的隔离点，使 fixture setup 能够完成并进入测试主体。
  - 作用：消除由符号删除、移动或改名造成的 setup error，避免把测试代码漂移误判为产品功能失败。
  - 完成记录：`p0-monkeypatch-001` 已删除 Smoke fixture 对 route 旧符号 `flush_langfuse` 的 patch，并将 Langfuse 单测改为直接验证当前 adapter helper 契约。
  - 验证证据：修复前复现 `3 errors` 和 `2 failed, 1 passed`；修复后 Smoke 为 `3 passed`，完整 unit suite 为 `48 passed, 1 xfailed`。
- [x] [DONE] 确认并修订 `pytest.ini` marker，使名称、测试层级和真实依赖边界一致。
  - 目的：用稳定 marker 区分 smoke、unit、integration、golden case、real LLM 和 blocking 等测试层级与执行 profile。
  - 作用：让本地命令和 CI 精确选择预期用例，防止真实 LLM 或外部依赖测试误入确定性 PR Gate，也避免应阻塞的测试被漏选。
  - 完成记录：`p0-markers-001` 已将 `integration` 定义为仓库内多个真实组件的协作，将 `real_llm` 独立定义为真实外部 LLM profile，并明确 `blocking` 只有被活动 CI Gate 选中时才具备阻塞意义；同时为 `test_golden_case_schema.py` 补齐 `unit` marker。
  - 验证证据：严格 marker 收集共 `93 tests collected` 且无 `PytestUnknownMarkWarning`；`-m unit` 完整选中 `49/93`；完整 unit 为 `48 passed, 1 xfailed`；CI Smoke 选择表达式为 `3 passed`。
- [x] [DONE] 将测试报告、缓存和临时产物与源码提交边界分离。
  - 目的：明确源码、人工维护 baseline 与运行时生成报告之间的版本控制边界。
  - 作用：保持 Git 状态干净，避免 Allure、缓存和质量报告污染提交，同时让 CI artifact 可以独立保存和追溯。
  - 完成记录：`p0-artifact-boundary-001` 已忽略 `allure-results/`、`allure-report/` 和 `tests/artifacts/quality_gate/`，并在测试报告说明中明确生成物不提交、`tests/baseline/quality_gate/` 继续由人工评审后纳入版本控制。
  - 验证证据：定向运行同时生成 Allure 与 Quality Gate 报告，结果为 `1 passed`、`gate_result=pass`；新生成目录均由 `.gitignore` 命中，目标路径 `git status` 无输出，已跟踪 baseline 的 `git diff --exit-code` 为 `0`。
- [x] [DONE] 在干净环境执行 smoke、unit、stream integration、stub golden。
  - 目的：验证四组 deterministic suites 不依赖开发机已有虚拟环境、缓存、环境变量或未声明包。
  - 作用：提前发现缺失依赖、导入错误、fixture setup error 和平台差异，证明当前测试资产具备进入 PR Gate 的基本可复现性。
  - 完成记录：`p0-closure-001` 在仓库外新建隔离 Python 3.11 环境，通过 `uv sync --frozen --group test --python 3.11` 安装锁定依赖，并分别执行四层 suite。
  - 验证证据：Smoke `3 passed`；Unit `48 passed, 1 xfailed`；Stream Integration `7 passed, 1 xfailed`；Stub Golden `5 passed`。聚合命令及清除常见外部服务凭据后的复跑均为 `63 passed, 2 xfailed`，无失败、XPASS 或 setup error。
- [x] [DONE] 保存准确命令、环境、revision、退出码和结果摘要，并形成独立 Run Record。
  - 目的：为每次验收保留可以复查和重放的最小执行证据。
  - 作用：失败时可以区分代码回归、测试缺陷和环境问题，也为 SOP 追溯、简历展示和后续基线比较提供可信记录。
  - 完成记录：已生成 `docs/testing/reports/p0-clean-environment-run-2026-07-28.md`，记录 HEAD、脏工作树限制、环境、版本、命令、退出码、分层结果、真实性边界、gate 状态和 warning。
- [x] [DONE] 只有成功执行并经人工确认的结果才能标记为 `Verified`。
  - 目的：把“测试执行成功”和“测试范围、断言与证据已经通过工程评审”区分开。
  - 作用：防止仅凭一次绿色运行或自动生成报告过度宣称覆盖完成，确保状态晋升仍由人类 Owner / Reviewer 对证明边界负责。
  - 当前状态：用户于 `2026-08-01` 明确要求暂时将 P0 Run Record 晋升为 `VERIFIED`；该确认仅适用于 2026-07-28 的执行快照，两个 xfail、dirty working tree 和 Gate 接线边界保持不变。

完成标准：全部 deterministic suites 可收集、无 setup error，并能在干净环境一条命令运行。

P0 技术完成度：`DONE`。证据晋升状态：`VERIFIED`（临时/用户确认，适用于 2026-07-28 执行快照）。

### P1：完成 Chat Stream 生命周期回归（`S1-高`）

- [x] [DONE] 固定 SSE 事件顺序和终止协议；已形成正常流与异常流的应用层 SSE 顺序契约。
  - 目的：把 `/chat/stream` 从“能输出文本”提升为有明确起始、增量、异常和终止状态的协议状态机，并定义允许的事件顺序与唯一终止条件。
  - 作用：防止前后端因事件乱序、缺少 terminal 或重复终止而出现解析漂移、流式卡死和用户无感知失败，同时让故障可以归因到具体协议阶段。
  - 完成状态：`DONE`（执行单元：`p1-sse-protocol-001`）。
  - 验证证据：`test_chat_stream_resilience_baseline_finishes_and_cleans_state` 断言正常流满足 `session_id → status+ → content+ → round_end → [DONE]`，且 `[DONE]` 唯一并位于末尾；`test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state` 断言异常流满足 `session_id → status+ → content → error`，`error` 唯一并位于末尾，且不得再出现 `[DONE]`。
  - 检查结果：定向命令 `python -m pytest <上述两个 nodeid> -q` 为 `2 passed`；完整 `test_resilience.py` 回归为 `7 passed, 1 xfailed`，其中唯一 `xfail` 是后续“用户 stop”步骤的既有缺口，不属于本项失败。
- [x] [DONE] 验证首个增量 content、多个增量块、完整输出和终止事件；已验证三个有序 SSE `content` 事件、精确拼接与持久化替身入参一致。
  - 目的：证明响应协议确实产生多个有序、可观察的 SSE `content` 事件，并保证事件文本拼接后与最终结果一致；进程内 `TestClient` 可能合并 HTTP 传输块，因此这里不以 `iter_text()` 次数证明真实网络分包。
  - 作用：及时发现首段 content 缺失、增量事件丢失/重复和终止前内容不完整等问题，保护应用层流式契约；真实网络缓冲与首包体验留给后续网络层测试证明。
  - 完成状态：`DONE`（执行单元：`p1-sse-protocol-001`）。
  - 验证证据：正常流脚本依次发出 `baseline-`、`stream-`、`ok` 三个非空 `content` 事件；测试逐项断言事件文本和顺序，拼接结果为 `baseline-stream-ok`，并验证 `_save_conversation_and_logs` 收到的响应文本与该完整结果一致，随后仅出现一个 `round_end` 和一个末尾 `[DONE]`。
  - 检查边界：本项证明应用层 SSE 事件增量，不证明真实网络分包或 TTFB；带 `--quality-gate` 的诊断执行没有功能用例失败，但现有 latency baseline 使报告为 `gate_result=fail`，该指标命名与 Gate 校准分别保留给 P1 后续指标项和 P4 处理。
- [ ] 实现客户端 `AbortSignal` 取消，不增加新的服务端取消接口。
  - 目的：复用 Fetch/HTTP stream 的标准取消传播，让用户 stop 从前端主动中止当前请求，而不引入额外 `/stop` API 和第二套会话状态。
  - 作用：减少取消接口与流式请求之间的竞态和状态同步成本，并为服务端 generator cleanup、cancelled 状态和持久化策略提供真实触发入口。
- [ ] 固定 stop 语义：`final_status=cancelled`，active state 清理一次，finalize 最多一次。
  - 目的：为主动停止建立区别于 success/degraded/failed 的确定终态，并把 active cleanup 与 finalize 约束为幂等操作。
  - 作用：避免 stop 后会话仍显示活跃、后台继续生成、重复 finalize 或终态被误报为成功，使前端提示、日志和质量报告能够一致识别用户取消。
- [ ] 非空部分响应最多保存一次；空响应只保存用户消息。
  - 目的：明确取消或异常时用户消息与 assistant 部分输出的持久化规则，区分“已有可恢复内容”和“尚未产生有效输出”两种路径。
  - 作用：防止重复落库、空 assistant 记录、用户输入丢失和历史重放出现伪完整回答，为后续真实磁盘回读断言提供稳定数据契约。
- [~] 覆盖正常结束、中途异常、空输出、整体超时、重复 finalize、客户端断开；其中正常、异常、空输出和单次 finalize 已部分覆盖。
  - 目的：用生命周期场景矩阵覆盖每一种主要终止来源，而不是只依赖 happy path 推断 cleanup、persistence 和 failure-stage 行为。
  - 作用：暴露只有在 timeout、disconnect 或重复收口时才出现的资源泄漏和状态不一致，并保证新增分支不会绕过统一 finalize 逻辑。
- [ ] 将进程内测试指标命名为 `first_chunk_ms`；真实网络测试才使用 `ttfb_ms`。
  - 目的：区分 TestClient/生成器内部首段产出耗时与包含网络栈、代理和部署环境的真实 Time To First Byte。
  - 作用：避免用进程内测量冒充网络性能指标，保证质量报告、baseline 和简历描述中的性能口径可解释、可比较。
- [!] 移除用户 stop 的 `xfail`，转换为稳定确定性断言。
  - 目的：在 runtime 满足取消契约后，把当前可执行缺口转为默认必须通过的回归测试。
  - 作用：让后续破坏 user-stop 的变更产生普通测试失败而不是被预期失败放行，真正把取消生命周期纳入确定性回归范围。

完成标准：每条终止路径都有明确 final status、cleanup、persistence 和 failure-stage 断言。

### P2：补齐 Tool、Context 与真实持久化（`S1-高`）

- [!] 修复重复 `tool_call_id`，同一 ID 跨轮只执行和注入一次。
  - 目的：把 `tool_call_id` 作为跨轮幂等键，阻止模型或上游重复发送同一调用时再次 dispatch、回注和产生副作用。
  - 作用：避免外部工具重复执行、历史消息污染、token 浪费和 Agent 循环不收敛，并使工具执行记录与上下文引用保持一一对应。
- [!] 移除 duplicate `tool_call_id` 的 `xfail`。
  - 目的：在执行去重和注入去重都实现后，将目标契约从 `XFAIL_GAP` 晋升为稳定回归。
  - 作用：防止重复 ID 问题在未来重现时被测试套件继续容忍，并使 Tool Loop 的幂等性具备可用于 Gate 的明确失败信号。
- [x] 已有并已执行 `real route + real loop + scripted LLM + fake tools` 集成测试。
  - 目的：保留真实 API route 与真实 Agent Loop 协作的确定性基线，同时只替换高波动的模型输出和外部工具结果。
  - 作用：证明 orchestration 控制流能够跨越 route/loop 边界，并为后续接入生产 context assembly 和真实本地持久化提供低风险扩展支点；不把它误称为真实外部 E2E。
- [x] 已在 Tool Loop 单元/组件层验证 tool result 进入下一轮 LLM messages，且顺序和次数正确。
  - 目的：验证工具执行结果能以正确 role、ID、顺序和次数反馈到下一轮模型上下文，形成完整的 call-result-next-round 状态转换。
  - 作用：捕获结果漏注入、重复注入、顺序错乱和错误关联，降低模型反复调用同一工具或基于缺失结果继续推理的风险。
- [ ] 使用生产 `build_system_prompt`、`build_context_supplement` 和历史消息装配路径。
  - 目的：让集成/Golden 回归消费真实 prompt、context supplement 和 history assembly，而不是测试专用固定字符串。
  - 作用：使生产 prompt、tool instruction、上下文顺序或历史装配变更能够触发确定性契约回归，同时明确仍不证明真实模型语义质量。
- [ ] 使用 `temp_path` 隔离 session/log 目录，调用真实 `MessageManager` 保存。
  - 目的：在测试专属临时目录中执行生产序列化和文件写入路径，既保持真实持久化逻辑又不污染用户会话与日志。
  - 作用：发现 spy 无法暴露的路径、编码、目录创建和 JSON 写入问题，并保证测试可并行、可清理、可重复运行。
- [ ] 重新实例化 `MessageManager`，从磁盘加载并断言 user/assistant 历史一致。
  - 目的：通过进程内重新实例化和磁盘回读验证数据真正持久存在，而不是只停留在旧对象内存或保存调用次数层面。
  - 作用：捕获写入后无法加载、字段丢失、顺序变化和 user/assistant 不一致等数据完整性缺陷，完成 route-to-disk-to-reload 证据闭环。
- [x] 当前 deterministic tests 已替换真实 LLM、RAG、MCP、通知和遥测，避免外部成本与不稳定性进入 PR。
  - 目的：为默认回归固定一个离线、可控的依赖真实性 profile，只保留目标仓库组件为真实执行对象。
  - 作用：降低付费、网络、认证和服务波动造成的 flaky/误归因，使失败更可能指向当前软件契约；同时保留真实外部 profile 作为独立非阻塞测试。

完成标准：证明真实路由、真实 loop、生产 context assembly 和真实本地持久化能够协作；不宣称证明真实模型质量或外部工具可用性。

### P3：升级 Golden Cases（`S2-中`）

- [~] deterministic `stub` profile 已落地并执行通过，但尚未接入 PR Blocking。
  - 目的：保留一组离线、可版本化、可重复的任务级 workflow 基线，并明确“本地可执行”与“已经阻塞 PR”是两个状态。
  - 作用：让开发者可以快速发现固定场景的流程回归，同时避免仅凭本地绿色结果过早宣称已经形成 Required Gate。
- [ ] Golden schema 增加工具参数子集断言、上下文证据和最终回答结构断言。
  - 目的：把工具参数语义、有效上下文引用和回答结构从自然语言期望转化为可版本化、可校验的 schema 字段。
  - 作用：使 Golden Cases 能发现“工具选对但参数错误”“回答正确但未引用上下文”“文本存在但结构破坏”等任务级退化。
- [ ] stub runner 使用生产 prompt、tool schema 和 context assembly。
  - 目的：让 runner 的被测输入装配与生产路径一致，只控制 LLM 脚本和外部工具结果。
  - 作用：将 prompt、tool schema 和 context assembly 的变更纳入可归因回归，减少测试专用装配导致的假通过。
- [~] 当前 LLM 输出和工具结果已脚本化，但 prompt、schema 和 context 仍是测试专用替身。
  - 目的：保留当前确定性控制方式并显式标注真实性缺口，避免把 scripted workflow 成功解释为生产装配或真实模型成功。
  - 作用：让当前用例继续稳定验证 loop contract，同时为替换测试专用 prompt/schema/context 提供清晰迁移边界。
- [~] 已有 no-tool、single/multi-tool、tool failure 和 history continuation；context usage、max-rounds 仍需完善。
  - 目的：用少量代表性场景覆盖主要任务路径，并补齐上下文使用和轮次耗尽这两类尚未形成任务级断言的高风险分支。
  - 作用：避免 case 数量增长但风险面仍单一，使 Golden 集合能够同时发现直接回答、工具协作、降级、历史延续和不收敛回归。
- [~] 每条 case 已包含 required/forbidden tool、rounds、final status 和 answer text contract；工具参数语义与上下文证据不足。
  - 目的：明确当前断言基线已经覆盖什么、还缺什么，防止“case 通过”等同于完整任务质量通过。
  - 作用：为后续优先增加参数子集和 context evidence 提供可审查清单，并维持现有 required/forbidden/round/status 契约的兼容性。
- [~] `real_llm` 已为显式 opt-in；尚未接入 `NIGHTLY` 或 `NON_BLOCKING` workflow。
  - 目的：把真实模型语义观察与 deterministic stub regression 分离，并为其定义显式、非默认的执行入口。
  - 作用：在不增加 PR 成本和波动的前提下观察模型/provider 漂移；后续接入 scheduled workflow 后可积累趋势证据而不成为确定性阻塞信号。

完成标准：stub golden 可以发现 workflow contract、tool schema 和 context assembly 回归；真实模型语义质量保持为独立非阻塞评估。

### P4：形成真正的 PR Quality Gate（最小接线 `S1-高`，完整化 `S2-中`）

- [ ] PR Blocking 候选范围包含 API smoke、Tool Loop unit、Chat Stream integration、stub golden。
  - 目的：定义覆盖入口、状态机、跨组件生命周期和任务级契约的最小确定性阻塞集合，而不是只运行 API happy-path smoke。
  - 作用：让 prompt/tool/context/stream 相关变更在合并前获得分层反馈，并避免把真实 LLM、外部服务或未稳定用例误纳入 blocking perimeter。
- [x] 已实现 `--quality-gate` 本地报告模式。
  - 目的：让开发者在提交前以与质量聚合器一致的方式生成 gate_result、baseline delta 和失败归因报告。
  - 作用：缩短 CI 失败后的复现与定位路径，并提供报告链路的本地调试入口；该模式本身不代表 CI 已强制阻断。
- [ ] 增加 `--quality-gate-enforce`，使 `gate_result=fail` 返回非零退出码。
  - 目的：把报告中的 fail 判级转换为进程级失败，使 CI 能依据退出码执行真正的门禁决策。
  - 作用：避免出现报告写着 fail 但 workflow 仍为绿色的假门禁，并允许本地报告模式与 CI enforce 模式分别使用。
- [!] retry、timeout、tool rounds、final status 来自实际运行记录，不统一硬编码为 `0`；当前部分指标固定为 `0`。
  - 目的：保证质量指标由测试过程和 workflow report 真实采集，而不是由 fixture 或聚合层填充统一默认值。
  - 作用：提高报告的诊断可信度，使重试、超时、循环调用和终态退化能够被定位与 baseline 比较，避免“数据结构存在但信息无效”。
- [x] 已实现 JSON、Markdown 和 terminal summary 输出。
  - 目的：同时提供机器可读、人类可读和命令行即时反馈三种报告视图，共用同一份判级事实来源。
  - 作用：支持 CI 自动处理、Reviewer 快速审阅和开发者本地排查，并为后续 artifact 上传和 SOP 追溯提供标准输出。
- [ ] CI 上传质量报告和测试结果 artifacts。
  - 目的：在临时 runner 结束后保留 JSON、Markdown、Allure/JUnit 等执行证据，并与具体 workflow run 绑定。
  - 作用：让失败可以在不复现现场的情况下完成 triage、审计和简历展示，也避免把运行产物提交到源码仓库。
- [ ] real LLM、真实 MCP 和网络性能测试进入 scheduled/non-blocking workflow。
  - 目的：为高成本、高波动或依赖外部环境的 profile 提供独立定时执行通道，与确定性 PR Gate 隔离。
  - 作用：持续观察 provider、工具服务和部署网络变化，同时避免外部故障、额度和性能噪声无谓阻塞日常 PR。
- [ ] 由人类在 GitHub 分支保护中把稳定的 deterministic workflow 设为 Required Check。
  - 目的：由仓库 Owner 在平台治理层确认哪些已评审、稳定的 workflow 必须通过后才能合并。
  - 作用：把“工作流存在”升级为实际合并约束，同时保留人类对误阻塞、权限和分支策略的最终责任，Agent 不自行声称 Required Check 已生效。

完成标准：任一 blocking contract 失败都会阻止 PR，且报告能定位 `case_id / failure_stage / final_status`。

### P5：完成可交接文档与 SOP Pilot（`S3-收口`）

- [ ] 编写“如何新增 API 测试、Tool Loop case、Golden Case、质量指标”的扩展指南。
  - 目的：把新增不同测试层和质量字段所需的目录、fixture、marker、断言、命令和证据要求整理成可操作步骤。
  - 作用：降低后续维护者对原作者隐性知识的依赖，使框架即使停止主动维护也能按既有模式安全扩展。
- [~] 已有 fixture、marker、golden YAML 和 quality-gate payload 样例，但尚未整理为统一扩展模板。
  - 目的：将分散在测试文件中的可复用写法提炼为最小模板，并保持与当前仓库原生约定一致。
  - 作用：减少复制旧用例造成的 marker、替身、字段和清理逻辑漂移，提高新测试首次可收集和可执行的成功率。
- [~] 部分测试文档已记录 test layer、authenticity profile、implementation status 和 gate status，仍需与当前执行证据对齐。
  - 目的：让文档中的层级、真实性、实现和 Gate 四个维度分别对应当前代码、命令和 CI 配置，而不是沿用历史判断。
  - 作用：防止新维护者把 fake/real、LANDED/PLANNED、local pass/PR blocking 混为一谈，使测试失败与覆盖边界更容易解释。
- [ ] 清理与当前代码或 CI 不一致的“已完成/已覆盖/已阻断”描述。
  - 目的：删除或降级没有实现、执行记录或 CI 配置支撑的完成性声明，并保留明确的 PARTIAL/XFAIL/NOT_WIRED 状态。
  - 作用：恢复文档可信度，避免简历、SOP 和项目交接基于过期或过度覆盖结论做出错误判断。
- [ ] 建立 Chat Stream 最小追溯链：风险 -> 场景 -> 用例 -> 测试资产 -> Run -> Triage -> Gate Record -> Quality Report。
  - 目的：用一条真实主线把需求风险、测试设计、自动化实现、执行、分析和门禁证据串成可追踪关系。
  - 作用：形成可以复查、展示和复制到其他功能的 SOP Pilot，并在失败时快速定位缺失的是场景、断言、执行还是 Gate 接线。
- [ ] SOP 明确区分 Agent 周边确定性软件测试与真实模型能力评估。
  - 目的：分别定义软件协议/状态/持久化契约和模型语义/任务质量评估的断言方式、依赖 profile 与 Gate 资格。
  - 作用：避免把 scripted stub 当成模型质量证明，也避免用 LLM judge 或真实模型波动充当确定性 PR Blocking 真相源。
- [ ] 每个阶段保留人工 review reference；Agent 不自行晋升状态。
  - 目的：为 Candidate、Reviewed、Executable、Verified 和 PR_BLOCKING 的状态变化保留 Owner/Reviewer 确认来源。
  - 作用：确保范围接受、baseline 晋升、误报处置和发布质量仍由人类负责，防止自动生成文本或一次绿色运行被直接升级为工程事实。

完成标准：不了解当前实现的人可以按文档新增测试、选择正确 profile，并理解测试证明与不证明的边界。

## 6. 推荐 PR 拆分

| PR | 内容 | 预期状态 |
|---|---|---|
| PR-1 | P0 测试基线与依赖修复 | deterministic suites 可执行 |
| PR-2 | P4a：把当前稳定 deterministic suites 接入 PR | 分层 PR feedback 建立 |
| PR-3 | P1 Stream 生命周期与 user stop | lifecycle contract 完成 |
| PR-4 | P2 Tool/context/persistence 闭环 | 垂直工作流完成 |
| PR-5 | P3 Golden schema 与 runner | deterministic golden 完成 |
| PR-6 | P4b：enforce、真实指标和 artifacts | PR gate 完整化 |
| PR-7 | P5 扩展指南、追溯记录和 SOP Pilot | 可交接闭环完成 |

## 7. 最终验收清单

- [x] P0 快照已证明干净环境安装后能运行全部 deterministic suites；当前 revision 变化后仍需重新执行。
- [ ] PR 目标命令连续运行 3 次，结果一致且无 flaky/XPASS。
- [ ] user stop 和 duplicate tool ID 不再是 `xfail`。
- [ ] 持久化测试重新实例化 MessageManager 并完成磁盘回读验证。
- [ ] Gate 单元测试覆盖 `pass / warn / fail` 和 enforce 退出码。
- [ ] CI 保存 JSON、Markdown 和测试结果 artifacts。
- [ ] PR Required Check 状态由仓库设置证据确认。
- [ ] Chat Stream 的质量报告、triage 和 gate record 可追溯到测试资产。
- [ ] 人类 Reviewer 确认后，相关结果才能标记为 `Verified`。

## 8. 当前不做

- MQTT 与真实硬件设备测试。
- 完整 MCP / OpenClaw 外部生态联调。
- 真实 RAG 服务作为 PR Blocking 依赖。
- 真实 LLM 语义结果作为确定性 PR Blocking 信号。
- LLM-as-a-Judge 平台。
- 可视化 Dashboard 或 Langfuse 替代平台。
- 全项目所有模块的横向覆盖扩张。

## Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| docs-p0-purpose-001 | 2026-07-28 | 为 P0 每项补充目的与作用说明 | DONE | 已为 P0 七项检查项分别增加目的和作用；说明已与当前依赖、失效 patch、marker、artifact、CI 和 revision 证据核对 | 人工审阅 P0 说明；确认后再执行 P0 第一项依赖修复 |
| p0-dependencies-001 | 2026-07-28 | 显式声明 P0 测试依赖并验证锁文件安装 | DONE | `pyproject.toml` 已声明 `pytest>=8.0.0`、`pytest-asyncio>=1.0.0`、`allure-pytest>=2.13.5` 和 `google-genai>=1.63.0`；`uv lock --check`、`uv sync --frozen --group test` 退出码为 0；Golden schema/runner 为 `14 passed` | 修复 `flush_langfuse`、`start_llm_generation_observation` 等失效 monkeypatch |
| p0-monkeypatch-001 | 2026-07-28 | 修复失效 Langfuse monkeypatch | DONE | 删除 Smoke fixture 对 `chat_routes.flush_langfuse` 的失效 patch；Langfuse 单测改为 patch `langfuse_integration.start_observation/update_observation` 并直接验证 adapter；Smoke `3 passed`，完整 unit `48 passed, 1 xfailed` | 确认并修订 `pytest.ini` marker 语义与依赖边界 |
| p0-markers-001 | 2026-07-28 | 对齐 pytest marker 的层级与依赖边界 | DONE | 修订 `pytest.ini` 中 smoke、blocking、integration、unit、real_llm、golden_case 的语义；补齐 Golden schema 的 `unit` marker；严格收集 `93` 项，`-m unit` 选中 `49` 项，unit `48 passed, 1 xfailed`，CI Smoke `3 passed` | 将测试报告、缓存和临时产物与源码提交边界分离 |
| p0-artifact-boundary-001 | 2026-07-28 | 分离测试运行产物与源码提交边界 | DONE | `.gitignore` 排除 Allure raw/HTML 和 Quality Gate 运行报告；报告说明固定生成物与人工 baseline 边界；定向运行 `1 passed`、`gate_result=pass`，生成目录不再出现在 Git 状态中，baseline 未改写 | 在干净环境执行 smoke、unit、stream integration、stub golden |
| p0-closure-001 | 2026-07-28 | 完成 P0 干净环境执行、Run Record 与评审边界 | DONE | 新建隔离 Python 3.11 环境并冻结安装；四层分别为 Smoke `3 passed`、Unit `48 passed, 1 xfailed`、Stream `7 passed, 1 xfailed`、Golden `5 passed`；聚合与凭据清除复跑均为 `63 passed, 2 xfailed`；用户已于 2026-08-01 临时确认该快照为 `VERIFIED` | 在当前 revision 上重跑时生成新的 Run Record；当前进入 P1 |
| p0-verify-001 | 2026-08-01 | 将 P0 Run Record 暂定晋升为 VERIFIED | DONE | 用户明确确认临时晋升；Run Record、报告索引和路线图已同步为 `VERIFIED`；原执行 HEAD 为 `70f781f...`，状态更新时 HEAD 为 `4e6fd1d...`，当前 HEAD 已为 `01090ce...`，后两者均未执行新的 P0 clean-environment Run；两个 `XFAIL_GAP` 及 Gate 未完整接线边界不变 | 当前 revision 需要复验时生成新 Run Record；当前继续 P1 |
| docs-p1-p5-purpose-001 | 2026-08-01 | 为 P1-P5 每项补充目的与作用说明 | DONE | P1-P5 共 38 个检查项均已补充目的与作用；自动检查 `MissingPurposeOrEffect=0`，原有状态符号未改变，Markdown `git diff --check` 通过 | 人工审阅说明；确认后按既定优先级进入 P1 Chat Stream 生命周期 |
| p1-sse-protocol-001 | 2026-08-01 | 固定 SSE 顺序/终止协议并验证多 content 增量拼接 | DONE | 正常流断言 `session_id → status+ → content×3 → round_end → [DONE]`，异常流断言 `session_id → status+ → content → error`；两个 terminal 均唯一且位于末尾；三段文本精确拼接并与保存入参一致；定向 `2 passed`，完整 resilience `7 passed, 1 xfailed`（既有 user-stop gap） | 执行 P1 第三项：前端 `AbortSignal` 取消与服务端 generator cleanup |
| docs-p0-p1-reconcile-001 | 2026-08-01 | 同步 P0 与 P1 已完成部分到测试文档体系 | DONE | 修正当前进度中的旧失败结果和 P0 ledger 状态；恢复 Chat Stream 精简路线图；同步 architecture overview、Part 02、Quality Gate、CI Gate、P0 Run Record supplement 和 portfolio；残留扫描未发现旧测试路径、P0 未完成声明或 P1 过度完成声明 | 执行 P1 第三项 `AbortSignal`；完成后再次同步状态与证据 |
