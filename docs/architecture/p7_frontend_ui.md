# P7 Frontend and UI Layer Deep Dive

## 1. 文档定位

### 1.1 为什么拆 P7
- P7 承担实时交互体验，尤其是 websocket/SSE 消费与状态同步。

### 1.2 与主文档 Part 7 的关系
- 主文档保留 UI 层职责概述。
- 本文档承接实时通信与前端状态通道细节。

### 1.3 与 P2 的边界
- P2 暴露 API 和 websocket 入口。
- P7 关注入口之后的连接管理、消息推送、前端消费语义。

## 2. P7 职责边界

### 2.1 连接管理
- 维护全局连接和会话连接集合。

### 2.2 消息投递
- 支持会话定向发送与全局广播。

### 2.3 统计与可观测
- 提供 websocket 连接统计数据用于运行态判断。

## 3. 关键对象与模块

### 3.1 `apiserver/websocket_manager.py`
- `connect/disconnect`
- `send_to_session/broadcast`
- `get_stats`

### 3.2 `apiserver/routes/tools.py`
- `/ws` websocket endpoint
- `/ws/stats`
- `/ws/broadcast`

## 4. 与健康诊断的运行映射

### 4.1 快速健康检查映射
- `apiserver/routes/system.py::/health` 直接读取 `websocket_manager.get_stats()`。

### 4.2 全量健康检查映射
- `system.health_check.check_websocket` 探测：
1. `/ws/stats`
2. `/ws/broadcast`（用 405 识别端点存在性）

### 4.3 结果解释
| 诊断项 | 结果意义 |
|---|---|
| websocket healthy | stats/broadcast 通道可访问 |
| websocket degraded | API 依赖未就绪或部分端点异常 |

## 5. 与测试的关系

### 5.1 现状
- smoke 只检查 `/health` 中 websocket 相关字段存在，不做真实 websocket 会话联调。

### 5.2 后续 integration
- 增加 websocket 建连、广播、断连回收验证。
- 增加跨 session 投递与排除 session 行为验证。

## 6. 当前非目标
- 不展开前端渲染层细节。
- 不展开语音/多模态 UI 交互语义细节。
