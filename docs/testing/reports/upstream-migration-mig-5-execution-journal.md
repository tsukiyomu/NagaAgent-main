# MIG-5 Langfuse runtime 恢复 — Execution journal

**Context：** MIG-0～MIG-4 完成本地迁移后，用户要求继续补齐“Langfuse 真正可用”，复用原局域网部署和凭据。

**Plan / task：** [upstream-migration-plan，第 9 节](../plans/upstream-migration-plan.md#9-mig-5-scope-and-acceptance-user-authorized-extension)，run `UPMIG-5`。

**Status：** `DONE`，2026-09-08；代码 `7c88065cda77838eda02316c8c0cd75e589430ed`，本地回归和提交后 LAN 上传/读回均通过。未 push / PR / merge。

## Result and plan alignment

chat route、三处 LLM 调用、单个工具任务和 API lifecycle 已接入；每次请求独立 trace，沿产品 session 分组，
重试按实际调用记录。观测上下文不跨 `yield` 悬挂；SDK 普通异常不改变业务结果，清理不在事件循环同步等待。
SDK 固定为 4.15.1，沿用现有 `.env` 与 LAN 服务 3.172.1，未改 key 或服务器。
默认不上传聊天正文；显式正文开关经过限长和脱敏。用法与设计依据在 [Langfuse 当前说明](../architecture/langfuse-observability.md#mig-5-当前用法与证明范围)。

**Compared with plan：** 与 MIG-5 验收范围对齐；MIG-0～MIG-4 的历史排除项没有被回填为当时已完成。
首次新 wiring 断言错误地期待 `[DONE]`；源代码和实际输出说明当前真实 LLM 路径以 `round_end` / 迭代耗尽结束，
因此修正新探针的范围，未修改产品协议或旧 Gate 测试。完整回归还发现两个新增文件同名，已重命名 integration 文件后重跑。
初次 SDK 下载超时后提高下载超时重试成功；原有锁定依赖版本没有变化，仅新增 SDK、OTLP HTTP exporter 和 wrapt。

## Evidence and proof limits

| Acceptance claim | Evidence and context | Observed result | Proof boundary |
|---|---|---|---|
| 现有 LAN 配置可用 | 读取根 `.env` 的三项配置；health 和带认证 projects API | HTTP 200；原服务 3.172.1 | 未输出 key，未调查历史停用的业务原因；旧提交只证明曾移除接入 |
| 适配与 runtime 契约 | [58 原 adapter cases](../../../tests/unit/test_langfuse_integration.py) + [9 runtime cases](../../../tests/unit/test_langfuse_runtime.py)，`runtime.xml` | 67 passed；含真实 SDK / 内存 exporter、session、parentage、交错流、关闭/取消、并发、隐私和有界等待 | 单测中的取消不等于浏览器 user-stop 语义完成；SDK 异常隔离不承诺任意 SDK 调用永不阻塞 |
| 实际调用点贯通 | [chat wiring](../../../tests/integration/observability/test_langfuse_chat_wiring.py)，`route-sdk-fixed.xml` | 内存版 1 passed，LAN 默认 skip；两条请求、四次 provider 调用、一次工具执行，共 7 spans | 真实 route/Loop/LLMService/dispatcher/SDK；provider、prompt、MCP 结果固定，保存 spy、memory 禁用 |
| LAN 上传及读回 | 提交后运行 [显式探针](../../../scripts/verify_langfuse_lan.py)；[长期机器清单](upstream-migration-mig-5-evidence.json) | **1 passed，23.21s**；2 traces / 7 observations，session、父子关系、结束时间、合成输出均匹配 | 真 SDK + 真 LAN 服务，未验收 UI 浏览器交互、真实模型、MCP/Memory、持久化回读 |
| 原有测试不回退 | `full-fixed.xml/json/log`，frozen `.venv`，MIG-5 工作树随后提交为 `7c88065c` | **189 passed、2 skipped、2 xfailed、12 subtests passed**；JUnit 193 records / 0 failure / 0 error / 4 skipped（含 xfail） | real-LLM 和 LAN 两个 opt-in 跳过；两个原 xfail 保留。没有新 GitHub run、Allure 重验或性能晋升 |
| 变更可追溯 | 同目录机器清单含代码 revision、源码/证据 SHA-256、完整命令及服务端 observation 白名单 | 本地代码提交完成；`git diff --check` 通过；仅增三项依赖 | 无 secret、无真实聊天历史入库；历史备份及用户未跟踪文件未纳入提交 |

最终验收 trace（在原项目 Traces 中按 ID 查找）：

- `chat.request`：`03113930b57d2212f2dd1b2a771b45a6`
- `chat.stream`：`1cc6f5b8332388ce533e546375f466ab`

本轮提交前、提交后各成功执行一次 LAN 探针，合计保留 **4 条合成 trace**，未删除原有数据。
默认正文开关仍为关闭；仅探针进程为合成数据显式开启。现有 NagaAgent 进程须重启才能加载接线，未强制重启用户应用。
Langfuse 仍是诊断侧通道，不是 pytest / CI 的真相源；Remote Memory 真实集成继续 `DELAYED`。

复现：先 `uv sync --frozen --group test`。离线回归设置 `NAGA_ENABLE_REAL_LLM_TESTS=0`、
`NAGA_ENABLE_LANGFUSE_LAN_TESTS=0`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，执行
`uv run --frozen python -m pytest -p pytest_asyncio.plugin tests -q --tb=short`。
LAN 验收执行 `uv run --frozen python scripts/verify_langfuse_lan.py --confirm-synthetic-upload`，会新写两条合成 trace。
本地原始证据位于 [`tests/artifacts/upstream_migration/mig-5/`](../../../tests/artifacts/upstream_migration/mig-5/)；
长期清单单独纳入 docs，未批量提交运行产物。

## Next step

回到 [P3-0](../plans/nagaagent-final-testing-plan.md)，以现有代码、测试和已可用的 trace 辅助整理基础 Agent workflow；本单元未启动 P3-0。
