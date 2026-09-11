# P3-0 收口当前基线 — Execution journal

**Context：** 为后续基础 Agent workflow 学习固定一个可复验、带已知风险的起点，分开旧故障注入历史与迁移后的正常开发分支。

**Plan / task：** [Final Testing Plan / P3-0](../plans/nagaagent-final-testing-plan.md#p3-0收口当前基线)，run `P3-0-2026-09-11`，承接 9 月 10 日本地验收。

**Status：** `DONE`。同一 revision 的本地全套、Smoke / Stream GitHub CI、JUnit 下载解析及 Owner 决定均已齐全。9 月 10 日的 `REVIEW_NEEDED` 保留在计划 ledger；9 月 11 日补齐原验收，不缩减完成条件，也不启动 P3-1。

## Result and plan alignment

验收代码为 `codex/upstream-langfuse-sync@357a8a6f553882fd68ac9c951b0ae92422ccae1c`，runtime 代码来自 `7c88065c`。
Owner 于 9 月 11 日选择 `tsukiyomu/NagaAgent-main` 并要求关闭 PR #2。已发布迁移分支，并用现有
`workflow_dispatch` 分别触发两条 CI；无需为取证新建 PR。PR #2 在 `2026-09-11T07:46:09Z`
关闭且未合并，证据分支仍为 `d6553a96...`；main 前后均为 `533d4a3e464c6ce13b719145ce400099e6dcf32d`。
本单元未修改应用、测试、workflow 或 lock；收口变更只包含文档与机器证据索引，不把后续文档提交冒充上述已测试 revision。

Remote Memory fixture 隔离已在 `981821be7b971c4123c8f41d7a77f176970cd872` 迁入，当前 resilience 文件与
恢复绿色的 `d6553a96...` 内容完全一致；后者不是当前分支祖先。因此不重复 cherry-pick，也不合并故障注入 PR 来获取已有隔离。
这是对计划旧实施假设的适配，仍保留“目标分支有隔离且可复验”的目标。

**Compared with plan：** 原验收已全部满足。9 月 10 日全套回归与 9 月 11 日远端 selection 绑定同一代码，
因此不为文档收口重复修改 fixture 或测试断言。PR #2 关闭前是 open、非 Draft；关闭后经 API 读回验证。
Langfuse 复核风险照实登记，没有修复或宣布关闭。

## Evidence and proof limits

精确命令、环境、JUnit testcase 标识、文件 hash、source blob 与只读 GitHub 快照集中于
[机器证据](p3-0-baseline-evidence.json)；原始产物分为 [9 月 10 日本地](../../../tests/artifacts/final_plan/p3-0-2026-09-10/)
与 [9 月 11 日远端取证](../../../tests/artifacts/final_plan/p3-0-2026-09-11/)。
本地环境为 Windows、Python 3.11.7、frozen `.venv`，两个 real-service opt-in 均为 0。
CI 使用 `ubuntu-latest`、Python 3.11、`uv sync --frozen --group test`；real LLM 显式关闭，LAN 未启用，插件自动加载关闭。

| 验收 / Pipeline 阶段 | 实际结果 | 证据与证明边界 |
|---|---|---|
| 候选 revision 与 fixture 来源 | `PASS`；来源 `981821be`，与恢复后文件一致，不含 C0 分支祖先 | 当前 Git tree、file diff、ancestry；没有宣称已落入远端 main |
| 本地 Smoke selection | `PASS`；3 passed，pytest 8.30s，exit 0 | [JUnit](../../../tests/artifacts/final_plan/p3-0-2026-09-10/smoke.xml)；真实路由 + fake LLM/Loop，断言 health 字段、固定回复/session、SSE 正文/terminal；不证明下游服务健康 |
| 本地 Stream selection | `PASS`；2 passed / 6 deselected，pytest 6.66s，exit 0 | [JUnit](../../../tests/artifacts/final_plan/p3-0-2026-09-10/stream.xml)；真实路由 + fake Loop / save spy，断言正常事件顺序、保存入参、唯一终止、异常 error 与 active cleanup；不证明真实 Loop/模型/落库回读 |
| 完整离线回归 | `PASS`（保留已知 gaps）；189 passed / 2 skipped / 2 xfailed + 12 subtests，pytest 122.65s，exit 0 | [JUnit](../../../tests/artifacts/final_plan/p3-0-2026-09-10/full.xml)；分组真实性见 [当前基线](../architecture/upstream-testing-baseline.md)，不等于完整 Agent E2E |
| CI checkout / Python / uv / 依赖安装 | `PASS`；两个 job 的对应 step 均 success | API job/step 记录；证明本次 runner 安装与接线，不证明所有 OS 或无缓存环境 |
| GitHub Smoke test / upload / download | `PASS`；[run 34576477047](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/34576477047)，JUnit `3 / 0 failures / 0 errors / 0 skipped` | test、upload 均 success；ZIP 已下载验 digest，解析 [XML](../../../tests/artifacts/final_plan/p3-0-2026-09-11/smoke-34576477047.xml)，用例集合与本地相同 |
| GitHub Stream test / upload / download | `PASS`；[run 34576480832](https://github.com/tsukiyomu/NagaAgent-main/actions/runs/34576480832)，JUnit `2 / 0 failures / 0 errors / 0 skipped` | test、upload 均 success；ZIP 已下载验 digest，解析 [XML](../../../tests/artifacts/final_plan/p3-0-2026-09-11/stream-contract-34576480832.xml)，用例集合与本地相同 |
| PR #2 与 Owner 决定 | `PASS`；目标 origin；PR `closed / merged=false`，证据分支保留 | [GitHub PR](https://github.com/tsukiyomu/NagaAgent-main/pull/2)、[前后状态](../../../tests/artifacts/final_plan/p3-0-2026-09-11/pr2-disposition.json)；不改变 main 或 Required |
| Current Progress / Architecture | 当前计划、候选、结果、风险与 `PARTIAL` 范围已同步 | [Current Progress](../CURRENT_PROGRESS.md)、[overview](../architecture/overview.md)、[baseline](../architecture/upstream-testing-baseline.md)、[CI](../architecture/ci-pr-gate.md)；Part 细节和 P3-1 workflow 映射未全部复核 |
| Build / deploy / real services | `NOT_RUN` | 无打包、部署、规则变更、真实 LLM、Memory/MCP 或新 Langfuse 上传；无性能/发布批准 |

JUnit 计数说明：本次 full XML 有 **193 个 testcase 元素**；`testsuite.tests=205` 将 12 个子测试计入，
`skipped=4` 包含 2 个 opt-in skip 和 2 个 xfail。不能把 205 当作独立测试用例数，也不能把两个 xfail 写成通过。
证据汇总脚本首次把 suite 计数等同于 testcase 数而报错；检查 XML 后修正汇总口径，原 JUnit 和测试断言没有改动。

远端两个 Artifact 均为 attempt 1，保留至 `2026-09-25T07:53:22Z`。长期索引保存 ID、完整 digest、
用例、run、revision 和步骤结果；原 ZIP/XML 留在本地生成目录，不把 14 天托管留存当成永久下载保证。
下载时只在 GitHub API 请求中使用现有凭据；跟随签名下载地址时不携带 GitHub 认证头，凭据与签名 URL 均未记录。

## Known risks and governance

- user-stop 与跨轮 duplicate tool-call ID 保留 executable xfail，分别属于 P3-3 / P3-2。
- 9 月 8 日 Langfuse 合成探针确认：多轮根输出漏前轮、提前关闭依赖后续内层清理、JSON 字符串内 password 未脱敏。
  [历史探针](../../../tests/artifacts/upstream_migration/mig-5/review-boundary-probes-2026-09-08.json) 绑定同一源码，本轮未重新运行或修复；具体含义见 [风险表](../architecture/upstream-testing-baseline.md#6-未完成范围与阅读规则)。
- 9 月 10 日只读确认保存的正文开关仍为 true；9 月 8 日重启/真实正文读回是历史已观察事实，本轮未重新验证活动进程或服务端。
- 旧 C0 Required 与 red/green 证据保留其原 revision。Stream 暂缓 Required、真实 Remote Memory `DELAYED` 的 Owner 决定不变。
  当前仓库已选定，但本轮未重新验证实际 Required，仍记为 `UNKNOWN`，没有晋升门禁。

可展示价值是基线治理：能说明正常开发分支怎样保留隔离而不引入故障注入历史，怎样用 revision、JUnit、已知缺口界定结论。
可以写成“迁移分支完成同 revision 的本地回归与两条 GitHub CI / JUnit 验收”；不能写成
“完整 pytest 已在 GitHub 运行”“新 revision 重做了负向红灯”“失败必然阻止合并”或“所有 Langfuse 边界已修复”。

## Next step

下一工作单元为 **P3-1：基础 Agent workflow 理解**，走读无工具、工具调用和 summary 三条代表路径；
本轮不启动，不自动合并 main、改变 Required 或修复其他工作单元。
