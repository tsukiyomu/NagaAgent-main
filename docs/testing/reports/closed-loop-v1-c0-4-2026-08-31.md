# Closed Loop V1 C0-4 CI/CD 执行结果说明书

## 1. 执行概览

| 字段 | 内容 |
|---|---|
| 项目 | `tsukiyomu/NagaAgent-main` |
| 工作单元 | `C0-4 — 验证重复稳定性和负向阻断` |
| 分支 | `codex/c0-4-intentional-red` |
| Draft PR | [#2 — test: verify C0-4 stream gate failure evidence](https://github.com/tsukiyomu/NagaAgent-main/pull/2) |
| CI 平台 | GitHub Actions / `ubuntu-latest` / Python 3.11 |
| 本地环境 | Windows / Python 3.11.7 / uv 0.9.24；首次稳定性执行使用独立 frozen test venv |
| 工作流 | `.github/workflows/pr-stream-contract-gate.yml` |
| Check | `PR Stream Contract Gate / Stream Contract Gate` |
| 总体结果 | `PASS`：`3x green -> intentional red -> failure Artifact -> restored green` 全部可追溯 |
| Gate 状态 | `NON_BLOCKING`：证明 Check 会失败，不证明 GitHub 已禁止 PR 合并 |

### 1.1 目标

证明 Stream Contract Gate 不是“一次碰巧绿色”，并验证以下闭环：

```text
稳定选择连续通过
  -> 确定性测试故障注入
  -> pytest exit 1 / Check red
  -> if: always() 继续上传 failure JUnit
  -> 恢复正确契约
  -> Check green / 无故障断言残留
```

### 1.2 范围与真实性

- 真实部分：GitHub pull-request workflow、GitHub-hosted runner、pytest 进程、真实 `/chat/stream` route、JUnit 生成与 Artifact Storage。
- 受控部分：fake `run_agentic_loop`、persistence spy、notification/telemetry side channel；remote-memory client 被 fixture 显式隔离。
- 未覆盖：真实 LLM、真实持久化回读、完整 Agent Workflow、取消/超时语义，以及 Branch Protection / Required Check 配置。

## 2. Pipeline 阶段说明

| 阶段 | 命令/任务 | 状态 | 产物 | 说明 |
|---|---|---|---|---|
| Checkout / runtime | checkout、Python 3.11、uv | PASS | runner log | 三个 PR revision 均完成环境准备 |
| Dependencies | `uv sync --frozen --group test` | PASS | runner log | frozen test dependencies；本地独立环境共安装/审计 156 packages |
| Target tests | `pytest test_resilience.py -m "integration and blocking and not real_llm" -q` | PASS / EXPECTED FAIL / PASS | JUnit XML | 只选择 baseline 与 midstream exception 两条 blocking SSE 契约 |
| Artifact upload | `actions/upload-artifact@v4` + `if: always()` | PASS | suite/run/attempt 唯一 Artifact | 红色 pytest step 后仍上传 failure JUnit |
| Restore verification | 源码 diff、远端 restored run、本地 full resilience | PASS | restored JUnit / terminal output | 当前 HEAD 恢复 `round_end == 1` |

## 3. 稳定性结果

### 3.1 隔离前发现与处理

首次本地故障探针发现 `stream_env` 仍可能调用真实 remote-memory client，并出现外部 HTTP `401`。
该结果不满足 C0-4 的依赖隔离条件，因此当时停止发布红色 revision，并在测试 fixture 中加入：

```python
import summer_memory.memory_client as memory_client
monkeypatch.setattr(memory_client, "get_remote_memory_client", lambda: None)
```

隔离修复 commit：`958b66b61afe782919278cd546039fdf269a30dd`。该事件分类为测试环境隔离缺口，
不是产品 SSE 契约失败。

### 3.2 三次连续绿色

精确目标 selection 在独立 Python 3.11 frozen test 环境中连续运行：

| 顺序 | pytest 结果 | JUnit | 退出码 |
|---|---|---|---|
| Green 1 | `2 passed, 6 deselected, 3 warnings in 13.19s` | `tests=2 / failures=0 / errors=0 / skipped=0` | `0` |
| Green 2 | `2 passed, 6 deselected, 3 warnings in 13.30s` | `tests=2 / failures=0 / errors=0 / skipped=0` | `0` |
| Green 3 | `2 passed, 6 deselected, 3 warnings in 11.63s` | `tests=2 / failures=0 / errors=0 / skipped=0` | `0` |

三个 JUnit 的 nodeid 集合一致，没有 flaky、XPASS、setup error 或 selection 漂移。

### 3.3 PR 初始绿色

- Revision：`958b66b61afe782919278cd546039fdf269a30dd`
- Run：[33392018497](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392018497)
- 结果：`Success`
- Artifact：`closed-loop-v1-stream-contract-junit-33392018497-1`
- Artifact id：`9757831203`
- Digest：`sha256:5c7738ac308ca25fe0867dfa70e7a49516ea04a2e7e67f745cb8e9fded9fa2bd`

## 4. 故障注入与红灯证据

### 4.1 故障设计

在 test-only commit `07ee89cbc1124c4430bbacdc213845fd73f78181` 中，把 baseline 对
`round_end` 数量的确定性期望从 `1` 临时改为 `2`。产品代码、workflow selection 和另一个 SSE
case 均未修改。

本地故障结果：`1 failed, 1 passed, 6 deselected`，退出码 `1`；直接断言为 `assert 1 == 2`。

### 4.2 GitHub 红灯

| 字段 | 证据 |
|---|---|
| Run | [33392294451](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451) |
| Revision | `07ee89cbc1124c4430bbacdc213845fd73f78181` |
| Job | `Stream Contract Gate` / job `99488532070` |
| pytest step | `failure` / process exit `1` |
| Upload step | `success` |
| Run conclusion | `Failure` |
| 同 revision Smoke | run `33392294453` 为 `success`，失败归因隔离在 Stream Contract |

该证据证明 workflow/Check 会因为真实 pytest assertion failure 变红。它不证明 PR merge 会被阻止；
后者要求该 Check 在 Branch Protection / Ruleset 中被设为 Required。

### 4.3 Failure Artifact

| 字段 | 证据 |
|---|---|
| 名称 | `closed-loop-v1-stream-contract-junit-33392294451-1` |
| Artifact id | `9757933428` |
| 大小 | `1542 bytes` |
| GitHub digest | `sha256:956e2a20c218ff9f2b9fc434accc7823680663039dccba701c9be77ec984d437` |
| 本地 ZIP digest | 与 GitHub digest 完全一致 |
| Expiry | `2026-09-14T12:33:13Z` |
| 包内容 | 仅 `junit-stream-contract.xml` |
| XML digest | `sha256:630c7b4ce74f6f6dc1bdd37b55c13a7dc70f8af42eee6d6ca3475837f26b7935` |
| XML 结果 | `tests=2 / failures=1 / errors=0 / skipped=0` |

失败 XML 可独立定位：

- nodeid：`tests.integration.chat_stream.test_resilience.TestChatStreamRouteWithFakeLoop::test_chat_stream_resilience_baseline_finishes_and_cleans_state`
- assertion message：`C0-4 intentional red: deliberately expected two round_end events`
- diff：`assert 1 == 2`
- source：`tests/integration/chat_stream/test_resilience.py:433`
- workflow run 与 revision：见上表。

## 5. 恢复绿色

### 5.1 代码恢复

restore commit `d6553a96f6987c5f58fdafddb99fc28e19c72eb0` 恢复正确契约：

```python
assert event_types.count("round_end") == 1
```

当前 `origin/main...HEAD` diff 仅有两行 remote-memory fixture 隔离，不包含故障 assertion。

### 5.2 GitHub 恢复 run

| 字段 | 证据 |
|---|---|
| Run | [33392789083](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083) |
| Revision | `d6553a96f6987c5f58fdafddb99fc28e19c72eb0` |
| Job | `Stream Contract Gate` / job `99490134368` |
| pytest / upload | `success / success` |
| Artifact | `closed-loop-v1-stream-contract-junit-33392789083-1` / id `9758123014` |
| GitHub 与本地 ZIP digest | `sha256:58d5dd7ec563da411d4a2ace0aa0d11484743ee638f31a835030a7ffdd3fc048` |
| 下载 XML | `tests=2 / failures=0 / errors=0 / skipped=0` |
| XML digest | `sha256:e7f27bbe2833a27476f3f6a557e29877206c49479a90f551c12665061ae3feac` |
| 同 revision Smoke | run `33392789069` 为 `success` |

### 5.3 当前复核

2026-08-31 再次执行：

```bash
uv run python -m pytest tests/integration/chat_stream/test_resilience.py -q
```

结果：`7 passed, 1 xfailed, 3 warnings in 13.76s`，退出码 `0`。唯一 xfail 是既有
`test_chat_stream_user_stop_contract_gap`，不是本次回归失败。

## 6. 质量门禁结果

| 门禁项 | 期望标准 | 实际结果 | 结论 |
|---|---|---|---|
| 重复稳定性 | 目标 selection 连续 3 次通过且集合一致 | 三次均 `2 passed, 6 deselected` | PASS |
| 确定性负向检测 | 故障断言使 Check 返回非零 | GitHub run `33392294451` 为 Failure / exit 1 | PASS |
| 失败证据保存 | pytest 失败后 upload 仍成功 | failure Artifact 已上传、下载、验 hash、解析 | PASS |
| 安全恢复 | 当前 tree 不含故障断言且远端重新绿色 | run `33392789083` Success；当前断言 `== 1` | PASS |
| PR 合并阻断 | Stream 必须是 Required Check | 未发现 Required 配置证据 | NON_BLOCKING / NOT PROVEN |

## 7. 失败与风险分析

### 问题 1：测试 fixture 曾调用真实 remote memory

- 所属阶段：依赖隔离。
- 直接证据：首次本地探针出现 remote-memory HTTP `401`。
- 分类：`TEST_DEFECT / ENVIRONMENT`，不是产品 SSE 缺陷。
- 处理：fixture 显式 monkeypatch `get_remote_memory_client` 为 `None`。
- 复核：三次稳定绿色和所有 PR runs 均在隔离后执行。

### 问题 2：PR #2 不能按普通 merge 直接进入 main

- PR #2 是专用证据 PR，历史中保留 intentional-red commit，当前保持 Draft。
- 当前文件树已经恢复正确断言，但普通 merge 会把故障提交带入目标分支历史。
- 若后续要保留 remote-memory fixture fix，应由人类评审后 squash 为干净提交，或单独 cherry-pick/重建干净 PR。
- 本任务不执行 merge、force-push、关闭 PR 或 Required Check 修改。

### 问题 3：Stream Check 仍为 NON_BLOCKING

- 红叉证明 Check 失败，不等于仓库规则禁止合并。
- Draft 状态也会影响合并按钮，因此不能把“按钮不可用”归因于 Stream Check。
- Required Check 的最终决定与配置证据属于 C0-6。

## 8. 可展示成果总结

建立并验证了一个可审计的 SSE Stream Contract CI 负向测试闭环：目标契约在隔离环境中连续稳定
通过；确定性断言故障能够使 GitHub Check 真实变红；`if: always()` 在失败后仍保存可下载 JUnit；
Artifact 可追溯到 nodeid、assertion、run 和 revision；恢复后 CI 和完整 resilience suite 重新绿色。

该成果证明了自动化失败检测与证据保存能力，不夸大为 Required merge gate 或完整 Agent Workflow
验证。

## 9. 附录

### 9.1 Revision 演化

```text
main@533d4a3e...
  -> 958b66b...  isolate remote-memory dependency / green
  -> 07ee89c...  intentional red probe / red
  -> d6553a9...  restore correct contract / green
```

### 9.2 本地证据路径

- Failure ZIP：`tests/artifacts/closed_loop_v1/c0-4-remote-red-33392294451.zip`
- Failure XML：`tests/artifacts/closed_loop_v1/c0-4-remote-red-33392294451/junit-stream-contract.xml`
- Restored ZIP：`tests/artifacts/closed_loop_v1/c0-4-remote-green-33392789083.zip`
- Restored XML：`tests/artifacts/closed_loop_v1/c0-4-remote-green-33392789083/junit-stream-contract.xml`

这些运行产物由 `.gitignore` 排除；长期证据保存在本报告、GitHub run URL、revision 和 digest 中。

## 10. 最终结论

- C0-4 acceptance：`DONE`
- Artifact status：`VERIFIED`
- Implementation status：fixture isolation `LANDED` 于证据分支，尚未合入 `main`
- Gate status：Stream Contract `NON_BLOCKING`
- 下一工作单元：C0-5 Traceability / Gate Record；本次按计划检查点停止，不执行 C0-5。
