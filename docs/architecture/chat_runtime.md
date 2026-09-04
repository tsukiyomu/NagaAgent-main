# Part 3 Core Service Layer Deep Dive (Runtime)

## 1. 文档定位
- 本文档承接主文档 Part 3，聚焦“请求进入后如何运行”。
- 与 P2 边界: P2 负责入口契约与入口治理，Part 3 负责运行时主链路。

## 2. 运行时主链路（概览）
- session create/reuse
- message build/context supplement
- run_agentic_loop
- context compression
- tool dispatch
- persistence and stream close

## 3. 核心对象与模块
- `apiserver/routes/chat.py`
- `apiserver/agentic_tool_loop.py`
- `apiserver/message_manager.py`
- `apiserver/context_compressor.py`
- `apiserver/message_queue.py`

## 4. 待补充
- 运行时状态机细节
- 关键失败路径与恢复策略
- 与 memory/tool/voice side channel 的跨模块协同
