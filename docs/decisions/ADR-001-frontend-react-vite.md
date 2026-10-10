# ADR-001: 前端采用 React 19 + Vite 单页应用（而非 Next.js）

## Status
Accepted (2026-10-09)

## Background
产品双核（创作工作室 + 运行时引擎）均为**重客户端交互**场景：卡片/世界书/预设的多字段编辑器、流式对话逐字渲染、世界书调试面板。无 SEO 需求、无首屏 SSR 诉求。部署目标为**单机 `docker compose up` 一键起**，服务越少越好。
候选：React 19 + Vite、Next.js 15、Vue 3 + Nuxt 3。

## Decision
选择 **React 19.1 + Vite 7.x + TypeScript 5.8**。理由：
1. 构建产物为纯静态文件，由 `api` 容器一并托管 —— compose 中**少一个 Node 运行时服务**，直接服务"单机一键起"目标。
2. 组件生态（shadcn/ui、TanStack Query、Zustand）在 React 侧最成熟，编辑器与聊天 UI 的现成范式最多。
3. Next.js 的 SSR/RSC 能力在本项目无对应诉求，反而引入额外构建与部署复杂度。
4. Vue 3/Nuxt 3 可用，但 shadcn/ui 生态以 React 为主，改造成本更高。

## Consequences
- 正面：部署面最小（静态托管）、构建简单、录制/调试直接。
- 负面：放弃 SSR（本项目不需要）；需自建路由（React Router 7）与数据获取约定（TanStack Query）。
- 约束：前端 TS 类型由 `openapi.yaml` 用 `openapi-typescript` 生成，禁止手写平行类型。

## Related ADRs
- ADR-002（UI 组件库与图标）
- ADR-009（部署形态）
