# P6 MCP and Tool Integration Deep Dive

## 1. 文档定位

### 1.1 为什么拆 P6
- MCP 层承担工具发现、注册、调用协同，是 agentic 运行能力核心外部接口层。

### 1.2 与主文档 Part 6 的关系
- 主文档保留职责概览。
- 本文档承接 MCP 服务与工具集成细节。

### 1.3 与 P2 的边界
- P2 负责 API 入口与转发。
- P6 负责 MCP registry/manager/server 的工具能力实现。

## 2. P6 职责边界

### 2.1 服务注册与发现
- 维护可见服务清单和 manifest 缓存。

### 2.2 工具调用
- 提供统一调用路径，屏蔽具体工具实现差异。

### 2.3 运行状态暴露
- 通过 MCP server 暴露 `/services`、`/status` 等运行态端点。

## 3. 关键对象与模块

### 3.1 `mcpserver/mcp_server.py`
- `/services`
- `/status`

### 3.2 `mcpserver/mcp_registry.py`
- 自动注册、服务可见性管理。

### 3.3 `mcpserver/mcp_manager.py`
- 服务列表格式化与统一调用入口。

## 4. 与健康诊断的运行映射

### 4.1 诊断链路
- `system.health_check.check_mcp_server`:
1. 端口连通
2. `/services` 端点
3. `/status` 端点
- `system.health_check.check_screen_vision_mcp`:
1. `screen_vision` 注册状态
2. `/call` 端点可达性

### 4.2 结果解释
| 诊断项 | 结果意义 |
|---|---|
| `mcp_server` healthy | MCP 基础服务发现与状态查询可用 |
| `screen_vision_mcp` degraded | 可选能力未注册或部分不可用，不一定是硬故障 |

## 5. 与测试的关系

### 5.1 现状
- smoke 不覆盖真实 MCP 依赖，避免外部波动影响门禁稳定。

### 5.2 后续 integration
- 增加真实 MCP server 联调测试。
- 增加关键工具调用成功与失败路径覆盖。

## 6. 当前非目标
- 不展开每个具体 MCP agent 的业务语义正确性。
- 不展开 tool loop 内部调度策略（由 Part 3 承接）。
