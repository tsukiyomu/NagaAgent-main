# Closed Loop V1 C0-3 Evidence-Backed Execution Journal

## 1. Work Unit

- Journal ID: `closed-loop-v1-c0-3-001`
- Date: `2026-08-20`
- Plan: [`../plans/closed-loop-v1-implementation-plan.md`](../plans/closed-loop-v1-implementation-plan.md)
- Task ID: `C0-3`
- Objective: 为 Smoke 和 Stream Contract CI 保存最小、结构化、可归因的 JUnit 执行证据。
- Purpose: 让一次 CI run 结束后，Reviewer、triage 工具或后续 Agent 仍能定位 suite、testcase、失败消息、run 和 attempt；避免只能翻阅易丢失的控制台日志。
- Completion criteria: 成功与失败 GitHub run 均可下载有效 JUnit，报告可定位具体 nodeid。
- Required evidence: workflow 结构、成功 JUnit 内容、失败 JUnit 内容、artifact 名称、文件清单、下载验证和保留期限。
- Exclusions: C0-4 的 `3x green -> intentional red -> restored green`；C0-6 的 Required Check 人类决策；Quality Gate enforce；真实 LLM、外部服务和 staging。
- Revision/environment: 本地实现最初基于 `codex/verify-stream-contract-gate`；最终托管验证 revision 为 `main@533d4a3e464c6ce13b719145ce400099e6dcf32d`；本地 Windows / Python `3.11.7` / uv `0.9.24`；远端 GitHub-hosted `ubuntu-latest` / Python 3.11。
- Implementation status: `DONE`（由 C0-4 托管失败路径证据于 2026-08-31 关闭）
- Learning status: `TEACH_BACK_PENDING`

本 journal 的主体保留 2026-08-20～23 调查时的历史边界；其中“真实 failed-run artifact 尚缺”在
2026-08-31 已由 C0-3 托管失败路径复核关闭。[Stream failure run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451)
证明 pytest step 失败、`if: always()` upload step 成功；artifact 已由 Agent 下载并解析。详细字段已
回填到 [`../plans/closed-loop-v1-implementation-plan.md`](../plans/closed-loop-v1-implementation-plan.md) 的 C0-3 证据列表。本次不登记 C0-4 完成。

### 1.1 2026-08-31 Closure Evidence

| Evidence | Verified fact |
|---|---|
| [Failure run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451) | Revision `07ee89cbc1124c4430bbacdc213845fd73f78181`；Stream job `99488532070` 和 pytest step 为 `failure`；`if: always()` upload step 为 `success`。 |
| Failure Artifact | `closed-loop-v1-stream-contract-junit-33392294451-1`；id `9757933428`；1542 bytes；digest `sha256:956e2a20c218ff9f2b9fc434accc7823680663039dccba701c9be77ec984d437`；expires `2026-09-14T12:33:13Z`。 |
| Download integrity | 认证下载后的 ZIP SHA256 与 GitHub digest 一致；包内仅有 `junit-stream-contract.xml`。 |
| JUnit parse | `tests=2 / failures=1 / errors=0 / skipped=0`；failure 定位到 `TestChatStreamRouteWithFakeLoop::test_chat_stream_resilience_baseline_finishes_and_cleans_state`、故障 assertion 和 `assert 1 == 2`。 |
| [Restored run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083) | Revision `d6553a96f6987c5f58fdafddb99fc28e19c72eb0`；pytest/upload 均 `success`；下载 JUnit 为 `tests=2 / failures=0 / errors=0 / skipped=0`；故障断言无残留。 |

结论：C0-3 的托管失败路径已经从“API metadata + 人工检查”升级为“真实红色 run + upload step +
authenticated archive download + digest match + independent XML parse”。下文 2026-08-20～23 的
`Unknowns`、`REVIEW_NEEDED` 和未认证 `401` 描述是执行过程中的历史快照，以本 closure evidence 和
第 16 节 Final Proof 为当前结论。

### 1.2 为什么需要 C0-3（目的）

C0-1 与 C0-2 已经解决“选择哪些契约”和“在哪里自动执行”两个问题，但 CI 当时仍主要是一个
**判定器**：pytest exit code 让 Check 变绿或变红，job log 供人即时阅读。它还不是一个稳定的
**证据系统**，因为 testcase、failure、revision 和一次具体 run/attempt 之间没有形成可下载、可复核的
结构化对象。

C0-3 的目的不是“多生成一个 XML”，而是建立以下不变量：

```text
每一次被 Gate 选择的测试执行
  -> 产生结构化 testcase 事实
  -> 与 suite / revision / run / attempt 一一关联
  -> 成功和失败都进入独立证据生命周期
  -> 缺失证据本身也被识别为基础设施错误
```

因此，pytest exit code 继续负责“是否通过”，JUnit Artifact 负责“发生了什么、以后如何解释”。两者
分工而不互相替代。

### 1.3 C0-3 在系统中的作用

```text
Decision / Gate Record
        ↑
Evidence Interpretation / Triage
        ↑
Evidence Storage  ← C0-3
        ↑
Test Execution    ← C0-1 / C0-2 已选择并接线
```

C0-3 的系统作用包括：

1. 用 JUnit 提供机器可解析的 testcase / failure 接口，减少对自然语言 log scraping 的依赖；
2. 用 Smoke / Stream 分离建立 evidence taxonomy，让 artifact 自身携带测试层与风险域；
3. 用 `run_id + run_attempt` 保留失败、重试、恢复之间的演化链，不覆盖原始状态；
4. 用 `if: always()` 将测试生命周期与证据收集生命周期分离；
5. 用 `if-no-files-found: error` 防止“承诺保存证据但实际为空”的假成功；
6. 用 14 天 retention 与 `.gitignore` 区分短期执行证据和长期源码版本控制；
7. 为后续人工 review、Agent triage、SOP traceability 和 Gate Record 提供可信输入。

它明确**不负责**自动根因诊断、修复测试、改变 pytest 结论、把 Stream 自动设为 Required，或证明
真实 LLM / 完整 Agent Workflow。

## 2. Learning Objective

完成本单元后，用户应能够解释：

1. JUnit 为什么是结构化执行证据，而不是另一套测试判定器；
2. `if: always()` 和 `if-no-files-found: error` 分别保护哪个失败路径；
3. suite、`run_id`、`run_attempt` 如何形成一次执行到一次 artifact 的映射；
4. 为什么运行产物应由 GitHub Artifact Storage 短期保存，而不是提交到 Git；
5. 为什么本地生成 XML 不等于远端 artifact 已可下载。

最简问题模型是：

```text
pytest assertion + exit code
  -> 决定 Check 成败
  -> 同时写 JUnit
  -> upload step 无论测试成功/失败都尝试保存 JUnit
  -> suite/run/attempt 唯一 Artifact 保存 14 天
```

## 3. Initial Understanding

### Confirmed facts

- 两个 PR workflow 在本任务前只运行 pytest，没有 `--junitxml` 或 JUnit upload step。
- `tests/smoke/test_api_smoke.py` 的 blocking selection 包含 3 条 Smoke。
- `tests/integration/chat_stream/test_resilience.py` 的目标 selection 包含 2 条 blocking SSE 契约。
- Stream 契约使用真实 FastAPI route、fake `run_agentic_loop`、persistence / notification spy；不调用真实 LLM。
- 仓库已有 `actions/upload-artifact@v4` 使用先例，但没有测试结果发布契约。
- `.gitignore` 已排除 Quality Gate 运行产物，但任务前没有排除 `tests/artifacts/closed_loop_v1/`。
- GitHub 官方 action 文档说明 retention 可显式配置，artifact v4 使用不可变语义；用户在 guided checkpoint 中批准 14 天保留期。

### Assumptions and inferences

- 14 天足以覆盖通常的 PR review 与短期 triage；若项目需要合规或长期趋势分析，应迁移到更长寿命的专用存储，而不是无条件延长所有 JUnit。
- GitHub hosted runner 使用 Ubuntu，因此 workflow 中双引号 marker expression 不受本地 Windows `cmd` 引号问题影响；C0-2 的真实 runner 已执行过同类 marker 命令。

### Unknowns

- 真实 GitHub success run 已触发，artifact ID、name、digest 和 expires_at 已验证；未认证 REST archive download 返回 HTTP `401`，本 Agent 未独立解析托管 ZIP 内容。
- 用户确认已人工检查远端结果，但没有提供逐字段的下载解析记录；该人类 review 与 API metadata 分开记录。
- 尚无真实 pytest failure run 证明红色 Check 后 upload step 仍成功并产生 failure JUnit。
- runner 在取消、强制终止或 pytest 启动前失败时不保证能生成 JUnit；缺失文件会由 upload step 明确报错，而不是伪装成已有报告。

## 4. Project Review Inventory

| File or symbol | Question | Behavior found | Evidence | Design impact |
|---|---|---|---|---|
| `.github/workflows/pr-smoke-gate.yml` | Smoke 如何执行和报告？ | Python 3.11 + frozen test dependencies；原命令无 JUnit | 完整 workflow 与 C0-2 远端记录 | 在原 pytest step 增加 JUnit，并追加独立 upload step |
| `.github/workflows/pr-stream-contract-gate.yml` | Stream 如何执行和报告？ | 独立 non-blocking PR Check；原命令无 JUnit | 完整 workflow 与 2026-08-10 PR 证据 | 保持 selection 不变，只增加 evidence publication |
| `tests/smoke/test_api_smoke.py` | JUnit 应包含哪些 testcase？ | 3 条 `smoke + blocking` API case | 测试函数和本地 XML | Smoke XML 必须精确出现 3 个名称 |
| `tests/integration/chat_stream/test_resilience.py` | Stream 的真实性和断言边界是什么？ | 两条目标 case 验证正常/异常终止、保存策略与 cleanup；loop 被替换 | fixture、test body 和本地 XML | 文档不得把 JUnit 描述为真实 LLM 或完整 workflow 证明 |
| `.gitignore` | 运行 XML 是否会污染源码？ | 任务前未覆盖 Closed Loop V1 路径 | `git check-ignore` | 新增 suite artifact 目录忽略规则 |
| `docs/testing/architecture/ci-pr-gate.md` | CI 事实来源是否反映 artifact？ | 任务前明确把 JUnit 留给 C0-3 | 文档全文 | 增加发布契约、proof boundary 与远端 pending 状态 |
| `docs/testing/architecture/part-02-api-stream.md` | Stream 文档是否仍宣称 JUnit 未实现？ | 原文明确说未上传 | 第 2.6 节 | 改为本地落地、远端 `REVIEW_NEEDED` |
| `docs/testing/reports/README.md` | 生成物边界是否完整？ | 原文把 CI artifact 描述为未来工作 | 输出清单与版本控制边界 | 增加 Closed Loop V1 JUnit 路径和当前状态 |
| `.gitignore` 的 `/docs/` | 计划和 journal 是否纳入 Git？ | `docs/` 当前整体被忽略 | `git check-ignore -v` | 文档已按用户要求更新于本地 workspace，但不会出现在普通 `git diff/status`；本任务不扩张到仓库 docs 跟踪策略 |

## 5. Problem Model

### Invariants

1. pytest assertion 和进程退出码仍是唯一 blocking truth。
2. 测试失败不能自动跳过证据上传；失败时最需要诊断证据。
3. 声称必须生成的 JUnit 如果缺失，CI 必须显式失败，不能只 warning。
4. Smoke 与 Stream、不同 run、同一 run 的不同 attempt 不能互相覆盖或混淆。
5. 运行生成 XML 不进入 Git；源码与短期执行证据拥有不同生命周期。
6. 本地结构/内容证据不能升级成远端 GitHub Storage 证据。

### Inputs, outputs, and state transitions

| 输入状态 | pytest 结果 | JUnit | Upload | 最终含义 |
|---|---|---|---|---|
| 正常执行且断言通过 | exit `0` | 成功结果 | `always()` 上传 | Check 由 pytest 判绿；artifact 保存通过证据 |
| 正常执行且断言失败 | exit `1` | 包含 failure | `always()` 上传 | Check 由 pytest 判红；artifact 保存失败证据 |
| collection/setup error 且 pytest 写出报告 | 非零 | 包含 error | `always()` 上传 | Check 红；artifact 支持基础设施/测试问题归因 |
| pytest 未启动、被强制终止或报告路径错误 | 非零或上游失败 | 缺失 | upload 以 `if-no-files-found: error` 失败 | 明确暴露 evidence pipeline 失败；不能伪称已有 JUnit |

### Ownership and source of truth

- pytest：testcase assertion、exit code 和 JUnit 内容的 source of truth。
- workflow：命令、发布条件、artifact 名称和 retention 的 owner。
- GitHub Artifact Storage：远端可下载对象、artifact ID/URL/digest 和服务端 retention 的 owner。
- Branch Protection / Ruleset：Required Check 的 owner；artifact 配置不改变 Gate status。

### Failure, retry, timeout, and cancellation model

- pytest assertion failure 后，upload step 因 `if: always()` 仍运行；原 pytest step 的失败不会被上传成功覆盖。
- 同一 run 重试时 `github.run_attempt` 递增，保留 attempt 之间的证据差异。
- `if: always()` 不能保证 runner 被强制取消或超时后仍有执行时间；本任务不声称覆盖该平台级中断。
- 没有 JUnit 时 `if-no-files-found: error` 只负责暴露缺口，不会合成或伪造报告。

### Coverage boundary

- This task proves: workflow 静态契约有效；两套选择能在本地生成可解析 JUnit；报告包含预期 testcase；assertion failure JUnit 包含失败名称、消息和源位置；生成目录被 Git 忽略；GitHub success runs 的测试与 upload step 成功；远端 artifact 具有预期 suite/run/attempt 名称、revision、digest 和 14 天 expiry。
- This task does not prove: 真实 failed-run artifact、C0-4 负向 CI 红灯、Required Check、真实 LLM 或完整 Agent Workflow；本 Agent 也未在未认证条件下下载并解析远端 ZIP。

## 6. Options and Trade-offs

| Option | Benefits | Costs and risks | Required assumptions |
|---|---|---|---|
| 只依赖 Actions log | 零 YAML 增量 | 难以机器解析；run 结束后缺少独立 testcase artifact | 人工阅读日志足够 |
| JUnit + 固定名称 + repository 默认 retention | 改动最少 | rerun identity 不清楚；生命周期受隐藏设置影响 | 不需要 attempt 对比，且 repository 设置稳定 |
| **JUnit + suite/run/attempt 名称 + 14 天（选中）** | 可归因、可比较、生命周期显式；符合 v4 不可变 artifact 模型 | 每个 attempt 产生独立对象；需要一次远端 run 验证 | 14 天覆盖常规 review/triage |
| 同时上传 Quality Gate JSON/Markdown | 更多诊断字段 | 容易把 `DIAGNOSTIC_ONLY` 与 blocking truth 混淆；扩大 C0-3 | 已有字段语义足够稳定且用户需要额外报告 |

## 7. Decision Record

- Selected option: 两个 suite 各生成一份 JUnit；用 `actions/upload-artifact@v4`、`if: always()`、`if-no-files-found: error`、suite/run/attempt 唯一名称和 14 天 retention 上传。
- Supporting evidence: 当前 workflow 确实缺少结构化报告；本地成功与失败 XML 均能承载 node/testcase 和 failure；官方 v4 文档支持显式 retention 与不可变 artifact。
- Why alternatives were rejected: console-only 不利于机器消费；固定名称/默认 retention 隐藏执行身份与生命周期；Quality Gate diagnostic 不是 V1 blocking truth，暂不混入。
- Conditions that invalidate this decision: 组织要求长期合规留存；平台不是支持 v4 的 GitHub.com runner；artifact 成本或限制变化；后续需要跨 suite 聚合和长期趋势查询。
- Rollback, fallback, or migration path: 删除两个 upload step 和 JUnit flag 即可回退；长期证据可迁移到专用对象存储/报告系统，同时保留 JUnit producer。
- New complexity introduced: 每个 workflow 增加一条输出路径和一个 upload step；每个 attempt 增加一个 14 天 artifact。

## 8. Guided-Learning Checkpoint

- Decision question presented: 是否采用显式 14 天 retention，而不是 repository 默认值？
- User's prediction or analysis: 用户批准 14 天方案，并要求以“它有什么作用、为什么这样做、什么证据证明”的方式更彻底解释。
- Comparison with repository evidence: 14 天能在 workflow 内固定短期证据生命周期；当前 repository 没有测试 artifact retention 先例，因此显式值比依赖隐藏默认值更可复核。
- Understanding that still needs clarification: 已完成解释；尚未收到用户独立 teach-back，因此保持 `TEACH_BACK_PENDING`，不标记 `MASTERED`。

## 9. Requirement-to-Code-to-Evidence Mapping

| Requirement or risk | Production location | Planned change | Test location | Assertion | Evidence |
|---|---|---|---|---|---|
| Smoke 生成 JUnit | `pr-smoke-gate.yml` pytest step | 增加 suite 路径 | `tests/smoke/test_api_smoke.py` | XML 3 tests，名称精确匹配 | `junit-smoke.xml` parse |
| Stream 生成 JUnit | `pr-stream-contract-gate.yml` pytest step | 增加 suite 路径 | `test_resilience.py` 两条 blocking case | XML 2 tests，其他 6 deselected | `junit-stream-contract.xml` parse |
| 失败时仍保存 | 两个 upload step | `if: always()` | 临时 failure probe | pytest exit `1` 且 XML failure=1 | `junit-failure-probe.xml` parse |
| 缺失报告不可静默 | 两个 upload step | `if-no-files-found: error` | workflow 结构检查 | 两个值均为 `error` | `workflow_artifact_contract=valid` |
| attempt 不覆盖 | artifact name | 加 run/attempt | workflow 结构检查 | 两名称均包含两个 context | 结构检查输出 |
| 生命周期可复核 | artifact inputs | `retention-days: 14` | workflow 结构检查 | 两个值均为 `14` | 结构检查输出 |
| 运行产物不入 Git | `.gitignore` | 忽略 Closed Loop 路径 | `git check-ignore` | 路径命中新增规则 | ignored status `!!` |

## 10. Planned Changes

| File or symbol | Planned change | Reason |
|---|---|---|
| `.github/workflows/pr-smoke-gate.yml` | Smoke JUnit + always upload | 保存 3 条 Smoke 的结构化证据 |
| `.github/workflows/pr-stream-contract-gate.yml` | Stream JUnit + always upload | 保存 2 条 SSE 契约的结构化证据 |
| `.gitignore` | 忽略 runtime JUnit 目录 | 分离 source 与 execution artifact |
| `docs/testing/architecture/ci-pr-gate.md` | 记录发布契约和 proof boundary | 保持 CI 事实来源准确 |
| `docs/testing/architecture/part-02-api-stream.md` | 更新 C0-3 当前态 | 避免继续声称 JUnit 未落地 |
| `docs/testing/reports/README.md` | 增加 JUnit 产物和版本控制边界 | 让报告消费者找到正确位置 |
| Closed Loop V1 plan / journal | 记录状态、证据与未验证项 | 可复核交接 |

## 11. Actual Changes

| File or symbol | Actual change | Difference from plan |
|---|---|---|
| 两个 PR workflows | 分别生成 JUnit，并用 v4、always、missing=error、唯一名称、14 天上传 | 无 |
| `.gitignore` | 增加 `tests/artifacts/closed_loop_v1/` | 无 |
| 三份 testing docs | 同步发布流程、边界、状态和运行目录 | 为消除现有明确 stale claim，加入 `part-02` 和 reports README |
| 临时本地验证资产 | 建立结构 parser、suite runner 和 failure probe，执行后删除源文件 | Windows `cmd` 无法可靠传递内联 Python/marker 引号后的恢复措施；只保留 3 份 ignored XML |

## 12. Execution Evidence

| Command or run | Environment | Exit/result | Artifact | What it proves | What it does not prove |
|---|---|---|---|---|---|
| 临时 YAML parser 对两个 workflow 的 8 项结构断言 | Python 3.11.7 + PyYAML BaseLoader | exit `0`; `workflow_artifact_contract=valid` | terminal output | JUnit flag、v4、always、missing=error、14 天、唯一名称和分离路径均编码正确 | GitHub 是否执行 action |
| `python -m pytest tests/smoke -m "smoke and blocking" -q --junitxml=.../junit-smoke.xml`（由本地 wrapper 传递精确 argv） | Windows / uv | exit `0`; `3 passed, 4 warnings in 8.76s` | `junit-smoke.xml`，551 bytes | Smoke selection 与 JUnit producer 可执行 | 远端上传 |
| Smoke XML parse | Python stdlib XML parser | exit `0`; tests=3/failures=0/errors=0 | 同上 | 3 个预期 testcase 名称存在 | assertion failure 内容 |
| `python -m pytest tests/integration/chat_stream/test_resilience.py -m "integration and blocking and not real_llm" -q --junitxml=.../junit-stream-contract.xml` | Windows / uv | exit `0`; `2 passed, 6 deselected, 5 warnings in 35.74s` | `junit-stream-contract.xml`，1496 bytes | 精确两条 SSE 契约生成结构化结果 | real LLM、其他 resilience case、远端上传 |
| Stream XML parse | Python stdlib XML parser | exit `0`; tests=2/failures=0/errors=0 | 同上 | 两个预期 node/testcase 名称存在 | GitHub artifact identity |
| 临时 deterministic failure probe | Windows / uv | expected exit `1`; `1 failed in 0.51s` | `junit-failure-probe.xml`，871 bytes | assertion failure 时 JUnit 仍生成 | `if: always()` 在 GitHub 的托管执行 |
| Failure XML parse | Python stdlib XML parser | exit `0`; tests=1/failures=1 | 同上 | testcase、`C0-3 failure evidence probe`、actual/expected 和源行均保存 | 真实产品缺陷或 C0-4 red run |
| `git diff --check` | HEAD workspace | exit `0`；只有 line-ending warning | tracked diff | tracked patch 无 whitespace error | docs 因 `/docs/` ignore 不在普通 diff 中 |
| `git check-ignore` / ignored status | HEAD workspace | 新路径显示 `!! tests/artifacts/closed_loop_v1/` | `.gitignore` | 运行 XML 不污染 Git status | 远端 artifact retention |
| [PR Smoke Gate run `32568350661`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/32568350661) | GitHub-hosted `ubuntu-latest`；`main@533d4a3...`；push；attempt 1 | run/job/test/upload step 全部 `success` | artifact id `9474671380` | success path 在托管 runner 真实执行并上传 | pytest failure 后是否仍上传 |
| Smoke artifact metadata API | GitHub Actions Artifact Storage | name `closed-loop-v1-smoke-junit-32568350661-1`；390 bytes；digest `sha256:0a9155...b25f`；expires `2026-09-05T10:43:33Z` | artifact metadata | suite/run/attempt identity、revision 关联、未过期和 14 天 retention | 未认证下载后的 XML 内容 |
| [PR Stream Contract Gate run `32568350679`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/32568350679) | GitHub-hosted `ubuntu-latest`；`main@533d4a3...`；push；attempt 1 | run/job/test/upload step 全部 `success` | artifact id `9474672187` | Stream success path 在托管 runner 真实执行并上传 | Stream Required 状态或 failed-run behavior |
| Stream artifact metadata API | GitHub Actions Artifact Storage | name `closed-loop-v1-stream-contract-junit-32568350679-1`；717 bytes；digest `sha256:2f5de8...b6a`；expires `2026-09-05T10:43:37Z` | artifact metadata | suite/run/attempt identity、revision 关联、未过期和 14 天 retention | 未认证下载后的 XML 内容 |
| Artifact archive download attempt | Unauthenticated GitHub REST API | 两个 archive endpoint 均 HTTP `401` | 无本地 ZIP | API metadata 与内容下载权限是不同边界 | 不能由此次 Agent 调用证明 ZIP 内容；不否定登录用户 UI 下载 |
| User remote inspection | GitHub UI；2026-08-23 | 用户确认已检查并同意继续 | human review statement | 用户接受当前 success evidence | 未提供 failed-run artifact 或逐字段 XML parse |

4 条/5 条 warning 均为现有第三方/API deprecation warning；没有 `PytestUnknownMarkWarning`、setup
error、XPASS 或外部服务调用证据。本任务不把 warning 当作 C0-3 artifact pipeline 失败。

## 13. Deviations and Recovery

| Initial assumption or failure | New evidence | Revised decision | Recovery result |
|---|---|---|---|
| 可用 `uv run python -c` 完成内联结构断言 | Windows `cmd` 把引号传坏，Python `SyntaxError`，exit `1` | 使用 ignored 临时 script 执行相同断言 | 8 项结构断言全部通过，exit `0`；script 已删除 |
| 可直接从 shell 传 `-m "smoke and blocking"` | `cmd` 把 `and` 当作 pytest 路径，exit `4` | wrapper 用参数数组传递原始 marker expression | Smoke `3 passed`；Stream `2 passed, 6 deselected`；wrapper 已删除 |
| 可递归删除临时 `__pycache__` | Windows policy 拒绝递归删除命令 | 枚举并删除唯一 `.pyc` 文件 | 临时源码与 bytecode 已移除；ignored XML 保留 |
| 计划和 journal 会出现在 Git diff | 当前 `.gitignore` 包含 `/docs/` | 按用户要求更新本地文件，明确版本控制边界，不擅自改变全仓 docs 策略 | 本地文档可检查；普通 Git 提交只包含 workflow 和 `.gitignore` 变更 |

## 14. Remaining Risks and Uncertainty

1. Success run 的 artifact 名称、ID、digest、revision 和 14 天 expiry 已验证；本 Agent 未认证下载返回 HTTP `401`，托管 ZIP 内容仅有用户人工检查声明和本地等价 JUnit parse，不伪装成独立远端 parse。
2. 仍需要测试失败 run 的托管证据；失败 run 可以与 C0-4 的 intentional-red run 复用，但不能提前宣称完成。
3. `if: always()` 不能承诺 runner 强制取消/超时后仍上传；无 JUnit 时 `if-no-files-found: error` 只能暴露失败。
4. `docs/` 当前被 Git 忽略；若这些计划和 journal 应进入正式版本控制，需要单独的人类仓库策略决定。
5. Stream 仍为 `NON_BLOCKING`；artifact publication 不会把它自动晋升为 Required Check。

## 15. Teach-Back

建议用户用自己的话回答：

1. 为什么 pytest exit code 和 JUnit Artifact 扮演不同角色？
2. `if: always()` 与 `if-no-files-found: error` 分别防止哪种证据丢失？
3. 为什么 artifact 名称需要 suite、run id 和 attempt？
4. 本地 `3 tests / 2 tests / 1 failure` XML 分别证明了什么，又没有证明什么？
5. 看到真实 GitHub run 的哪些字段后，才可以把 C0-3 从 `REVIEW_NEEDED` 改成 `DONE`？

### User explanation or application evidence

- 用户已批准 14 天 retention，并准确指出“验证证据之前应先建立目的与作用的逻辑前提”，同时提供了从 JUnit、suite taxonomy、run identity、failure upload、missing-file error、retention 到 evidence boundary 的参考解释。这证明用户已识别 C0-3 的核心不是 YAML 语法，而是证据模型；尚未以自己的独立闭环解释回答全部五个 teach-back 问题，因此不标记 `MASTERED`。

## 16. Final Proof

- Acceptance result: `DONE`；success 与 failed-run artifact path 均为远端 `VERIFIED`。
- Evidence location: 本 journal、两份 workflow、`tests/artifacts/closed_loop_v1/*.xml` 本地 ignored outputs、Smoke run `32568350661`、Stream success run `32568350679`、Stream failure run `33392294451`、restored green run `33392789083` 及对应 artifact metadata/下载内容。
- Human review required: C0-3 不再有缺失证据；C0-6 仍需仓库 Owner 单独确认 Stream 是否设为 Required。
- Gate or release effect: 无 Gate status 变更；Smoke 保持 `PR_BLOCKING`（历史 Draft PR 证据），Stream 保持 `NON_BLOCKING`。

## 17. Next Recommended Task

- C0-4 已完成；下一工作单元为 C0-5，形成最小 Traceability 与 Gate Record。
