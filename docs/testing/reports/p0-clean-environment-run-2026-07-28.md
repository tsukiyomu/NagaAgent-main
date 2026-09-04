# P0 Clean Environment Run Record

## 1. Record Status

| Field | Value |
|---|---|
| Run ID | `p0-closure-001` |
| Executed at | `2026-07-28T23:33:48+08:00` |
| Execution result | `PASS_WITH_EXPECTED_XFAIL` |
| Artifact status | `VERIFIED` |
| Review status | `USER_CONFIRMED_PROVISIONAL` |
| Verified | Yes；用户于 `2026-08-01` 明确要求暂时晋升为 `VERIFIED` |

本次状态晋升只适用于本记录所述的 2026-07-28 执行快照：HEAD `70f781f6d3e46ecdded15eb92c133a6ce9a47e40` 加当时记录的 dirty working tree。状态更新时仓库 HEAD 已为 `4e6fd1d3bc47812da6f3b231cd734be09d57d86e`，本次没有在新 HEAD 上重新执行测试；因此该 `VERIFIED` 是临时/暂定的执行证据确认，不是当前 revision、PR Gate 或发布质量认证。

## 2. Scope

本次只验收 P0 deterministic baseline：

1. API Smoke；
2. Unit；
3. Chat Stream Integration（排除 `real_llm`）；
4. Stub Golden Cases。

未执行真实 LLM、真实 MCP、RAG、MQTT、硬件、付费服务或生产环境测试。

## 3. Source And Environment

| Field | Value |
|---|---|
| Repository | `F:\Programme\Agent\NagaAgent-main` |
| Branch | `main` |
| HEAD | `70f781f6d3e46ecdded15eb92c133a6ce9a47e40` |
| Working tree | `DIRTY`；结果反映 HEAD 加当前本地修改，不能仅通过 HEAD 重建 |
| Tracked diff fingerprint | `e4fcc6080d08396297333fb2e03eb9cbf422a222` |
| Relevant-source manifest | 105 files；SHA-256 `a508c58431b9fea127c79d97583fc3a5aa6d287b61491ee42a373ea80fc4df4c` |
| OS | Windows 11 专业工作站版，Windows NT `10.0.22000.0` |
| uv | `0.9.24` |
| Python | CPython `3.11.7` 64-bit |
| pytest | `9.1.1` |
| pytest-asyncio | `1.4.0` |
| Clean environment | `C:\Users\tsukiyomu\AppData\Local\Temp\nagaagent-p0-clean-env-20260728-p0closure001` |

隔离环境路径在执行前不存在，由本次 `uv sync` 新建；未复用仓库原有 `.venv`。第二次聚合执行还清除了常见 LLM、Langfuse 和代理环境变量，并使用全新的临时 `HOME/USERPROFILE`。

## 4. Dependency Installation

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\Users\tsukiyomu\AppData\Local\Temp\nagaagent-p0-clean-env-20260728-p0closure001'
uv sync --frozen --group test --python 3.11
```

结果：

- Exit code：`0`
- 创建全新虚拟环境；
- 安装 `156` 个包；
- `uv lock --check` exit code：`0`，解析 `164` 个包。

## 5. Layered Execution Results

| Suite | Exact pytest selection | Result | Exit code |
|---|---|---:|---:|
| Smoke | `uv run python -m pytest tests/smoke -m "smoke and blocking" -q` | `3 passed` | `0` |
| Unit | `uv run python -m pytest tests/unit -m "unit" -q` | `48 passed, 1 xfailed` | `0` |
| Stream Integration | `uv run python -m pytest tests/integration/chat_stream/test_resilience.py -m "integration and not real_llm" -q` | `7 passed, 1 xfailed` | `0` |
| Stub Golden | `uv run python -m pytest tests/golden_cases -m "golden_case" -q` | `5 passed` | `0` |

全部分层命令均完成 collection、fixture setup、test call 和 teardown，没有 setup error。

## 6. Single Replay Command

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\Users\tsukiyomu\AppData\Local\Temp\nagaagent-p0-clean-env-20260728-p0closure001'
uv run python -m pytest tests/smoke tests/unit tests/integration/chat_stream/test_resilience.py tests/golden_cases -m "not real_llm" -q
```

首次聚合结果：

- Exit code：`0`
- `63 passed, 2 xfailed`
- `12 warnings`
- `74.83s`

清除 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GOOGLE_API_KEY`、`GEMINI_API_KEY`、`NAGA_ENABLE_REAL_LLM_TESTS`、Langfuse 和代理变量，并切换到临时 `HOME/USERPROFILE` 后复跑：

- Exit code：`0`
- `63 passed, 2 xfailed`
- `7 warnings`
- `22.55s`
- 无 XPASS、失败或 setup error。

## 7. Expected Gaps

| Test | Status | Meaning |
|---|---|---|
| `test_duplicate_tool_call_id_is_deduplicated_across_rounds` | `XFAIL_GAP` | 当前 runtime 尚未跨轮去重重复 `tool_call_id`；属于后续 Tool Loop 收敛修复 |
| `test_chat_stream_user_stop_contract_gap` | `XFAIL_GAP` | 当前 runtime 尚无明确 user-stop 生命周期契约；属于后续 Chat Stream 生命周期修复 |

这两个 xfail 是已编码的产品能力缺口，不是 P0 环境或 fixture setup 问题，也不能标记为已覆盖。

## 8. Authenticity And Proof Boundary

| Suite | Real parts | Controlled parts | Proves | Does not prove |
|---|---|---|---|---|
| Smoke | FastAPI app、route、请求/响应封装、TestClient lifecycle | LLM、Agent Loop、memory、telemetry、persistence；socket guard 禁止外部连接 | 关键 API 可启动并满足最小响应/SSE 终止契约 | 真实模型、真实工具和真实持久化 |
| Unit | 目标模块和状态机逻辑 | scripted inputs、fake executors、临时路径 | 模块级分支、错误归一和状态契约 | 完整 route-to-storage 链路 |
| Stream Integration | 真实 `/chat/stream` route；部分用例使用真实 Agent Loop | fake loop 或 fake streaming LLM；外部副作用替换 | SSE 完成/异常路径与 cleanup 基线 | user stop、真实网络 TTFB、真实 LLM/MCP |
| Stub Golden | 真实 Agent Loop 和断言 runner | scripted LLM、tool schema/result、空队列 | 确定性 workflow contract 与任务级结构断言 | 真实模型语义质量或外部工具可用性 |

## 9. Gate And Artifact Status

- Smoke 已接入 `.github/workflows/pr-smoke-gate.yml` 的 PR workflow；是否在 GitHub 分支保护中被设置为 Required Check，本地证据无法确认，状态为 `UNKNOWN`。
- Unit、Stream Integration 和 Stub Golden 当前尚未全部接入 PR blocking workflow，状态为 `NOT_WIRED`。
- Allure 与 Quality Gate 运行产物被 `.gitignore` 排除；执行后目标 artifact 路径未污染 Git 状态。
- `tests/baseline/quality_gate/` 保持已跟踪且本次没有被改写。

## 10. Warnings And Review Checklist

观察到的 warning 来自 Pydantic class config、LiteLLM resource API、websockets legacy API 和 HTTPX per-request cookies 的弃用提示；本次没有证据表明它们造成 deterministic suite 失败。

人类评审状态：

1. 用户已于 `2026-08-01` 明确要求暂时将 P0 标记为 `VERIFIED`；
2. 两个 xfail 继续作为 P1/P2 的 `XFAIL_GAP`，不因本次状态晋升而视为已完成；
3. dirty working tree、当前 HEAD 已变化以及完整 PR Gate 尚未接线的限制继续有效；
4. 进入测试专用 PR、切换 revision 或修改相关测试/生产代码后，应重新执行并生成新的 Run Record。

## 11. Supplement

### 11.1 两个 xfail 的归属

当前两个 `xfail` 都是已经落成可执行测试的 `XFAIL_GAP`：测试能够被 pytest 收集和执行，但生产 runtime 尚未满足目标契约。它们不是依赖安装、fixture setup 或测试框架故障。

| Test | Test layer / authenticity | Architecture ownership | Roadmap phase | Current gap |
|---|---|---|---|---|
| `test_chat_stream_user_stop_contract_gap` | Integration/API；real `/chat/stream` route + slow fake loop + persistence/finalize spy | Part 02：API / Chat Stream 为 `OWNER`；前端取消入口是关联 `BOUNDARY` | P1：Chat Stream 生命周期 | 客户端提前断开后，runtime 尚未提供稳定、可断言的 cancelled/finalize/cleanup/persistence 语义 |
| `test_duplicate_tool_call_id_is_deduplicated_across_rounds` | Unit/Component；real Agent Loop + scripted LLM + fake tool dispatch | Part 04：Agentic Tool Loop 为 `OWNER` | P2：Tool、Context 与真实持久化 | 相同 `tool_call_id` 跨轮出现时，历史中的 tool message 和 assistant tool-call 引用仍可能重复注入 |

### 11.2 User Stop：Part 02 / P1

- 测试位置：`tests/integration/chat_stream/test_resilience.py::TestChatStreamRouteWithFakeLoop::test_chat_stream_user_stop_contract_gap`。
- 当前模拟方式：客户端读取第一段 SSE 后关闭 in-process stream；slow fake loop 保留后续 chunk，用于近似用户主动停止。
- 目标契约：客户端断开不能被当作正常完成；route 必须完成一次 finalize、释放 active state，并遵守 cancelled 状态和部分响应保存策略。
- 当前 xfail 已锁定的断言：没有 `[DONE]`、`finalize_called == 1`、`save_call_count == 0`、`active_cleaned is True`。
- 证明边界：当前测试使用真实 route，但 loop 是 fake，也没有运行真实前端 `AbortSignal`；因此它只能锁定服务端 route 收口目标，不能证明浏览器到服务端的真实取消传播。
- 后续完成条件：P1 接入前端 `AbortSignal`，明确 `final_status=cancelled`、finalize/cleanup 严格一次，并补齐非空部分响应与空响应的持久化断言后移除 xfail。

### 11.3 Duplicate Tool ID：Part 04 / P2

- 测试位置：`tests/unit/agentic_tool_loop/test_loop_message_injection.py::test_duplicate_tool_call_id_is_deduplicated_across_rounds`。
- 当前模拟方式：scripted LLM 在连续两轮返回相同 `dup-id`，fake dispatcher 两次都返回成功，第三轮检查进入 LLM 的历史消息。
- 目标契约：相同 ID 对应的 tool message 只能保留一条，assistant 历史中的同 ID tool-call 引用也只能保留一条。
- 当前失败含义：`run_agentic_loop` 尚未建立跨轮 `tool_call_id` 去重状态，重复结果仍可能污染上下文。
- 证明边界：当前 xfail 直接锁定的是“历史注入去重”；因为 fake dispatcher 仍会处理两轮调用，它尚未独立证明“重复 ID 只执行一次”。P2 修复时还需要增加 dispatch 次数/副作用断言，才能覆盖“只执行和注入一次”的完整契约。
- 后续完成条件：P2 在 runtime 增加跨轮去重，补足执行次数断言，并将该 xfail 转为稳定回归。

实施顺序保持为：先完成 P1 User Stop，再进入 P2 Duplicate `tool_call_id`。两项在转为稳定通过前都不能宣称为已覆盖能力。

### 11.4 P0 之后的 P1 同步说明（2026-08-01）

P0 Run Record 形成后，P1 已完成两个独立工作项：

1. 正常流与异常流的应用层 SSE 顺序、唯一 terminal 契约已经 `LANDED`；
2. 三个有序 `content` 事件、完整拼接和 persistence spy 入参一致性已经 `LANDED`。

对应的后续执行证据为定向 `2 passed`、完整 resilience `7 passed, 1 xfailed`。唯一 `xfail` 仍是本记录 11.2 所述 user-stop gap。这些 P1 结果发生在 P0 执行快照之后，因此不会回写或替换第 5、6 节的历史运行数字，也不会把 P0 `VERIFIED` 自动延伸到当前 revision。当前优先级以 [`../plans/sop-compiler-runtime-practical-roadmap.md`](../plans/sop-compiler-runtime-practical-roadmap.md) 为准，API/Stream 实现状态以 [`../architecture/part-02-api-stream.md`](../architecture/part-02-api-stream.md) 为准。
