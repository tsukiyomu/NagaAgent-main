# Closed Loop V1 Implementation Plan

## 1. 文档定位

- 文档状态：`CANDIDATE`
- 计划类型：`C0 / P4a 最小垂直闭环`
- 当前主线：`P0 baseline + P1 已落地 SSE 契约`
- 目标 revision：`01090ce1c60492c411624d057afd10517b504666`
- 制定日期：`2026-08-03`
- 当前优先级真相源：[`sop-compiler-runtime-practical-roadmap.md`](sop-compiler-runtime-practical-roadmap.md)
- Chat Stream 架构说明：[`../architecture/part-02-api-stream.md`](../architecture/part-02-api-stream.md)
- CI 事实来源：[`../architecture/ci-pr-gate.md`](../architecture/ci-pr-gate.md)

本计划只定义并实施第一条可执行、可报告、可阻断、可追溯的测试架构闭环。它不要求先完成全部 P1，也不把“拥有很多复杂用例”等同于“测试架构已经形成闭环”。

## 2. Key Result

使用少量已有、确定性、可归因的用例完成以下垂直链路：

```text
风险与协议契约
  -> Pytest 分层用例
  -> 干净环境安装
  -> PR CI Check
  -> pytest 退出码判定
  -> JUnit / Markdown / 执行日志 Artifact
  -> Failure / Triage Record
  -> Gate Record
  -> 人类确认 Required Check
```

Closed Loop V1 的成功标准不是“P1 所有生命周期场景都完成”，而是证明一个测试需求能够从风险定义一直流转到 PR 决策和可复核证据。

## 3. 当前证据基线

| 资产 | 当前证据 | 实现状态 | Gate 状态 | 边界 |
|---|---|---|---|---|
| P0 dependency / fixture / marker / artifact baseline | P0 Run Record：Smoke `3 passed`、Unit `48 passed, 1 xfailed`、Stream `7 passed, 1 xfailed`、Golden `5 passed` | `LANDED`；历史快照临时 `VERIFIED` | Smoke 已接入；2026-08-10 Draft PR 显示 `Required` | 当前 revision 尚未重新完成 P0 clean-environment Run |
| API Smoke | `.github/workflows/pr-smoke-gate.yml` 执行 3 条 `smoke and blocking` | `LANDED` | `PR_BLOCKING`；`pull_request` Check 成功且显示 `Required` | 不证明 integration 或完整 Agent Workflow |
| 正常 SSE 契约 | `test_chat_stream_resilience_baseline_finishes_and_cleans_state` | `LANDED`，远端 PR 定向执行通过 | `NON_BLOCKING`；已接入 `Stream Contract Gate` | real route + fake loop + persistence spy |
| 异常 SSE 契约 | `test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state` | `LANDED`，远端 PR 定向执行通过 | `NON_BLOCKING`；已接入 `Stream Contract Gate` | 验证 expected error terminal，不是产品测试失败 |
| User Stop | `test_chat_stream_user_stop_contract_gap` | `XFAIL_GAP` | `NOT_WIRED` | 不进入 Closed Loop V1 blocking perimeter |
| Quality Gate Summary | 本地 JSON / Markdown / terminal producer 已存在 | `PARTIAL` | `NOT_WIRED` | 当前 latency 和 expected-degraded 语义不适合作为 V1 阻塞真相源 |

## 4. Closed Loop V1 范围

### 4.1 Blocking perimeter

第一版只选择五条代表性测试：

1. `test_health_smoke`
2. `test_chat_non_stream_smoke`
3. `test_chat_stream_smoke_has_terminal_event`
4. `test_chat_stream_resilience_baseline_finishes_and_cleans_state`
5. `test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state`

这五条分别提供：

| 角色 | 用例 | 证明内容 |
|---|---|---|
| 最小入口 | Health / non-stream / stream smoke | FastAPI 入口与最小响应契约没有被改挂 |
| 正常复杂协议 | SSE baseline | 多 `content`、拼接、保存 spy、唯一 `[DONE]` 和 cleanup |
| 异常复杂协议 | SSE midstream exception | 部分响应后以唯一 `error` 收尾、无 `[DONE]`、不错误保存并完成 cleanup |

### 4.2 Explicitly out of scope

- P1 `AbortSignal`、`final_status=cancelled` 和 user-stop `xfail` 修复。
- 整体 timeout、重复 finalize、真实客户端断开。
- 真实 `MessageManager` 磁盘保存与重新加载。
- Duplicate `tool_call_id` 修复。
- 完整 Tool / Context / Golden Case PR Gate。
- 真实 LLM、MCP、RAG、MQTT、硬件和 staging。
- `--quality-gate-enforce`。
- 真实网络 TTFB 与 latency blocking。

## 5. Gate 决策原则

### 5.1 V1 阻塞真相源

Closed Loop V1 使用 pytest assertion 和进程退出码作为唯一 blocking truth：

```text
selected pytest case failed / setup error / collection error
  -> process exit code != 0
  -> GitHub job failed
  -> PR Check red
```

原因：

1. 当前 pytest 断言已经直接固定业务和 SSE 协议契约。
2. 当前 Quality Gate 的进程内 `ttfb_ms` 实际是 `first_chunk_ms` 语义。
3. Midstream exception 是“预期降级路径通过”，不能因为 `workflow_final_status=degraded` 或 `failure_stage=tool_dispatch` 被误判为测试失败。
4. `--quality-gate-enforce` 尚未实现，不能把报告中的 `gate_result` 描述为实际 PR 决策。

### 5.2 V1 报告定位

- JUnit XML：机器可读的测试结果真相源。
- GitHub job log：环境、安装、命令和失败堆栈证据。
- Gate Record Markdown：记录 revision、选择范围、结果、真实性边界和人类结论。
- 当前 Quality Gate JSON / Markdown：可以作为 diagnostic artifact，但不得决定 V1 job exit code，也不得宣称已通过正式 Quality Gate。

## 6. Implementation Work Units

### C0-1：冻结并标记 Blocking 测试集合

- 状态：`[x] [DONE]`
- 目的：让 CI 通过稳定 marker 选择现有两条 SSE 契约，而不是依赖易碎的 `-k` 表达式或手写 nodeid 列表。
- 作用：后续新增符合资格的 Stream Contract 时，只需经评审后增加 `blocking` marker，无需重写 workflow 命令。
- 实施内容：
  1. 给两条已落地 SSE 核心用例增加 `pytest.mark.blocking`。
  2. 不给 user-stop `xfail`、real LLM 或其他尚未评审用例增加 blocking marker。
  3. 验证 marker selection 只收集预期两条 integration case。
- 建议命令：

  ```bash
  uv run python -m pytest tests/integration/chat_stream/test_resilience.py -m "integration and blocking and not real_llm" --collect-only -q
  ```

- 完成状态：`DONE`（2026-08-03）。
- 验证证据：
  1. 已给以下两条用例增加 `pytest.mark.blocking`：
     - `tests/integration/chat_stream/test_resilience.py::TestChatStreamRouteWithFakeLoop::test_chat_stream_resilience_baseline_finishes_and_cleans_state`
     - `tests/integration/chat_stream/test_resilience.py::TestChatStreamRouteWithFakeLoop::test_chat_stream_resilience_midstream_exception_returns_error_and_cleans_state`
  2. Collection 命令：`uv run python -m pytest tests/integration/chat_stream/test_resilience.py -m "integration and blocking and not real_llm" --collect-only -q`。
  3. Collection 结果：精确收集 `2/8`，其余 `6 deselected`，退出码 `0`；输出 nodeid 仅为上述两条，因此 user-stop、real LLM 与其他未评审 case 均未混入。
  4. 定向回归命令：`uv run python -m pytest tests/integration/chat_stream/test_resilience.py -m "integration and blocking and not real_llm" -q`。
  5. 定向回归结果：`2 passed, 6 deselected, 5 warnings in 34.68s`，退出码 `0`。5 条 warning 均为第三方库/API deprecation warning，无 `PytestUnknownMarkWarning`、setup error、XPASS 或外部网络依赖。
  6. 真实性边界保持不变：真实 `/chat/stream` route + 可控 fake loop + persistence spy；本任务未修改 CI，因此 Gate 状态仍为 `NOT_WIRED`，不能宣称 `PR_BLOCKING`。
- 完成标准：精确选中两条 SSE 契约，无 user-stop、real LLM 或其他 case 混入。

### C0-2：建立独立 Stream Contract CI Check

- 状态：`[x] [DONE]`
- 目的：把已通过的 SSE integration 从本地资产升级为 PR 可见的独立检查。
- 作用：让 Smoke 失败与 Stream Contract 失败分别归因，避免单个大 job 隐藏测试层级和失败位置。
- 实施内容：
  1. 保留现有 `Smoke Blocking Gate`。
  2. 新增独立 job 或 workflow，显示名称固定为 `Stream Contract Gate`。
  3. 使用 Python 3.11、uv 和 `uv sync --frozen --group test`。
  4. 执行 `integration and blocking and not real_llm` selection。
  5. 设置合理 timeout 和 concurrency cancellation。
- 建议命令：

  ```bash
  uv run python -m pytest tests/integration/chat_stream/test_resilience.py \
    -m "integration and blocking and not real_llm" \
    -q \
    --junitxml=tests/artifacts/closed_loop_v1/junit-stream-contract.xml
  ```

- 完成状态：`DONE`（2026-08-10）。本地实现、真实 `pull_request` 接线和 GitHub runner 目标命令均已验证。
- 验证证据：
  1. 新增 `.github/workflows/pr-stream-contract-gate.yml`，workflow 名称为 `PR Stream Contract Gate`，独立 job id 为 `stream-contract`，Check 显示名称为 `Stream Contract Gate`；现有 `Smoke Blocking Gate` 未修改。
  2. workflow 配置 Python 3.11、`astral-sh/setup-uv@v4`、`uv sync --frozen --group test`、20 分钟 job timeout，以及按 Git ref 分组的 `cancel-in-progress: true`。
  3. 触发范围为面向 `main` / `master` 的 `pull_request`、推送到 `main` 和 `workflow_dispatch`。
  4. 使用 PyYAML BaseLoader 对 Smoke 与 Stream 两份 workflow 做结构断言，结果 `workflow_pair=valid`、退出码 `0`；确认两个 Check 名称分离且 Stream 命令精确使用 `integration and blocking and not real_llm` selection。
  5. 本地执行 `uv sync --frozen --group test`，结果 `Audited 156 packages`、退出码 `0`。
  6. 本地执行 workflow 等价命令，结果 `2 passed, 6 deselected, 5 warnings in 37.39s`、退出码 `0`；未执行 user-stop、real LLM 或其他未评审 case。
  7. 已同步 `docs/testing/architecture/ci-pr-gate.md`、`part-02-api-stream.md` 与 `overview.md` 的 workflow、命令、真实性边界、远端 PR 结果和 Required / non-blocking 状态。
  8. 一次组合结构检查因 PowerShell 内层引号转义产生 `SyntaxError`；改为通过标准输入运行相同结构断言后成功，未导致文件或环境变更。
  9. 2026-08-10 的 Draft PR 汇总页显示两个独立 `pull_request` Check 均成功：`PR Smoke Gate / Smoke Blocking Gate` 约 24 秒，`PR Stream Contract Gate / Stream Contract Gate` 约 22 秒。
  10. 执行 revision 为 `44a0af58d56e9b872ee064a36b1a193d3a7f353c`，head branch 为 `codex/verify-stream-contract-gate`。
  11. Stream GitHub runner 执行结果为 `2 passed, 6 deselected, 3 warnings in 2.61s`；命令精确使用 `integration and blocking and not real_llm` selection。
  12. Gate 边界：Smoke 在该 PR 页面显示 `Required`，可分类为 `PR_BLOCKING`；Stream 未显示 `Required`，因此 C0-2 完成后仍分类为 `NON_BLOCKING`，不能宣称 Stream 已阻止不合格 PR 合并。
  13. 绿色 PR 接线已满足 C0-2；故意失败与恢复绿色的负向实证由 C0-4 单独完成。当前未提供可写入文档的 PR / Actions Run URL，持久化链接留待 C0-3/C0-5 Gate Record 补齐。
  14. 文档一致性搜索已确认 architecture 下不再存在“只运行 Smoke”“Stream 远端待验证”或两条目标 SSE 契约 `NOT_WIRED` 的当前态描述；保留的 `NOT_WIRED` 仅对应 user-stop、Golden Cases 或 2026-08-01 历史状态。一次包含 PowerShell 反引号的搜索命令因引号解析失败，改用安全模式后退出码 `0`。
- 完成标准：PR 或手动触发后生成独立 `Stream Contract Gate`，测试失败时 job 返回非零退出码。

### C0-3：保存最小执行 Artifact

- 状态：`[x] [DONE]`
- 目的：
  1. **解决“CI 只有结论、没有可复用事实”的缺口。** 在 C0-3 之前，pytest 退出码可以让 Check 变绿或变红，Actions log 也能供人临时查看，但 run 结束后没有一份稳定、结构化、可独立下载的 testcase 结果。系统知道“失败了”，却没有建立“失败的是哪条契约、失败信息是什么、属于哪个 revision/run/attempt”的持久证据对象。
  2. **把瞬时测试输出固化为可审计的执行事实。** 将每次 Smoke / Stream Contract 执行转换成机器可解析的 JUnit，并让该文件与 suite、workflow run、attempt、revision 和保存期限建立明确关系。这样成功与失败不只是页面状态，而是可以被再次读取、比较和引用的记录。
  3. **建立证据生命周期不依赖测试结果的核心不变量。** 测试可以成功或失败，但只要 pytest 已产生 JUnit，证据收集就必须继续；如果承诺的 JUnit 缺失，缺失本身也必须被识别为 evidence pipeline 错误，不能用 warning 掩盖成“报告已保存”。
  4. **明确判定与解释的职责分离。** pytest assertion 和退出码继续回答“本次 Check 是否通过”；JUnit Artifact 回答“哪些 case 发生了什么，后来如何复核”。C0-3 不引入第二套 Gate 判定器，也不让 diagnostic report 改写 pytest 结论。
- 作用：
  1. **在 Test Execution 与 Evidence Interpretation 之间建立保存层。** Closed Loop V1 因此不再只有“执行 -> 绿/红”，而是形成“执行 -> 结构化事实 -> 保存事实 -> 人/工具解释事实”的可扩展链路，为后续 Failure/Triage Record 和 Gate Record 提供输入。
  2. **建立 evidence taxonomy。** Smoke 与 Stream Contract 使用不同 JUnit 路径和 artifact 名称，使报告在存储层就携带测试层与风险域信息；后续消费者无需先解析混合报告，才能判断失败属于最小 API 可用性还是 SSE 协议/生命周期契约。
  3. **支持失败归因与独立 triage。** JUnit 固定 testcase、failure/error、assertion 和源位置；Reviewer 或 Agent 可以先读取结构化失败包，再决定是否深入 job log，而不是从数千行自然语言日志中猜测状态。
  4. **保留执行演化链。** `run_id + run_attempt` 让首次失败、重试和恢复结果成为不同的不可变证据对象，支持比较“修复前/修复后”，避免 rerun 覆盖原始失败历史。
  5. **分离源码与运行证据生命周期。** workflow 和测试代码进入长期版本控制；JUnit 作为短期 PR review / triage 证据由 GitHub Artifact Storage 保存 14 天，不制造每次运行都变化的 Git diff。
  6. **为后续 Agent-assisted Testing / SOP 能力铺设可信输入层。** C0-3 本身不自动诊断、不生成最终 Gate 决策，也不证明完整 Agent Workflow；它提供后续诊断、追溯、项目展示和自动化决策所依赖的稳定事实接口。
- 实施内容：
  1. Smoke 和 Stream Contract 分别生成 JUnit XML。
  2. 使用 `actions/upload-artifact@v4` 上传测试结果。
  3. Artifact 名称包含 suite 和 run identity，避免不同 job 互相覆盖。
  4. 保留失败时上传条件 `if: always()`。
  5. 可附带当前 Quality Gate JSON / Markdown，但必须标记为 `DIAGNOSTIC_ONLY`。
- 完成状态：`DONE`（2026-08-31 复核）。本地 workflow、成功/失败 JUnit 内容与源码边界均已验证；真实 GitHub success 与 failure run、upload step、artifact identity/digest、14 天服务端到期时间及下载后 XML 内容均已验证。
- 验证证据：
  1. `.github/workflows/pr-smoke-gate.yml` 的 pytest 命令已增加 `--junitxml=tests/artifacts/closed_loop_v1/junit-smoke.xml`；`.github/workflows/pr-stream-contract-gate.yml` 已增加独立的 `junit-stream-contract.xml` 路径，两个 suite 不共享输出文件。
  2. 两个 workflow 均使用 `actions/upload-artifact@v4`，artifact 名称分别为 `closed-loop-v1-smoke-junit-${{ github.run_id }}-${{ github.run_attempt }}` 和 `closed-loop-v1-stream-contract-junit-${{ github.run_id }}-${{ github.run_attempt }}`，可从 suite 定位测试层、从 run/attempt 定位执行和重试。
  3. 两个 upload step 均配置 `if: always()`、`if-no-files-found: error` 和 `retention-days: 14`。作用分别是测试失败后仍保存证据、报告缺失时显式暴露 evidence pipeline 错误，以及把短期 PR review / triage 生命周期固定在 workflow 中。
  4. 使用 PyYAML BaseLoader 对两个 workflow 做 8 项结构断言，结果 `workflow_artifact_contract=valid`、退出码 `0`；确认 JUnit flag、v4 action、always 条件、missing-file error、14 天保留、run/attempt identity 和 suite 路径分离全部成立。
  5. 本地执行 Smoke 等价 argv，结果 `3 passed, 4 warnings in 8.76s`、退出码 `0`；解析 `junit-smoke.xml` 得到 `tests=3 / failures=0 / errors=0 / skipped=0`，testcase 精确为 health、non-stream chat 和 stream terminal 三条 Smoke。
  6. 本地执行 Stream Contract 等价 argv，结果 `2 passed, 6 deselected, 5 warnings in 35.74s`、退出码 `0`；解析 `junit-stream-contract.xml` 得到 `tests=2 / failures=0 / errors=0 / skipped=0`，testcase 精确为 baseline 与 midstream exception 两条 SSE 契约。
  7. 临时 deterministic failure probe 预期退出 `1`，JUnit 解析为 `tests=1 / failures=1`，并保存 testcase 名、`C0-3 failure evidence probe` assertion、actual/expected diff 和源代码行；证明 pytest assertion failure 时 JUnit 仍提供独立归因信息。临时 probe 与验证脚本执行后已删除，不进入测试集合或源码。
  8. `.gitignore` 已增加 `tests/artifacts/closed_loop_v1/`；`git check-ignore`/ignored status 显示运行目录为 `!!`，因此本地 XML 不污染源码状态。已同步 `ci-pr-gate.md`、`part-02-api-stream.md` 与 reports README 的发布流程、真实性边界和本地/远端证据状态。
  9. Blocking truth 未改变：Smoke / Stream 仍由 pytest assertion 和退出码决定 Check 成败；JUnit 是机器可读执行证据，不读取当前 Quality Gate diagnostic 来改变 job exit code。Gate 状态仍为 Smoke `PR_BLOCKING`、Stream `NON_BLOCKING`。
  10. commit `533d4a3e464c6ce13b719145ce400099e6dcf32d` 推送到 `main` 后触发 [PR Smoke Gate run `32568350661`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/32568350661)。run event 为 `push`、attempt 为 `1`、结论为 `success`；`Smoke Blocking Gate` job `97020157953` 和 `Upload smoke JUnit artifact` step 均为 `success`。
  11. Smoke run 生成 artifact `closed-loop-v1-smoke-junit-32568350661-1`：artifact id `9474671380`、size `390 bytes`、digest `sha256:0a9155edddc587d99797e25a5c63b4527e5b50a60e42553042e2cb6fd9e2b25f`、`expired=false`，创建于 `2026-08-22T10:43:34Z`，到期于 `2026-09-05T10:43:33Z`；到期时间与 14 天 retention 契约一致。
  12. 同一 commit 触发 [PR Stream Contract Gate run `32568350679`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/32568350679)。run event 为 `push`、attempt 为 `1`、结论为 `success`；`Stream Contract Gate` job `97020157697` 和 `Upload stream contract JUnit artifact` step 均为 `success`。
  13. Stream run 生成 artifact `closed-loop-v1-stream-contract-junit-32568350679-1`：artifact id `9474672187`、size `717 bytes`、digest `sha256:2f5de8366287c11bf35c01c4fe35b51995656ec290c5448a14e198475f637b6a`、`expired=false`，创建于 `2026-08-22T10:43:38Z`，到期于 `2026-09-05T10:43:37Z`；到期时间与 14 天 retention 契约一致。
  14. 用户于 2026-08-23 确认已人工检查远端 success 结果。当时公开 REST API 只能独立证明 metadata，未认证 archive download 返回 HTTP `401`，所以当次记录没有宣称 Agent 已解析托管 ZIP；该历史边界未被回写成虚假证据。
  15. C0-3 托管失败路径复核使用现有 Git 凭据完成真实 GitHub failure artifact 下载。首次向 GitHub API 发起认证下载后，客户端把认证头带到对象存储重定向目标而收到 `401`；改为先获取 GitHub `302 Location`，再在不转发认证头的情况下请求短期签名 URL，成功下载 ZIP。该恢复不降低认证要求，也没有输出或落盘凭据。
  16. 完整调查、设计选择、命令、远端 CI 结果、proof boundary、恢复记录和 teach-back 问题见 [`../reports/closed-loop-v1-c0-3-2026-08-20.md`](../reports/closed-loop-v1-c0-3-2026-08-20.md)。
  17. [Stream failure run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451) 在 revision `07ee89cbc1124c4430bbacdc213845fd73f78181` 上由真实 pytest assertion failure 变红；test step `failure`，`if: always()` upload step `success`。artifact `closed-loop-v1-stream-contract-junit-33392294451-1`（id `9757933428`，1542 bytes，digest `sha256:956e2a20c218ff9f2b9fc434accc7823680663039dccba701c9be77ec984d437`，expires `2026-09-14T12:33:13Z`）已下载并解析：`tests=2 / failures=1 / errors=0 / skipped=0`，可定位 baseline nodeid、故障注入 assertion、`assert 1 == 2`、run 和 revision。恢复 revision `d6553a96f6987c5f58fdafddb99fc28e19c72eb0` 的 [run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083) 已重新变绿且故障断言无残留。该证据先关闭 C0-3 的真实 failed-run Artifact 缺口，并在用户后续明确继续后复用于 C0-4 验收。
- 完成标准：成功与失败 run 均能下载有效 JUnit；报告可定位到具体 nodeid。

### C0-4：验证重复稳定性和负向阻断

- 状态：`[x] [DONE]`
- 目的：
  1. **排除“一次碰巧绿色”的假信心。** 单次成功只能证明某个 revision 在某次环境中通过，不能证明 marker selection、fixture 隔离和断言在重复执行时稳定；因此需要在同一受控环境中连续运行并比较测试集合、结果和异常信号。
  2. **证明测试具有负向检测能力，而不是“只会变绿”。** 通过一个确定、可解释的 SSE 契约破坏，验证 pytest assertion、进程退出码和 GitHub Check 能够对真实的不满足条件作出失败响应，降低 false negative 风险。
  3. **验证故障实验可以安全恢复。** 故障注入必须位于隔离证据分支/提交中，红灯与 failure Artifact 保存后恢复正确断言并重新获得绿色；`main` 和最终文件树不得残留故障代码。
  4. **固定 Check 失败与合并强制之间的边界。** C0-4 证明 `Stream Contract Gate` 会因测试失败而变红，但不把红叉、Draft 状态或不可用的 Merge 按钮解释成 GitHub 已强制禁止合并；Required Check 仍由 C0-6 验证。
- 作用：
  1. **为 Gate 资格评审提供稳定性、隔离性和失败敏感性证据。** C0-4 回答“这组测试是否足够可重复、可归因且能抓住确定性破坏”，为后续人工讨论 `PR_BLOCKING` 提供输入，但本身不改变 Gate 状态。
  2. **建立可比较的 `green -> red -> restored green` 对照链。** revision、workflow run、JUnit、assertion 和恢复结果一一对应，使 Reviewer 能把失败归因到故障提交，而不是外部服务、selection 漂移或偶发环境问题。
  3. **验证 C0-3 证据层在失败与恢复阶段都可用。** 红色 run 必须保留可下载 failure JUnit，恢复 run 必须保留新的 success JUnit；C0-4 消费并检验 C0-3 建立的 Artifact 生命周期，而不重新定义 pytest 判定规则。
  4. **为 C0-5 和 C0-6 提供决策输入。** C0-5 使用三阶段执行事实形成 Traceability / Gate Record；C0-6 再由仓库 Owner 根据这些证据决定是否配置 Required Check。
- 实施内容：
  1. 在干净环境连续运行目标命令 3 次。
  2. 结果必须无 flaky、XPASS、setup error 或 selection 漂移。
  3. 在临时分支或测试专用提交中故意破坏一个确定性 SSE 期望。
  4. 保存红色 CI run 和失败 artifact。
  5. 还原故意破坏并重新获得绿色 run；不得把破坏提交留在目标分支。
- 完成状态：`DONE`（2026-08-31）；用户明确继续后，复用既有证据完成正式复核，没有重复注入故障。
- 验证证据：
  1. 独立 Python 3.11 frozen test 环境中，精确目标 selection 连续三次为 `2 passed, 6 deselected`，耗时分别为 `13.19s / 13.30s / 11.63s`；三个 JUnit 均为 `tests=2 / failures=0 / errors=0 / skipped=0`，nodeid 集合一致，无 flaky、XPASS、setup error 或 selection 漂移。
  2. 首次探针发现 fixture 会访问真实 remote memory 并返回 HTTP `401`，因此先停止红灯发布；commit `958b66b61afe782919278cd546039fdf269a30dd` 将 remote-memory client 显式隔离，之后 [initial green run `33392018497`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392018497) 成功。
  3. test-only commit `07ee89cbc1124c4430bbacdc213845fd73f78181` 临时把 baseline 的 `round_end == 1` 改为 `== 2`；[red run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451) 为 `Failure`、process exit `1`，同时产生一个 JUnit Artifact。
  4. Failure Artifact `closed-loop-v1-stream-contract-junit-33392294451-1`（id `9757933428`）的本地 ZIP SHA256 与 GitHub digest `956e2a20...984d437` 完全一致；解析为 `tests=2 / failures=1`，可定位 baseline nodeid、故障 assertion、`assert 1 == 2`、source、run 和 revision。
  5. restore commit `d6553a96f6987c5f58fdafddb99fc28e19c72eb0` 恢复 `round_end == 1`；[restored run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083) 为 `Success`，restored Artifact 下载解析为 `tests=2 / failures=0 / errors=0 / skipped=0`。
  6. 当前本地/远端分支 head 均为 `d6553a96...`；`origin/main...HEAD` diff 只包含 remote-memory fixture 隔离，不含故障断言。当前完整 resilience suite 复核为 `7 passed, 1 xfailed, 3 warnings in 13.76s`、退出码 `0`。
  7. Draft [PR #2](https://github.com/tsukiyomu/NagaAgent-main/pull/2) 是专用证据 PR，历史包含故障提交，不应按普通 merge 进入 `main`；本任务未 merge、force-push、关闭 PR 或修改仓库规则。
  8. 完整 CI/CD 报告见 [`../reports/closed-loop-v1-c0-4-2026-08-31.md`](../reports/closed-loop-v1-c0-4-2026-08-31.md)。准确 Gate 边界仍为 Stream `NON_BLOCKING`：已证明 Check 会红，不证明 GitHub 会禁止合并。
- 完成标准：`3x green -> intentional red -> restored green` 全部可追溯。

### C0-5：形成最小 Traceability 与 Gate Record

- 状态：`[x] [DONE]`
- Architecture synchronization addendum：`[x] [DONE]`（2026-09-01）；已同步 `overview.md`、`part-02-api-stream.md` 与 `ci-pr-gate.md` 的 C0-5 当前事实，其他 architecture 文件因不拥有该事实而保持不变；未进入 C0-6。
- 目的：
  1. **解决证据已经存在但彼此分散的问题。** C0-1～C0-4 分别产生 marker、测试 nodeid、workflow、run、Artifact、failure assertion 和恢复结果；如果没有统一记录，Reviewer 仍需在代码、Actions 页面和多份报告之间手工拼接事实。
  2. **把执行事实转换成可评审的工程结论。** Gate Record 不只罗列“通过/失败”，还要说明风险、断言、真实/受控依赖、失败分类、修复证据、non-goals 和剩余缺口，让人类能够判断证据是否足以支持下一步 Gate 决策。
  3. **让第三方可以独立复核同一条链路。** 阅读者应能从一个 SSE 风险出发，追踪到场景、pytest nodeid、revision、GitHub run、JUnit Artifact、failure classification 和最终结论，而不依赖本次 Agent 的口头说明或临时上下文。
  4. **防止验证范围被执行结果过度扩张。** Record 必须同时保存已证明内容与未证明内容，例如 real route + fake loop 的真实性边界、user-stop `XFAIL_GAP`、真实 LLM/持久化未覆盖以及 Stream 仍为 `NON_BLOCKING`。
- 作用：
  1. **建立 Closed Loop V1 的追溯索引。** 把“风险/需求 -> 测试 -> CI -> Artifact -> triage -> 决策”固化为一个长期可读入口，避免关键关系只存在于短期 GitHub Artifact 或控制台日志中。
  2. **统一失败语义和 triage 交接。** 明确区分产品契约失败、故意故障探针、测试隔离缺口、环境问题和预期降级路径，减少后续 Reviewer/Agent 对红灯含义的二次猜测。
  3. **形成可复用的人机协作接口。** 新的 Reviewer 或 Agent 可以从 Gate Record 获取 exact command、revision、证据位置和待决问题，再继续复核或扩展，而不必重做已经完成的调查。
  4. **连接技术证据与人类治理。** C0-5 只生成可审计的决策材料，不修改 Branch Protection、批准合并或自动晋升 Gate；它把清晰、有限且可追溯的输入交给 C0-6。
- 最小追溯链：

  ```text
  SSE 卡死 / 乱序 / 错误终止风险
    -> 正常与 midstream exception 场景
    -> 两条 integration test nodeid
    -> Stream Contract Gate run
    -> JUnit artifact
    -> failure classification / triage
    -> Gate Record
  ```

- Gate Record 必须包含：
  1. objective、scope、revision、environment；
  2. exact commands、exit code、test summary；
  3. real / controlled dependencies；
  4. verified proof 与明确 non-goals；
  5. artifact 和 CI run reference；
  6. human review conclusion；
  7. remaining P1 gaps。
- 完成状态：`DONE`（2026-09-01，workspace scope）。已形成独立 Traceability / Gate Record；风险、两条测试、真实/受控依赖、revision、GitHub run、JUnit identity/digest、failure classification、恢复证据、当前 Gate 边界与 Reviewer 状态均可从单一入口复核。当前 `.gitignore` 忽略 `/docs/`，所以本地记录已完成但尚未发布为仓库版本化文档。
- 验证证据：
  1. 新增 [`../reports/closed-loop-v1-c0-5-2026-09-01.md`](../reports/closed-loop-v1-c0-5-2026-09-01.md)，同时作为 C0-5 Gate Record 与 evidence-backed execution journal；采用独立报告而非继续膨胀 C0-4 报告或本计划。
  2. 追溯矩阵将正常 SSE、midstream exception、intentional-red 和 remote-memory isolation 四类风险/事件连接到精确 nodeid、关键断言、dependency profile、revision、run、Artifact、classification 与当前决定。
  3. 2026-09-01 执行 `git fetch origin main` 成功；证据基线仍为 `origin/main@533d4a3...`，当前证据分支为 `d6553a96...`，相对 main 的最终 tree 只包含两行 remote-memory fixture 隔离，不含故障断言。
  4. 当前 revision collection 复核为精确 `2/8`、`6 deselected`；定向执行为 `2 passed, 6 deselected, 3 warnings in 12.59s`、退出码 `0`，JUnit 为 `tests=2 / failures=0 / errors=0 / skipped=0`。本地 shell wrapper 无法保留 exact marker 表达式中的空格，故使用限定文件内等价 `-m=blocking`；GitHub exact workflow expression 的 green/red/restored 证据不受影响。
  5. 公开 GitHub 页面再次确认 PR #2 为 Draft、包含 3 个证据提交且无 review；run `33392018497 / 33392294451 / 33392789083` 依次为 Success / Failure(exit 1) / Success，并显示对应 Artifact。
  6. Human-boundary conclusion 已明确保存：用户要求继续 C0-5 只授权形成记录，不等于批准 Required；没有 Repository Owner / Ruleset 证据时 Stream 保持 `NON_BLOCKING`，exact human governance decision 交给 C0-6。
  7. `git check-ignore -v` 确认 `.gitignore:247` 的 `/docs/` 规则命中本报告；本任务没有擅自修改 ignore policy 或 force-add 文档。该发布边界已写入 Gate Record 和 Current Progress。
  8. Architecture sync 使用 ownership-based 选择：`overview.md` 增加当前阶段与阅读入口，`part-02-api-stream.md` 增加 SSE 风险/断言/classification 追溯，`ci-pr-gate.md` 增加 normalized pipeline result 与 Check/Required 边界；`rg -l C0-5 docs/testing/architecture` 精确命中这 3 个文件，所有 Gate Record link target 均存在。
  9. `git diff --exit-code -- .github tests` 为 `0`，证明本次 architecture 同步没有修改 workflow 或测试；`git check-ignore -v` 再次确认 3 份 architecture 文档仍受 `/docs/` ignore policy 管理。
- 完成标准：第三方能够从风险追踪到测试、CI、artifact 和决策。

### C0-6：人类确认 Required Check 与闭环状态

- 状态：`[x] [DONE]`
- 目的：
  1. **把“存在一个 Check”与“平台强制该 Check”彻底分开。** Workflow YAML、绿色/红色 run 和 artifact 只能证明检查能够执行与报告；只有 Branch Protection / Ruleset 中的 Required status check 才能证明不满足条件时 GitHub 会阻止合并。
  2. **由仓库 Owner 承担风险接受与合并策略责任。** 是否把 `Stream Contract Gate` 设为 Required 涉及速度、稳定性、维护成本、例外流程和团队发布策略，不能由测试名称、Agent 判断或一次成功/失败运行自动决定。
  3. **为 Gate 状态建立平台级直接证据。** 最终结论必须引用适用目标分支、规则状态和 exact check context；如果证据不存在或 Owner 决定暂不强制，文档必须保持 `NON_BLOCKING / UNKNOWN`，不能推测为 `PR_BLOCKING`。
  4. **完成 Closed Loop V1 的人类确认终点。** 将 C0-1～C0-5 的技术证据与明确的人类决定结合，记录闭环是晋升、保持非阻塞还是暂缓，以及剩余风险和后续责任人。
- 作用：
  1. **把测试工程能力转换为真实仓库治理。** 在 Owner 批准时，把经过评审、稳定、可归因且有恢复证据的 Check 纳入合并规则；在不批准时，同样保存明确理由，避免模糊状态。
  2. **防止 Gate 自我晋升。** Agent、pytest marker、workflow 名称和报告都不能自行改变合并权限；C0-6 保留“人类决策、平台执行”的控制边界。
  3. **让 `PR_BLOCKING` 声明可审计。** Repository Settings 截图、ruleset/branch rule 导出或等价 API 证据应与 exact check name、目标分支和评审结论关联，后续规则变化时也能识别旧证据已经失效。
  4. **给 Closed Loop V1 一个准确的关闭结论。** 关闭记录应分别写清测试实现状态、执行证据状态和 Gate 状态；即使决定保持 Stream `NON_BLOCKING`，也应记录这是明确治理决定，而不是遗漏或默认推断。
- 实施内容：
  1. 仓库 Owner 评审两条 SSE case 的 blocking 资格。
  2. 人类在 Branch Protection / Ruleset 中决定是否把 `Stream Contract Gate` 设为 Required Check。
  3. 保存设置证据或明确记录保持 `UNKNOWN / NON_BLOCKING` 的决定。
- 完成状态：`DONE`（2026-09-01）。Repository Owner 明确选择 `A — DEFER_REQUIRED_PROMOTION`：Stream 保持 `NON_BLOCKING`，remote memory 在两条 SSE 契约测试中隔离，真实 remote-memory 集成覆盖标为 `DELAYED`；本轮未修改任何 GitHub 规则。
- 验证证据：
  1. [`../reports/closed-loop-v1-c0-6-2026-09-01.md`](../reports/closed-loop-v1-c0-6-2026-09-01.md) 保存 blocking qualification、exact check context、目标分支、平台探针和 Owner 决策选项。
  2. 两条 SSE case 的 selection、3x stable、intentional-red、failure Artifact、归因和 restored green 均满足进入 Owner 评审的技术材料要求。
  3. `origin/main@533d4a3...` 尚未包含 `get_remote_memory_client -> None` 隔离；该隔离只存在于证据分支 `d6553a9...`，而首次探针已观察到未隔离的真实 remote-memory HTTP `401`，所以当前不满足“目标分支无不受控外部依赖”的立即晋升条件。
  4. 未认证 `GET /repos/tsukiyomu/NagaAgent-main/rulesets` 返回 HTTP `200` 和 `[]`；它只证明公开调用者看不到 repository ruleset，不能排除 classic branch protection。
  5. 未认证 `GET /repos/tsukiyomu/NagaAgent-main/branches/main/protection` 返回 HTTP `401 Requires authentication`；内置浏览器访问 Settings 也不可用，因此 exact Required 配置继续为 `UNKNOWN`。
  6. Owner 选择了推荐项 A：暂缓晋升并保持 Stream `NON_BLOCKING`。这是一项明确治理决定，不是对平台设置的推测；没有平台证据时不得写成 `PR_BLOCKING`。
  7. 当前证据分支执行 `uv run python -m pytest tests/integration/chat_stream/test_resilience.py -m=blocking -q --junitxml=tests/artifacts/closed_loop_v1/junit-stream-contract-c0-6.xml`，退出码 `0`，结果 `2 passed, 6 deselected, 3 warnings in 12.66s`；JUnit 为 `tests=2 / failures=0 / errors=0 / skipped=0`。随后完整文件回归为 `7 passed, 1 xfailed, 3 warnings in 13.54s`、退出码 `0`。
  8. 产品 remote memory 保持 `LANDED`；只把真实认证、云端查询和回退验证从当前 SSE lifecycle profile 分离为 `DELAYED`。隔离 clean landing 仍需后续干净 PR，不复用含 intentional-red 历史的 PR #2。
- 完成标准：已通过明确 Owner 非晋升决定关闭 C0-6；Stream 为 `NON_BLOCKING`，平台 Required enforcement 仍未证明，禁止标记为 `PR_BLOCKING`。

## 7. Acceptance Criteria

- [x] Marker selection 精确包含 3 条 Smoke 和 2 条 SSE Contract 候选，不包含 user-stop/real LLM。
- [x] Python 3.11 干净环境可以通过 `uv sync --frozen --group test` 安装。
- [x] Smoke 与 Stream Contract 使用独立 GitHub Check 名称。
- [x] Stream Contract 目标命令连续运行 3 次一致通过。
- [x] 故意破坏一个确定性断言时，`Stream Contract Gate` 返回失败。
- [x] 恢复后 Gate 重新变绿，无破坏代码残留。
- [x] 成功和失败 run 都上传可下载 JUnit Artifact。
- [x] Failure 可以定位到 `nodeid / assertion / workflow run / revision`。
- [x] Gate Record 完成风险到 PR 决策的追溯链。
- [x] Quality Gate diagnostic 与 pytest blocking truth 明确分离。
- [x] Required Check 只有在人类提供仓库设置证据后才能标记为 `PR_BLOCKING`。

## 8. Stop Conditions

出现以下任一情况时，不得晋升 Closed Loop V1：

1. 目标命令存在 flaky、XPASS、setup error 或外部网络依赖。
2. Selection 意外包含 user-stop `xfail`、real LLM 或未评审 case。
3. 预期异常场景因为 `degraded / tool_dispatch` 被报告层误判为测试失败。
4. 当前 `ttfb_ms` 被描述为真实网络 TTFB 或用于 blocking。
5. Artifact 无法关联 revision、job 和测试 nodeid。
6. GitHub workflow 成功但没有证据证明 Required Check，文档却标记为 `PR_BLOCKING`。

## 9. Closure Definition

只有满足以下条件，Closed Loop V1 才能由人类从 `CANDIDATE` 晋升为 `VERIFIED`：

```text
Reviewed test perimeter
  + deterministic 3x pass
  + intentional red proof
  + restored green proof
  + downloadable artifacts
  + traceability Gate Record
  + explicit human gate decision
```

闭环完成后再回到 P1，优先实现 `AbortSignal -> cancelled semantics -> persistence policy -> timeout / duplicate finalize -> first_chunk_ms`。

## Progress Ledger

| Run ID | Date | Selected Task | Status | Evidence | Next Recommended Task |
|---|---|---|---|---|---|
| closed-loop-v1-plan-001 | 2026-08-03 | 创建 Closed Loop V1 实施计划 | DONE | 已基于 HEAD `01090ce...`、现有 Smoke workflow、两条已落地 SSE 契约、当前 Quality Gate 边界和 P0/P1 执行证据形成计划；未修改 CI 或测试代码 | 人工评审 Blocking perimeter；确认后执行 C0-1 |
| closed-loop-v1-c0-1-001 | 2026-08-03 | C0-1 冻结并标记 Blocking 测试集合 | DONE | 两条目标 SSE 用例已增加 `blocking` marker；collection 精确为 `2/8`、退出码 0；定向回归 `2 passed, 6 deselected`、退出码 0；CI 未修改，Gate 仍为 `NOT_WIRED` | C0-2 建立独立 `Stream Contract Gate` CI Check |
| closed-loop-v1-c0-2-001 | 2026-08-03 | C0-2 建立独立 Stream Contract CI Check | REVIEW_NEEDED | 新增独立 workflow 并同步 CI 架构说明；结构断言通过，依赖安装退出码 0，等价测试命令 `2 passed, 6 deselected`；尚无远端 run URL / commit SHA / job exit evidence，因此不标记 DONE | 提交并触发 `Stream Contract Gate`，回填远端 run 证据后复核 C0-2 |
| closed-loop-v1-c0-2-002 | 2026-08-10 | C0-2 远端 PR Check 证据复核与架构文档同步 | DONE | commit `44a0af58...` 的 Draft PR 上 Smoke 与 Stream 两个 `pull_request` Check 独立成功；Stream runner 为 `2 passed, 6 deselected`；已同步 `overview.md`、`ci-pr-gate.md` 与 `part-02-api-stream.md`，并明确 Smoke `PR_BLOCKING`、Stream `NON_BLOCKING` | C0-3 保存最小执行 Artifact |
| closed-loop-v1-c0-3-001 | 2026-08-20 | C0-3 保存最小执行 Artifact | REVIEW_NEEDED | Smoke / Stream workflow 已生成独立 JUnit，并以 suite/run/attempt 唯一名称、`if: always()`、missing-file error 和 14 天 retention 上传；本地为 Smoke `3 passed`、Stream `2 passed, 6 deselected`，XML testcase 精确；failure probe 保存 assertion 与源行；尚无真实 GitHub 上传/下载证据 | 提交并触发成功 GitHub run，下载和解析两个 artifact；C0-4 intentional-red run 后再补失败 artifact 证据并复核 C0-3 |
| closed-loop-v1-c0-3-002 | 2026-08-23 | C0-3 目的/作用深化与远端 success artifact 复核 | REVIEW_NEEDED | 将目的扩展为问题缺口、执行事实、证据生命周期和职责分离；将作用扩展为保存层、证据分类、失败归因、attempt 演化链、生命周期分离和 Agent/SOP 输入。commit `533d4a3...` 的 Smoke/Stream push run、upload step、artifact id/name/digest/14-day expiry 均由 GitHub API 验证，用户已人工检查；仍缺真实 failed-run artifact | 执行 C0-4 intentional-red，在失败 Check 中验证 `if: always()` 上传可下载 failure JUnit；恢复绿色后回填 C0-3 `DONE` |
| closed-loop-v1-progress-view-001 | 2026-08-31 | 建立 Testing Current Progress 单页入口 | DONE | 新增 `docs/testing/CURRENT_PROGRESS.md`，从 testing README 首位链接；集中呈现 C0-1～C0-6 状态、C0-3 唯一剩余证据、Gate 边界和 C0-4 执行链，不复制详细 journal | 执行 C0-4：3x green -> intentional red + failure Artifact -> restored green |
| closed-loop-v1-c0-3-003 | 2026-08-31 | C0-3 真实 failed-run Artifact 缺口关闭 | DONE | 隔离故障探针使 Stream run `33392294451` 真实变红，pytest step failure 而 `if: always()` upload success；Artifact id/name/digest/expiry 已验证，ZIP 已下载且 digest 匹配，JUnit 可定位 nodeid/assertion/run/revision；恢复 run `33392789083` 绿色且无故障断言残留 | 等待用户明确开始 C0-4 |
| closed-loop-v1-c0-4-001 | 2026-08-31 | C0-4 重复稳定性与真实负向检测闭环 | DONE | 目标 selection 连续 3 次绿色；PR #2 的 run `33392294451` 在故障 revision 上真实变红并上传可下载 failure JUnit；restore run `33392789083` 恢复绿色，当前 full resilience 为 `7 passed, 1 xfailed`，分支 diff 无故障断言；Stream 仍为 `NON_BLOCKING` | C0-5 形成最小 Traceability 与 Gate Record |
| closed-loop-v1-rationale-001 | 2026-09-01 | 深化 C0-4～C0-6 目的与作用 | DONE | C0-4 增加重复稳定性、负向检测、安全恢复和 Check/merge 边界；C0-5 增加证据聚合、工程结论、第三方复核和 non-goal 约束；C0-6 增加平台强制、人类所有权、Required 直接证据和闭环决策，并保持既有状态/步骤/证据不变 | C0-5 形成最小 Traceability 与 Gate Record |
| closed-loop-v1-c0-5-001 | 2026-09-01 | C0-5 最小 Traceability 与 Gate Record | DONE | 新增独立 C0-5 Gate Record，把 SSE 风险、两条 nodeid、断言、dependency profile、green/red/restored revisions/runs、JUnit artifact、failure classification、恢复证据和当前 `NON_BLOCKING` 决定连接为单一审计入口；当前 collection `2/8`，定向回归 `2 passed, 6 deselected`；PR #2 仍 Draft 且无 review；`/docs/` ignore policy 使记录当前仅存在于 workspace，未发布到 Git | C0-6 由 Repository Owner 决定 Required，并保存 Branch Protection / Ruleset 直接证据 |
| closed-loop-v1-c0-5-arch-sync-001 | 2026-09-01 | C0-5 testing architecture consistency sync | DONE | 按事实 ownership 同步 `overview.md`、`part-02-api-stream.md`、`ci-pr-gate.md`；C0-5 search 精确命中 3 文件，4 个 Gate Record links 可解析，Stream `NON_BLOCKING` / C0-6 Owner boundary 一致；`.github` 与 `tests` 无工作区变更 | C0-6 由 Repository Owner 决定 Required，并保存 Branch Protection / Ruleset 直接证据 |
| closed-loop-v1-c0-6-001 | 2026-09-01 | C0-6 blocking qualification 与 Owner 决策检查点 | REVIEW_NEEDED | exact check 为 `Stream Contract Gate`；两条 case 的稳定性、负向检测、Artifact 和恢复证据 review-ready；但 remote-memory 隔离尚未进入 `main`，classic protection API 未认证返回 `401`，没有平台 Required 直接证据；未修改任何规则 | Owner 明确选择“暂缓晋升（推荐）/ 长期 Non-blocking / 现在 Required”之一 |
| closed-loop-v1-c0-6-002 | 2026-09-01 | C0-6 Owner 选择 A 并关闭 non-blocking 闭环 | DONE | Owner 明确选择 `DEFER_REQUIRED_PROMOTION`；Stream 保持 `NON_BLOCKING`，真实 remote-memory profile 标为 `DELAYED`；证据分支隔离复核 `2 passed, 6 deselected`，JUnit `2/0/0/0`；Branch Protection / Ruleset 未修改，`PR_BLOCKING` 未宣称 | 用干净 PR 将两行 fixture 隔离落入 `main`，目标分支复跑后再单独评审 Required |
