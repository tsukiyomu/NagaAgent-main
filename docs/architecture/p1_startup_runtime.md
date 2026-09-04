# P1 Startup and Runtime Orchestration Deep Dive

## 1. 文档定位

### 1.1 为什么拆 P1
- P1 负责“服务能不能起来并持续可用”，是健康诊断链路的基础前提。

### 1.2 与主文档 Part 1 的关系
- 主文档保留总纲。
- 本文档承接启动与服务编排细节。

### 1.3 与 P2 的边界
- P2 负责对外 HTTP 入口。
- P1 负责 API/Agent/MCP/TTS 等进程运行基础与启动编排。

## 2. P1 职责边界

### 2.1 启动编排
- 初始化运行时依赖并按顺序/并行拉起服务。

### 2.2 运行期维持
- 保持服务线程与后台循环活跃。

### 2.3 端口与进程准备
- 处理端口可用性与失败降级，避免全局起不来。

## 3. 关键对象与模块

### 3.1 `main.py`
- `ServiceManager` 负责 `start_all_servers` 及各子服务启动方法。

### 3.2 被拉起服务
- API Server
- Agent Server
- MCP Server
- TTS Server

## 4. 与健康诊断的运行映射

### 4.1 诊断关注点
- `system/health_check.py` 检查 `api_server/agent_server/mcp_server` 端口与健康端点。

### 4.2 关键映射
| 诊断项 | 依赖的 P1 能力 | 结果意义 |
|---|---|---|
| `check_api_server` | API 服务被成功拉起且端口可连 | API 入口基础可用 |
| `check_agent_server` | Agent 服务被成功拉起且端口可连 | 运行时代理能力可用 |
| `check_mcp_server` | MCP 服务被成功拉起 | 工具注册/发现基础可用 |

## 5. 与测试的关系

### 5.1 现状
- smoke 层主要验证 P2 入口可用，不直接覆盖 P1 全部启动路径。

### 5.2 后续 integration
- 建议补“全服务拉起后运行 `/health/full`”的联调测试。

## 6. 当前非目标
- 不展开启动脚本、打包模式和跨平台细节。
- 不展开每个子服务内部实现逻辑。
