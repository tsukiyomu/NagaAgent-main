# Chat Stream Test Closure Roadmap

> `SUSPENDED`（2026-08-18）：本文件保留 P0/P1 历史快照；当前优先级见 [`../sop-compiler-runtime-practical-roadmap.md`](../sop-compiler-runtime-practical-roadmap.md)。

## 1. 文档定位

本文件是 `/chat/stream` 测试闭环的历史精简路线图。原完整进度与 Ledger 保存在 [`current-progress-and-priorities.md`](current-progress-and-priorities.md)；架构、真实性和断言细节以 [`../../architecture/part-02-api-stream.md`](../../architecture/part-02-api-stream.md) 为准。

- 最近同步：`2026-08-01`
- 当前仓库 HEAD：`01090ce1c60492c411624d057afd10517b504666`
- 当前主线：`P1 Chat Stream 生命周期`
- 状态规则：完成项使用 `DONE / LANDED`；可执行但预期失败的能力缺口使用 `XFAIL_GAP`；尚未接入 CI 的测试使用 `NOT_WIRED`。

## 2. 当前同步快照

| 阶段 | 技术状态 | 证据状态 | Gate 状态 | 当前结论 |
|---|---|---|---|---|
| P0 可复现测试基线 | `DONE` | `VERIFIED`（临时，仅适用于 2026-07-28 Run Record 快照） | Smoke workflow 已运行成功；Required Check `UNKNOWN` | 依赖、失效 monkeypatch、marker、artifact 边界和干净环境执行已收口 |
| P1 SSE 顺序与终止协议 | `DONE / LANDED` | 定向 `2 passed`；完整 resilience `7 passed, 1 xfailed` | `NOT_WIRED` | 正常流与异常流的应用层 SSE 顺序及唯一 terminal 已固定 |
| P1 多增量与完整拼接 | `DONE / LANDED` | 三个 `content` 精确拼接并与 persistence spy 入参一致 | `NOT_WIRED` | 证明应用层 SSE 事件增量，不证明真实网络分包或 TTFB |
| P1 User Stop | `XFAIL_GAP` | `test_chat_stream_user_stop_contract_gap` | `NOT_WIRED` | `AbortSignal`、cancelled 终态、cleanup/finalize 幂等和部分响应保存仍未落地 |
| P1 其他生命周期矩阵 | `PARTIAL / PLANNED` | 正常、异常、空输出和单次 finalize 已有部分覆盖 | `NOT_WIRED` | timeout、重复 finalize、客户端断开和指标重命名仍待完成 |

## 3. P0：已完成的测试基线

- [x] 在 test dependency group 显式声明 `pytest`、`pytest-asyncio`、`allure-pytest` 等测试依赖。
- [x] 修复 `flush_langfuse`、`start_llm_generation_observation` 等失效 monkeypatch。
- [x] 对齐 `smoke / blocking / integration / unit / real_llm / golden_case` marker 语义。
- [x] 隔离 Allure、Quality Gate、pytest cache 等生成物与源码/baseline 边界。
- [x] 在仓库外全新 Python 3.11 环境安装并执行 deterministic suites。
- [x] 保存命令、环境、revision、退出码、真实性边界和结果摘要。
- [x] 用户于 `2026-08-01` 将 P0 Run Record 临时晋升为 `VERIFIED`。

P0 Run Record：[`../../reports/p0-clean-environment-run-2026-07-28.md`](../../reports/p0-clean-environment-run-2026-07-28.md)。该记录绑定 HEAD `70f781f...` 加当时 dirty working tree；当前 HEAD 已变化，因此不能把这份 `VERIFIED` 解释成当前 revision 或发布质量认证。

## 4. P1：当前已完成部分

### 4.1 SSE 顺序与唯一终止

- [x] 正常流：`session_id -> status+ -> content+ -> round_end -> [DONE]`。
- [x] `[DONE]` 唯一且必须位于事件序列末尾。
- [x] 异常流：`session_id -> status+ -> content -> error`。
- [x] `error` 唯一且必须位于末尾；异常流不得再出现 `[DONE]`。

### 4.2 多增量与完整输出

- [x] 首个 `content` 非空。
- [x] 三个 `content.text` 依次为 `baseline-`、`stream-`、`ok`。
- [x] 拼接结果精确等于 `baseline-stream-ok`。
- [x] persistence spy 接收到的 assistant response 与完整拼接结果一致。
- [x] 事件计数和顺序按 SSE `data:` block 解析，不使用 `TestClient.iter_text()` 次数冒充网络分包。

## 5. P1：接下来执行

1. `AbortSignal`：前端 `chatStream` 接受并传播取消信号，不新增服务端 `/stop` 接口。
2. Stop 终态：固定 `final_status=cancelled`，active cleanup 严格一次，finalize 最多一次。
3. 持久化：非空部分响应最多保存一次；空响应只保存用户消息。
4. 生命周期矩阵：补齐整体 timeout、重复 finalize 和真实客户端断开。
5. 指标语义：进程内指标改名为 `first_chunk_ms`；只有真实网络 profile 使用 `ttfb_ms`。
6. 移除 user-stop `xfail`，转为稳定确定性断言。

## 6. 执行证据与边界

| 选择 | 结果 | 解释 |
|---|---|---|
| 两条 SSE 顺序/增量核心用例 | `2 passed` | 支持 P1 前两项 `DONE / LANDED` |
| `tests/integration/chat_stream/test_resilience.py -q` | `7 passed, 1 xfailed` | 唯一 `xfail` 是尚未完成的 user stop |
| 同套件加 `--quality-gate` | 功能用例无失败；`gate_result=fail` | 现有进程内 latency 相对 baseline 触发 severe regression；不等于 SSE 契约失败，也不等于 PR Gate 已接线 |

当前没有证明：真实浏览器取消传播、真实网络 TTFB、真实磁盘持久化回读、真实 LLM 语义质量、真实 MCP/工具可用性或完整生产 E2E。
