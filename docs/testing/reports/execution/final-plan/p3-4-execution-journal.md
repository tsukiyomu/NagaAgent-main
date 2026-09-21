# P3-4 Agent Workflow Non-blocking CI — Execution journal

**Context:** Final Plan 已用 P3-2 关闭一个真实 loop 契约缺口；本单元将其与现有五条 Golden Cases 接入可诊断的真实 PR 回归。

**Plan / task:** [Final Testing Plan / P3-4](../../../plans/nagaagent-final-testing-plan.md#p3-4建立-agent-workflow-non-blocking-ci-与-quality-artifact)，run `P3-4-2026-09-21`。

**Status:** `DONE`。独立 PR Check 的初始绿色、可控红灯、恢复绿色及各自可下载 Artifact 已验证；Required 晋升不在本单元授权内。

本记录与下方 study 文档单独同步到 P3-4 Draft PR；工作区内 Final Plan / Current Progress 及其他报告目录迁移尚未随本次文档提交，因此远端总表的旧状态不是本工作单元的最新验收结论。

## Result and plan alignment

[Draft PR #3](https://github.com/tsukiyomu/NagaAgent-main/pull/3) 以
`codex/upstream-langfuse-sync@8057510b` 为 base、`codex/p3-4-agent-workflow-regression` 为 head。
新增独立 [workflow](../../../../../.github/workflows/pr-agent-workflow-regression.yml)，在 PR 中运行
20 条 Tool Loop 和 5 条 stub Golden Cases，输出 JUnit、逐 case Quality JSON/Markdown、Allure results/HTML
及 pytest 退出码到 run/attempt 唯一的 Artifact。未修改 Smoke/Stream、Branch Protection 或 Required Check。
PR 历史包含有意红灯提交 `ffbf0130`，当前 HEAD 的断言已由 `842fd976` 恢复并在真实 PR run 通过；此 Draft PR 不自动合并。

**Compared with plan:** 实现范围对齐。由于原 [Quality producer](../../../../../tests/support/quality_gate.py)
未包含 Golden nodeid、JSON 不列逐 case 状态，而且任意未知失败被默认归因到 `finalize`，本单元补齐
Golden 纳入与状态来源标记；真实红灯发现非阻断失败在 5% baseline 容差内仍显示 `gate_result=pass`，
于是将该诊断结果调整为 `warn`。这些不改变 pytest 的 Check 成败判定。

## Key Engineering Decisions

1. **独立 Check、两套判定各司其职。** 已有 Smoke/Stream workflow 只上传 JUnit，Quality producer 在 pytest
   terminal summary 中落盘且不改退出码。Agent 回归另开 workflow，固定 20+5 的离线 selection，pytest assertion
   决定 job；Quality 只诊断。绿色→红色→恢复绿色 run 证明二者分离，仍不证明 Required enforcement。
2. **按同一 selection 比 baseline，并标出证据来源。** 原 `stub_main.json` 的 32-case 历史范围不能与 25-case
   PR 集合直接比较；新 baseline 固定 25 条。Golden 上报真实 stub report 的终态和阶段，其余 unit 缺上报时
   `final_status_source=pytest_outcome`，未知失败阶段为 `unknown`。红灯 ZIP 给出 case、阶段来源和
   `pass_rate_delta=-0.04`；延迟 0/`None` 不视为性能测量。
3. **失败后继续证据流水线。** workflow 的 HTML 生成、必需文件校验和 Artifact 上传均为 `if: always()`；
   故意断言不匹配时 pytest exit 1、job failure，而 HTML 与上传仍 success，失败 ZIP 已下载验 hash。

## Evidence and proof limits

执行环境：本地 Windows / Python 3.11.7 / pytest 9.1.1 / uv 0.9.24 / `allure-pytest` 2.16.0
（lock）/ Allure CLI 2.34.1；GitHub runner 为 `ubuntu-latest`、Python 3.11、frozen test group，
`NAGA_ENABLE_REAL_LLM_TESTS=0`、`NAGA_ENABLE_LANGFUSE_LAN_TESTS=0`、
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，显式加载 asyncio 与 Allure 插件。真实 LLM、route、外部工具、
remote memory 和部署都不在本次 selection。

| Acceptance claim | Evidence and context | Observed result | Proof boundary |
|---|---|---|---|
| 固定 selection 与 baseline | 本地 `tests/artifacts/allure/p3-4-20260921-local-restored-1/quality/agent_quality_report.json`（不提交）、[baseline](../../../../../tests/baseline/quality_gate/agent_workflow/stub_main.json) | 本地恢复后 25 passed、exit 0；Quality 25/25、pass-rate delta 0、rounds delta 0；Allure HTML 已生成 | 本地额外未跟踪探针以 `--ignore` 排除，以匹配 PR 的 20+5；延迟 delta 为 `None` |
| Quality producer 契约 | `tests/unit/test_quality_gate_summary.py` | 8 passed、exit 0；Allure HTML 生成成功 | synthetic records 验证 Golden 纳入、失败来源与 warn，不等于真实 PR 执行 |
| 真实 PR 初始绿灯 | [run `35592650072`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35592650072)，`06b27f98` / artifact `10635151858` | `pull_request`、Check success；pytest exit 0，Quality 25/25；HTML、校验、上传 success；ZIP 1,250,692 B，SHA-256 `d3f93f12a36e02d1d7d24807e1a3a774e2369098314b712060664cdc0f84c107`，下载一致 | 证明独立成功 Check 与下载，不代表长期稳定或 Required |
| 真实 PR 可控红灯 | [run `35613331550`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613331550)，`1fab4ab5` / artifact `10645277612` | 故意把 dispatch 次数断言改为 2；pytest exit 1、Check failure；Quality 24/25、`warn`、delta -0.04；HTML、校验、上传 success；ZIP 1,259,133 B，SHA-256 `4428e09c749b058c07a695504ef357913c316289d081217998399f6838711273`，下载一致 | JUnit 能见 `assert 1 == 2`；Quality 未上报 runtime 阶段，诚实标 `unknown`；并非产品缺陷 |
| 恢复最终 HEAD | [run `35613699256`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613699256)，`842fd976` / artifact `10644993899` | `pull_request`、Check success；pytest exit 0，JUnit `25/0/0/0`；Quality 25/25、`pass`、pass-rate/rounds delta 0、latency delta `null`；HTML、校验、上传 success；ZIP 1,250,317 B，SHA-256 `db0f9174426836498d49beeaa5f5c3c43d26f2827989fe70c5d178190c7e8d1d`，下载一致 | 证明当前 HEAD 的 25 条离线 PR selection，非 Required、真实模型/外部工具、长期稳定性或延迟基准 |

本地等价命令（未跟踪探针仅在本地排除；CI 原样选择整个目录）:

```text
.venv\Scripts\python.exe -m pytest tests/unit/agentic_tool_loop tests/golden_cases --ignore=tests/unit/agentic_tool_loop/test_live_duplicate_probe_harness.py -q --quality-gate --quality-gate-profile stub --quality-gate-baseline-dir=tests/baseline/quality_gate/agent_workflow --quality-gate-artifacts-dir=tests/artifacts/allure/p3-4-20260921-local-restored-1/quality --junitxml=tests/artifacts/allure/p3-4-20260921-local-restored-1/junit-agent-workflow.xml --alluredir=tests/artifacts/allure/p3-4-20260921-local-restored-1/allure-results
allure generate tests/artifacts/allure/p3-4-20260921-local-restored-1/allure-results -o tests/artifacts/allure/p3-4-20260921-local-restored-1/allure-report
```

本地 Allure results 位于 `tests/artifacts/allure/p3-4-20260921-local-restored-1/allure-results/`；
HTML 入口位于同级 `allure-report/index.html`，生成命令 exit 0。单测 HTML 位于
`tests/artifacts/allure/p3-4-20260921-quality-unit-2/allure-report/index.html`；
红灯单用例 exit 1 后也在 `tests/artifacts/allure/p3-4-20260921-local-red-1/allure-report/index.html`
生成报告。这些是本地测试产物，不提交到 GitHub 源码树。
最初两个本地预检分别因重复注册插件（exit 1）和 Windows cmd 对带空格 marker 的引号处理（exit 4）
未执行有效测试；对应 `local-baseline-1/-2` 没有有效 Allure results/HTML，未用于验收。

远端[初始绿色 run](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35592650072)、
[可控红灯 run](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613331550) 和
[恢复绿色 run](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/35613699256) 的 ZIP
均已下载到本地 `tests/artifacts/allure/` 验 hash；后者内含
`allure-results/` 的 25 个结果、`allure-report/index.html`、`junit-agent-workflow.xml`、
`quality/agent_quality_report.json`、`quality/agent_quality_summary.md` 和 `pytest-status.txt`；
Artifact 元数据 digest 与下载文件 SHA-256 相同。红灯 Artifact 也包含失败后的 HTML，
其 Quality `warn` 是诊断，不能覆盖 pytest exit 1。

## Next step

保留 Draft PR 供 Owner review；若要晋升 Required，先另行积累稳定 PR run、审查分支规则与真实依赖边界，
由 Owner 明确决定。本次不合并、不修改规则，也不自动启动已暂停/条件单元。
