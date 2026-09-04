# Quality Gate Summary Testing

> **Migration status：`REVIEW_NEEDED / NOT_WIRED`。** Quality Gate 代码和 CI 接线尚未迁入
> target branch。详见 [`../MIGRATION_STATUS.md`](../MIGRATION_STATUS.md)。
>
> 对应 [`overview.md`](overview.md) 第 8 章。

## 8.0 快速理解：Quality Gate 到底是什么
- `Quality Gate` 不是重新执行测试，也不是新的评测平台。
- 它当前做的事情可以压缩成一句话：
  把 `pytest` 跑出来的一组测试结果统一汇总成 `pass / warn / fail`，并生成可对比 baseline 的报告。
- `Quality Gate Summary` 的核心流程不是重新执行测试，而是消费测试结果。
- 测试用例在执行过程中采集关键运行数据，并将这些数据整理成结构化 report；随后通过 `quality_gate_case` 写入 pytest record。Quality Gate 聚合器在测试结束阶段统一读取这些 records，进行字段归一、metric 聚合、baseline 对比，并最终输出 `pass / warn / fail`。
- 这里的 `metric` 不是只看某一条 case，而是先把纳入范围的 case 指标做聚合，例如把单条 case 的 `ttfb_ms` / `total_latency_ms` 汇总成 `ttfb_p95_ms` / `total_latency_p95_ms`。
- 这里的 `baseline` 可以理解成“之前一次被接受的结果快照”，后续运行会拿当前聚合结果和它对比，判断是正常、轻微退化，还是明显回归。
- 它现在主要覆盖三类输入：
  1. `p2_api` smoke / resilience
  2. `agentic_tool_loop` unit gate
  3. `real_llm` smoke
- 它当前不承担这些职责：
  1. dashboard
  2. dataset / judge 平台
  3. Langfuse trace / score 平台
  4. Golden Cases 本体

## 8.1 一次测试运行中，QG 如何工作
- 一次启用了 `--quality-gate` 的测试运行，当前最短链路是：
  `test case -> pytest report + optional quality_gate_case payload -> quality_gate aggregator -> JSON / Markdown / terminal / Allure`
- 按执行顺序拆开是：
  1. `pytest` 执行测试
  2. 测试用例采集事实
  3. `_build_stream_report(...)` 做初次整理
  4. `_publish_quality_gate_case(...)` 写入 pytest record
  5. `tests/conftest.py` 收集 records
  6. `tests/support/quality_gate.py` 做归一化 / 聚合 / baseline 对比 / 判级
  7. 输出 JSON / Markdown / terminal / Allure
- 这里要明确一个边界：
  pytest outcome 是“这条测试是否通过”的事实来源，payload 只是补充语义和 metrics。

## 8.2 各组件职责分工
- 当前实现可以分成 4 层：
  1. `tests/support/quality_gate.py`
     - 规则核心
     - 负责 case 归一、指标聚合、baseline 对比、`pass / warn / fail`
  2. `tests/conftest.py`
     - pytest 接入层
     - 负责 CLI 参数注册、pytest hook 收集、terminal summary 和产物落盘
  3. 各测试文件中的 producer helper
     - 典型例子是 `_publish_quality_gate_case(...)`
     - 负责把单条测试看到的观测结果整理成结构化 payload
  4. Allure
     - 展示层
     - 负责可视化已有结果，不负责定义 gate 规则
- 当前这 4 层分别解决的是：
  1. 谁产生测试语义
  2. 谁收集运行结果
  3. 谁做规则判级
  4. 谁负责展示

## 8.3 一个具体例子：`/chat/stream` 测试如何进入 QG
- 以 `tests/integration/chat_stream/test_resilience.py` 为例，当前链路是：
  1. 测试通过 `_stream_run(...)` 跑一次真实的 `/chat/stream`
  2. `_stream_run(...)` 收集最小 stream 观测值
  3. `_build_stream_report(...)` 把这些观测值整理成 report
  4. 如果还需要 workflow 语义，再调用 `build_failure_attribution(...)`
  5. `_publish_quality_gate_case(...)` 把 report + attribution 合成 `quality_gate_case` payload
  6. pytest hook 收集 payload
  7. quality gate 聚合器统一判级
- 这条链路里，`_build_stream_report(...)` 只负责采集事实，不负责最终判级。
- 以当前 `/chat/stream` resilience 用例为例，初次整理出的 report 主要包括：
  1. `ttfb_ms`
  2. `total_latency_ms`
  3. `event_count`
  4. `done_seen`
  5. `finalize_called`
  6. `save_call_count`
  7. `active_cleaned`
- 当前 `p2_api` 里最关键的两个时间字段来自单 case 观测：
  1. `ttfb_ms`（当前代码字段名，P1 待迁移）
     - 从发起 `/chat/stream` 请求开始计时
     - 到进程内 `TestClient` 收到第一个非空 transport chunk 为止
     - 这一 profile 更准确的语义是 `first_chunk_ms`，不能作为独立进程、代理或真实网络 TTFB 证据
  2. `total_latency_ms`
     - 从发起请求开始计时
     - 到整个 stream 结束并退出 `client.stream(...)` 为止
- 也就是说，当前字段计算的是“进程内首次观察到非空 chunk 多久”，不是“整段回答结束多久”；在字段重命名前不应把它表述为真实网络首包性能。
- 一个直观例子：
  1. `12:00:00.000` 发起请求
  2. `12:00:01.800` 收到第一个非空 chunk
  3. 这条 case 的 `ttfb_ms = 1800`
- `_publish_quality_gate_case(...)` 并不负责“计算 gate 结果”。
- 它只负责把这一条测试的观察结果，变成后续聚合器可以消费的结构化输入。

## 8.4 数据来源与输入边界
- 当前 quality gate 直接消费的不是业务代码，而是测试层暴露出的最小结果字段。
- 当前主要输入来源包括：
  1. `tests/integration/chat_stream/test_resilience.py`
  2. `tests/integration/chat_stream/test_real_llm_smoke.py`
  3. `tests/unit/agentic_tool_loop/test_loop_failure_attribution.py`
  4. pytest 原生 `passed / failed / skipped`
- 当前常见输入字段包括：
  1. `case_id`
  2. `feature`
  3. `story`
  4. `blocking`
  5. `non_blocking`
  6. `final_status`
  7. `failure_stage`
  8. `ttfb_ms`
  9. `total_latency_ms`
  10. `event_count`
  11. `done_seen`
  12. `finalize_called`
  13. `save_call_count`
  14. `active_cleaned`
  15. `tool_rounds`
  16. `tool_count`
  17. `retry_count`
  18. `workflow_timeout_count`
- 当前输入边界要明确：
  1. 没有 `quality_gate_case` payload 的测试，仍然可以被纳入 gate 汇总
  2. 但没有 payload 的测试通常只能贡献粗粒度 outcome，不能贡献完整 metrics / stage 信息
  3. 当前不依赖 Langfuse traces 作为 gate truth
  4. 当前不依赖任何联网外部评测系统

## 8.5 Case Record Producer Contract

### 8.5.1 `_publish_quality_gate_case(...)` 职责
- `_publish_quality_gate_case(...)` 是测试侧 producer helper，不是业务逻辑的一部分。
- 它当前负责：
  1. 收集单条测试已经观察到的 route / workflow 信息
  2. 将这些信息写入 `request.node.user_properties`
  3. 以固定键名 `quality_gate_case` 暴露给 pytest hook
- 在当前实现里，它是典型 producer，但不是唯一 producer。

### 8.5.2 `quality_gate_case` payload 字段
- `_publish_quality_gate_case(...)` 负责把 report 与 case 语义组合起来。
- 当前推荐 payload 最小字段包括：
  1. `case_id`
  2. `feature`
  3. `story`
  4. `blocking`
  5. `non_blocking`
  6. `final_status`
  7. `failure_stage`
  8. `reason`
  9. `metrics`
- 当前 `metrics` 内部主要字段包括：
  1. `ttfb_ms`
  2. `total_latency_ms`
  3. `event_count`
  4. `tool_rounds`
  5. `tool_count`
  6. `retry_count`
  7. `workflow_timeout_count`

### 8.5.3 pytest outcome 与 payload 的优先级
- pytest outcome 仍然是执行层事实来源。
- `quality_gate_case` payload 的职责不是覆盖 pytest 结果，而是补充语义和 metrics。
- 当前优先级可以概括为：
  1. `outcome` 决定这条测试在 gate 里的基础通过状态
  2. `payload.final_status` 如果合法，优先用于 workflow 语义；否则回退为 outcome 推断值
  3. `payload.failure_stage` 如果合法，优先用于阶段归因；否则回退为 outcome 推断值
  4. `payload.metrics` 如果存在，优先作为聚合输入；否则只保留粗粒度结果

### 8.5.4 blocking / non_blocking 语义
- `blocking` 表示这条 case 属于第一版 gate 的硬门禁候选。
- `non_blocking` 表示这条 case 会进入报告与对比，但默认不直接参与 blocking 失败。
- 当前默认语义是：
  1. payload 显式给出时，优先采用 payload
  2. `feature == real_llm` 的 case 默认视为 `non_blocking`
  3. 其他测试如果没有明确标记，只能先按 pytest outcome 参与粗粒度汇总

## 8.6 Case Record Normalization

### 8.6.1 feature 归类规则
- 当前 `feature` 归类规则直接来自 `tests/support/quality_gate.py`：
  1. 带 `real_llm` marker 或文件名命中 `test_real_llm_smoke.py` -> `real_llm`
  2. `tests/smoke/*` -> `p2_api`
  3. `tests/integration/chat_stream/*` -> `p2_api`
  4. `tests/unit/agentic_tool_loop/*` -> `agentic_tool_loop`

### 8.6.2 story 归类规则
- 当前 `story` 只接受：
  1. `correctness`
  2. `stability`
  3. `performance`
- payload 中给出且合法时直接采用，否则默认回退为 `correctness`。

### 8.6.3 `final_status` 与 `failure_stage` 归一
- 当前允许的 `final_status` 集合是：
  1. `success`
  2. `degraded`
  3. `failed`
- 若 payload 没给或给了非法值，则按 pytest outcome 归一：
  1. `passed` -> `success`
  2. `failed` -> `failed`
  3. 其他情况 -> `degraded`
- 当前允许的 `failure_stage` 最小集合是：
  1. `none`
  2. `llm_output_parse`
  3. `tool_call_normalize`
  4. `tool_dispatch`
  5. `tool_result_injection`
  6. `context_assembly`
  7. `summary_round`
  8. `finalize`
- 若 payload 没给或给了非法值，则按当前默认回退规则：
  1. pytest `failed` -> `finalize`
  2. 其他情况 -> `none`

### 8.6.4 metrics 归一
- 当前 `metrics` 归一分两层：
  1. 单 case 层：优先读 payload 的 `metrics`
  2. 聚合层：对数值字段做类型归一、过滤 `None`
- 当前实现会额外补齐：
  1. 如果 `metrics` 中缺 `tool_rounds`，但 payload 顶层存在 `rounds`，则回填
  2. 如果 `metrics` 中缺 `tool_count`，但 payload 顶层存在 `tool_call_count`，则回填
- 这一步只负责把 case-level metrics 统一成稳定输入，不直接负责 `pass / warn / fail`。

## 8.7 Gate Evaluation Decision Flow
- Gate evaluation 使用两个列表：
  1. `reasons`
     - 硬失败原因
  2. `warn_reasons`
     - 警告原因
- 最终规则是：

```python
if reasons:
    gate_result = "fail"
elif warn_reasons:
    gate_result = "warn"
else:
    gate_result = "pass"
```

- 当前可以把执行顺序理解成下面这张表：

| Step | 检查内容 | 命中后写入 | 结果影响 |
|---|---|---|---|
| 1 | blocking case outcome 不是 `passed` | `reasons` | `fail` |
| 2 | blocking case 出现 `final_status=failed` | `reasons` | `fail` |
| 3 | blocking case 的 `failure_stage` 是 `finalize` / `tool_dispatch` | `reasons` | `fail` |
| 4 | `pass_rate` 低于 baseline `-5%` | `reasons` | `fail` |
| 5 | `ttfb_p95_ms` / `total_latency_p95_ms` 超过 baseline `+50%` | `reasons` | `fail` |
| 6 | `avg_tool_rounds` 超过 baseline `+2` | `reasons` | `fail` |
| 7 | `ttfb_p95_ms` / `total_latency_p95_ms` 超过 baseline `+25%` | `warn_reasons` | `warn` |
| 8 | `avg_tool_rounds` 超过 baseline `+1` | `warn_reasons` | `warn` |
| 9 | `retry_count` 超过 baseline `+1` | `warn_reasons` | `warn` |
| 10 | `workflow_timeout_count > 0` | `warn_reasons` | `warn` |

### 8.7.1 blocking case 规则
- 当前 blocking case 的基本规则是：
  1. `blocking=True` 且 `non_blocking=False` 的 case 才进入 blocking 集合
  2. 任何 blocking case 的 pytest outcome 不是 `passed`，都会触发 `fail`
  3. 当前还会特别识别 blocking stability failure：
     - `final_status == failed`
     - 或 `failure_stage in {finalize, tool_dispatch}`

### 8.7.2 non-blocking / real_llm 规则
- 当前 `real_llm` 默认走 non-blocking 语义。
- 它的结果仍然会：
  1. 出现在 case 汇总中
  2. 参与报告展示
  3. 参与部分 `warn / fail` 参考
- 但第一版默认不作为 blocking failure 源。

### 8.7.3 判级结果为什么不在聚合阶段决定
- 当前实现故意把这三件事分开：
  1. `metric aggregation`
     - 先算出 current run 的整体指标
  2. `baseline compare`
     - 再和历史健康线比较
  3. `gate evaluation`
     - 最后判断 `pass / warn / fail`
- 这样做的原因是职责清晰。
- 聚合本身不决定通过与否，它只负责生成“这一轮运行的整体表现”。

## 8.8 Metric Taxonomy And Gate Assertions

### 8.8.1 指标选择依据
- 当前指标不是随意添加的，而是来自三类风险：
  1. 主链路正确性风险
     - 例如 SSE 是否收尾、finalize 是否执行、active flag 是否清理
  2. workflow 稳定性风险
     - 例如 tool loop 是否收敛、失败是否可归因、summary round 是否触发
  3. 体验与成本退化风险
     - 例如进程内首 chunk、完整响应耗时、tool rounds、tool count 是否相比 baseline 明显上升；真实网络 TTFB 需要独立 network profile

### 8.8.2 Correctness
- 当前纳入 correctness 的字段包括：
  1. `final_status`
  2. `done_seen`
  3. `finalize_called`
  4. `active_cleaned`
  5. `required_tool`（后续 Golden Cases / 更高层 case 可扩展）
  6. `context_used`（后续可扩展）
  7. `answer_points`（后续可扩展）
- 当前 correctness 更适合硬门禁，因为它直接反映功能正确性和主链路收尾语义。

### 8.8.3 Stability
- 当前纳入 stability 的字段包括：
  1. `failure_stage`
  2. `retry_count`
  3. `workflow_timeout_count`
  4. `unhandled_exception`（更高层 attribution 可扩展）
  5. `max_rounds_exceeded`（后续可扩展）
- 当前 stability 更适合硬门禁，因为它更接近“系统是否可靠结束”，而不是轻微体验退化。

### 8.8.4 Performance
- 当前纳入 performance 的字段包括：
  1. `ttfb_ms`
  2. `total_latency_ms`
  3. `tool_rounds`
  4. `tool_count`
- 当前 performance 适合走 `baseline + tolerance`，而不是死阈值 blocking。
- 原因是这类指标更容易受运行环境、真实模型波动、以及后续 staging 差异影响。

## 8.9 Metric Aggregation

### 8.9.1 什么是 metric aggregation
- `metric aggregation` 指的是将每条 case 上报的指标汇总成本次测试运行的整体指标。
- 它本身不决定 `pass / warn / fail`。
- 它只负责生成 current run 的整体指标，后续再由 baseline compare 和 gate rules 判断是否退化。

### 8.9.2 case-level metrics 到 suite-level metrics
- 当前更严谨的说法是：
  1. 输入集合来自每条“提供了有效数值型字段”的 case
  2. 聚合前会过滤 `None`、`NaN`、`Inf`
  3. 然后再按字段类型做不同聚合
- 对 `ttfb_p95_ms` 和 `total_latency_p95_ms`，当前实现要特别说明：
  1. 它们不是某一条测试 case 的耗时
  2. 它们是纳入 gate 范围内所有有效 case 的聚合指标
  3. `ttfb_p95_ms` 的输入集合来自每条有效 case 的 `metrics.ttfb_ms`
  4. `total_latency_p95_ms` 的输入集合来自每条有效 case 的 `metrics.total_latency_ms`
  5. 当前 percentile 不是简单取最大值，而是按排序后位置做线性插值
  6. 如果只有 1 个有效值，则 p95 直接等于这个值
  7. 最终结果按毫秒保留 2 位小数写入 `agent_quality_report.json`
- 所以当前报告里的 `ttfb_p95_ms=21375.0` 只表示“纳入 gate 的进程内 case 首 chunk 观测值的 95 分位约为 21.375 秒”，不是某一条用例固定等于该值，也不是网络 TTFB 结论。

### 8.9.3 当前聚合字段

| 输出指标 | 输入指标 | 聚合方式 | 含义 |
|---|---|---|---|
| `ttfb_p95_ms` | `ttfb_ms` | p95 | 当前是进程内首 chunk 高位表现；P1 迁移后应在此 profile 改名为 `first_chunk_p95_ms` |
| `total_latency_p95_ms` | `total_latency_ms` | p95 | 完整响应耗时高位表现 |
| `avg_tool_rounds` | `tool_rounds` | 平均值 | 平均 workflow 轮次 |
| `max_tool_rounds` | `tool_rounds` / `max_tool_rounds` | 最大值 | 最坏 case 的轮次深度 |
| `avg_tool_count` | `tool_count` | 平均值 | 平均工具调用次数 |
| `retry_count` | `retry_count` | 求和 | 本次运行总 retry 次数 |
| `workflow_timeout_count` | `workflow_timeout_count` | 求和 | 本次运行总 timeout 次数 |

### 8.9.4 聚合结果如何用于 baseline compare
- 当前职责边界是：
  1. `metric aggregation`
     - 先算当前整体表现
  2. `baseline compare`
     - 再和历史健康线比较
  3. `gate evaluation`
     - 最后判断 `warn / fail`
- 因此 `metric aggregation` 不应该被并入 `Baseline Compare`。

## 8.10 Baseline Compare

### 8.10.1 baseline 是什么
- baseline 不是固定业务阈值，而是某个 profile 下被确认健康的一次测试运行快照。
- 它保存的是当时那次运行的 suite-level 指标，而不是某一条 case 的断言文本。

### 8.10.2 baseline 文件来源
- 当前 baseline 文件路径规则是：
  `tests/baseline/quality_gate/{profile}_main.json`
- 例如：
  1. `tests/baseline/quality_gate/stub_main.json`
  2. `tests/baseline/quality_gate/real_llm_main.json`
- 当前 baseline 内容来自 `_build_baseline_payload(...)`，也就是把本次运行的聚合结果快照写入文件。

### 8.10.3 baseline bootstrap
- 当前 baseline 缺失时，第一版会自动 bootstrap：
  1. 用当前结果写入新的 baseline 文件
  2. 在报告里标记 `baseline_bootstrap=true`
- 这样做的目标是先让 gate 规则落地成可运行系统，而不是把“第一次运行”本身当成失败。

### 8.10.4 baseline update 原则
- baseline 不应在每次运行时自动覆盖。
- 第一版实现只有在 baseline 文件不存在时才自动生成。
- 后续如果要更新 baseline，应当基于“当前结果已被确认是新的健康版本”这个前提显式更新，而不是把每次结果都自动刷新成新的参考线。

### 8.10.5 current vs baseline delta
- 当前报告中的 `regression` 区域主要输出：
  1. `baseline`
  2. `pass_rate_delta`
  3. `latency_delta`
  4. `rounds_delta`
  5. `baseline_bootstrap`
- 其中：
  1. `pass_rate_delta` 是当前 pass_rate 与 baseline pass_rate 的差值
  2. `latency_delta` 是当前 `total_latency_p95_ms` 相对 baseline 的比例变化
  3. `rounds_delta` 是当前 `avg_tool_rounds` 与 baseline 的差值
- 当前宽松容忍规则包括：
  1. `pass_rate` 不低于 baseline `-5%`
  2. `ttfb_p95_ms` 允许 baseline `+25%`
  3. `total_latency_p95_ms` 允许 baseline `+25%`
  4. `avg_tool_rounds` 允许 baseline `+1`
  5. `retry_count` 允许 baseline `+1`
- 第一版故意宽松，是为了先让规则可解释、可复现、可被团队接受，后续再逐步收紧。

## 8.11 Output Artifacts

### 8.11.1 `agent_quality_report.json`
- 这是当前最重要的机器可消费真相源。
- 它主要承载：
  1. suite summary
  2. metrics
  3. regression delta
  4. failure list

### 8.11.2 `agent_quality_summary.md`
- 这是当前的人类可读高信号摘要。
- 它主要展示：
  1. `gate_result`
  2. 关键 metrics
  3. baseline delta
  4. failure case
  5. gate notes

### 8.11.3 pytest terminal summary
- 当前 terminal summary 负责快速回答：
  1. 这次 gate 是 `pass / warn / fail`
  2. 产物文件写到了哪里
  3. baseline 路径是什么
  4. 关键 delta 是多少

### 8.11.4 推荐 JSON 结构
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
    "avg_tool_count": 1.3,
    "retry_count": 1,
    "workflow_timeout_count": 0
  },
  "regression": {
    "baseline": "tests/baseline/quality_gate/stub_main.json",
    "pass_rate_delta": -0.02,
    "latency_delta": 0.12,
    "rounds_delta": 0.3,
    "baseline_bootstrap": false
  },
  "failures": [
    {
      "case_id": "stream_midstream_exception",
      "feature": "p2_api",
      "failure_stage": "tool_dispatch",
      "reason": "stream terminated before done event"
    }
  ]
}
```

## 8.12 Allure Visualization Scope

### 8.12.1 可视化字段
- 当前 Allure 只作为展示层承载，不重新定义 gate 规则。
- 当前最小映射包括：
  1. `epic = Agent Workflow Quality Gate`
  2. `feature = p2_api / agentic_tool_loop / real_llm`
  3. `story = correctness / stability / performance`

### 8.12.2 附件展示
- 当前 Allure 优先挂这两类附件：
  1. `agent_quality_report.json`
  2. `agent_quality_summary.md`
- 它解决的是“怎么看结果”，不是“怎么定规则”。

### 8.12.3 非目标
- 当前明确不是：
  1. 自定义 Web UI
  2. baseline 存储中心
  3. Langfuse gate truth
  4. 在 Allure 中重新实现 scoring logic

## 8.13 Test Plan / Acceptance Criteria

### 8.13.1 schema 验收
- 需要验证：
  1. report JSON 顶层字段齐全
  2. `gate_result` 枚举合法
  3. `summary / metrics / regression / failures` 结构稳定

### 8.13.2 判级规则验收
- 需要验证：
  1. blocking correctness 失败时一定 `fail`
  2. blocking stability 失败时一定 `fail`
  3. 仅 performance 轻微退化时为 `warn`
  4. 无退化时为 `pass`

### 8.13.3 baseline compare 验收
- 需要验证：
  1. baseline 缺失时能自动 bootstrap
  2. `latency_delta / rounds_delta / pass_rate_delta` 计算稳定
  3. profile 间 baseline 不混用

### 8.13.4 Allure 展示验收
- 需要验证：
  1. 能看到 suite 汇总
  2. 能看到 case 状态
  3. 能查看 JSON / Markdown 附件
  4. 第一版不要求复杂 trend 图

## 8.14 当前边界与非目标
- 当前实现是“本地可执行的 gate summary + baseline compare + optional Allure 展示”。
- 当前还不是：
  1. 完整 PR 强阻塞系统
  2. 多环境统一评测平台
  3. Golden Cases regression 平台
  4. Langfuse 替代品
- 当前边界也包括：
  1. `real_llm` 第一版默认 non-blocking
  2. performance 第一版默认宽松
  3. 没有 payload 的普通测试仍然只贡献粗粒度 outcome
  4. 进程内字段当前仍名为 `ttfb_ms`，但语义只是 `first_chunk_ms`；字段迁移和 baseline 校准尚未完成
  5. 2026-08-01 的 Stream resilience 诊断运行没有功能用例失败，但因 latency baseline severe regression 得到 `gate_result=fail`；该结果不能表述为 P1 SSE 契约失败或 PR Gate 已生效

## 8.15 后续扩展
- 后续可以继续扩：
  1. 把更多测试层纳入 producer contract
  2. 扩展 correctness 语义，如 `required_tool / context_used / answer_points`
  3. 引入更细粒度的 failure attribution
  4. 在 CI 中把 `gate_result` 变成真正的准入规则
  5. 等 baseline 稳定后逐步收紧 performance tolerance
