# NagaAgent Agent Workflow Quality Gate

## 1. 展示定位

本页面向简历、面试和开源作品展示，目标是在 3 分钟内说明 NagaAgent 当前测试体系解决了什么真实工程问题。

当前主线可以概括为：

> Deterministic Agent Workflow Quality Gate for Tool-Using LLM Agents

它的重点不是把完整线上环境全部跑起来，而是把非确定性的 agent workflow 拆成可复现、可诊断、可门禁的灰盒回归体系。

## 2. 最小闭环

```text
pytest markers / CI profile
  -> deterministic smoke / integration / unit suites
  -> FastAPI route or real run_agentic_loop under controlled fakes
  -> assertions + quality_gate_case payload
  -> failure attribution
  -> Quality Gate Summary
  -> JSON / Markdown / terminal / optional Allure
```

### PR Smoke Gate

- 覆盖 `/health`、`/chat`、`/chat/stream`。
- 运行命令：`uv run python -m pytest tests/smoke -m "smoke and blocking" -q`。
- 用途：低成本阻止基础 API、路由和 SSE 入口回归。
- 当前证据：workflow 已成功运行；是否已在 Branch Protection 中配置为 Required Check 仍为 `UNKNOWN`。

### SSE Resilience Integration

- 真实 FastAPI route，替换 LLM、loop、telemetry、notify、save 等高波动依赖。
- P1 已落地正常流 `session_id -> status+ -> content+ -> round_end -> [DONE]`、异常流 `session_id -> status+ -> content -> error`、唯一末尾 terminal，以及三段 `content` 精确拼接和保存 spy 一致性。
- 其他覆盖包括 tool error、notify failure、compression failure、empty output 和 active flag cleanup；user stop 仍为 `XFAIL_GAP`。
- 用途：验证 `/chat/stream` 的协议、生命周期和异常收尾，而不是验证模型回答质量。

### Agentic Loop State Gate

- 真实 `run_agentic_loop(...)` 编排路径，替换 fake LLM、fake queue、fake tool dispatcher、fake compression。
- 覆盖 convergence、dispatch contract、message injection、context compression、failure attribution。
- 用途：把多轮工具调用 agent loop 固定成可回归的状态机行为。

### Quality Gate Summary

- 通过 pytest hook 收集 pytest outcome 和 `quality_gate_case` payload。
- 聚合 `final_status`、`failure_stage`、latency、tool rounds、tool count、retry、timeout 等指标。
- 输出 `agent_quality_report.json`、`agent_quality_summary.md` 和 terminal summary，并与 baseline 做 pass / warn / fail 判级。

## 3. 当前已做成果

- P0 已完成依赖、失效 monkeypatch、marker、artifact 边界和干净环境执行；Run Record 为临时 `VERIFIED` 快照，不代表当前 revision 或发布认证。
- CI 已有 PR smoke blocking workflow。
- pytest 已定义 `smoke`、`blocking`、`integration`、`unit`、`real_llm` markers。
- `p2_api` 已覆盖 smoke、SSE resilience integration、opt-in real LLM smoke。
- `agentic_tool_loop` 已覆盖状态机收敛、工具分发契约、消息注入、上下文压缩、失败归因。
- `failure_attribution` 已固定最小 schema：`final_status`、`failure_stage`、`rounds`、`tool_call_count`、`summary_triggered`、`unhandled_exception`。
- `quality_gate_summary` 已实现 v1：pytest hook 收集、case 归一、metrics 聚合、baseline compare、JSON / Markdown / terminal 输出。

## 4. 本地展示命令

```bash
uv run python -m pytest tests/smoke -m "smoke and blocking" -q
uv run python -m pytest tests/unit/agentic_tool_loop -q
uv run python -m pytest tests/integration/chat_stream -q
uv run python -m pytest tests/smoke tests/integration/chat_stream tests/unit/agentic_tool_loop --quality-gate
```

`real_llm` 是非阻塞补充，只有显式开启真实模型凭据时运行：

```bash
NAGA_ENABLE_REAL_LLM_TESTS=1 uv run python -m pytest tests/integration/chat_stream/test_real_llm_smoke.py -m real_llm
```

## 5. 报告样例口径

以下是历史展示样例，不是 2026-08-01 P1 诊断执行的最新结果：

```text
gate_result=pass
total=32 passed=32 failed=0 warned=0
ttfb_p95_ms=2728.25
total_latency_p95_ms=2728.25
avg_tool_rounds=1.083
failure_stage_distribution={none: 32}
baseline_delta={pass_rate: 0.0, latency: 0.0, rounds: 0.0}
```

这些数字代表的是测试运行的质量快照，不是模型语义评分。pytest assertion 仍是事实来源，Quality Gate Summary 负责聚合、归因和展示。

当前 P1 Stream resilience 的最新功能结果为 `7 passed, 1 xfailed`；带 `--quality-gate` 的诊断报告因进程内 latency 相对 baseline 严重退化而得到 `gate_result=fail`。这不应被包装成 Gate 通过，也不改变已通过 SSE 功能断言的结果。

## 6. 当前边界

- 当前主线是灰盒 workflow regression，不是完整线上 E2E。
- P1 当前只完成 SSE 顺序/唯一终止和多增量拼接；`AbortSignal`、cancelled 终态、timeout、重复 finalize、真实持久化回读和 `first_chunk_ms` 重命名仍未完成。
- 真实 LLM、真实 MCP / OpenClaw、真实 memory backend、完整 staging 环境暂不进入 PR blocking gate。
- E2E / staging 的价值是发现环境组合问题，适合作为 release 前或定时非阻塞检查；它不替代当前的 deterministic quality gate。
- 后续 Golden Cases 应依据 [`../architecture/part-11-golden-cases.md`](../architecture/part-11-golden-cases.md) 中最后一章的业务 mapping 定义任务契约，再落 case 和 baseline。

## 7. 简历表述

Designed and implemented a layered testing and quality-gate framework for a tool-using open-source AI agent system. The framework includes deterministic PR smoke gates, SSE streaming resilience regression, state-machine-oriented tests for a non-deterministic agentic tool loop, structured failure attribution, and a baseline-aware quality-gate summary that emits JSON, Markdown, and terminal reports for CI-driven reliability assessment.
