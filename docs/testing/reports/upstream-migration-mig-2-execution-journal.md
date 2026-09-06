# MIG-2：Langfuse adapter 与确定性测试迁移

日期：2026-09-07。状态：`DONE`，仅指本工作单元。

## 1. 先看结论

Langfuse 的本地适配模块和测试已迁到 `codex/upstream-langfuse-sync`，并修复两类生命周期缺陷。
正式隔离回归为 **58 passed**；pytest-only 环境复核也通过。
这证明适配模块的已测契约，不代表聊天链路已经接回 Langfuse、真实 trace 已上传或 CI 已运行。

- 上游固定基线：`c2caa9079b9eb48129f550c43a5485231d404d3b`。
- 保留分支：`codex/c0-4-intentional-red@d6553a96f6987c5f58fdafddb99fc28e19c72eb0`，未改动。
- 本轮开始 HEAD：`e5209c55`；代码/测试提交：`c7122124f0491dee17f87b546f3d2561aa2622c5`。
- [迁移计划与验收](../plans/upstream-migration-plan.md)、[简明进度](../CURRENT_PROGRESS.md)、
  [Langfuse 架构及覆盖映射](../architecture/langfuse-observability.md)。

## 2. 这部分属于哪里，为什么这样迁移

### 保留现有能力，区分“模块存在”与“被运行时调用”

NagaAgent 的 `LLMService` 负责请求模型，`execute_tool_calls` 负责并发分派工具。
Langfuse adapter 则负责把这些过程的数据转换成观测记录；它是旁路，不是模型或工具执行器。

仓库证据是：旧 revision 保留 `apiserver/langfuse_integration.py` 和三个 helper 测试，但 LLM、tool、
chat、lifecycle 已没有调用 adapter；目标 upstream 也没有这些调用或 SDK 依赖。
此前 `MIGRATION_STATUS.md` 对 MIG-2 的限定是迁移 adapter/tests 并核对调用点。
因此本轮保留该范围，不依据历史架构示例自动恢复整条 runtime tracing 链路。

工程原则：迁移验收要区分代码资产、运行时调用和外部服务证据。
以后看到“文件与旧报告都在，但没有调用者”的模式，应检查真实接线；文件存在不是功能已启用的证据。

### 将 SDK 的整个 context 生命周期纳入异常隔离

旧 `start_observation` 只捕获 `start_as_current_observation(...)` 的创建异常，却将 context 直接交给 caller。
SDK 可能在 `__enter__` 或 `__exit__` 才失败；其退出返回值还可能吞掉业务异常。
用 fake SDK 注入这些故障后，正式隔离红灯复现了 22 个 context 相关失败 case。

改动是增加 `_safe_sdk_context`，供 observation 和 attribute propagation 共用：创建/进入失败时仍让
业务 body 执行一次；退出失败不替代业务结果；收到业务异常、`CancelledError` 或 `GeneratorExit` 时
清理已进入的 context 并重新抛出原异常对象。忽略 SDK 的 suppression 返回值。

工程原则：可选观测依赖不拥有业务异常的处理权。
识别线索是 `try: return sdk_context(...)`：它只包住创建，不覆盖 `with` 真正发生的进入与退出。
测试注入的是普通 SDK 异常；这不是对任意进程级中断、真实 SDK 内部状态或死锁的保证。

### 清理不应成为首次初始化入口

旧 flush/shutdown 调用 `get_langfuse_client()`；未使用过观测的进程也可能在清理时初始化 SDK，重复
shutdown 还会重复清理。另 4 个隔离红灯 case 暴露了这两种行为。

现在 cleanup 只读已存在 client；shutdown 先移除共享引用，再分别 best-effort 执行 flush 和 shutdown。
测试验证重复调用不重关 client，以及 flush 失败仍会尝试 shutdown。
同时修正了旧注释中“不阻塞退出”的过强承诺：同步 SDK 方法没有 adapter 级 deadline。

工程原则：资源创建与资源释放要有明确所有者，终止清理不应凭空创建待清理资源。
以后看到 cleanup 里调用“get-or-create”函数，应检查这个风险；长时间阻塞则要另用超时/线程模型处理。

## 3. 测试边界与执行中的修正

真实部分：从仓库源文件加载的 adapter。受控部分：SDK module/client/context/observation、dotenv 和合成配置。
API route、LLM、tool executor、Remote Memory 和真实 Langfuse 不在正式 unit 的执行路径内。

首次探针沿用旧测试的 package import。实际发现 `apiserver/__init__.py` 会立即导入 `api_server`，
在 fixture 生效前加载完整应用和配置；该次结果为 26 failed / 32 passed / 3 warnings。
没有对该导入过程做网络审计，因此它不作为“零外部依赖”的证据。
随后改用 `importlib` 从路径加载真实 adapter 文件，并重新取得隔离红灯结果后才修复产品模块。

正式 fixture 不读取项目 `.env`，清空 Langfuse 配置键，阻止真实 SDK 导入，并封锁 socket connect。
命令关闭第三方 pytest 自动插件和 conftest 加载，避免旧 Allure/全局 fixture 混入。
后续用只含 pytest 及其五个依赖的独立环境复核，进一步证明没有依赖旧应用环境才能通过。

保留三个旧 helper 测试，新增 17 个测试函数，总计 20 functions，经参数化展开为 58 cases。
没有将它们称为 58 个 Agent 业务场景。当前不恢复未注册的 `unit` marker；MIG-3 统一处理分层配置。
逐组断言、失败含义与真实性映射见 [Langfuse 架构页](../architecture/langfuse-observability.md)。

## 4. 可复核执行证据

工作目录：`F:\Programme\Agent\NagaAgent-main`。Python `3.11.7`；pytest `9.1.1`。

正式红灯命令（修复前的保留版 adapter + 已隔离的新测试）：

```text
.venv\Scripts\python.exe -m pytest --disable-plugin-autoload --noconftest tests/unit/test_langfuse_integration.py -q --tb=short --junitxml=tests/artifacts/upstream_migration/mig-2-isolated-red.xml
```

提交后的独立环境复核命令：

```text
uv run --isolated --no-project --offline --python .venv/Scripts/python.exe --with pytest==9.1.1 python -m pytest --disable-plugin-autoload --noconftest tests/unit/test_langfuse_integration.py -q --tb=short --junitxml=tests/artifacts/upstream_migration/mig-2-committed-green.xml
```

`--offline` 使用本机 uv cache；在未缓存 pytest 的机器上需要先准备依赖，并非所有新机器都可直接离线执行。
独立环境实际包清单：pytest 9.1.1、pluggy 1.6.0、iniconfig 2.3.0、packaging 26.3、Pygments 2.20.0、colorama 0.4.6。

| 检查 | 结果 | 证据含义 |
|---|---|---|
| 正式隔离红灯 | exit 1；26 failed / 32 passed，1.21s | 新测试确实检测到旧 adapter 的 context/cleanup 缺陷 |
| 修复后原虚拟环境 | exit 0；58 passed，0.49s；`mig-2-green.xml` | adapter 已测契约通过 |
| pytest-only 独立环境 | exit 0；58 passed，0.48s；`mig-2-minimal-green.xml` | 不依赖旧应用依赖或完整 API import |
| commit `c7122124` 后独立复核 | exit 0；58 passed，0.62s | 验证结果对应已保存代码 |
| 解析四份正式 JUnit | 均为同一组 58 test identities；green 无 failures/errors/skipped | 没有通过减少 selection 或 skip 把结果变绿 |
| `py_compile` 两个 Python 文件 | exit 0 | 语法可编译，不代表 API 启动通过 |
| 静态 test inventory | 1 file / 20 functions / 1 fixture；无 CI test command | 静态枚举与 58 参数化 case 是不同计数 |
| `git diff --cached --check` | exit 0 | 提交文件无 whitespace error |
| 文档链接与代码身份检查 | 6 份本轮文档的 51 个本地链接目标存在；adapter/tests blob 与 `c7122124` 一致 | 文档可导航，记录仍指向实际验证过的代码 |
| upstream 调用点与依赖搜索 | adapter 外没有 Langfuse 引用；未修改 dependency/lock/workflow | runtime 与 CI 状态仍是 `NOT_WIRED` |

本地原始证据保存在 `tests/artifacts/upstream_migration/`，未作为 CI Artifact 发布，也未纳入本轮 Git 提交：

- [隔离红灯 JUnit](../../../tests/artifacts/upstream_migration/mig-2-isolated-red.xml)，SHA-256：
  `2ba0db790e9ca6a8920f2080fd8b3f71d206bf6c87e068390bd62cfbfd6dadfa`。
- [提交后绿色 JUnit](../../../tests/artifacts/upstream_migration/mig-2-committed-green.xml)，SHA-256：
  `5d0bf198c6ebb6f137b7c7599bbdca2024a0a4345f55fc1e102081bca852fc78`。
- [静态 inventory](../../../tests/artifacts/upstream_migration/mig-2-inventory.md)。

Git blob：adapter `0e93294fd4cfdd4385b875de3ca65159f7dcb4c5`；tests `40d46b191dc14fcff85ad113d6915f3b7fdbd249`。

## 5. 审查与未证明项

本轮进行了作者自审，不作为独立 reviewer 或人类批准。审查关注 context 的异常所有权、测试 import 隔离、
共享 client 清理、保持已有 helper 字段，以及无 runtime/dependency/CI 扩张。
没有把历史业务接线示例复制进 upstream：例如当前 dispatcher 会跳过未知 agentType，旧示例却返回错误结果，
照搬会改变业务行为。实际调用点核对记录在架构页。

尚未证明或未实施：

- 真实 Langfuse SDK 兼容、鉴权、上报、UI 可见性和父子 observation 关系。当前环境也未安装 SDK。
- chat/LLM/tool/lifecycle 接线与 SSE、retry、并发工具的运行时回归。
- 数据脱敏、总 payload 字节预算、flush/shutdown 超时：截断不是脱敏，异常隔离不是有界退出。
- 全量 pytest、旧 Smoke/Stream GitHub workflows、Required Check 和完整目标 baseline。

没有 push、新 PR、merge、gate-policy 或 release 变更；已有用户未跟踪文件、备份目录和旧 artifacts 保留。
这些缺口不阻止原定 adapter/tests 迁移验收，但会阻止将本轮称为“真实 Langfuse 集成完成”。

下一步是 MIG-3：迁移兼容的测试基础设施和 CI 资产；MIG-4 再做回归与新 baseline 确认。
若后续要重新启用 Langfuse runtime，需要明确单独的接线、SDK、数据和集成验收范围。

## 6. 本轮技能如何影响工作

- [evidence-backed-execution-rationale](C:/Users/tsukiyomu/.codex/skills/evidence-backed-execution-rationale/SKILL.md)：以代码和红灯证据解释三项取舍，并加入可复用的识别线索；未增加 teach-back 阻塞。
- [agent-assisted-testing](C:/Users/tsukiyomu/.codex/skills/QA/agent-assisted-testing/SKILL.md)：促成 collection 级隔离、负向回归和真实/fake 边界说明。
- [test-engineering-doc-mapper](C:/Users/tsukiyomu/.codex/skills/QA/test-engineering-doc-mapper/SKILL.md)：将局部 unit 证据映射到观测模块，纠正“helper 测试证明 SSE”的旧表述。
- [plan-progress-checkpoint](C:/Users/tsukiyomu/.codex/skills/plan-progress-checkpoint/SKILL.md)：沿用 MIG-2 和单条 ledger，不把局部验证提升为全迁移完成。
- [code-review-and-quality](C:/Users/tsukiyomu/.codex/skills/code-review-and-quality/SKILL.md)：按正确性、结构、安全和性能审查，并保留真实接线前必须复核的限制。
