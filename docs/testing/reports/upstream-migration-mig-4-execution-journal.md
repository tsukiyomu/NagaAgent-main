# MIG-4：回归验收与新测试基线

> 日期：2026-09-07 · Run ID：`UPMIG-4` · 状态：`DONE`\
> 验收对象：`codex/upstream-langfuse-sync@981821be7b971c4123c8f41d7a77f176970cd872`\
> 结论：**本地测试基线通过；远端 CI 与真实外部服务不在本次验收中。**

## 1. 执行概览

MIG-3 迁入的测试与上游原有测试可以在同一个独立 frozen-lock 环境中运行：
`179 passed, 1 skipped, 2 xfailed`，另有 `12 subtests passed`，没有非预期失败。
启用 Allure / Quality Gate 后结果和用例身份集合一致；两组 CI 选测分别连续三次通过。

本次提名的是**可继续开发的本地代码/测试基线**，不是性能基线、线上完整闭环、发布批准或 Required 晋升。
机器可核对的版本、JUnit SHA-256、选中用例、已知缺口及报告统计见
[`upstream-migration-mig-4-baseline.json`](upstream-migration-mig-4-baseline.json)。

环境：Windows，Python 3.11.7，pytest 9.1.1，pytest-asyncio 1.4.0，allure-pytest 2.16.0。
独立环境为 `.pytest_cache/mig4-venv`，通过 `uv sync --frozen --group test --offline` 从本机缓存创建，
没有替换原 `.venv`。这证明本地缓存下的 lock 可安装，不证明干净 Ubuntu 网络安装成功。

## 2. 验证阶段

以下是本地执行阶段，不是虚构的 GitHub pipeline run。

| 阶段 | 结果 | 原始证据，均位于 `tests/artifacts/upstream_migration/mig-4/` |
|---|---|---|
| Frozen 安装 | exit 0，156 packages installed | `sync.log` / `sync.json` |
| 完整 pytest | 179 passed / 1 skipped / 2 xfailed，exit 0；pytest 42.22s | `full.log` / `full.json` / `full.xml` |
| Smoke selection | 精确 3 条；三次均 3 passed | `smoke-collect.log`、`smoke-1/2/3.xml` |
| Stream selection | 精确 2/8 条；三次均 2 passed、6 deselected | `stream-collect.log`、`stream-1/2/3.xml` |
| 故意 assertion mismatch | exit 1，JUnit 1 failure，符合预期 | `probe-assertion.log/json/xml` |
| 故意吞掉连接异常 | exit 1，JUnit 1 teardown error，符合预期 | `probe-offline_guard.log/json/xml` |
| Allure + Quality Gate 全套复跑 | 同样 179 / 1 / 2，exit 0；pytest 31.24s | `quality.log/json/xml`、`allure/`、`quality/` |
| 产物解析与一致性 | 完整/报告用例身份相同，三次选测身份相同，Allure 附件无缺失 | 本报告及 baseline JSON |
| 工作树、依赖、workflow 静态自查 | 产品和上游三个测试文件未改；已有依赖版本未变；YAML/上传路径符合契约 | MIG-3 commit、`uv.lock`、两份 workflow |

重复测试只说明这三次没有观察到 selection 漂移或失败，不作长期“零 flaky”承诺。

## 3. Gate 决策与证据边界

| 对象 | 当前目标分支状态 | 不能推导的结论 |
|---|---|---|
| Smoke / Stream workflow 文件 | `LANDED`，本地等价 selection `VERIFIED` | 未发布，不宣称新 revision 已有 GitHub green/red/upload |
| pytest exit code | 通过/故障两类路径已验证 | JUnit 或 Allure 不能把失败改成成功 |
| Required Check | `UNKNOWN_ON_TARGET`；未读取或更改平台规则 | Check 名字包含 Blocking 不证明禁止合并 |
| Stream Owner 决定 | 保留此前暂缓晋升 Required 的范围 | 不因迁移自行升级策略 |
| Quality Gate | 本地诊断输出；未接入两个 PR job | `gate_result=pass` 不等于全套测试、性能或发布批准 |
| 旧 C0 GitHub 证据 | 仍绑定旧 revision | 不继承为新 upstream 的远端执行证据 |

两份 workflow 保留 `if: always()`、缺报告时报错和 14 天保留期；本次只静态核对该契约。
负向 probe 是独立的本地合成测试，不改业务断言、不提交故障分支、不代表本次 GitHub 真的变红。
其源码保存在本地 `tests/artifacts/upstream_migration/probe_assertion.py` 与 `probe_offline_guard.py`，
文件名不匹配常规 `test_*.py` 收集规则。

## 4. 测试覆盖与报告口径

| 已执行集合 | 结果 | 保留下来的真实行为 / 仍受控部分 |
|---|---|---|
| 上游三个测试文件 | 56 passed，另有 12 subtests passed | 原断言原样执行；配置、工具名、assets、更新/TTS 的测试边界不扩张 |
| Langfuse adapter | 58 passed | 真实 adapter + fake SDK；没有 trace 上传 |
| Smoke | 3 passed | 真实 FastAPI 入口；模型/Loop/副作用受控 |
| SSE resilience | 7 passed、1 xfailed | route 收尾真实；分组使用 fake Loop 或真实 Loop + fake LLM |
| Loop unit | 19 passed、1 xfailed | 真实编排/分支；模型、工具、queue/compression 按用例替换 |
| API failure attribution | 7 passed | 测试侧归因结构，不是实际生产异常覆盖率 |
| Golden 任务 / runner / schema | 5 + 5 + 9 passed | 五个 YAML 场景、固定输出和规则断言；不是五个真实线上 E2E |
| Quality report helper | 5 passed | 规则/指标/报告结构 |
| Offline bootstrap | 5 passed | 早期配置/连接隔离、恢复与 socketpair 例外 |
| opt-in real LLM | 1 skipped | 未授权真实调用，不能计作通过 |

JUnit 实际为 **182 testcase / 0 failure / 0 error / 3 skipped**。
pytest 将两个 `xfail` 也编码为 JUnit skipped；因此 XML 的 3 skipped 与控制台的 1 skipped + 2 xfailed 一致。
12 个 unittest subtests 不增加本次 JUnit testcase 数，不能再加到 182 上。

Allure：182 个 result JSON（179 passed、3 skipped），104 个附件文件，引用的附件均存在。
这里只验证原始结果及附件，**没有生成或浏览 HTML 报告**。

Quality Gate：只汇总 `p2_api` / `agentic_tool_loop` 的 32 条记录，29 passed，其余为 skip/xfail，
`failed=0`、`warned=0`、`gate_result=pass`。它没有覆盖全部 182 条，也不包含 Langfuse/Golden 等完整集合。
本次显式使用新的本地 advisory 目录，报告 `baseline_bootstrap=true`、各 regression delta 为 null；
helper 自动生成的 `stub_main.json` **仅是诊断种子，未晋升或提交为性能标准**。
原 `tests/baseline/quality_gate/*.json` 保持来源内容；默认 CLI 仍会读取它们，后续目标分支诊断应显式指定 baseline 目录。
进程内 TestClient 延迟不等于真实网络 TTFB，本次不能声称无性能回退。

## 5. Build / Deploy

`NOT_RUN`。Build & Release workflow 保持上游原样；没有构建发布包、创建 Release、部署或回滚。
没有 push / PR / merge。代码验收 revision 为 `981821be`；随后文档提交不改变被测产品/测试树。

## 6. 已知缺口与风险

- `test_chat_stream_user_stop_contract_gap`：已有预期失败；运行时尚无明确 user-stop / 取消收尾契约。
- `test_duplicate_tool_call_id_is_deduplicated_across_rounds`：已有预期失败；跨轮重复 id 去重尚未实现。
- 两个 `xfail` 均保留来源的非 strict 标记。本轮无 XPASS；未来变绿后仍需主动复核并移除标记，不能依赖它自动报错提醒。
- 四个依赖弃用 warning：LiteLLM 的 Pydantic config、importlib resources，以及 websockets 两类旧接口。
  本次未升级产品依赖消除 warning。
- Langfuse 的 SDK 安装、运行时接线、真实 SDK 兼容、trace 父子关系和数据脱敏仍未完成。
- Remote Memory 保留为产品特性，真实认证/query/fallback `DELAYED`；LLM、MCP、持久化回读和完整 E2E 未验证。
- 隔离护栏只覆盖已检查的 Python 配置与 TCP 入口，不是安全沙箱。显式 `NAGA_ENABLE_REAL_LLM_TESTS=1` 会关闭该全局离线隔离，本次没有启用。
- 只有本地 Windows 证据；新 revision 的 Ubuntu Actions、Artifact upload/download、Required 状态未验证。

两个合成红灯被归类为**预期负向探针**，不是产品缺陷；两个既有 xfail 是**已知契约缺口**，不是本轮迁移新增失败。

## 7. 这一步的工程价值

这次工作的价值是让“换到新上游后还能信任哪些测试”有可核对的答案：保留上游改动、前移隔离边界、
验证异常不会被吞成假绿、核对选测身份和报告产物，并把历史远端证据与当前本地结果分开。
它可用于展示迁移与测试治理能力，但不应写成新增 179 个业务场景、完整 Langfuse 平台或全产品 E2E。

## 8. 下一步与文档状态

MIG-0～MIG-4 的本地迁移工作已完成，P3-0 的迁移前置条件已满足；**本次不自动启动 P3-0**。
后续可基于新基线整理基础 Agent workflow 的学习/测试范围。若优先启用 Langfuse，需要另行恢复并验证运行时调用链。
远端 CI 发布与验收需要后续明确授权，不能把本次 DONE 当成远端全部完成。

Current Progress、Migration Status、计划状态及架构入口已同步；模块级全部历史细节没有逐行重新认证，
更详细的架构梳理仍属于后续 P3-0。映射入口见 [新测试基线说明](../architecture/upstream-testing-baseline.md)。
收尾检查通过：本轮 58 处新增/修改的本地文档链接可解析；基线记录的代码文件/JUnit hash 匹配，
来源分支仍为 `d6553a96...`，迁移五个单元均标记 DONE，代码提交之后的变更仅为文档。

## 9. 复现与证据索引

在项目根目录的 PowerShell 中，使用独立环境并显式选择插件：

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.pytest_cache/mig4-venv"
$env:NAGA_ENABLE_REAL_LLM_TESTS = "0"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
uv sync --frozen --group test --offline
uv run --frozen python -m pytest -p pytest_asyncio.plugin tests -q --tb=short --junitxml=tests/artifacts/upstream_migration/recheck/full.xml
uv run --frozen python -m pytest -p pytest_asyncio.plugin tests/smoke -m "smoke and blocking" -q
uv run --frozen python -m pytest -p pytest_asyncio.plugin tests/integration/chat_stream/test_resilience.py -m "integration and blocking and not real_llm" -q
uv run --frozen python -m pytest -p pytest_asyncio.plugin -p allure_pytest.plugin tests -q --alluredir=tests/artifacts/upstream_migration/recheck/allure --quality-gate --quality-gate-artifacts-dir=tests/artifacts/upstream_migration/recheck/quality --quality-gate-baseline-dir=tests/artifacts/upstream_migration/recheck/advisory-baseline
```

`--offline` 安装要求本机已有依赖缓存；缺缓存不表示产品测试失败。上述 `recheck/` 避免覆盖本次证据。
实际命令 argv、exit code、耗时与 revision 位于每次运行同名 `.json`；完整 stdout/stderr 位于 `.log`。

- [完整 JUnit](../../../tests/artifacts/upstream_migration/mig-4/full.xml)
- [负向 assertion JUnit](../../../tests/artifacts/upstream_migration/mig-4/probe-assertion.xml)
- [吞掉连接异常的 JUnit](../../../tests/artifacts/upstream_migration/mig-4/probe-offline_guard.xml)
- [Quality 摘要](../../../tests/artifacts/upstream_migration/mig-4/quality/agent_quality_summary.md)
- [基线及 hash 清单](upstream-migration-mig-4-baseline.json)
- [MIG-3 迁移理由和变更记录](upstream-migration-mig-3-execution-journal.md)

原始 artifacts 与独立 venv 保留在本机，不作为 GitHub 已发布产物；报告与基线清单纳入 Git。
测试风险控制和文档映射要求用于限定真实性/证据边界，结果报告按阶段区分 PASS、已知缺口与未执行项；
没有把执行者自查冒充为独立审核或 Owner merge approval。
