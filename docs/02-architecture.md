# AI 角色扮演平台 — 技术架构文档

- 版本: v1.0 (Phase 1)
- 日期: 2026-10-09
- 作者: 高见远（首席架构师）
- 状态: 待团队评审
- 版本锚定核对日期: 2026-10-09（所有版本号均在此日于官方 PyPI / GitHub Releases / 官方文档核对）

---

## 0. 阅读指南

本文档回答"用什么、为什么、能不能跑、跑起来长什么样"。
内容契约（字段级定义）见 `docs/spec/schemas.md`；接口契约见 `docs/spec/openapi.yaml`；关键决策见 `docs/decisions/ADR-*.md`。

**不做什么（Out-of-Scope，本 MVP 显式不做）**

| 不做项 | 说明 |
|---|---|
| 广场 / 社区分享 | 仅保留数据模型余地（`visibility` 字段），本期无 UI、无 API、无审核流 |
| 群聊 / 多角色同台 | 会话引擎按单角色设计，多角色不在本期 |
| 评分 / 续作 / 派生 | 无 |
| 多租户 / 账号体系 | v1 单机单用户；仅保留 `owner_id` 边界字段与鉴权接口占位 |
| 移动端 / 小程序 | 本期仅桌面浏览器 |
| 云端图像生成正式接入 | 仅定义 `ImageProvider` 接口 + 本地 ComfyUI 实现；云端仅留适配器接口 |

---

## 1. 目标与架构原则

### 1.1 产品双核

1. **创作工作室**（离线、低频、重编辑）：角色卡 / 世界书 / 预设 / 群聊配置（v2）/ 图集素材
2. **运行时引擎**（在线、高频、重编排）：会话状态机 → 世界书触发 → 记忆摘要 → 上下文组装 → LLM 调度 → 画面生成钩子

### 1.2 架构原则（排序即优先级）

1. **单机自部署优先**：`docker compose up` 必须能起。不为"未来规模"引入本期不必要的服务。
2. **分层可上云**：每一层边界（存储、鉴权、LLM 运行时、资产存储）都留可替换接缝，二期加多租户不推倒重来。
3. **Schema 即契约**：创作工作室与运行时引擎读写同一套 Schema，禁止各写一套（详见 `docs/spec/schemas.md` §1 铁律）。
4. **对标社区事实标准**：角色卡兼容 SillyTavern V2，世界书兼容其 Lorebook 字段语义，导入不丢字段。
5. **重编排逻辑必须可观测**：世界书为何触发/未触发、上下文为何这样组装，必须能一键复现（这是产品护城河，也是最大 bug 源）。

---

## 2. 分层架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│  表现层  Presentation                                                      │
│  React 19 SPA (Vite 7) + shadcn/ui + Tailwind CSS v4 + Lucide 图标         │
│  ├ 工作室 Studio：卡片/世界书/预设 编辑器、图集、导入导出                   │
│  └ 剧场 Play：流式对话、场景图、世界书调试面板                            │
├──────────────────────────────────────────────────────────────────────────┤
│  接入层  API Gateway (FastAPI 路由 + SSE)                                  │
│  /api/v1/**  RESTful + OpenAPI 3.0 | /api/v1/sessions/{id}/stream (SSE)    │
│  中间件：鉴权占位(no-op) | 请求日志 | 限流(本地) | 内容合规钩子            │
├──────────────────────────────────────────────────────────────────────────┤
│  业务层  Domain Services                                                   │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌────────────────────┐    │
│  │ 内容仓库   │ │ 会话引擎   │ │ 世界书触发   │ │ 上下文组装         │    │
│  │ ContentSvc │ │ SessionSvc │ │ WorldInfoEng │ │ ContextAssembler   │    │
│  └────────────┘ └────────────┘ └──────────────┘ └────────────────────┘    │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌────────────────────┐    │
│  │ 记忆引擎   │ │ LLM 调度   │ │ 图像钩子     │ │ 导入导出/兼容层    │    │
│  │ MemorySvc  │ │ LLMRouter  │ │ ImageHook    │ │ STCompatAdapter    │    │
│  └────────────┘ └────────────┘ └──────────────┘ └────────────────────┘    │
├──────────────────────────────────────────────────────────────────────────┤
│  适配层  Adapters（可替换接缝，二期上云在这里换实现）                      │
│  LLMProvider: Ollama | OpenAI-compat | 云 API(智谱/通义/DeepSeek)          │
│  EmbeddingProvider: bge-large-zh | bge-m3 | 云 embedding                   │
│  ImageProvider: ComfyUI(本地) | 云图像 API                                 │
│  ModerationProvider: 本地 no-op | 云内容安全                               │
│  AssetStore: 本地文件系统 | 对象存储(S3/OSS)                              │
│  AuthProvider: no-op(单机) | JWT/OIDC(多租户)                             │
├──────────────────────────────────────────────────────────────────────────┤
│  数据层  Data                                                              │
│  PostgreSQL 18 + pgvector 0.8.6                                           │
│  ├ 内容仓库：cards / worldbooks / presets (JSONB + 关系列)                 │
│  ├ 会话态：sessions / messages / memory_snapshots                          │
│  ├ 向量：content_embeddings (pgvector, HNSW)                               │
│  ├ 全文：pg_trgm GIN 索引（CJK 子串/模糊）                                 │
│  └ 任务：image_jobs / exports                                              │
│  资产：本地卷 ./data/assets（可切对象存储）                               │
└──────────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
     Ollama (本地 LLM, GPU)          ComfyUI (本地出图, GPU)
     宿主机原生或容器 profile         宿主机原生（用户已部署）
```

**分层依赖方向**：表现层 → 接入层 → 业务层 → 适配层 → 数据层。**禁止反向依赖**（业务层不得 import 具体 LLM SDK，只能依赖 `LLMProvider` 接口）。

---

## 3. 技术选型对比矩阵

> 说明：每层给出至少 3 个候选；"选中"项标注版本号与锚定来源。未标注版本的候选即不作为主选，仅作对比。示例代码均会标注"以 X 为例（示例，非指定）"。

### 3.1 前端框架

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **React + Vite + TS** | React 19.1 / Vite 7.x / TS 5.8 | **选中** | 纯客户端交互重（编辑器 + 流式对话），无需 SSR；构建产物为静态文件，由后端一并托管，compose 少一个 Node 运行时服务，最贴合"单机一键起"。生态与组件库最成熟 |
| Next.js | 15.4.x | 否 | 提供 SSR/RSC，但本项目无 SEO/首屏渲染诉求；引入额外 Node 服务与构建复杂度，单机部署收益为负 |
| Vue 3 + Nuxt 3 | 3.5.x | 否 | 生态可用，但 shadcn/ui 生态以 React 为主，团队组件复用成本更低的是 React |

### 3.2 前端 UI 组件库

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **shadcn/ui (Radix UI primitives + Tailwind)** | Radix 1.x / Tailwind CSS 4.1 / shadcn CLI | **选中** | 源码复制入仓、无运行时黑盒、可深度定制；与 Tailwind v4 token 体系天然契合；默认配 Lucide 图标；无障碍由 Radix 保障 |
| Ant Design | 5.x | 否 | 组件齐但视觉"企业中台味"重，深度定制成本高；与自定义 token 体系冲突较多 |
| MUI | 6.x/7.x | 否 | Emotion 运行时样式与 Tailwind 共存有冲突；定制主题需改造其 theme 系统 |

### 3.3 图标库（P0 铁律：锁定唯一一套）

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **Lucide** | lucide-react 1.0+ | **选中（锁定）** | 统一 24x24 网格、默认 2px 描边、纯描边风格、MIT/ISC 许可、可 tree-shaking、官方 React 包、与 shadcn/ui 默认集成。满足"统一描边、可矢量缩放、16/20/24px 尺寸规范" |
| Heroicons | @heroicons/react 2.2+ | 否 | 仅 300+ 图标，覆盖面不足；属 Tailwind 团队但本项目的定制面更大 |
| Tabler Icons | @tabler/icons-react 3.x | 否 | 数量大（5400+），但已选 Lucide 即须唯一，避免混用 |
| Phosphor | @phosphor-icons/react 2.x | 否 | 6 种字重带来风格决策面，与"统一描边"目标相悖 |

**图标库使用规范（硬约束）**
- 全项目唯一使用 `lucide-react`，禁止引入第二套图标库，禁止 emoji 充当功能图标。
- 尺寸只允许 `16 / 20 / 24px` 三档（对应 `size` 属性或 `w-4 h-4 / w-5 h-5 / w-6 h-6`）。
- 颜色一律继承 `currentColor`，禁止硬编码（唯一例外 `#fff` / `#000`）。
- 装饰性图标加 `aria-hidden="true"`；有语义的图标用 `role="img"` + `aria-label`。
- 品牌 logo 场景：Lucide 1.0 已移除品牌图标，若确需品牌标识，单独以 Simple Icons 单文件 SVG 引入（不构成"混用图标库"，仅为品牌资产）。

### 3.4 状态管理

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **Zustand + TanStack Query** | zustand 5.x / @tanstack/react-query 5.x | **选中** | Zustand 管客户端 UI 态（编辑器草稿、播放器当前会话）；TanStack Query 管服务端态（缓存/失效/重试），职责清晰，样板少 |
| Redux Toolkit | 2.x | 否 | 样板与概念负担大，本项目无复杂时间旅行/大型团队协作诉求 |
| Jotai | 2.x | 否 | 原子化适合细粒度派生，但与 Query 缓存边界不如 Zustand 直观 |

### 3.5 后端框架

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **FastAPI + Uvicorn** | FastAPI 0.141.1 / Uvicorn 0.48.0 / Python 3.12 | **选中** | AI 生态（tokenizer、embedding、ComfyUI 客户端、sentence-transformers）全部在 Python；原生 async + SSE 流式；Pydantic 2.13.4 校验 + 自动 OpenAPI 生成，与 spec-as-contract 天然契合 |
| NestJS | 12.x | 否 | 工程化强，但 LLM/向量/分词生态需跨语言桥接，单机场景净增复杂度 |
| Hono / Express | 5.x / 4.x(5.2) | 否 | 轻量，但同上：中文分词、embedding、向量检索需另起 Python 进程 |

### 3.6 数据库

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **PostgreSQL + pgvector** | PostgreSQL 18.6 / pgvector 0.8.6 | **选中** | 一个库同时覆盖：关系数据 + JSONB(卡片/世界书) + 向量(记忆召回) + 模糊全文(pg_trgm)。事务一致、迁移路径清晰、二期上云最直接 |
| SQLite | 3.4x | 否 | 单机够用，但并发写弱、无 pgvector 等价物（sqlite-vss 生态小）、多租户/上云要重写，与"分层可上云"冲突 |
| MongoDB | 7.x | 否 | 文档模型适配卡片，但向量（Atlas Vector Search 依赖云）与关系查询能力弱于 PG，且引入新范式 |

### 3.7 ORM / 数据访问

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **SQLAlchemy 2.0 (async) + Alembic** | SQLAlchemy 2.0.x / Alembic 1.18.x / asyncpg 0.30.x | **选中** | 2.0 行式 API 成熟；与 async 栈贴合；Alembic 迁移可控。向量列与 FTS 查询走原生 SQL 逃生舱 |
| SQLModel | 0.0.x | 否 | FastAPI 亲儿子，但与 async 会话、复杂 JSONB、迁移的成熟度不足，遇复杂查询需退回 SQLAlchemy |
| Tortoise ORM | 0.2x | 否 | 生态与迁移（Aerich）成熟度低于 Alembic |

### 3.8 全文索引方案

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **PostgreSQL + pg_trgm GIN** | 随 PG 18.6 内置 | **选中** | CJK 无需分词器即可子串/模糊匹配（按字符 trigram），零额外服务；配合 pgvector 覆盖"精确 + 语义"双路。数据量 < 10 万条绰绰有余 |
| SQLite FTS5 + jieba | FTS5 内置 | 否 | FTS5 默认 `unicode61` 把连续中文当整段一个 token，需 jieba 预分词 + 外部内容表 + 触发器维护同步，且与已选 PG 形成"双库"，违背单库原则 |
| Meilisearch | 1.x | 否 | 中文检索体验好、排序强，但为独立服务（+1 容器 +索引同步），MVP 数据量下性价比不足。**作为升级路径保留**（当卡片/条目破 10 万或需要排序相关度时引入） |
| PG 全文检索 tsvector + zhparser/pg_jieba | 扩展 | 否（暂） | 需在镜像内编译第三方扩展，部署复杂度上升；作为"需要排序式全文检索"时的升级路径 |

### 3.9 向量检索方案

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **pgvector + HNSW** | pgvector 0.8.6 | **选中** | 与业务库同库、事务一致、无需单独服务；HNSW 索引在百万级内性能足够；`0.8.2` 已修 HNSW 并行构建的 CVE，锚定 `0.8.6` |
| Milvus | 2.5.x | 否 | 千万级才划算，单机 MVP 引独立服务属过度设计 |
| Qdrant | 1.x | 否 | 性能好，但同样引入第二套存储；MVP 不必要 |
| Chroma | 0.5.x | 否 | 原型友好但运维/持久化弱于 pgvector，且与 PG 目标冲突 |

### 3.10 本地推理服务

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **Ollama** | 0.33.x | **选中** | Windows 原生安装即用 GPU、自带模型管理、暴露 OpenAI 兼容 `/v1/chat/completions`（流式），适配层零成本；官方明确支持 RTX 50 系（compute 12.0） |
| llama.cpp (server) | 最新 release | 备选 | 与 Ollama 同源 GGUF；当需要精细控制 GPU 层卸载 / 自定义量化时使用。作为 `LLMProvider` 的第二实现保留 |
| vLLM | 0.9.x+ | 否 | 吞吐强但显存要求高（14B 需 ~28GB+），且 sm_120 轮子可用性有风险；单机交互场景是"1 会话不并高并发"，收益低 |

### 3.11 LLM 适配层

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **自研薄适配层（OpenAI-compatible 协议）** | httpx 0.28.x | **选中** | Ollama / 智谱 / 通义 DashScope / DeepSeek / OpenAI 均提供 OpenAI 兼容端点；一层 httpx 流式封装即可全部打通，无重依赖、行为完全可控 |
| LiteLLM | 1.x | 备选 | 100+ provider 统一，省事但引入较大依赖与间接层；当 provider 数量爆发时再引入 |
| LangChain | 1.4.x | 否 | 抽象重、调试成本高；本项目的"编排"是自研护城河，不愿被黑盒抽象遮蔽 |

### 3.12 容器化 / 编排

| 候选 | 版本(锚定) | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **Docker Compose (CLI 插件 v2 语法)** | Docker Engine 28.x / Compose v2.29+ | **选中** | `docker compose up` 一条命令；单机多服务（api + db + 可选 ollama）编排足够；无需 K8s |
| Kubernetes / k3s | 1.3x | 否 | 单机 MVP 严重过度设计。二期上云时，compose 服务与 K8s 的 Deployment 可一一映射 |
| Podman Compose | 5.x | 否 | 可用，但 Windows + NVIDIA GPU 直通生态成熟度不如 Docker Desktop 方案 |

### 3.13 Embedding 模型（记忆召回用）

| 候选 | 版本/维数 | 结论 | 理由 / 否决理由 |
|---|---|---|---|
| **BAAI/bge-large-zh-v1.5** | 326M / 1024 维 | **选中（默认）** | 中文 C-MTEB 第一梯队，本地可跑（CPU 亦可，显存<2GB）；隐私友好 |
| BAAI/bge-m3 | 568M / 1024 维 | 备选 | 多语言 + 多粒度，长文本（8192）更强；显存占用更高（>2GB），作为高质量档 |
| BAAI/bge-small-zh-v1.5 | 24M / 512 维 | 轻量档 | 极轻量、CPU 秒级；作为低配兜底 |
| 云 embedding（智谱 embedding-3 / 通义） | API / 1024 维 | 备选 | 数据不出境/无 GPU 时的合规路径 |

> 说明：Embedding 与主推理**分开选型**。Embedding 模型小，可放 API 容器内以 CPU/ONNX 运行（规避容器内 GPU 的 sm_120 风险），详见 §4.9。

### 3.14 汇总（选中栈一览）

| 层 | 选中 | 版本锚定 |
|---|---|---|
| 前端框架 | React + Vite + TS | React 19.1 / Vite 7.x / TS 5.8 |
| UI 组件库 | shadcn/ui + Radix + Tailwind | Radix 1.x / Tailwind 4.1 |
| 图标库（锁定） | **Lucide** | lucide-react 1.0+ |
| 状态管理 | Zustand + TanStack Query | zustand 5.x / react-query 5.x |
| 后端框架 | FastAPI + Uvicorn | 0.141.1 / 0.48.0 / Python 3.12 |
| 数据库 | PostgreSQL + pgvector | 18.6 / 0.8.6 |
| ORM | SQLAlchemy 2.0 async + Alembic | 2.0.x / 1.18.x / asyncpg 0.30.x |
| 全文索引 | PG pg_trgm GIN（升级: Meilisearch） | 内置 |
| 向量检索 | pgvector HNSW | 0.8.6 |
| 本地推理 | Ollama（备选 llama.cpp） | 0.33.x |
| LLM 适配 | 自研 OpenAI 兼容薄层（备选 LiteLLM） | httpx 0.28.x |
| 容器编排 | Docker Compose v2 | Engine 28.x / Compose v2.29+ |
| Embedding | bge-large-zh-v1.5（备选 bge-m3） | 1024 维 |

---

## 4. 核心技术可行性验证

> 结论先行：**整体可行**。唯一"真坑"是容器内 Python GPU 推理遇到 sm_120 轮子问题（§4.9），已有明确规避方案（把重 GPU 任务放宿主机原生运行时）。

### 4.1 单机 `docker compose up` 一键起

**服务清单（默认 2 个容器）**

| 服务 | 镜像 | 作用 | 数据卷 |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg18` | PostgreSQL 18 + pgvector 0.8.6 | `pgdata:/var/lib/postgresql/data` |
| `api` | 自建 `python:3.12-slim` | FastAPI（`/api/v1/**` + SSE + 托管 SPA 静态文件） | `assets:/app/data/assets`、`config:/app/data/config` |
| `ollama`（profile: `local-llm`，可选） | `ollama/ollama:0.33.x` | 本地 LLM | `ollama:/root/.ollama` |

ComfyUI **不入 compose**（用户已在宿主机部署），通过 `host.docker.internal:8188` 访问。

**用户前置只需装**：
1. **Docker Desktop for Windows**（WSL2 backend）——必需
2. **NVIDIA 驱动 ≥ 570**（Blackwell sm_120 最低要求）——若跑本地 LLM/出图必需
3. **NVIDIA Container Toolkit**（仅当选择"容器内跑 Ollama/GPU"时需要；若 Ollama 与 ComfyUI 都跑宿主机原生，则**不需要**）
4. **Ollama**（宿主机原生安装，最省事路径）与 **ComfyUI**（用户已有）

**结论**：默认路径（Ollama + ComfyUI 宿主机原生、容器只跑 api+db）前置只需 Docker Desktop + NVIDIA 驱动，`docker compose up -d` 即可访问 `http://localhost:8000`。**风险低**。

### 4.2 LLM 流式输出与前端逐字渲染

- **协议选型：SSE（Server-Sent Events）**，非 WebSocket。理由见 ADR-007。单向 token 流用 SSE 更简单、穿透代理友好、浏览器原生 `EventSource` 自动重连。
- **后端**：FastAPI `StreamingResponse(media_type="text/event-stream")`，逐块 yield。
- **事件类型**（详见 `openapi.yaml` 与 §5.4）：

| event | data | 用途 |
|---|---|---|
| `world_info` | 本轮命中的世界书条目 + 预算裁决 | 打开"世界书调试"，让用户看见引擎为何这样组装 |
| `start` | `message_id`、`prompt_tokens` | 建立流式占位消息 |
| `delta` | `{ "text": "..." }` | 逐字追加 |
| `usage` | token 统计 | 成本/预算可视化 |
| `image` | `asset_id` | 画面生成完成后回推 |
| `done` | 最终消息记录 id | 收尾 |
| `error` | 错误码 + 可读消息 | 失败 |

- **前端**：`EventSource` 订阅 → 按 `event` 分发 → React 端对 `delta` 做追加；建议按 rAF 批量刷新以降低重渲染（逐字节流）。
- **中断**：另设 `POST /api/v1/sessions/{id}/interrupt`（幂等），服务端置中断标志、关闭流并落"未完成消息"。
- **风险**：SSE 长连接经反向代理需关闭缓冲（`proxy_buffering off` / `X-Accel-Buffering: no`）。**中低风险，已知解法**。

### 4.3 会话状态机：建模、持久化、中断恢复

**状态机**（单一会话一条记录，字段 `state_machine.current`）

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
   ┌────────┐  enqueue   ┌───────────┐  tokens  ┌────────────┐
   │  idle  │───────────▶│ assembling│─────────▶│ generating │
   └────────┘            └───────────┘          └────────────┘
        ▲                      │ error              │ 完成
        │                      ▼                    ▼
        │                ┌──────────┐        ┌────────────────┐
        └────────────────│  error   │        │ post_processing│
             reset       └──────────┘        └────────────────┘
        │                                           │
        │            interrupt                      │ 摘要/事实抽取/出图钩子
        └───────────────────────────────┐           ▼
                                  ┌─────────────┐  ┌──────┐
                                  │ interrupted │─▶│ idle │
                                  └─────────────┘  └──────┘
```

- **权威状态在数据库，不在内存**：`sessions.state_machine` 只存枚举 + 计数 + `last_error`。任何一次生成请求都可从持久化状态**幂等重建**。
- **持久化模型**：`sessions`（元数据 + state_machine + memory JSONB）、`messages`（消息流，逐条落库）、`memory_snapshots`（滚动摘要版本）。
- **中断恢复**：
  1. 流式生成时，先落一条 `messages.status='streaming'` 占位；
  2. 每 N 个 delta（或每 X ms）把已生成文本 upsert 回该消息（**检查点**）；
  3. 正常结束 → `status='complete'`；客户端中断 → `status='incomplete'`（保留已生成部分）；
  4. 服务重启 → 启动扫描：把滞留 `streaming` 的消息标记 `incomplete`，会话状态回 `idle`；
  5. 恢复动作 = 对该消息执行 **swipe / 重新生成**（因为 prompt 是从持久态重建的，不依赖旧请求内存）。
- **风险**：状态机是"沉默逻辑错误"高发区（枚举漏迁、并发两次请求）。**防线**：状态迁移写成显式表 + 单测覆盖非法迁移；同一会话加**悲观锁/乐观版本号**防并发双击。**中风险，需测试支撑**。

### 4.4 世界书触发引擎

**触发流程（每轮对话执行一次）**

```
输入：最近 scan_depth 条消息文本 W、世界书条目集合 E、当前常驻标记
  │
  ├─ 1. 常驻条目 (constant=true) 无条件入选
  ├─ 2. 关键词匹配：对每条 enabled 条目
  │       ├ 普通: keys 任一在 W 中（子串；case_sensitive 控制大小写）
  │       ├ 整词: match_whole_words=true 时按词边界匹配
  │       ├ 正则: use_regex=true 时用 regex_flags 编译，对 W 做 search
  │       └ selective: 需 keys 与 secondary_keys 同时命中
  ├─ 3. 向量召回（vector_recall=true 的条目）：对 W 的 embedding 与条目 embedding 做相似度，≥ vector_threshold 则入选
  ├─ 4. 递归触发（recursive_scanning=true）：新入选条目的 content 再作为扫描文本，回到步骤 2（限制深度 ≤ 3，防环）
  ├─ 5. 排序：按 insertion_order 升序（小者在前）
  ├─ 6. 预算裁决：累计 token 超过 token_budget 时，按 priority 降序保留、低 priority 先丢
  └─ 输出：入选条目（含插入位置） + 完整裁决轨迹 trace
```

**插入位置语义**（兼容 ST 世界书）

| position | 语义 |
|---|---|
| `before_char` | 角色定义之前 |
| `after_char` | 角色定义之后 |
| `before_example` | 示例对话之前 |
| `after_example` | 示例对话之后 |
| `at_depth` | 从历史末端倒数 `depth` 条处插入（`role` 指定注入角色） |

**触发不到的排查手段（产品化，不是日志）**
- `POST /api/v1/worldbooks/{id}/test`：传一段样例文本，返回**每条条目的逐项判定**：是否命中、命中哪个 key、匹配类型（keyword/regex/vector/constant）、token 数、预算内是否保留、最终插入位置。
- 会话内 `GET /api/v1/sessions/{id}/last-context`：返回**上一轮真实组装的完整 prompt** + 触发 trace + 预算占用表。
- 前端"世界书调试面板"直接消费这两个接口，红/绿标记每条条目命运。

**风险**：递归触发可能成环、token 估算与真实不一致、正则性能（病态回溯）。**防线**：递归深度硬上限、token 用与模型一致的分词器估算（见 §4.7）、正则时长/复杂度上限、非法正则编译失败降级为字面匹配并告警。**中高风险，属护城河逻辑，必须测试覆盖**。

### 4.5 记忆与摘要：三段协作 + 裁剪

**三段结构**

| 段 | 内容 | 生成方式 | 生命周期 |
|---|---|---|---|
| A. 滚动摘要 | 把"已摘要窗口"之前的对话压缩成一段叙述 | LLM 定期压缩（每 N 轮或超阈值） | 长期，随对话演进覆盖旧版 |
| B. 关键事实 | 结构化 key-value（如"玩家名字=林", "已获得物品=旧怀表"） | LLM 抽取 + 正则兜底 | 长期，去重合并 |
| C. 向量召回 | 从历史消息/条目中按语义相似度取 Top-K 片段 | embedding + pgvector 查询 | 按需，每轮动态 |

**协作方式（每轮组装前）**
1. 取 A（滚动摘要）+ B（当前事实表）作为"长期记忆块"。
2. 用**当前用户输入**（+ 最近 1~2 条消息）作为查询，去 pgvector 取 C 的 Top-K（K 由预算定，默认 5）。
3. 组装顺序：长期记忆块（A+B）在前，向量召回块（C）在后，均置于历史消息之前、世界书 `before_char` 之后。

**触发时机**：当 `messages` 中"未摘要消息"的 token 总数超过阈值（默认 = 历史预算的 80%）时，后台把最老的一批未摘要消息压缩进 A，并推进 `summary_upto_message_id`；同一时点做 B 的事实抽取。

**token 超限裁剪顺序**（先丢这些，绝不丢）
1. 丢最老的、已进入摘要窗口的原始消息（它们已在 A 里）
2. 缩小 C 的 Top-K（K: 5 → 3 → 1 → 0）
3. 截断 B 里 confidence 最低的事实
4. 再不够 → 强制触发一次摘要压缩，把更多消息并进 A

**永不裁剪**：当前用户消息、系统基座提示、角色核心定义、`post_history_instructions`。

### 4.6 上下文组装（Context Engineering）— 产品护城河

**最终 prompt 骨架**（顺序即模型看到的顺序）

```
[1] 系统基座      preset.prompt_template.system（含 {{char}}/{{user}}/{{persona}} 占位符替换）
[2] 角色定义块    name / description / personality / scenario
[3] 世界书 · before_char 命中条目
[4] 长期记忆块    滚动摘要(A) + 关键事实(B)
[5] 向量召回块    C（语义相关历史片段）
[6] 示例对话      mes_example（如预算允许）
[7] 世界书 · before_example / after_example 命中条目
[8] 历史消息      最近 N 轮（oldest→newest），受历史预算约束
[9] 世界书 · at_depth 命中条目（插在倒数 depth 处）
[10] 历史后指令   post_history_instructions
[11] （预留）用户当前输入由历史消息末端自然承接
```

**token 预算分配**（默认值，可在 preset 覆盖）

| 段 | 默认占比 | 说明 |
|---|---|---|
| 角色定义块 | 15% | 固定，超限时按字段优先级截断（description 优先于 scenario） |
| 世界书 | 25% | 由 `worldbook.token_budget` 与预算占比取小 |
| 长期记忆(A+B) | 15% | 超限时先压 B 再压 A |
| 向量召回(C) | 5% | 动态 K |
| 历史消息 | 35% | 保留最近 N 轮，超出触发摘要 |
| 预留输出 | 5% | 保证模型有生成空间 |

- 总预算 = `preset.context_budget.max_context_tokens - reserve_for_output`。
- 估算器：与所选模型一致的分词器（本地模型用其 GGUF tokenizer / `tiktoken` 兜底），**估算值须与实际 usage 对账**（组装后记录 `estimated_tokens`，生成后记录 `actual_prompt_tokens`，偏差写入调试面板）。
- 组装结果**全量落库**（`context_snapshots`）：prompt 全文 + 各段 token 数 + 世界书 trace + 预算占用。可复现、可审计、可回归测试。

**为什么这是护城河**：同样的模型与卡片，组装顺序 / 预算分配 / 世界书裁决不同，体验天差地别。这层的正确性必须靠**确定性测试**守住（给定固定输入 → 断言组装出的 prompt 逐字一致）。

**风险（Top 1 逻辑风险）**：**沉默逻辑错误**——组装顺序错、占位符漏替换、预算算错，都不报错但体验悄悄崩坏。**防线**：固定夹具（fixture）的黄金 prompt 快照测试 + 变异测试。

### 4.7 全文索引与中文分词

| 方案 | 中文能力 | 额外依赖 | 结论 |
|---|---|---|---|
| PG `pg_trgm` GIN | 子串/模糊可用（字符级 trigram） | 无（随 PG） | **选中**：MVP 主力，覆盖"按标题/标签/正文关键词搜卡片与条目" |
| SQLite FTS5 + jieba 预分词 | 好（需写入/查询两端一致分词） | 需双库 + 触发器同步 | 否（与单库原则冲突） |
| Meilisearch 1.x | 好（内置 CJK 处理 + 排序） | +1 服务 | 升级路径（数据量破 10 万或需排序相关度时） |
| PG tsvector + zhparser/pg_jieba | 好（真正分词） | 镜像内编译扩展 | 升级路径（需排序式全文检索时） |

**中文分词处理结论**：
- MVP **不引入分词器**，用 `pg_trgm`（三字组）+ `ILIKE` 组合，对中文子串检索足够。
- 检索 UI 层做关键词高亮（前端 `highlightText` 转义后 `<mark>`）。
- 明确：`pg_trgm` 是"子串/模糊"，pgvector 是"语义"——**两者互补不互替**（ADR-005）。

### 4.8 图像生成钩子

**接口**（`ImageProvider`）：`queue(prompt, params) -> job_id` / `status(job_id)` / `result(job_id)`。

**ComfyUI 适配（用户已有，本地直连）**
1. 准备一个**导出为 API 格式**的工作流模板 JSON（存为平台资产，节点 id 映射到可注入字段：positive/negative prompt、seed、width/height、steps、checkpoint）。
2. 提交：`POST http://host.docker.internal:8188/prompt`，body `{"prompt": <注入后的API格式工作流>, "client_id": "<uuid>", "prompt_id": "<uuid>"}`。
3. 跟踪：`GET /history/{prompt_id}` 轮询（简单）或 `WS /ws?clientId={uuid}` 监听 `executing` 且 `node=null` 判定完成（推荐）。
4. 取图：`GET /view?filename=&subfolder=&type=` 下载字节 → 存入 `AssetStore` → 生成 `asset_id`。
5. 落库：`image_jobs`（status: queued/running/done/failed）+ 关联到 `messages.meta.image_asset_id` 或 `sessions.scene.bg_asset_id`。
6. 回推：通过会话 SSE 的 `image` 事件或前端轮询 `GET /api/v1/images/jobs/{id}`。

**异步任务流**：图像生成**不阻塞**对话流。触发钩子（如每 N 轮 / 场景切换 / 用户手动"出图"）→ 入队 `image_jobs` → 后台 worker（FastAPI 内的 asyncio 任务或独立轻量 worker）推进。

**云备选路径**：同一接口的 `CloudImageProvider` 实现（OpenAI-compatible images 或国内图像 API），仅需配置切换。

**风险**：ComfyUI 工作流格式随节点版本变动；容器访问宿主机端口在 Windows 需 `host.docker.internal` 且 Docker Desktop 已默认支持。**中低风险**。

### 4.9 本地推理兜底：RTX 5060Ti 16GB 与 sm_120 兼容坑（重点核实）

**A. Blackwell / sm_120 兼容坑（真实存在，务必规避）**
- RTX 50 系（含 5060 Ti）计算能力为 **sm_120**，**驱动必须 ≥ 570**，否则 `nvidia-smi` 可能报 "no devices found" 或识别不到设备。
- CUDA 建议 **12.8+**（12.4 为下限）。
- **PyTorch 连续踩坑**：稳定版 PyTorch 曾**未编译 sm_120 内核**，会出现 `RuntimeError: No CUDA GPUs are available` 或 `capability sm_120 is not compatible` 警告；必须安装 **cu128 及以上**轮子，或 nightly。`pip install` 还可能因"Requirement already satisfied"静默留在旧 cu124 build——需 `--force-reinstall --no-cache-dir`。
- 另一个隐蔽坑：`CUDA_VISIBLE_DEVICES=""`（空串 ≠ 未设置），会让 PyTorch 看不到 GPU 而 `nvidia-smi` 正常。
- Linux 下 Blackwell 需 **open kernel module**（proprietary 变体支持不佳）；Windows 原生用官方 Game Ready/Studio 驱动即可。

**B. 规避策略（架构层）**
1. **重 GPU 任务全部放宿主机原生运行时**（Ollama + ComfyUI），**不在 api 容器内跑 GPU torch**。
2. **api 容器内的 embedding 用 CPU / ONNX Runtime**（bge 系列 326M，CPU 单条百毫秒级，足够）。
3. 若必须容器内 GPU：镜像基线用 `nvidia/cuda:12.8-*-runtime`，装 cu128 轮子，并做 `nvidia-smi` + `torch.cuda.is_available()` 启动自检，**起不来就降级为 CPU 并在 UI 明确提示**（不要静默）。

**C. 16GB 显存能跑什么（实测口径）**

| 模型 | 规模 | 量化 | 显存 | 速度 | 结论 |
|---|---|---|---|---|---|
| Qwen3-8B | 8B 稠密 | Q8_0 | ~10.7GB | ~29 t/s | **最稳，长上下文首选** |
| Qwen3-14B | 14B 稠密 | Q4_K_M | ~9–11GB（4k 上下文可逼近 16GB 峰值） | ~32 t/s | **甜点，但 16GB 偏紧** |
| Gemma3-12B | 12B | Q4_K_M | ~8GB | 35+ t/s | 可用 |
| GPT-OSS-20B / Qwen3-30B-A3B | MoE（激活 3.6B/A3B） | Q4/FP4 | ~12GB | 快（MoE 优势） | **推荐：容量与速度兼得** |
| Qwen3-32B | 32B 稠密 | Q4_K_M | ~20GB | — | **单卡装不下，禁止作为默认** |
| 27B/35B | 稠密 | IQ3/IQ3_XXS | 15–22GB | — | 仅 CPU+GPU 混合卸载，慢 |

- **KV Cache 随上下文线性增长**：4K→32K，KV 可能从 ~1GB 涨到 8GB+。**默认上下文设为 8K–16K**，不要盲目拉满。
- **推荐默认模型档**：8B 稠密（Q8_0，长上下文/低配）与 14B 稠密（Q4_K_M，质量）二选一；MoE（如 GPT-OSS-20B / Qwen3-30B-A3B）作为"速度优先"档。**32B 稠密明确排除**。
- 内存建议 ≥ 显存 1.5 倍（≥32GB），NVMe SSD，PCIe Gen4 x16。

**结论**：本地推理**可行**，但必须按上述**降级策略**设计——本地不是唯一路径，云端 API 作为一等备选（合规起见可走国内云）。

### 4.10 内容合规（面向国内）

- **F6 为 P0 不降级项**：定义 `ModerationProvider` 接口（`check_input(text)` / `check_output(text)`），在**输入进 LLM 前**与**输出回流后**各拦一次。
- v1 默认实现 = `builtin_wordlist`（**基础词表 + 正则**，可配置、**单机可整体关闭**），成本约 1–2 人日；云内容安全 API 作为 `provider: cloud` 适配器保留给上云期。
- 命中且 `block_on_match=true` → 返回中性提示 + 错误码 4031，**不产生 LLM 调用**；输出默认附"AI 生成内容"标识。
- 卡片/世界书**导入**时做一次静态词表扫描，结果记录但默认不阻断本地使用（避免劝退创作者）。
- **成本评估与选型依据见 §9.3**（回应 OPEN-001）。

---

## 5. 部署形态设计

### 5.1 v1 单机 docker compose

```
ai-roleplay/
├─ docker-compose.yml
├─ .env.example              # LLM_PROVIDER / OLLAMA_BASE_URL / DB_PASSWORD / COMFYUI_URL ...
├─ apps/
│  ├─ api/                    # FastAPI
│  └─ web/                    # React SPA（构建产物由 api 容器托管）
└─ data/                     # 宿主机挂载（可整体备份/迁移）
   ├─ pgdata/                # 数据库（也可用命名卷）
   ├─ assets/                # 头像/图集/生成图
   └─ config/                # 运行配置、工作流模板
```

**compose 关键点**
- `db` 用 `pgvector/pgvector:pg18`，健康检查 `pg_isready`，`api` 依赖 `depends_on: db: condition: service_healthy`。
- `api` 单端口 `8000` 暴露（`/api/v1/**` + 静态 SPA 兜底路由）。
- `ollama` 置于 `profiles: [local-llm]`，GPU 通过 `deploy.resources.reservations.devices` 声明（Linux/Compose 支持；Windows 走 Docker Desktop GPU 支持）。
- ComfyUI 走 `host.docker.internal:8188`（Windows/macOS Docker Desktop 默认提供）。

**启动**：`cp .env.example .env && docker compose up -d`（默认不含 ollama profile）。

### 5.2 数据卷与备份

| 卷 | 内容 | 备份方式 |
|---|---|---|
| `pgdata` | 全部结构化数据 | `pg_dump`（每日 cron/sidecar）+ WAL 归档（可选） |
| `assets` | 图片/素材 | 增量快照（rsync / 文件复制） |
| `config` | 配置与工作流模板 | 随 git 或快照 |

**另提供"可移植导出"**：`GET /api/v1/exports/{cardId}` 等接口把"卡片 + 世界书 + 预设 + 引用素材"打包为 zip（含 manifest.json 声明 schema 版本），便于迁移与分享。

### 5.3 从单机升级到多租户 SaaS 的迁移路径（边界已在 v1 预留）

| 边界 | v1 形态 | 上云形态 | 迁移动作 |
|---|---|---|---|
| 数据归属 | 所有内容行含 `owner_id`（默认 `'local'`） | 多租户 | 启用 PG RLS，按 `owner_id/workspace_id` 隔离；新旧行统一填列 |
| 鉴权 | `AuthProvider` = no-op | JWT/OIDC | 替换实现 + 中间件启用，接口签名不变 |
| 资产存储 | `AssetStore` = 本地 FS | S3/OSS | 换实现，`asset_id` 不变（存 key 而非路径） |
| LLM 运行时 | 本地 Ollama | 云 API / 自建推理集群 | 换 `LLMProvider` 实现，per-request 配置 |
| 应用形态 | 单容器 | 多副本 + 负载均衡 | compose → K8s Deployment（一一映射），无状态化已由 §4.3 保证 |
| 全文索引 | pg_trgm | Meilisearch / PG zhparser | 增加索引服务 + 回填任务 |
| 合规 | no-op 钩子 | 云内容安全 | 启用 `ModerationProvider` 云实现 |

**要点**：**v1 就把这些"缝"留出来，但全部按单机默认值运行**——二期只换实现，不动业务代码。

---

## 6. 风险清单（按优先级排序）

| # | 风险 | 类型 | 影响 | 缓解 |
|---|---|---|---|---|
| 1 | **上下文组装 / 世界书触发的沉默逻辑错误** | 高（护城河逻辑） | 不报错但体验悄悄崩坏，最难发现 | 黄金 prompt 快照测试 + 变异测试 + 触发 trace 可视化 + 组装结果全量落库 |
| 2 | **sm_120 (Blackwell) 容器内 GPU 兼容** | 高（环境） | 可能导致"一键起"带 GPU 时失败 | 重 GPU 任务放宿主机原生；容器内 embedding 走 CPU/ONNX；启动自检 + 显式降级提示；锚定 CUDA 12.8 + cu128 |
| 3 | **会话状态机并发/恢复正确性** | 中高 | 双击/重启导致状态错乱、消息重复 | 显式迁移表 + 版本号乐观锁 + 检查点式落库 + 启动回收滞留 streaming |
| 4 | 世界书递归触发成环 / 正则病态回溯 | 中 | 请求卡死或结果异常 | 递归深度硬上限（3）、正则复杂度/时长上限、编译失败降级 |
| 5 | token 估算与实际不一致 | 中 | 超限截断、成本失控 | 用与模型一致的分词器 + 估算值与 usage 对账，偏差可视化 |
| 6 | 中文全文检索体验 | 中低 | 搜索不准 | MVP pg_trgm 子串够用；预留 Meilisearch/zhparser 升级路径 |
| 7 | SSE 经反代缓冲 | 低 | 流式"卡顿/不流" | 关缓冲（`X-Accel-Buffering: no`）、心跳注释 |
| 8 | ComfyUI 工作流格式漂移 | 低 | 出图失败 | 工作流模板版本化 + 提交前节点校验 + 失败可回退到纯文本 |

---

## 7. P0 规则遵守声明

- **图标库锁定唯一一套**：`lucide-react`（§3.3），尺寸 16/20/24px，统一描边，全项目不混用；禁止 emoji 作为功能图标。
- **无紫→粉渐变**：本架构不推荐任何 Indigo→Pink 类渐变方案；颜色一律走设计 token（由设计师定义），架构层不硬编码颜色。唯一例外 `#fff` / `#000`。
- **无空洞占位**：所有"选用 X 为例"的示例均标注（示例，非指定）。
- **技术栈/选型无关原则**：本文档只定"用什么"，"怎么做才对"的规范由专家团另行定义；示例代码一律标注示例性质。
- **架构文档不使用 emoji**。

---

## 8. 端到端验证步骤（Phase 2 完成定义）

一条可执行的核心闭环验证（覆盖成功流 + 一条错误流）：

1. `cp .env.example .env && docker compose up -d` → `db` 与 `api` 健康。
2. 建卡片：`POST /api/v1/cards`（导入一张 SillyTavern V2 JSON）→ 200，`GET /api/v1/cards/{id}` 字段完整（含 `character_book`）。
3. 建世界书：含 1 条 `constant=true` 条目 + 1 条关键词条目（key = "怀表"）。
4. 世界书自测：`POST /api/v1/worldbooks/{id}/test` body 含"怀表" → 返回该条目"命中且预算内保留"；body 不含 → 该条目"未命中"，常驻条目仍入选。
5. 开会话：`POST /api/v1/sessions`（绑定卡片+预设+世界书）→ `state_machine.current=idle`。
6. 流式对话：`GET /api/v1/sessions/{id}/stream?input=...` → 依次收到 `world_info` → `start` → 多个 `delta` → `usage` → `done`；消息落库 `status=complete`。
7. 记忆生效：连发超过阈值的消息后，`memory` 中出现非空 `rolling_summary` 与 `facts`；`GET /api/v1/sessions/{id}/last-context` 可见各段 token 占用。
8. 出图钩子：手动触发 `POST /api/v1/images/jobs` → `image_jobs` 变 `done` → `asset_id` 关联到消息。
9. **错误流**：把 `LLM_PROVIDER` 指向一个不可达地址 → 流式返回 `error` 事件，会话状态回 `idle`，用户消息保留、无半截 assistant 消息污染。
10. 中断恢复：对话中调用 `POST /interrupt` → 消息标 `incomplete`；重新生成（swipe）成功。

达标口径：以上 10 步全通过 + 组装逻辑回归集为绿。

---

## 9. 与 PRD / OPEN-DECISIONS 的对齐（含对未决项的裁决输入）

> 本节回应 `docs/decisions/OPEN-DECISIONS.md` 中登记、以架构师结论为解除条件的项，并同步 PRD §6/§9 的 P0 降级裁定。

### 9.1 P0/P1 边界与架构的对应（重要：与 PRD 降级裁定一致）

PRD 已裁定若干"降级"，架构据此调整实现口径（**Schema 仍保留字段下余地，但 MVP 实现按 P0 口径**）：

| 功能 | PRD 裁定 | 架构实现口径 |
|---|---|---|
| F14 向量检索记忆增强 | P1（不做） | `vector_recall` / `vector_top_k` 字段**保留在 Schema（下余地）**，但 **MVP 默认关闭**；P0 记忆 = 关键词/常驻触发 + 自动摘要 + 事实落库（段 A+B）。pgvector 表可建但不接召回段 |
| F15 全文索引（跨会话/跨卡） | P1→v2（不做） | pg_trgm 仅用于**内容库列表级搜索/筛选（P0）**；跨会话全文检索归 v2 |
| F13 预设/采样编辑 UI | P1（不做） | 预设 Schema 与默认预设**必须有**（运行时 F7 依赖），但"预设编辑器 UI"归 P1 |
| F1 多后端管理面板 | P0→P1 | v1 仅**单后端**配置（`GET/PUT /config/llm`），多后端后置 |
| F12 ComfyUI | 完整工作流编辑器 → "检测+出图+归档"轻量钩子 | 工作流以**模板资产**形式内置少量预设，不做可视化编辑器 |
| F6 内容审核层 | **不降级（P0）**，可插拔+可关闭 | 默认 `builtin_wordlist`（基础词表）+ 可整体关闭 + 接口可插云；见 §9.3 |
| F5 世界书触发 / F8 自动摘要 / F3 资产导入导出 | **不降级（P0）** | 已列为架构核心；世界书触发引擎见 §4.4，摘要见 §4.5 |

### 9.2 OPEN-002 裁决输入：LLM 接入策略（默认本地 还是 默认云）

**结论：统一 OpenAI 兼容适配层 + 首启向导二选一，默认"自动探测本机 Ollama"优先，未探测到则引导填云端 key。**

- 适配层：单实现 `LLMProvider`（OpenAI 兼容协议），provider 枚举 `ollama | openai_compatible | zhipu | dashscope | deepseek`（见 `openapi.yaml` `LlmConfigInput`）。
- **默认策略的理由**：用户环境明确有 RTX 5060Ti 且已跑 ComfyUI，本机 Ollama 是"数据私有 + 零成本 + 全离线"最优解；同时尊重 PM 对"接云更省心"的担忧——**向导同时提供两条路径**，并且**默认值由探测决定**，不让用户做选择题。
- **错误分类枚举**（F1 必须锁定，最大流失点）：`model_not_found` / `endpoint_invalid`（端点缺 `/v1`）/ `auth_failed` / `quota_exhausted`（余额为 0）/ `network_unreachable` / `timeout` / `unknown`，配套**中文修复指引**。已写入 `POST /config/llm/test` 契约。
- 提供 `GET /system/selfcheck` 与 `POST /onboarding/samples`（内置示例卡）服务于 §9 的"15 分钟链路"。

### 9.3 OPEN-001 裁决输入：审核层成本评估

**结论：v1 做"可插拔 + 可关闭 + 基础词表"的审核层（约 1–2 人日），不做分类模型。**

| 方案 | 成本 | 能力 | 结论 |
|---|---|---|---|
| **基础词表 + 正则（builtin_wordlist）** | 1–2 人日 | 输/出双端命中式拦截、可配置、可关闭 | **选中（默认）** |
| 本地分类模型（如安全分类小模型） | +3–5 人日 + 显存占用 | 语义级识别 | 不选（与 16GB 显存争用、收益边际低） |
| 云内容安全 API | 接入 1–2 人日 + 按量费 | 强识别 + 合规背书 | 保留为 `ModerationProvider: cloud` 适配器，上云期启用 |

- 落点：中间件在**输入进 LLM 前**与**输出回流后**各拦一次；命中且 `block_on_match=true` → 返回中性提示 + 4031 错误码，**不产生 LLM 调用**。
- 单机自部署允许**整体关闭**（`enabled=false`）；输出默认附"AI 生成内容"标识（合规要求）。
- 风险提示：基础词表拦截率/误拦率需按 PRD §8 指标（≥95% / ≤5%）抽检调词表。

### 9.4 OPEN-006 裁决输入：中文分词与索引成本评估

**结论：内容库"搜索 + 筛选"进 P0（低成本），跨会话全文检索归 v2（高成本）。**

| 方案 | 成本 | 中文效果 | 归期 |
|---|---|---|---|
| **pg_trgm + ILIKE（列表级搜索/筛选）** | 0.5–1 人日 | 子串/模糊够用 | **P0** |
| 前端关键词高亮 | 0.5 人日 | — | P0 |
| Meilisearch 服务 + 索引同步 | 3–5 人日 + 运维 | 好 + 排序 | v2 |
| PG tsvector + zhparser/pg_jieba（镜像编译） | 2–3 人日 | 好 + 排序 | v2 |

- 依据：MVP 数据量 < 10 万条，`pg_trgm` 子串检索足够且有索引支撑；分词器/独立服务属边际收益低、部署负担高。
- 结论支持设计师主张的"**内容库搜索/筛选进 P0**"（低成本可满足），同时确认"**会话历史全文搜索（F15）进 P1/v2**"。

### 9.5 OPEN-004 裁决输入：ST 卡片兼容

**结论：支持导入（V1/V2/V3 JSON/PNG/WEBP），内部用自有 Schema + 转换器，导出可回 ST V2。** 详见 ADR-008 与 `docs/spec/schemas.md` §3.4/§4.4。满足 PRD"多本世界书绑定 + 完整导出"（`worldbook_ids: []` 数组 + `POST /export/bundle`）。

### 9.6 其他对齐点

- **F9 会话分支**：新增 `POST /sessions/{id}/fork`（从指定消息分叉出一条独立会话）。
- **F10 埋点**：新增 `POST /events`（**仅本地落盘、匿名、不上报**，事件命名 `{对象}_{动作}`）+ `GET /diagnostics/export`（脱敏诊断包）。
- **首启"15 分钟"**：`/system/selfcheck` + `/config/llm/test` + `/onboarding/samples` 三件套支撑向导链路。
- **未受架构阻断的未决项**：OPEN-003（题材，Schema 与题材无关，已解耦）、OPEN-005（产品定名，仅影响包名/镜像名，不影响架构）。

