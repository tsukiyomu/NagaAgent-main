# 文档要求

testing_architecture.md保持当前的目录结构，只准添加不准修改。

然后详细的讲解和解释都添加到对应的模块里，每个模块的目录如下：

![测试文档结构](../img/image-20260428211733612.png)

> `SUSPENDED`（2026-08-18）：本文件保留总体 Gate 设计背景；当前优先级和 Compiler/Runtime 路线见 [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md)。

# 三个计划

## 1. 工具调用工作流回归：补“状态机门禁”，不要补成工具观测平台

你现在这条是：

> 构建 Agent 工具调用工作流回归，覆盖工具选择、参数生成、工具失败/超时、重复 tool_call_id、超过 max rounds、降级回答等场景，验证 Agent 在外部工具不稳定或模型输出异常时能否收敛到可解释最终状态。

这条方向对，但还需要补 4 个关键词：

> **状态转移、硬断言、收敛规则、失败归因。**

你现在文档里已经明确 `agentic_tool_loop` 不该继续测 SSE，而是测 `run_agentic_loop(...)` 背后的多轮编排，重点包括 round loop、max_rounds、tool call parsing、tool result 注入、early convergence、summary round 和 queued message injection。

所以这条应该补成：

> 构建 Agent 工具调用工作流回归，围绕 LLM 输出解析、tool_calls 标准化、dispatcher 执行、tool_results 注入、next round / stop / summary 的状态转移设计用例，覆盖工具选择、参数生成、工具失败/超时、重复 tool_call_id、超过 max rounds、降级回答等场景，并通过硬断言验证 workflow 能否收敛到可解释最终状态。

### 这一条要补的具体内容

#### A. 状态转移表

你要在文档里补一个表：

| 当前状态              | 输入事件            | 预期状态               | 必须断言                        |
| --------------------- | ------------------- | ---------------------- | ------------------------------- |
| `round_start`         | no tool call        | `final_answer`         | 不调用 `execute_tool_calls`     |
| `round_start`         | valid tool call     | `tool_dispatch`        | tool name / args 被标准化       |
| `tool_dispatch`       | tool success        | `tool_result_injected` | tool result 进入下一轮 messages |
| `tool_dispatch`       | tool error          | `failure_count + 1`    | 不中断整个 loop                 |
| `failure_count >= 2`  | repeated failure    | `summary_round`        | 不继续无限 tool call            |
| `round == max_rounds` | still has tool call | `summary_round`        | summary round 不带 tools        |
| `summary_round`       | final output        | `stop`                 | `round_end(has_more=False)`     |

这能把“工具测试”变成“workflow 状态机测试”。

#### B. 硬门禁断言

这些适合进 stub 模式，作为 CI 前稳定门禁：

- `rounds <= max_rounds + 1`
- `duplicate_tool_call_id == false`
- `tool_results_injected_once == true`
- `execute_tool_calls_called_expected_times`
- `final_status in ["success", "degraded", "summary"]`
- `unhandled_exception == false`
- `summary_round_triggered_when_expected == true`
- `tool_result_message_count == expected`

这些都是**确定性断言**，不依赖 Langfuse。

#### C. 失败归因字段

不要做 trace 平台，但要输出最小 failure stage：

```
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

`failure_stage` 建议固定这几个：

- `llm_output_parse`
- `tool_call_normalize`
- `tool_dispatch`
- `tool_result_injection`
- `context_assembly`
- `summary_round`
- `finalize`

这就很像“质量门禁报告”，而不是 Langfuse 那种“可观测平台”。

------

## 2. Golden Cases：补“baseline 对比”，不要补成 LLM-as-a-Judge 平台

你现在这条是：

> 构建 Agent Workflow Golden Cases 离线回归集，围绕任务完成质量设计可断言用例，覆盖工具选择正确性、参数语义正确性、上下文有效引用、错误降级路径和最终回答结构，识别 prompt / tool schema / context assembly 变更导致的任务级质量退化。

这条最关键。它是你从“框架测试”走向“AI 工程质量”的核心。

但这里一定要避免和 Langfuse 重合。Langfuse Datasets 本身就是用结构化数据集做 experiments 和 benchmarks。
 所以你不要强调“我做数据集平台 / 评测平台”，而要强调：

> **我做的是可版本化的 golden cases + baseline regression gate。**

### 这一条要补的具体内容

#### A. Golden case schema

建议每条 case 不要只写输入输出，而是写成 workflow 断言：

```
case_id: gc_tool_search_001
group: tool_selection
profile: stub_or_real_llm
user_input: "帮我查询 NagaAgent 的启动方式并总结"
expected:
  final_status: success
  required_tool: knowledge_search
  max_rounds: 3
  required_answer_points:
    - "启动命令"
    - "配置文件"
    - "运行方式"
  forbidden:
    - "编造不存在的参数"
    - "不调用工具直接回答"
gate:
  blocking: true
  baseline_compare: true
```

重点是：**case 描述的是任务级质量要求，而不是单纯期望文本。**

#### B. 双 oracle：stub 精确断言 + real_llm 宽松断言

你需要明确：

| Profile    | Oracle 类型                  | 断言方式                                         |
| ---------- | ---------------------------- | ------------------------------------------------ |
| `stub`     | deterministic oracle         | 精确断言 tool name、args、rounds、messages delta |
| `real_llm` | semantic / structural oracle | 断言工具选择、关键点覆盖、最终状态、无明显胡说   |
| `staging`  | integration oracle           | 断言真实链路可用、真实 tool 返回被消费           |

你当前文档已经有 `stub / real_llm / staging` 的运行模式分层：`stub` 追求快、稳、离线、可重复，`real_llm` 验证真实模型路径不破坏基本 workflow，`staging` 用于发现本地测试覆盖不到的环境问题。
 Golden Cases 应该继承这个分层，不要另起一套平台。

#### C. Baseline 文件

这是你要补的重点。

每次跑完 golden cases，生成：

```
{
  "baseline_version": "2026-04-27",
  "case_count": 20,
  "pass_rate": 0.9,
  "tool_selection_acc": 0.95,
  "context_usage_acc": 0.85,
  "avg_rounds": 2.1,
  "p95_latency_ms": 4200,
  "max_failure_rate": 0.1
}
```

当前结果和 baseline 比：

```
{
  "current_pass_rate": 0.85,
  "baseline_pass_rate": 0.9,
  "delta": -0.05,
  "gate_result": "failed",
  "reason": "tool_selection_acc dropped by 8%"
}
```

这才是“CI 前质量门禁”。

#### D. Gate 规则

不要一开始太复杂。建议：

| 指标                               | Gate 规则                      |
| ---------------------------------- | ------------------------------ |
| blocking golden cases              | 必须 100% pass                 |
| non-blocking golden cases          | pass rate 不低于 baseline - 5% |
| tool selection accuracy            | 不低于 baseline - 3%           |
| context usage accuracy             | 不低于 baseline - 5%           |
| avg rounds                         | 不高于 baseline + 1            |
| failure rate                       | 不高于 baseline + 5%           |
| hallucination / unsupported answer | blocking case 中必须为 0       |

注意：这里不是“打分平台”，而是**变更准入规则**。

#### E. Case 分组

建议只做 20 条以内：

| 分组                      | 数量 | 目标               |
| ------------------------- | ---- | ------------------ |
| no-tool final answer      | 3    | 不该调工具时别乱调 |
| single tool success       | 4    | 工具选择和参数生成 |
| tool failure fallback     | 3    | 工具失败不胡说     |
| context usage             | 4    | 给了上下文要用     |
| max rounds / summary      | 2    | 不死循环           |
| safety / refusal          | 2    | 不越权、不编造     |
| regression from known bug | 2    | 历史 badcase 回归  |

不要一上来做 100 条，这会变成维护负担。

------

## 3. 自动化报告：补“门禁报告”，不要补成 dashboard

你现在这条是：

> 在自动化报告中补充 TTFB、完整输出耗时、tool round 数、异常类型、重试次数、final status 等指标，用于定位响应退化、循环调用、异常终止和 workflow 不收敛问题。

这条要保留，但要从“报告字段”升级成“gate summary”。

你当前文档已经补了最小报告字段，包括 `ttfb_ms`、`total_latency_ms`、`event_count`、`done_seen`、`finalize_called`、`save_call_count`、`active_cleaned`，并且说明这些字段用于 resilience 套件和后续 real_llm / staging 扩展。

接下来要补的是：

> **报告不仅展示结果，还要给出 pass / warn / fail。**

### 这一条要补的具体内容

#### A. 报告结构

建议输出一个 `agent_quality_report.json`：

```
{
  "run_id": "2026-04-27T12:00:00",
  "profile": "stub",
  "suite": "agent_workflow_regression",
  "summary": {
    "total": 20,
    "passed": 18,
    "failed": 2,
    "gate_result": "failed"
  },
  "metrics": {
    "ttfb_p95_ms": 900,
    "total_latency_p95_ms": 5000,
    "avg_tool_rounds": 2.1,
    "max_tool_rounds": 4,
    "retry_count": 1,
    "workflow_timeout_count": 0
  },
  "regression": {
    "baseline": "baseline/main.json",
    "pass_rate_delta": -0.05,
    "latency_delta": 0.18,
    "rounds_delta": 1.2
  },
  "failures": [
    {
      "case_id": "gc_tool_004",
      "failure_stage": "tool_result_injection",
      "reason": "tool result was not injected into next round"
    }
  ]
}
```

#### B. 报告输出不要做 UI

不要做 dashboard。输出这三个就够：

- `agent_quality_report.json`
- `agent_quality_summary.md`
- pytest terminal summary

如果以后接 Langfuse，它只是**记录 trace / score**，不是你的主系统。你当前价值在于“本地可复现 + baseline gate”。

#### C. 指标分成三类

| 类型        | 指标                                                     | 是否适合 gate          |
| ----------- | -------------------------------------------------------- | ---------------------- |
| Correctness | final_status、required_tool、context_used、answer_points | 适合硬门禁             |
| Stability   | exception_type、retry_count、timeout、max_rounds         | 适合硬门禁             |
| Performance | TTFB、total_latency、rounds、tool_count                  | 适合 baseline 阈值门禁 |

不要把所有指标都硬卡。比如 latency 可以用 baseline + 容忍度，不要写死。

------

## 4. 三条合起来的最终方向

你这三条不要平行写成“功能列表”，而要形成一个闭环：

```
Agent Workflow Regression Gate
├── 1. Tool Loop State Regression
│   └── 验证工具调用链路是否收敛
├── 2. Golden Cases Baseline Regression
│   └── 验证任务级质量是否低于 baseline
└── 3. Quality Gate Report
    └── 输出 pass/warn/fail + failure_stage + baseline delta
```

这就非常清楚：你不是 Langfuse，你是“门禁”。

## 最终判断

你的三条方向要补的不是“更多平台功能”，而是：

> **每条都加上 baseline、gate、failure_stage、blocking/non-blocking 的概念。**

这样它就不是 Langfuse，不是 dashboard，也不是单纯测试框架，而是：

> **面向 Agent Workflow 的 CI 前质量门禁 / regression gate。**



