# MIG-3：测试与 CI 资产迁移执行记录

> 日期：2026-09-07 · Run ID：`UPMIG-3` · 状态：`DONE`\
> 代码提交：`981821be7b971c4123c8f41d7a77f176970cd872`\
> 分支：`codex/upstream-langfuse-sync`；后续验收见 [MIG-4 报告](upstream-migration-mig-4-execution-journal.md)。

## 1. 结果与范围

旧分支的测试基座、分层 pytest、五个 Golden 场景、报告 helper 和两个 PR workflow
已迁入新 upstream 代码树。产品代码、上游自带测试和 Release workflow 没有被旧版本覆盖。
本次最大的适配不是修改业务断言，而是让测试在**收集阶段就不读取开发者配置、不连接外部服务**。

用户授权连续完成 MIG-3 / MIG-4。MIG-3 负责可兼容资产迁入，MIG-4 负责独立环境回归和新基线。
没有 push、创建 PR、merge、修改 Required Check，也没有恢复 Langfuse 运行时或调用真实服务。

固定输入：上游 `c2caa9079b9eb48129f550c43a5485231d404d3b`；保留来源
`d6553a96f6987c5f58fdafddb99fc28e19c72eb0`。两条历史没有共同祖先，继续按文件选择性迁移，不合并历史。
原 ZIP 与来源分支未改动，备份详情见 [迁移计划](../plans/upstream-migration-plan.md)。

## 2. 迁入与保留清单

| 资产 | 本次处理 | 用途与边界 |
|---|---|---|
| `pytest.ini`、root conftest、support helpers | 恢复并适配 | marker、fixture、结果归因与报告入口 |
| Smoke、SSE resilience、Loop unit、归因 unit | 迁入原断言 | API 协议、收尾和 Loop 编排回归；不验证真实模型质量 |
| 五个 Golden YAML、runner/schema tests | 迁入 | 用固定模型输出和工具结果验证任务编排；不是完整真实 E2E |
| 两份 `tests/baseline/quality_gate/*.json` | 原样保存 | **历史数值，不自动作为新版本性能标准** |
| Smoke / Stream PR workflows | 迁入并固定离线环境与插件 | 保留 Check 名称、精确 selection、JUnit 与 `if: always()` 上传契约 |
| `pyproject.toml` / `uv.lock` | 加入 test group 依赖 | 六个测试相关包新增；所有已锁定产品包版本未变 |
| Langfuse 58 cases | 只补回已注册的 `unit` marker | MIG-2 adapter 契约不变，运行时仍未接线 |
| 上游三个测试文件 | 字节不变 | 配置/工具名、Live2D assets、更新路由与 TTS 的现有断言保留 |
| 新增 offline bootstrap 与 5 cases | 新实现 | 提前隔离配置和连接，检验隔离本身 |

共恢复 30 个原先不存在的来源资产；加上适配/新增文件，代码提交包含 35 个文件。
这不是 5,582 行全新开发：大部分是保留分支已有资产的迁移。

## 3. 关键工程判断：为什么这样适配

### 3.1 为什么不能只把旧 fixture 复制过来

源码事实：[`system/config.py`](../../../system/config.py) 的 `get_config_path()` 优先读取项目根目录
`config.json`；[`apiserver/__init__.py`](../../../apiserver/__init__.py) 导入时就加载 API。
Golden/Loop 测试在模块导入阶段触达这些代码，普通 function fixture 此时还没开始执行。

风险是：测试尚未运行断言，就可能读取开发者凭据、用户历史状态，或初始化外部连接。
因此在 [`tests/conftest.py`](../../../tests/conftest.py) 导入应用之前安装
[`OfflineBootstrap`](../../../tests/support/offline_bootstrap.py)：

- 将测试进程中的 `Path.home()` / `APPDATA` 指向临时目录；不移动或删除真实用户目录。
- 仅让配置选择逻辑看不到真实项目 `config.json`，仍执行产品自己的优先级代码；上游测试创建的临时配置仍可见。
- 禁用 dotenv 自动载入、移除所列模型/Langfuse 环境凭据，关闭 OTEL，并让 LiteLLM 使用本地 cost map。
- 拦截 Python TCP 连接入口，只放行标准库 `socketpair` 为 Windows asyncio 创建的私有 self-pipe。

这属于**控制测试输入而保留被测逻辑**。识别线索是“配置在 import 时读取”：看到这个模式，隔离必须早于 collection，不能仅靠请求 fixture。
五个隔离测试及上游配置优先级测试共同验证这次适配没有把优先级算法整体替换为假实现。

### 3.2 为什么捕获网络异常还不够

应用可能捕获连接异常并走 fallback；单纯抛异常仍可能让 pytest 显示通过。
因此 bootstrap 记录连接尝试，autouse teardown 把被吞掉的尝试转成测试错误，session finish
也检查 collection 阶段的尝试。负向探针故意吞掉 `RuntimeError`，最终仍得到 exit `1` 和 JUnit error。

这属于**测试失败不能被被测系统的容错逻辑吞掉**。它是 Python 测试进程的连接护栏，不是操作系统防火墙；
不能据此声称拦截了任意子进程、UDP、DNS 或 native library 的全部联网方式。当前 suite 未验证这些路径。

### 3.3 为什么保留上游代码和旧缺口

上游 Loop 已有 MCP 名称还原和 assistant reasoning 回放等变化。回填旧产品文件会覆盖这些改进，
因此只迁测试资产，保留现有产品实现和上游测试。回归没有要求弱化业务断言。
两个既有 `xfail`（user-stop、跨轮重复 tool id 去重）保留原标记，不把它们当作已修复。

### 3.4 为什么报告基线和代码基线分开

旧 JSON 的延迟来自旧 revision / 环境。它们保留供历史解释，但 MIG-4 显式指定新的本地
advisory 目录，不覆盖旧 baseline，也不以新环境一次执行作为性能晋升依据。
两个 PR job 继续以 pytest 退出码决定成败，不接入 Quality Gate 的诊断判级。

## 4. 执行与验证

本地原 `.venv` 的预检查（Python 3.11.7；明确禁用插件自动加载，只启用 pytest-asyncio）：

| 检查 | 实际结果 | 证据文件（本地） |
|---|---|---|
| Smoke 初探 | `3 passed`，exit 0 | `mig-3-smoke-probe.xml` |
| 初次完整回归，尚未加入 5 个隔离测试 | `174 passed, 1 skipped, 2 xfailed`，另有 12 个 subtests passed | `mig-3-full-probe.xml` |
| 隔离测试 + Smoke + resilience | `15 passed, 1 xfailed`，exit 0 | `mig-3-isolation.xml` |
| 吞掉网络异常的负向探针 | exit 1；JUnit 1 error，符合预期 | `mig-3-guard-negative.xml` |
| `uv lock --offline` | 成功；仅六个测试包新增 | `uv.lock` diff |
| 独立环境 `uv sync --frozen --group test --offline` | 成功，安装 156 个包 | `mig-4/sync.log` / `sync.json` |
| YAML 结构、selector、JUnit 路径、上传契约检查 | 通过；不是 GitHub runner 实际运行 | 两份 workflow + 本地静态检查 |
| 保护路径 diff、staged whitespace check | 通过；产品/上游测试/Release 未改 | `git diff` / 代码提交 |

上述 XML 位于 [`tests/artifacts/upstream_migration/`](../../../tests/artifacts/upstream_migration/)。
它们是本地原始证据，没有上传为 GitHub Artifact。最终同 revision 的完整复验与 hash 以 MIG-4 为准。
独立环境 sync 发生在代码提交前，元数据 HEAD 为 `505c4742` + 待提交 test group/lock；
提交后所有 MIG-4 pytest 均使用 `981821be`、相同 lock 和 `uv run --frozen`。

## 5. 自查与剩余边界

按测试风险控制核对了真实/替身依赖、失败归因和 Gate 边界；按代码质量检查核对 diff、依赖变化和负向结果。
这是执行者自查，不是假称独立 reviewer 已批准 merge。

- 迁入 workflows 不等于已在 GitHub 上运行，更不等于 Required。
- Langfuse 只有 adapter + fake SDK 单测；SDK 依赖、chat/LLM/tool/lifecycle 接线仍缺失。
- Remote Memory 仍是产品功能；测试中隔离，真实集成 `DELAYED`。
- 独立 frozen 环境仅在 Windows 复验；Ubuntu runner 尚未验证。
- 临时目录若被 Windows 日志 handler 占用可能保留；真实用户数据与原 `.venv` 未被清理。
- 上游若改变 config 加载路径或网络实现，需要同步调整隔离契约，不能“一劳永逸”。

MIG-3 结束后按用户授权继续 MIG-4，不增加人工暂停点。
