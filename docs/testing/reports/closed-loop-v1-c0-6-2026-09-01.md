# Closed Loop V1 C0-6 Owner Decision Record

## 1. Work-unit contract

| Field | Value |
|---|---|
| Work unit | `C0-6 — 人类确认 Required Check 与闭环状态` |
| Date | `2026-09-01` |
| Target branch | `main` |
| Exact check context | `Stream Contract Gate` |
| Objective | 由 Repository Owner 在“晋升 Required / 保持 Non-blocking / 暂缓”中作出明确决定，并用平台配置或明确的非晋升决定关闭治理边界 |
| Current result | `DONE` |
| Current gate truth | Stream Contract `NON_BLOCKING`；Closed Loop V1 `VERIFIED`（non-blocking closure） |
| Learning status | `TEACH_BACK_PENDING` |
| Exclusions | 本检查点不修改 Branch Protection / Ruleset，不合并 PR #2，不把 Agent 判断当作 Owner 授权 |

## 2. Outcome first

Repository Owner 于 2026-09-01 明确选择 **A：暂缓晋升**。因此 `Stream Contract Gate` 继续
`NON_BLOCKING`，本轮不修改 Branch Protection / Ruleset。C0-1～C0-5 已证明这两条 SSE
测试具有稳定 selection、确定性断言、真实失败敏感性、失败 Artifact 和恢复证据，已经达到 Owner
评审材料的质量；但实际目标分支 `main@533d4a3...` 尚未包含 remote-memory fixture 隔离，首次探针已证明
缺少该隔离会访问真实服务并返回 HTTP `401`。Required gate 的“无不受控外部依赖”条件因此尚未在 `main`
满足。

此外，公开 rulesets API 没有返回可见 ruleset，而 classic branch protection API 对未认证访问返回
HTTP `401`。这不足以证明 Required 已配置或未配置，所以平台强制状态仍不得标记为 `PR_BLOCKING`。

Owner 决定：**暂缓晋升并明确保持 `NON_BLOCKING`**；先把 `958b66b...` 的两行 fixture
隔离通过干净 PR 落入 `main`，在目标分支重新获得绿色 Stream run，再读取已认证的 Repository Settings
并决定是否设为 Required。

## 3. Blocking qualification review

| Criterion | Evidence | Assessment |
|---|---|---|
| Reviewed scope | exact selection 为两条 `integration and blocking and not real_llm` SSE case | `HUMAN_REVIEWED` |
| Deterministic selection | collection `2/8`，连续三次均 `2 passed, 6 deselected` | `PASS` |
| Failure sensitivity | intentional-red revision `07ee89c...` 使 run `33392294451` 的 pytest 真实 exit `1` | `PASS` |
| Failure attribution | failure JUnit 可定位 nodeid、`assert 1 == 2`、run、revision | `PASS` |
| Recovery | restore revision `d6553a9...` 的 run `33392789083` 重新绿色 | `PASS` |
| Artifact lifecycle | success/failure 均由 `if: always()` 上传 JUnit，retention 14 days | `PASS` |
| Controlled dependencies on evidence branch | real route + fake loop + persistence spy；`get_remote_memory_client -> None` | `PASS_ON_EVIDENCE_BRANCH` |
| Controlled dependencies on `main` | `main@533d4a3...` 不含上述两行隔离；首次探针曾触发真实 remote memory HTTP `401` | `FAIL_FOR_IMMEDIATE_PROMOTION` |
| Clean landing path | Draft PR #2 历史包含 intentional-red commit，不应作为普通 merge 直接进入 `main` | `REMEDIATION_REQUIRED` |
| Platform Required evidence | 没有已认证 Branch Protection / Ruleset 读取证据 | `UNKNOWN` |

## 4. Remote-memory isolation and delayed scope

remote memory 是项目的正式能力，而不是可以从产品范围删除的偶然依赖：README 将登录用户的 NagaMemory
云端与未登录时的本地 GRAG 记忆路径列为系统能力；`apiserver/routes/chat.py` 的 `/chat/stream` 在回答前
会调用 `get_remote_memory_client()` 做 RAG 记忆召回。

当前决定只调整测试真实性边界：

| Item | Status | Meaning |
|---|---|---|
| Remote-memory product feature | `LANDED` | 产品代码和 stream route 保持不变 |
| Remote memory inside the two blocking SSE contract cases | `ISOLATED` on evidence branch | fixture 把 `get_remote_memory_client` 固定为 `None`，避免认证/网络决定 SSE 契约结果 |
| Real remote-memory authentication/query/fallback verification | `DELAYED` | 当前不纳入 `Stream Contract Gate`；后续应使用独立 opt-in/integration 或 staging profile 验证 |
| Clean landing on `main` | `PENDING` | 证据 PR 历史包含 intentional-red commit；应另用干净 PR 只落地两行隔离 |

这不是“remote memory 不重要”，而是让每个测试只有一个清晰失败含义：Stream Check 失败优先表示 SSE
生命周期契约回归；真实 memory profile 失败才表示认证、网络、云端查询或回退行为异常。

## 5. Platform read-only inspection

### 5.1 Repository rulesets

```text
GET https://api.github.com/repos/tsukiyomu/NagaAgent-main/rulesets
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
HTTP 200
body: []
```

这个结果只证明：**未认证调用者没有看到 repository ruleset**。它不能排除 classic branch protection，
也不能替代 Owner 登录后的 Repository Settings 证据。

### 5.2 Classic branch protection

```text
GET https://api.github.com/repos/tsukiyomu/NagaAgent-main/branches/main/protection
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
HTTP 401
message: Requires authentication
```

因此 exact required status checks、目标分支适用规则和 enforcement 状态均为 `UNKNOWN`。内置浏览器访问
GitHub Settings 也在本环境中超时并显示“无法访问此站点”，没有生成可用的登录态截图。

## 6. Owner decision

Repository Owner 的选择为：

1. `A — DEFER_REQUIRED_PROMOTION`。
2. Stream Gate 保持 `NON_BLOCKING`；这是一项明确治理决定，不是配置状态的猜测。
3. remote memory 在当前两条 SSE 契约中隔离；真实 remote-memory 集成覆盖标为 `DELAYED`。
4. 没有授权或执行 GitHub 权限设置修改，也没有批准合并 PR #2。

重新评审 Required 的进入条件是：隔离通过干净 PR 进入 `main`、目标分支重新获得绿色 Stream run，且
Owner 能读取并保存适用于 `main` 的已认证 Branch Protection / Ruleset 证据。

## 7. Execution evidence and references

```text
uv run python -m pytest tests/integration/chat_stream/test_resilience.py
  -m=blocking -q
  --junitxml=tests/artifacts/closed_loop_v1/junit-stream-contract-c0-6.xml
exit 0
2 passed, 6 deselected, 3 warnings in 12.66s
JUnit: tests=2 / failures=0 / errors=0 / skipped=0

uv run python -m pytest tests/integration/chat_stream/test_resilience.py -q
exit 0
7 passed, 1 xfailed, 3 warnings in 13.54s
```

该执行证明当前证据分支的受控 remote-memory profile 下两条 SSE 契约仍通过；它不证明真实
NagaMemory 服务、认证、网络、云端查询或本地 GRAG 回退。完整文件中的唯一 `xfail` 仍是已知
user-stop contract gap，不属于 remote-memory failure。

- [`C0-5 Gate Record`](closed-loop-v1-c0-5-2026-09-01.md)
- [`C0-4 CI/CD report`](closed-loop-v1-c0-4-2026-08-31.md)
- [initial green run `33392018497`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392018497)
- [intentional-red run `33392294451`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392294451)
- [restored green run `33392789083`](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/33392789083)
- Evidence revisions: `main@533d4a3e464c6ce13b719145ce400099e6dcf32d`；evidence branch `d6553a96f6987c5f58fdafddb99fc28e19c72eb0`

## 8. Review boundary

- Human decision: `CONFIRMED — A / DEFER_REQUIRED_PROMOTION`
- Platform mutation: `NOT PERFORMED`
- Merge/release effect: `NONE`
- Required status claim: `NOT PROVEN`
- Closed Loop V1 result: `VERIFIED` as an evidence-and-decision loop；这不等于 Stream `PR_BLOCKING`。
- Next transition: 用干净 PR 只落地 remote-memory fixture 隔离；本 C0-6 工作单元不自动开始该下一任务。
- Publication boundary: `/docs/` 当前被 `.gitignore` 忽略；本记录存在于共享 workspace，但尚未提交或发布到 GitHub。
