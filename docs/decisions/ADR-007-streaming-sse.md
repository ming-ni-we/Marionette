# ADR-007: 会话流式传输采用 SSE（Server-Sent Events），而非 WebSocket

## Status
Accepted (2026-10-09)

## Background
对话回复需要流式逐字渲染。候选：SSE、WebSocket。
本场景的流是**单向**的（服务端 → 客户端 token 流）；客户端中断是低频动作，可用独立 HTTP 请求表达。

## Decision
选择 **SSE**（`text/event-stream`），后端用 FastAPI `StreamingResponse`。理由：
1. 单向流用 SSE 是最小匹配，语义清晰（`EventSource` 原生支持、自动重连）。
2. 穿透代理/防火墙友好（基于 HTTP），无需握手升级。
3. 事件类型可表达多路信息：`world_info`（触发轨迹）、`start`、`delta`、`usage`、`image`、`done`、`error`。
4. 客户端中断用独立幂等端点 `POST /sessions/{id}/interrupt` 表达，不依赖双向通道。
5. WebSocket 的双向能力在本场景无必要，反而增加连接管理与心跳复杂度。

## Consequences
- 正面：实现简单、协议清晰、调试直观（curl 可看流）。
- 负面：SSE 经反向代理需关闭缓冲（`X-Accel-Buffering: no`）并加心跳注释；不支持服务端主动多路（本项目不需要）。
- 约束：中断端点必须幂等；生成中并发请求同一会话返回 409（乐观锁 `state_machine.version`）。

## Related ADRs
- ADR-003（后端）
