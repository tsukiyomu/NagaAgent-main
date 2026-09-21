# P3-4 Agent Workflow PR Regression — Implementation Walkthrough

## 学习目标与源码范围

这份讲解回答：P3-2 的 Loop 契约和现有 Golden Cases 怎样从本地测试变成独立的 PR Check；一次 pytest 结果怎样同时进入 Quality、JUnit 和 Allure；失败后为什么还能留下可下载证据。执行结果与验收状态以 [P3-4 Journal](../execution/final-plan/p3-4-execution-journal.md) 为准，本文专注实现链路。

- 工作单元：[Final Plan / P3-4](../../plans/nagaagent-final-testing-plan.md#p3-4建立-agent-workflow-non-blocking-ci-与-quality-artifact)。
- 仓库与版本：`tsukiyomu/NagaAgent-main`，基点 `8057510b`，讲解的最终源码为 `codex/p3-4-agent-workflow-regression@842fd976`。下文行号按这个提交核对；当前相关源码文件没有未提交改动。
- 提交边界：`06b27f98` 增加 workflow、Quality/Golden 接线和 25-case baseline；`ffbf0130` 临时改错一条断言做红灯；`1fab4ab5` 让非阻断 case 的失败至少显示 Quality `warn`；`842fd976` 恢复正确断言。首次提交还收纳了先前 P3-2 工作树里的 Loop 去重代码与目标测试；那是本 Check 所验证的**前置产品契约**，不是 P3-4 新设计的去重算法。需要深入去重时先看[目标测试](../../../../tests/unit/agentic_tool_loop/test_loop_message_injection.py#L334)与 [`run_agentic_loop`](../../../../apiserver/agentic_tool_loop.py#L1391)。
- 可观察证据：[Draft PR #3](https://github.com/tsukiyomu/NagaAgent-main/pull/3) 的[初始绿灯](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35592650072)、[受控红灯](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613331550)、[恢复绿灯](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613699256)。本文只读取已有源码和 Artifact，没有重新执行测试或改变 Gate。

## 学习地图

| 按因果顺序读 | 核心问题 | 源码入口 |
|---|---|---|
| [1. 选什么、何时跑](#1-独立-pr-check-先限定执行边界) | PR 到来时为何只跑 20+5，且不拉进真实服务？ | [workflow](../../../../.github/workflows/pr-agent-workflow-regression.yml#L1) |
| [2. 测试结果从哪里来](#2-golden-把真实-loop-的受控运行报告交给-pytest) | Golden 的业务终态与 pytest 通过/失败为何是两种信息？ | [Golden 测试](../../../../tests/golden_cases/test_agent_workflow_golden_cases.py#L23)、[runner](../../../../tests/support/golden_cases.py#L422) |
| [3. 结果怎样汇总](#3-pytest-hook-将-case-转为可追溯的-quality-记录) | nodeid、case ID、失败阶段和来源如何写入 JSON？ | [pytest hook](../../../../tests/conftest.py#L112)、[Quality producer](../../../../tests/support/quality_gate.py#L245) |
| [4. baseline 与判定](#4-baseline-比较不接管-pytest-退出码) | 24/25 为何是 `warn`，但 CI 仍红？ | [baseline](../../../../tests/baseline/quality_gate/agent_workflow/stub_main.json)、[`_evaluate_gate`](../../../../tests/support/quality_gate.py#L396) |
| [5. 失败后的证据](#5-pytest-失败后仍生成-html-并上传-artifact) | 退出码 1 怎样与可下载的 HTML/JUnit/Quality 同时存在？ | [workflow](../../../../.github/workflows/pr-agent-workflow-regression.yml#L58) |
| [6. 断言与边界](#6-测试与真实-pr-run-分别证明了什么) | 单测和三次 PR run 各自证明什么、没证明什么？ | [Quality 单测](../../../../tests/unit/test_quality_gate_summary.py#L233)、[P3-4 Journal](../execution/final-plan/p3-4-execution-journal.md) |

先看整条数据流，后面每节沿此顺序展开：

```text
PR event → 独立 workflow → 20 条 Loop unit + 5 条 Golden stub
                                ├─ pytest/JUnit：断言与退出码
                                ├─ pytest hook → Quality cases → baseline/delta → JSON/MD
                                └─ allure-pytest → allure-results → Allure CLI → HTML
                  以上产物 + pytest-status → run/attempt 唯一的 Artifact
```

## 1. 独立 PR Check 先限定执行边界

新建的 [`pr-agent-workflow-regression.yml`](../../../../.github/workflows/pr-agent-workflow-regression.yml#L1) 定义单独的 `Agent Workflow Regression` job。它在目标分支为 `main`、`master` 或 `codex/upstream-langfuse-sync` 的 `pull_request` 上运行，也支持手动触发；没有改 Smoke/Stream workflow，也没有 `push` 触发。PR #3 以迁移分支为 base，因此确实走到了这条 `pull_request` 路径。

工作流把真实模型和 Langfuse LAN 测试开关设为 `0`，关闭 pytest 插件自动加载，并从 frozen test group 安装依赖。核心选择在 [workflow 第 63～71 行](../../../../.github/workflows/pr-agent-workflow-regression.yml#L63)：

```yaml
uv run --frozen python -m pytest \
  -p pytest_asyncio.plugin -p allure_pytest.plugin \
  tests/unit/agentic_tool_loop tests/golden_cases \
  -m "not real_llm" -q \
  --quality-gate --quality-gate-profile stub \
  --quality-gate-baseline-dir=tests/baseline/quality_gate/agent_workflow \
  --quality-gate-artifacts-dir="$EVIDENCE_DIR/quality" \
  --junitxml="$EVIDENCE_DIR/junit-agent-workflow.xml" \
  --alluredir="$EVIDENCE_DIR/allure-results"
```

`-p` 显式加载 asyncio 和 Allure 适配器，是因为自动加载已关闭；`--alluredir` 采集原始结果，而 HTML 要在后续用 CLI 单独生成。`--quality-gate` 启用仓库自己的 pytest hook，`--quality-gate-profile stub` 选择离线比较基线。`EVIDENCE_DIR` 带 `github.run_id` 和 `github.run_attempt`，不同运行/重试不会混写结果。

这组路径选择实际产生 20 条 Loop unit + 5 条 Golden。Loop unit 执行真实 `run_agentic_loop` 状态机，但 LLM、dispatcher、queue/compression 等依测试受控；Golden runner 也调用真实 Loop，却提供脚本化 LLM 和工具结果。它不是 `/chat/stream` route、真实 provider、Memory 或外部工具的集成测试。P3-2 的重复 ID 测试现在是 20 条之一：第三轮 history、dispatch 次数和 SSE 结果各有断言，见[目标测试第 334～419 行](../../../../tests/unit/agentic_tool_loop/test_loop_message_injection.py#L334)。P3-4 做的是把这项既有契约纳入 PR 回归，不在此处重讲 Loop 的去重实现。

这里有两个不同的“非阻断”：workflow 目前没有被设置为 GitHub Required Check，所以不是平台层的合并强制门禁；但**在此 workflow 内**，任何被选中的 pytest 断言失败仍会让 job 失败。别把 `NON_BLOCKING` 误读为“测试失败也返回绿色”。

## 2. Golden 把真实 Loop 的受控运行报告交给 pytest

原有 [Golden runner](../../../../tests/support/golden_cases.py#L422) 会校验 case schema，准备消息、脚本化 LLM、受控工具响应和空 queue，然后调用真实 `run_agentic_loop(...)`。它从收集到的 SSE 与 dispatch 结果构造 `GoldenCaseRunReport`，包括 `final_status`、`failure_stage`、`rounds` 和 `tool_call_count`。这些值来自本次 stub 执行，不是 CI 后处理凭空猜的。

P3-4 在 [Golden 测试第 23～39 行](../../../../tests/golden_cases/test_agent_workflow_golden_cases.py#L23) 加入 `request`，在断言预期前把运行报告塞进 pytest 的 `user_properties`：

```python
report = await run_stub_golden_case(case, monkeypatch)
request.node.user_properties.append(
    (
        "quality_gate_case",
        {
            "case_id": case.case_id,
            "feature": "golden_cases",
            "final_status": report.final_status,
            "failure_stage": report.failure_stage,
            "rounds": report.rounds,
            "tool_call_count": report.tool_call_count,
        },
    )
)
result = assert_golden_case_report(case, report)
```

放在断言之前很重要：即便 Golden 的预期检查失败，pytest report 仍能携带已得到的 runtime 信息。`final_status` 描述的是 runner 观察到的执行终态，`outcome` 描述的是 pytest 对**预期契约**的判断；两者不能互相代替。例如受控 Loop 成功结束但没有调用 case 要求的工具时，runtime 可以报 `success`，pytest 仍可因 Golden 断言失败。这是依据代码说明的可能情形，不是声称本次 PR 发生了这类故障。

真实恢复绿灯 ZIP 中的 `gc_history_continue_001` 可核对这条路径：`case_id` 是场景名、`feature=golden_cases`，`outcome=passed`，`final_status=success`/`failure_stage=none`，两者的 source 都是 `case_report`；`tool_rounds=1`、`tool_count=0`。这证明报告使用了 Golden 自己的值，但不证明生产环境中会出现相同轮数或结果。

## 3. pytest hook 将 case 转为可追溯的 Quality 记录

仅把属性附到测试节点还不够，报告生产者必须认得它。P3-4 在 [`infer_feature`](../../../../tests/support/quality_gate.py#L53) 中加入 `tests/golden_cases/ → golden_cases`；否则这些 nodeid 会被 `should_include_for_gate` 排除。相邻的 [`tests/conftest.py`](../../../../tests/conftest.py#L161) 也允许 Golden 获得 Allure hierarchy label。

原有 [`pytest_runtest_makereport`](../../../../tests/conftest.py#L112) hook 在启用 Quality 时读取 pytest 的 `nodeid`、`when/outcome`、`duration`、markers、`user_properties` 和失败长文本，并按 nodeid 保存一条最终记录。call 阶段还能生成随测试推进的 Quality snapshot；最终 [`pytest_terminal_summary`](../../../../tests/conftest.py#L179) 再用完整记录写报告。P3-4 主要扩充的是这条既有汇总链的 Golden 识别与输出字段，不是重新实现 pytest 收集器。

[`_build_case_record`](../../../../tests/support/quality_gate.py#L245) 把一条原始 pytest 记录变成可查询的 case：

```python
"final_status": _normalize_final_status(reported_final_status, outcome),
"final_status_source": "case_report" if has_final_status else "pytest_outcome",
"failure_stage": _normalize_failure_stage(reported_failure_stage, outcome),
"failure_stage_source": "case_report" if has_failure_stage else "fallback",
"reason": str(payload.get("reason") or record.get("failure_reason") or ""),
```

如果 Golden 提供合法值，就保持原报告并写 `case_report` 来源；如果普通 unit 没有上报这些字段，才根据 pytest outcome 回退推断状态。P3-4 把“没有 runtime 阶段信息的失败”的默认阶段由 `finalize` 改成 [`unknown`](../../../../tests/support/quality_gate.py#L128)。这样只能说“测试失败了，产品阶段未知”，不能假装知道是 finalize 出错。失败原因则优先取 case payload，否则取 pytest 的失败文本。

新增的 `cases` 数组与 Markdown case 表，让所有 25 条都可以按 case ID、pytest outcome、终态和阶段阅读；`failures` 还带 nodeid、outcome、final_status、stage、reason，见 [`_build_failures`](../../../../tests/support/quality_gate.py#L298) 与[报告组装](../../../../tests/support/quality_gate.py#L608)。此前 JSON 只有聚合结果，难以从一个 delta 追到具体失败 case。

受控红灯 ZIP 给出一个反例：`test_duplicate_tool_call_id_is_deduplicated_across_rounds` 的 `outcome=failed`、`final_status=failed`，但 `final_status_source=pytest_outcome`、`failure_stage=unknown`、`failure_stage_source=fallback`；reason 指向测试第 394 行的 `AssertionError`。它精确说明断言失败，**不**声称真实 Loop 的 `finalize` 或 `tool_dispatch` 出错。

## 4. baseline 比较不接管 pytest 退出码

旧 Quality baseline 的 32 条范围与本工作流的 25 条不是同一个 selection，直接比较通过率没有意义。P3-4 新增 [`agent_workflow/stub_main.json`](../../../../tests/baseline/quality_gate/agent_workflow/stub_main.json)，其中 `case_count=25`、`pass_rate=1.0`、`avg_rounds=1.6`，并用 `--quality-gate-baseline-dir` 指向该目录。最终报告额外写出 `baseline_version` 和 `baseline_case_count`，方便读者知道正在与哪份基线比较。

[`_base_scorecard`](../../../../tests/support/quality_gate.py#L318) 用 passed/failed case 计算 `pass_rate`；[`_evaluate_gate`](../../../../tests/support/quality_gate.py#L396) 与基线相减。受控红灯时，一条失败导致 `24/25 = 0.96`，所以 `pass_rate_delta = 0.96 - 1.00 = -0.04`。原有的严重回退条件是“低于 baseline 5 个百分点”，这次 4 个百分点不会触发它。P3-4 后续补了独立的可见性规则：

```python
non_blocking_failures = [
    c for c in cases if not (c["blocking"] and not c["non_blocking"]) and c["outcome"] == "failed"
]
if non_blocking_failures:
    warn_reasons.append(f"non-blocking cases failed: {len(non_blocking_failures)}")
```

因此同一红灯同时满足：Quality 24/25、`gate_result=warn`；pytest 退出码 1；GitHub Check 为 failure。原因是 25 条测试没有 `blocking` marker，Quality 把该失败记为 advisory warning；workflow 并没有把 Quality 结果映射为 shell 退出码，而是原样 `exit "$test_exit_code"`。这里的 case-level `blocking`、Quality `warn/fail` 和 GitHub Required status 是三套不同语义。证据流水线本身（HTML 生成、文件核验等）失败也可能让 job 失败，不能把“Quality 不改退出码”理解成“只有 pytest 可能令 job 失败”。

新 baseline 记录的是汇总指标和 `case_count`，**没有**保存并逐项校验 25 个 nodeid；路径选择由 workflow 决定，case count 是元数据，不是 selection identity 锁。`ttfb_p95_ms` 和 `total_latency_p95_ms` 在该受控基线里是 0，最终 `latency_delta=null`，不能拿它讲性能提升或 SLO。`avg_rounds=1.6` 也只对报告了 rounds 的受控 case 有解释力。这里的可迁移原则是：先固定同一 profile/selection 的可诊断基线，再讨论数值趋势；若要治理未来 case 漂移，需要额外的 nodeid manifest 或显式 baseline 更新策略，本次没有实现。

## 5. pytest 失败后仍生成 HTML 并上传 Artifact

[workflow 第 58～100 行](../../../../.github/workflows/pr-agent-workflow-regression.yml#L58) 把“测试是否通过”和“失败证据是否保存”拆开。pytest 先把退出码写入 `pytest-status.txt`，然后按原码退出：

```bash
test_exit_code=$?
printf 'pytest_exit_code=%s\n' "$test_exit_code" > "$EVIDENCE_DIR/pytest-status.txt"
exit "$test_exit_code"
```

后续 Allure HTML、文件核验和上传步骤都有 `if: always()`。HTML 步骤先确认原始 `*-result.json` 存在，运行 `allure generate`，再检查 `allure-report/index.html`；文件核验检查 pytest status、JUnit、Quality JSON/MD 和 HTML。上传使用 `if-no-files-found: error`。这些检查防止把“只创建了空目录”误报为已生成报告；若 CLI 或结果不可用，步骤会显示失败，而不是拿旧 HTML 顶替。

`allure-pytest` 与 CLI 是两个环节：适配器在 pytest 时生成 `allure-results`，CLI 在之后转换成 HTML。workflow 先检查两个工具，缺 CLI 时尝试安装 2.34.1；即使安装失败也继续让 pytest 运行，以便保留可获得的原始结果，但 HTML/核验会按实际情况失败。Quality JSON/MD 是仓库自己的报告，[`_maybe_attach_allure_files`](../../../../tests/support/quality_gate.py#L551) 还会尽力把它们附到 Allure；Artifact 同时直接保存独立的文件，因此不必依赖在 HTML 中找附件才能读取最终 Quality 数据。

一条实际执行路径是受控红灯 run `35613331550`：临时把[目标测试第 394 行](../../../../tests/unit/agentic_tool_loop/test_loop_message_injection.py#L394) 的正确断言 `dispatch_batches == 1` 改成要求 `2`，真实值仍为 `1`。pytest exit 1，JUnit 留下 `assert 1 == 2`；Allure HTML、必需文件核验和 Artifact 上传仍 success。随后 `842fd976` 恢复断言，run `35613699256` 的 pytest exit 0、JUnit 为 25 tests / 0 failures / 0 errors / 0 skipped。故障注入只为了验证红灯与产物链，不是产品缺陷；最终 HEAD 已恢复。

## 6. 测试与真实 PR run 分别证明了什么

新增的 [`test_quality_gate_summary.py`](../../../../tests/unit/test_quality_gate_summary.py#L233) 用合成 pytest record 检查三个容易出错的映射：Golden 节点被纳入、case 上报的 `degraded/tool_dispatch` 被保留；缺 runtime 阶段的 unit failure 变成 `unknown/fallback` 并带 pytest reason；25 条里失败 1 条且基线容差未触发时仍为 `warn`、delta `-0.04`。它证明 producer 逻辑的预期，不等于 GitHub 真跑过。

真正的 PR run 则证明接线和证据传递：[初始绿灯](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35592650072) 25/25；[红灯](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613331550) 24/25，HTML/上传成功；[恢复绿灯](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613699256) 25/25。三份 Artifact 已下载验 SHA-256。最终恢复绿 ZIP 内含 25 个 Allure result、HTML 入口、JUnit、Quality JSON/MD 与 `pytest-status.txt`；红灯 ZIP 是追查 24/25 的具体样本。ZIP 属于 Actions 运行产物（14 天保留），本地副本不提交源码；精确 run ID、digest、环境和本地命令仍以 [Journal](../execution/final-plan/p3-4-execution-journal.md) 为事实来源。

这组证据支持“离线 deterministic Agent workflow 回归在真实 PR 上会发出独立反馈，失败后仍有证据可查”。它不支持“真实 LLM/MCP/Memory 已通过”“Quality 数值代表回答质量”“性能已达标”或“此 Check 已经 Required”。PR 仍是 Draft，历史上保留故意红灯提交；本讲解只解释实现，不授权合并或改变平台规则。

## 继续阅读

想沿单个 case 追踪时，先看 [Golden 测试](../../../../tests/golden_cases/test_agent_workflow_golden_cases.py#L23) 怎样提交 `quality_gate_case`，再看 [hook](../../../../tests/conftest.py#L112) 和 [`_build_case_record`](../../../../tests/support/quality_gate.py#L245)，最后到[恢复绿 run](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613699256) 的 Artifact 查看 `quality/agent_quality_report.json`。想看负向路径，就从[红灯 run](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613331550) 的同一 case ID 追到 JUnit 断言与 [workflow 的 `if: always()`](../../../../.github/workflows/pr-agent-workflow-regression.yml#L77)。Loop 去重本身看 [P3-2 目标测试](../../../../tests/unit/agentic_tool_loop/test_loop_message_injection.py#L334)，不要把它与本单元的 CI 接线混为一谈。
