# Agent Workflow Golden Cases Implementation Plan

> `SUSPENDED`（2026-08-18）：V1 历史实现与后续设想保留在此；当前执行顺序见 [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md)。

## 1. 文档定位

本文档只负责记录 Golden Cases 的实施范围、优先级和验收顺序。

- 正式模块说明、Case Contract 和业务 mapping：
  [`../../architecture/part-11-golden-cases.md`](../../architecture/part-11-golden-cases.md)
- 当前实施状态：
  `design ready / implementation planned`
- 第一版目标：
  建立一个可以加载业务 case、执行真实 Agent workflow、自动断言并通过 pytest 输出结果的最小闭环。

本文档不替代正式测试模块文档，也不重复描述完整业务流程。

## Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| 2026-06-17-001 | 2026-06-17 | Step 1: Create schema dataclass and schema error classes. | DONE | Added `tests/support/golden_cases.py` with Golden Case schema dataclasses and schema error classes; added `tests/unit/test_golden_case_schema.py`; `python -m pytest tests/unit/test_golden_case_schema.py -q` passed 4 tests. | Step 2: Implement file discovery and loader. |
| 2026-06-17-002 | 2026-06-17 | Step 2: Implement file discovery and loader. | DONE | Added `discover_golden_case_files(...)`, `load_golden_cases(...)`, and mapping-to-dataclass conversion; extended schema tests for JSON loading, YAML loading, duplicate IDs, missing fields, and discovery; `python -m pytest tests/unit/test_golden_case_schema.py -q` passed 8 tests. | Step 3: Add four minimal case files. |
| 2026-06-17-003 | 2026-06-17 | Step 3: Add four minimal case files. | DONE | Added four stub YAML cases under `tests/golden_cases/cases`: no-tool, single-tool web search, tool-timeout fallback, and multi-tool search+fetch; extended loader test to load repository case files; `python -m pytest tests/unit/test_golden_case_schema.py -q` passed 9 tests. | Step 4: Implement runner with stub LLM and stub tool results. |
| 2026-06-17-004 | 2026-06-17 | Step 4: Implement runner with stub LLM and stub tool results. | DONE | Added `run_stub_golden_case(...)` and `GoldenCaseRunReport`; runner patches deterministic LLM, tool dispatcher, queue, compression, and calls real `run_agentic_loop(...)`; added runner tests for no-tool, multi-tool, and timeout fallback; `python -m pytest tests/unit/test_golden_case_schema.py tests/unit/test_golden_case_runner.py -q` passed 12 tests. | Step 5: Implement assertion checker. |
| 2026-06-17-005 | 2026-06-17 | Step 5: Implement assertion checker. | DONE | Added `GoldenCaseAssertionError`, `GoldenCaseAssertionResult`, `evaluate_golden_case_report(...)`, and `assert_golden_case_report(...)`; checker validates required/forbidden tools, tool order, rounds, final status, answer points, summary flag, and unhandled exception; `python -m pytest tests/unit/test_golden_case_schema.py tests/unit/test_golden_case_runner.py -q` passed 14 tests. | Step 6: Add pytest parametrized entry file. |
| 2026-06-17-006 | 2026-06-17 | Step 6: Add pytest parametrized entry file. | DONE | Added `tests/golden_cases/test_agent_workflow_golden_cases.py` with one parametrized stub-profile test over loaded case files; `python -m pytest tests/golden_cases/test_agent_workflow_golden_cases.py -q` passed 4 tests with expected unregistered `golden_case` marker warning. | Step 7: Register golden_case marker. |
| 2026-06-17-007 | 2026-06-17 | Step 7: Register golden_case marker. | DONE | Added `golden_case` marker to `pytest.ini`; `python -m pytest tests/golden_cases/test_agent_workflow_golden_cases.py -q -W error::pytest.PytestUnknownMarkWarning` passed 4 tests with no unknown-marker warning. | Step 8: Run local pytest command and fix failures. |
| 2026-06-17-008 | 2026-06-17 | Step 8: Run local pytest command and fix failures. | DONE | Ran `python -m pytest tests/golden_cases -m golden_case -q`; command passed 4 tests with only existing websockets deprecation warnings and no failures to fix. | Golden Cases v1 complete; next recommended work is optional Quality Gate integration or additional cases. |
| 2026-06-17-009 | 2026-06-17 | P1 Step 1: Add `gc_history_continue_001` case file. | DONE | Added `tests/golden_cases/cases/gc_history_continue_001.yaml` for BF-02 history/current-instruction precedence; updated loader schema test expectations; `python -m pytest tests/golden_cases -m golden_case -q` passed 5 tests and `python -m pytest tests/unit/test_golden_case_schema.py -q` passed 9 tests. | P1 Step 2: Add `gc_memory_recall_001` case file. |

## Current Execution Checklist

- [DONE] Step 1: Create schema dataclass and schema error classes.
- [DONE] Step 2: Implement file discovery and loader.
- [DONE] Step 3: Add four minimal case files.
- [DONE] Step 4: Implement runner with stub LLM and stub tool results.
- [DONE] Step 5: Implement assertion checker.
- [DONE] Step 6: Add pytest parametrized entry file.
- [DONE] Step 7: Register golden_case marker.
- [DONE] Step 8: Run local pytest command and fix failures.

## P1 Execution Checklist

- [DONE] P1 Step 1: Add `gc_history_continue_001` case file.
- [TODO] P1 Step 2: Add `gc_memory_recall_001` case file.
- [TODO] P1 Step 3: Add `gc_skill_selected_001` case file.
- [TODO] P1 Step 4: Add `gc_long_context_compression_001` case file.
- [TODO] P1 Step 5: Re-run Golden Cases command after 8-case expansion.

### 1.1与主线方向的关系

本计划服务于当前主线：Agent Workflow Quality with Memory Governance。

Golden Cases v1 的重点不是构建通用评测平台，也不是完整 memory research，而是先把 tool-using agent 的任务级 workflow regression 做成可执行、可断言、可回归的最小闭环。当前阶段优先验证 no-tool、single-tool、tool-failure、multi-tool-chain 等 workflow 路径，确保 prompt / tool schema / context assembly / loop 变更不会破坏核心任务流程。

Memory governance、context assembly、context compression 和真实 LLM / staging profile 属于后续扩展方向，应在 workflow runner、assertion checker和 quality gate 稳定后逐步接入。



## 2. 当前已经具备

以下能力可以直接复用，不需要在 Golden Cases 中重新开发。

### 2.1 API 与工作流测试基础

1. `tests/smoke`
   - `/health`
   - `/chat`
   - `/chat/stream`
2. `tests/integration/chat_stream`
   - 真实 FastAPI route
   - SSE 正常收尾
   - 异常恢复
   - tool error
   - finalize
   - active flag 清理
3. `tests/unit/agentic_tool_loop`
   - 多轮收敛
   - 工具分发
   - 工具结果注入
   - queue 消息注入
   - context compression
   - failure attribution

### 2.2 测试辅助能力

1. `tests/support/agentic_tool_loop_helpers.py`
   - scripted LLM
   - fake queue
   - SSE helper
2. `tests/support/failure_attribution.py`
   - `final_status`
   - `failure_stage`
   - `rounds`
   - `tool_call_count`
   - `summary_triggered`
   - `unhandled_exception`
3. pytest markers
   - `smoke`
   - `blocking`
   - `integration`
   - `unit`
   - `real_llm`

### 2.3 Quality Gate 基础

当前已经支持：

1. `quality_gate_case` payload 收集。
2. pytest outcome 和业务 metrics 聚合。
3. JSON、Markdown 和 terminal summary。
4. baseline compare。
5. `pass / warn / fail` 判级。
6. `stub_main.json` 和 `real_llm_main.json` 通用 baseline。

这些 baseline 目前属于现有 Quality Gate，不是 Golden Cases 专属 baseline。

### 2.4 Golden Case 设计

[`../../architecture/part-11-golden-cases.md`](../../architecture/part-11-golden-cases.md) 已明确：

1. Case schema。
2. Stub、Real LLM、Staging 三种 profile。
3. workflow-level assertion checker 原则。
4. 第一批 8 条 case。
5. 第二批候选 case。
6. baseline 和 gate 规则。
7. BF-01 至 BF-10 的业务 mapping。
8. 与 unit、integration 和 staging 的边界。

## 3. 第一版必须实现

第一版只实现可执行的最小闭环。以下项目均为必须项。

### 3.1 Golden Case 执行目录

建议建立：

```text
tests/
  golden_cases/
    cases/
    test_agent_workflow_golden_cases.py
  support/
    golden_cases.py
```

目录名称可以根据现有 pytest 结构微调，但必须明确区分：

1. case 数据。
2. runner/support。
3. pytest 测试入口。

### 3.2 统一 Case Schema

第一版至少支持：

```text
case_id
business_flow
group
profile
input
fixtures
expected
gate
```

`expected` 至少支持：

```text
final_status
required_tools
forbidden_tools
max_rounds
required_answer_points
forbidden_answer_points
summary_triggered
unhandled_exception
```

### 3.3 Case Loader

Loader 第一版只需完成：

1. 读取 YAML 或 JSON case。
2. 校验必填字段。
3. 校验 `case_id` 唯一。
4. 校验 profile 和 business flow 合法。
5. 将数据转换为 runner 可使用的结构。
6. Schema 错误时给出可定位的失败信息。

第一版不需要建设通用数据集管理平台。

### 3.4 统一 Runner

Runner 至少负责：

1. 根据 case 创建用户输入和历史消息。
2. 注入 scripted LLM。
3. 注入固定工具结果或工具故障。
4. 调用真实 `run_agentic_loop(...)`。
5. 收集轮次、工具调用、结果注入和最终回答。
6. 生成统一 workflow report。

涉及 route、memory 或 Skill 的 case，可以在基础 runner 稳定后再扩展对应 adapter。

### 3.5 最小 Fixtures

第一版只准备四类 fixture：

1. 直接回答 fixture。
2. 单工具成功 fixture。
3. 工具 timeout/error fixture。
4. 多工具依赖链 fixture。

第一版不要求同时完成 memory、Skill、真实 MCP 和真实外部服务 fixture。

### 3.6 基础 assertion checker

必须自动断言：

1. `required_tools` 是否全部调用。
2. `forbidden_tools` 是否未调用。
3. 工具调用顺序是否正确。
4. `rounds` 是否未超过上限。
5. `final_status` 是否符合预期。
6. `required_answer_points` 是否出现。
7. `forbidden_answer_points` 是否未出现。
8. `unhandled_exception` 是否为 false。

第一版使用确定性结构化断言，不引入 LLM-as-a-Judge。

### 3.7 第一批 4 条 Stub Cases

第一版先实现：

| case_id | 业务目标 | 主要验证 |
|---|---|---|
| `gc_no_tool_answer_001` | 无需工具时直接回答 | 不乱调工具、单轮收敛 |
| `gc_tool_web_search_001` | 单工具查询并总结 | 工具和参数正确、消费工具结果 |
| `gc_tool_timeout_fallback_001` | 工具失败后降级 | 不伪造结果、受控收敛 |
| `gc_multi_tool_search_fetch_001` | 搜索后抓取正文 | 工具顺序和跨轮依赖正确 |

这 4 条分别覆盖：

1. 不调用工具。
2. 单工具成功。
3. 工具失败。
4. 多工具链。

### 3.8 Pytest 执行入口

第一版需要：

1. 增加 `golden_case` marker。
2. 支持独立执行 Golden Cases。
3. 支持按 profile、group 或 case ID 筛选。
4. 保证 stub profile 离线、确定性、可重复。

建议本地命令：

```bash
uv run python -m pytest tests/golden_cases -m golden_case -q
```

## 4. 第一版发布验收标准

以下条件全部满足，即可认为 Golden Cases v1 可以发布：

1. 4 条 stub case 可由数据文件加载，不是在测试函数中硬编码全部场景。
2. 4 条 case 均通过同一个 runner 执行。
3. 4 条 case 均通过统一 assertion checker 断言。
4. 至少覆盖 no-tool、single-tool、tool-failure、multi-tool 四类路径。
5. 测试不依赖真实 LLM、网络、线上环境或真实 MCP。
6. 同一 commit 连续执行结果稳定。
7. 失败时能定位到 case、断言字段和 workflow stage。
8. README 或正式测试文档提供一条可复现命令。

第一版发布不要求 Golden Case 专属 baseline、Real LLM case 或 Staging。

## 5. 建议紧接第一版补充

以下项目有较高展示价值，但不阻塞最小 v1。

### 5.1 扩展到首批 8 条 Cases

在前 4 条稳定后补充：

1. `gc_history_continue_001`
2. `gc_memory_recall_001`
3. `gc_skill_selected_001`
4. `gc_long_context_compression_001`

这一步把测试范围从 tool loop 扩展到 context、memory、Skill 和 compression。Memory / context cases 只在 workflow golden case runner 稳定后接入，用来验证 memory recall、context injection 和 compression 是否造成任务级退化；不在 v1 中实现完整 memory policy 评测。

### 5.2 接入现有 Quality Gate

需要：

1. 增加 `golden_cases` feature。
2. 将 workflow report 转换为 `quality_gate_case` payload。
3. 在报告中展示 case group、business flow 和失败阶段。
4. 复用现有 JSON、Markdown、terminal 和 Allure 输出。

不需要重新实现一套 Quality Gate。

### 5.3 Golden Case Stub Baseline

第一版增强阶段新增独立 baseline：

```text
tests/golden_cases/baselines/stub.json
```

至少记录：

1. case-level pass/fail。
2. tool selection accuracy。
3. context usage accuracy。
4. unsupported answer count。
5. rounds。
6. failure stage distribution。

baseline 必须人工确认更新，不能自动覆盖。

### 5.4 非阻塞 CI Job

建议先作为独立、非阻塞 workflow：

1. 只运行 stub profile。
2. 上传 Golden Case 报告。
3. 观察稳定性后再决定是否进入 required check。

## 6. 后续再做

以下内容不进入第一版主线。

### 6.1 Real LLM Profile

1. 选择 1-2 条稳定 case 做真实模型镜像。
2. 使用宽松结构化 assertion checker。
3. 非阻塞运行。
4. 单独保存 `real_llm` baseline。

### 6.2 Staging Profile

1. 接入真实 LLM、memory 和少量真实工具。
2. 验证认证、网络、schema 和部署配置。
3. 作为定时或发布前检查。
4. 不作为第一版 PR blocking gate。

### 6.3 复杂 Cases

后续根据真实 badcase 增加：

1. context conflict。
2. queue message injection。
3. failure replan。
4. partial result synthesis。
5. max rounds summary。
6. route finalize 和 persistence。

### 6.4 当前明确不做

1. 完整线上生产环境。
2. 全量真实 MCP / OpenClaw 联调。
3. 大规模 Golden Case 数据集。
4. 通用 LLM-as-a-Judge。
5. 自动语义打分平台。
6. Langfuse 取代 pytest 或 Quality Gate。
7. 全平台 E2E 覆盖。

## 7. 推荐实施顺序

```text
P0: Schema + Loader
  -> P0: Runner + 4 类 Fixtures
  -> P0: 基础 assertion checker
  -> P0: 4 条 Stub Cases
  -> 发布 Golden Cases v1
  -> P1: 扩展到 8 条 Cases
  -> P1: 接入 Quality Gate
  -> P1: 生成 Stub Baseline
  -> P1: 增加非阻塞 CI
  -> P2: Real LLM 镜像
  -> P2: Staging 与真实 badcase
```

## 8. 最终范围判断

当前并不缺一整套测试框架。已经存在的 loop、integration、failure attribution 和 Quality Gate 能力应直接复用。Langfuse / LangSmith 可作为后续 trace、score、dataset run 和人工 review 的外部观察层，但 Golden Cases v1 的主价值仍是本地可复现、pytest 可执行、baseline 可对比的 regression gate

Golden Cases 当前真正缺少的是：

```text
业务 Case 数据
  -> Loader
  -> Runner
  -> Fixtures
  -> assertion checker
  -> 可执行 pytest Cases
```

先完成这条链路，就能形成可发布的任务级回归最小闭环。Quality Gate、baseline、Real LLM 和 Staging 按优先级逐步接入。
