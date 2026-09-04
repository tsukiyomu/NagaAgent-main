# P8 Infra and Engineering Layer Deep Dive

## 1. 文档定位

### 1.1 为什么拆 P8
- P8 提供运行保障与可观测能力，`system/health_check.py` 是其中核心诊断机制。

### 1.2 与主文档 Part 8 的关系
- 主文档保留基础设施职责总纲。
- 本文档承接内部健康诊断机制与工程运行边界。

### 1.3 与 P2 的边界
- P2 提供 `/health`、`/health/full` 入口契约。
- P8 提供 `/health/full` 背后的内部诊断聚合与判定逻辑。

## 2. P8 职责边界

### 2.1 诊断执行
- 对多服务做端口、HTTP 端点、可选能力探测。

### 2.2 结果聚合
- 产出单项服务状态与整体摘要。

### 2.3 运行观测
- 输出健康度与分层状态（healthy/degraded/unhealthy/unknown）。

## 3. 关键对象与模块

### 3.1 `system/health_check.py`
- `HealthChecker`
- `check_all`
- `get_summary`
- `perform_startup_health_check`

### 3.2 关键状态模型
- `ServiceStatus`
- `HealthCheckResult`

## 4. 诊断项与 Part 映射

| 诊断项 | 探测目标 | 对应 Part |
|---|---|---|
| `api_server` | 端口、`/health`、`/ws/stats` | Part 2 + Part 7 |
| `agent_server` | 端口、`/health` | Part 1 |
| `mcp_server` | 端口、`/services`、`/status` | Part 6 |
| `screen_vision_mcp` | 服务注册与 `/call` 可达性 | Part 6 |
| `proactive_vision` | `/proactive_vision/config/status/metrics` | Part 1 + Part 3 |
| `websocket` | `/ws/stats`、`/ws/broadcast` | Part 7 |

## 5. 与测试的关系

### 5.1 现状
- smoke 层不直接断言完整诊断树，避免把真实依赖引入阻塞门禁。

### 5.2 后续 integration
- 增加 `/health/full` 结构与关键字段断言。
- 增加故障注入场景，验证 degraded/unhealthy 判定正确性。

## 6. 当前非目标
- 不涵盖业务语义正确性（如模型回答质量）。
- 不涵盖复杂运维场景（跨机房、容灾、分布式队列一致性）。
