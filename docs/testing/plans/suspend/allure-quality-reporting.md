# Allure + Gate Summary 文档计划

> `SUSPENDED`（2026-08-18）：Allure 展示后置，当前先完成可审计 Artifact 与 Gate Runtime；执行顺序见 [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md)。

## Summary
本文件现保存在 `docs/testing/plans/suspend/allure-quality-reporting.md`，只定义 `自动化门禁报告 + Allure 可视化接入`，不把它写成 dashboard 规划，也不和 Golden Cases 混成一个体系。

第一版范围先基于`现有测试层`汇总结果：
- `p2_api` resilience / smoke
- `agentic_tool_loop` unit gate
- `real_llm` smoke

第一版 gate 采用`宽松策略`：
- 先给 `pass / warn / fail`
- correctness / stability 可硬卡
- performance 只做 baseline 对比或 warning
- 不把 latency、波动型指标做成死阈值 blocking

## 文档内容设计
文档建议分 5 节，按下面结构写，避免再做额外产品化设计。

### 1. Positioning
明确这份文档的边界：
- 这是 `quality gate summary + report contract` 规划
- Allure 只是可视化承载层，不是主系统
- 不做 dashboard
- 不做 trace 平台
- 不做 dataset / judge 平台
- 主要价值是：
  - 本地可复现
  - CI 可消费
  - baseline 可比较
  - 面试时可解释规则设计

### 2. Report Contract
固定三种输出物：
- `agent_quality_report.json`
- `agent_quality_summary.md`
- `pytest` terminal summary
- Allure 作为第四层展示，不作为唯一真相源

建议在文档里固定 JSON 结构：
```json
{
  "run_id": "2026-05-04T12:00:00Z",
  "profile": "stub",
  "suite": "agent_workflow_regression",
  "summary": {
    "total": 20,
    "passed": 18,
    "failed": 1,
    "warned": 1,
    "gate_result": "warn"
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
    "baseline": "tests/baseline/stub_main.json",
    "pass_rate_delta": -0.02,
    "latency_delta": 0.12,
    "rounds_delta": 0.3
  },
  "failures": [
    {
      "case_id": "stream_midstream_exception",
      "failure_stage": "finalize",
      "reason": "stream terminated before done event"
    }
  ]
}
```

同时固定 `agent_quality_summary.md` 的职责：
- 人类可读
- 只保留高信号摘要
- 展示 gate_result、关键 delta、失败 case、建议动作

### 3. Metric Taxonomy And Gate Rules
文档中明确把指标分三类，并解释为什么这样分：

- `Correctness`
  - `final_status`
  - `required_tool`
  - `context_used`
  - `answer_points`
  - `done_seen`
  - `finalize_called`
  - `active_cleaned`

- `Stability`
  - `exception_type`
  - `retry_count`
  - `workflow_timeout_count`
  - `max_rounds_exceeded`
  - `unhandled_exception`

- `Performance`
  - `ttfb_ms`
  - `total_latency_ms`
  - `tool_rounds`
  - `tool_count`

第一版宽松 gate 规则建议写死为：
- `pass`
  - blocking correctness/stability 全部通过
  - 无 blocking failure
  - baseline 对比未出现明显退化
- `warn`
  - correctness/stability 通过
  - 但 performance 或非 blocking 指标有轻微退化
- `fail`
  - 任一 blocking correctness/stability 失败
  - 或 baseline 指标退化超过容忍范围

第一版宽松阈值建议：
- blocking correctness cases：`100% pass`
- blocking stability cases：`100% pass`
- `pass_rate`：不低于 baseline `-5%`
- `ttfb_p95_ms`：允许 baseline `+25%`
- `total_latency_p95_ms`：允许 baseline `+25%`
- `avg_tool_rounds`：允许 baseline `+1`
- `retry_count`：允许 baseline `+1`
- `workflow_timeout_count`：`warn` 起步，先不直接 blocking
- `real_llm` 套件默认只参与 `warn/fail` 参考，不进第一版 PR blocking

文档里要明确解释：
- 为什么 correctness/stability 适合硬门禁
- 为什么 performance 适合 baseline + tolerance
- 为什么第一版要宽松
  - 当前真实环境波动还没完全收敛
  - 先让规则可落地、可解释、可复现
  - 后续再逐步收紧

### 4. Allure Integration Plan
这节只写“怎么挂结果”，不要扩成平台设计。

建议文档定义 Allure 只展示四类信息：
- suite 级汇总
- case 级 pass/warn/fail
- 关键 metrics
- baseline delta / failure_stage

建议接入方式写成：
- pytest 保留原有测试结构
- 在测试后处理或聚合脚本中生成 `agent_quality_report.json`
- 再把聚合结果映射到 Allure：
  - `epic`: `Agent Workflow Quality Gate`
  - `feature`: `p2_api` / `agentic_tool_loop` / `real_llm`
  - `story`: `correctness` / `stability` / `performance`
  - attachment:
    - `agent_quality_report.json`
    - `agent_quality_summary.md`
    - 关键 failure attribution 片段

文档里明确非目标：
- 不做自定义 Web UI
- 不把 Allure 当作 baseline 存储中心
- 不把 Langfuse 结果直接当 gate truth
- 不在 Allure 中重新定义评分逻辑

### 5. Rollout
按三步落地，避免一次做重：

1. 第一阶段
   - 补文档
   - 固定 report schema
   - 固定 pass/warn/fail 规则
   - 不要求实现 Allure 自定义展示

2. 第二阶段
   - 基于现有测试层生成 `agent_quality_report.json`
   - 生成 `agent_quality_summary.md`
   - pytest terminal summary 输出 gate_result

3. 第三阶段
   - 把聚合结果接到 Allure
   - 先展示，不增加额外阻塞规则
   - 等 baseline 稳定后再考虑收紧 performance gate

## Important Interfaces
需要在文档中明确的对外契约只有这些：

- 报告文件名
  - `agent_quality_report.json`
  - `agent_quality_summary.md`

- 顶层字段
  - `run_id`
  - `profile`
  - `suite`
  - `summary`
  - `metrics`
  - `regression`
  - `failures`

- gate_result 枚举
  - `pass`
  - `warn`
  - `fail`

- failure_stage 来源
  - 复用现有 failure attribution 体系
  - 至少支持：
    - `llm_output_parse`
    - `tool_call_normalize`
    - `tool_dispatch`
    - `tool_result_injection`
    - `context_assembly`
    - `summary_round`
    - `finalize`

## Test Plan
文档中应把验收标准写清楚，面向后续实现者：

- schema 验收
  - report JSON 字段齐全
  - gate_result 枚举合法
  - summary / metrics / regression / failures 结构稳定

- 规则验收
  - blocking correctness 失败时一定 `fail`
  - blocking stability 失败时一定 `fail`
  - 仅 performance 轻微退化时为 `warn`
  - 无退化时为 `pass`

- 数据来源验收
  - `p2_api resilience` 现有最小 report 字段能被聚合
  - `agentic_tool_loop` failure attribution 能进入 failures 列表
  - `real_llm` 结果可作为 non-blocking profile 纳入展示

- Allure 验收
  - 可看到 suite 汇总
  - 可看到 case 状态
  - 可查看 JSON / Markdown 附件
  - 不要求第一版有复杂 trend 图

## Assumptions
- 规划文档暂存在 `docs/testing/plans/suspend/allure-quality-reporting.md`
- 第一版 gate 只覆盖现有测试层，不等待 Golden Cases 完整落地
- 第一版 Allure 只做可视化承载，不承担规则判断
- 第一版性能门禁采取宽松 baseline 容忍策略，不做死阈值 blocking
- `real_llm` 第一版默认 non-blocking，只参与展示和 warning 参考
