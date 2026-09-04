# Testing Reports And Allure Results

本目录只解释测试结果在哪里生成、如何读取，以及哪些结果可以作为证据；不保存手工维护的“假运行结果”。

## 结果位置

| 输出 | 位置 | 类型 | 是否手工编辑 |
|---|---|---|---|
| Allure raw results | [`allure-results/`](../../../allure-results/) | pytest/Allure 运行生成的 JSON、TXT 和附件 | 否 |
| Quality Gate JSON | [`tests/artifacts/quality_gate/agent_quality_report.json`](../../../tests/artifacts/quality_gate/agent_quality_report.json) | 机器可读聚合结果 | 否 |
| Quality Gate Markdown | [`tests/artifacts/quality_gate/agent_quality_summary.md`](../../../tests/artifacts/quality_gate/agent_quality_summary.md) | 人类可读摘要 | 否 |
| Closed Loop V1 JUnit | [`tests/artifacts/closed_loop_v1/`](../../../tests/artifacts/closed_loop_v1/) | Smoke / Stream Contract testcase、failure 和 error 执行结果 | 否 |
| Quality Gate baseline | [`tests/baseline/quality_gate/`](../../../tests/baseline/quality_gate/) | 人工评审后维护的比较基线 | 仅经评审更新 |

## 设计与计划文档

- [Quality Gate Summary 契约](../architecture/part-08-quality-gate-summary.md)
- [Allure 与 Quality Reporting 暂停计划](../plans/suspend/allure-quality-reporting.md)
- [Langfuse Observability 边界](../architecture/langfuse-observability.md)

## 执行记录

- [2026-09-03：Final Testing Plan 价值与决策分析](final-testing-plan-analyze.md) — `DONE / TEACH_BACK_PENDING`；解释 P3-0～P3-9 的证据依据、工程价值、简历价值、建议完成线与不可夸大边界，不代表任何 P3 实施单元已完成。
- [2026-07-28：P0 干净环境验收](p0-clean-environment-run-2026-07-28.md) — `VERIFIED`（用户于 2026-08-01 临时确认）；仅适用于记录中的执行快照，当前 revision 变化后仍需重跑。
- [2026-08-20～31：C0-3 最小 Artifact 闭环](closed-loop-v1-c0-3-2026-08-20.md) — `DONE`；success/failure JUnit、远端 upload/download、digest 和 nodeid 归因已验证。
- [2026-08-31：C0-4 稳定性与真实负向检测](closed-loop-v1-c0-4-2026-08-31.md) — `DONE`；`3x green -> intentional red -> failure Artifact -> restored green` 可追溯，Stream Gate 仍为 `NON_BLOCKING`。
- [2026-09-01：C0-5 Traceability / Gate Record](closed-loop-v1-c0-5-2026-09-01.md) — `DONE`；从 SSE 风险连接到两条 nodeid、断言、dependency profile、revision、CI run、JUnit Artifact、failure classification、恢复证据和当前 `NON_BLOCKING` 决定；同一事实已同步到 architecture 的 overview / Part 2 / CI owner 文档，Required 人类决定仍属于 C0-6。

## 使用边界

- `allure-results/` 是原始运行产物，不是长期知识文档，也不应与 Part 详细说明混放。
- Allure 负责展示，不重新定义 pass/warn/fail 规则。
- pytest assertion 是确定性事实来源；Quality Gate 负责聚合和判级。
- Langfuse trace 是诊断证据，不自动成为 PR Blocking 真相源。
- 报告文件存在不代表当前 revision 已通过；必须同时保留命令、revision、环境、退出码和时间。

## 版本控制边界

- `allure-results/`、`allure-report/`、`tests/artifacts/quality_gate/` 和 `tests/artifacts/closed_loop_v1/` 是运行时生成目录，由 `.gitignore` 排除，不作为源码提交。
- `tests/baseline/quality_gate/` 是人工评审后维护的健康基线，继续纳入版本控制；测试运行不得无审查地覆盖或晋升 baseline。
- Smoke 与 Stream Contract workflow 已配置独立 JUnit Artifact，使用 suite/run/attempt 唯一名称并保留 14 天；本地 success/failure 报告内容已验证，commit `533d4a3...` 的两个远端 success run 已验证 upload step、artifact ID/digest 和 expiry。2026-08-31 的 Stream failure run `33392294451` 已进一步证明 pytest 失败后 `if: always()` upload 成功；下载 ZIP 的 digest 与 GitHub metadata 一致，内部 JUnit 可定位 nodeid、assertion、run 和 revision。恢复 run `33392789083` 重新绿色，C0-3 与 C0-4 均已关闭。证据 PR #2 保持 Draft，不应按普通 merge 进入 `main`。
