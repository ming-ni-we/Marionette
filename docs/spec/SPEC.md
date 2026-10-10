# Spec — 提线 (Marionette) v1.0

> 生成日期：2026-10-09
> 基于：`docs/01-prd.md`（PRD v1）+ `docs/02-architecture.md`（架构 v1）+ `docs/03-uiux.md`（UIUX v1）
> 状态：**已锁定**（用户已确认三文档 + 四项形态决定）
> 形态：**云端私有部署 · 仅限自用**（不对外运营、不发行）
> 本 Spec 是团队内部唯一契约。开发以本文为准，任何超出「§2 MVP 范围」的内容一律走 §13 变更流程。

---

## 1. 产品定义

- **一句话描述**：在你自己的实例上，**15 分钟内**从零开始一场带世界书触发与长期记忆的角色扮演——角色卡、世界书、图集全程以**可移植文件**形态进出，随时完整带走，换模型不换档。
- **目标用户**：**当前仅单一用户（本人自用）**。三个 persona 作为设计参照而非法定用户：
  - 林澈 / 26 / 独立同人写手（核心参照）——痛点：AI 记不住伏笔、被酒馆配置劝退、图与角色对不上
  - 周雨桐 / 22 / 陪伴玩家——痛点：失忆、尺度被吞、平台改规则就没了
  - 老张 / 34 / 跑团 DM——痛点：世界书递归要手搓、NPC 管理乱、立绘散落
- **核心问题**：现有方案把「创作」和「运行」割裂了——能创作的工具门槛高到劝退，开箱即用的工具又拿走了创作主权与记忆控制权。**没有人把「创作者级深度」和「15 分钟上手」合到同一个形态里。**

---

## 2. MVP 范围（锁定——不在此列表的功能一律不做）

RICE = (Reach × Impact × Confidence) / Effort

| 优先级 | # | 功能 | 验收标准摘要 | RICE |
|---|---|---|---|---|
| P0 | F1 | 首启向导 + 单一后端接入 + 连通性自检 | 填一个后端 → 测试连接 → 3s 内明确成败 + 归类失败原因 | 7.50 |
| P0 | F16 | 内容库搜索与筛选（卡/世界书/预设/图集） | 列表页支持关键词 + 标签 + 排序 | 9.00 |
| P0 | F2 | 角色卡编辑器 | 描述/人格/场景/开场白/示例对话/头像齐全，PNG/JSON 导入导出 | 6.00 |
| P0 | F3 | 内容仓库（卡/世界书/预设） | 存得住、导得出、Tavern V2 双向兼容 | 5.00 |
| P0 | F4 | 世界书编辑器 | 关键词触发条目 + 顺序 + 优先级 + **按角色绑定多本** | 4.50 |
| P0 | F5 | 世界书运行时触发 | 会话中按关键词/正则/递归注入上下文，命中可观测 | 4.32 |
| P0 | F6 | 内容安全审核层 | 输入/输出双端，规则可配置、**可整体关闭** | 4.00 |
| P0 | F7 | 会话运行时引擎 | 会话状态机 + 上下文装配 + LLM 调度（流式） | 3.75 |
| P0 | F8 | 记忆 / 摘要系统 | 自动摘要 + 关键事实落库 + 会话内召回 | 3.60 |
| P0 | F9 | 会话管理 | 多会话 + 重 roll/分支 + 导出 | 3.20 |
| P0 | F12 | 图像生成钩子（**轻量版**） | 触发 → 出图 → **自动归档进角色图集** | 1.92 |
| P0（子集） | F11 | 角色图集 / 资产库 | 仅做「存图 + 按角色归档 + 可检索」 | 2.80 |
| P0（最简版） | F10 | 埋点 + 自诊断日志 | 本地匿名落盘 + 可导出诊断包 | 3.20 |
| P1 | F13 | 预设 / 采样参数编辑 | 系统提示 + 采样档位（简化版） | 1.87 |
| P1 | F14 | 向量检索记忆增强 | Schema 留字段，**v1 默认关闭** | 1.20 |
| v2 | F15 | 跨会话历史全文检索 | 与 F16 口径不同：F16 搜「内容资产」，F15 搜「历史消息」 | 0.60 |

**MVP 一句话**：编辑一张「现代日常向」角色卡 → 挂一本世界书 → 一键开一场会话 → 世界书触发 + 记忆摘要生效 → 场景出图并存入角色图集。

---

## 3. 明确不做（Out-of-Scope — 锁定）

| 不做的功能 | 原因 | 何时考虑 |
|---|---|---|
| 广场（发现/浏览/评分/续作/派生） | 仅限自用，无社交分发场景；且需服务端运营 | 若将来对外开放 |
| 群聊 / 多角色同台 | 运行时复杂度高，非最小闭环 | v2 |
| 多租户 / 账号体系 | 仅单一用户；只需一道访问门，不做用户模型 | 若将来对外开放 |
| 云端同步 / 多端 | 已直接是云端单实例，无同步需求 | 有第二台设备时 |
| 原生移动端 App | 桌面浏览器优先 | 有明确需求后 |
| 语音 TTS / Live2D / 动态立绘 | 非创作→运行核心 | v2 / v3 |
| 完整 ComfyUI 工作流编辑器 | 会拖垮「15 分钟」承诺 | v2 |
| 向量检索 / RAG 记忆（F14） | 先用「关键词触发 + 摘要」验证「记忆默认生效」假设 | P1 → v2 |
| 跨会话历史全文检索（F15） | v1 数据量下价值低 | v2 |
| **商店发行 / 版号 / 商业化** | **用户明确仅限自用，不对外开放** | 若将来对外 |
| **内容安全审核的服务端全量分类能力** | 自用形态下不需要；基础词表足够 | 若将来对外开放 |

---

## 4. 技术架构（锁定 — 含版本锚定）

### 4.1 选型表

| 层 | 技术 | 版本 | 锁定原因 |
|---|---|---|---|
| 前端框架 | React + Vite + TypeScript | 19.1 / 7 / 5.8 | SPA 单实例，无 SSR 需求 |
| 前端 UI | shadcn/ui (Radix primitives) | 最新 | 组件源码可控、无运行时锁定 |
| CSS | Tailwind CSS | 4.1（`@theme`） | Token 直接映射为 CSS 变量 |
| **图标库（唯一）** | **Lucide (`lucide-react`)** | 1.0+ | 描边统一 2px、尺寸 16/20/24px，**全项目不得混用其他图标库** |
| 状态管理 | Zustand / TanStack Query | 5 / 5 | UI 状态与服务器缓存分离 |
| 后端框架 | FastAPI + Uvicorn | 0.141.1 / 0.48 | 异步 + 原生 OpenAPI + SSE |
| 语言/校验 | Python / Pydantic | 3.12 / 2.13.4 | 与前端契约双向校验 |
| 数据库 | PostgreSQL + pgvector | 18.6 / 0.8.6 | 单库同时承担关系 + 向量 + 模糊检索 |
| ORM / 迁移 | SQLAlchemy (async) + Alembic | 2.0 / 1.18 | 显式迁移，禁止 `create_all` 上生产 |
| 全文/模糊检索 | `pg_trgm` GIN + `ILIKE` | 内置 | 对 CJK 免分词即可子串/模糊匹配，零额外服务 |
| LLM 适配 | **自研 OpenAI 兼容薄层** | — | 一份代码接多家，避免绑定厂商 SDK |
| 本地推理（可选） | Ollama | 0.33.x | **降级为可选后端**（见 §4.3） |
| 容器编排 | Docker Compose | Engine 28.x / Compose v2 | 单实例足够，上 K8s 是过度设计 |
| 反向代理 | Caddy（自动 HTTPS） | 2.x | 自动证书，零运维 |

### 4.2 分层与依赖方向

```
表现层 (React SPA) → 接入层 (FastAPI 路由 + SSE) → 业务层 (8 个 Domain Service)
  → 适配层 (可替换接缝) → 数据层 (PostgreSQL + 卷)
```

**禁止反向依赖**：业务层不得 import 任何具体 LLM/图像 SDK，只能依赖 `LLMProvider` / `ImageProvider` / `AssetStore` / `ModerationProvider` / `AuthProvider` 接口。

业务层 8 个 Service：`ContentSvc` / `SessionSvc` / `WorldInfoEngine` / `ContextAssembler` / `MemorySvc` / `LLMRouter` / `ImageHook` / `STCompatAdapter`。

### 4.3 部署形态（**相对 Phase 1 的关键变更**）

原设计是「单机 Docker 一键起」；现锁定为**云端私有单实例**：

| 维度 | 锁定值 |
|---|---|
| 服务器 | 单台云服务器（建议 2 vCPU / 4 GB 起，Ubuntu 22.04 LTS） |
| 容器 | `caddy`（反代 + HTTPS）+ `api`（同时托管 SPA 静态产物）+ `db`（`pgvector/pgvector:pg18`） |
| 入口 | 域名 + Caddy 自动 HTTPS；**必须**有访问控制（见下） |
| **访问控制** | `AuthProvider` 从 no-op 改为**单用户口令 + 签名会话令牌**（HttpOnly Cookie）。不做用户表、不做注册、不做密码找回 |
| **LLM 默认后端** | **云端 API（用户自备 key）**。原「自动探测本机 Ollama」改为：探测到可访问的 Ollama 端点才启用，否则走云端 API |
| **图像生成** | **云端图像 API（BYOK）** —— `ImageProvider` = `CloudImageProvider`（OpenAI 兼容 images 接口或国内图像 API）。本机 ComfyUI 适配器（`LocalComfyUIProvider`）代码保留但 **v1 默认关闭**，留作后续可选实现 |
| 资产存储 | `AssetStore` = 服务器本地卷 `./data/assets`（接口已抽象，可切对象存储） |
| 备份 | `pg_dump` 每日 cron + `assets` 增量同步；保留 ≥7 天 |
| 环境变量 | 全部经 `.env` 注入，**密钥不入库、不进 git** |

> **合规口径（用户已决策仅限自用）**：不面向境内公众提供服务 → **通常无需**大模型备案/登记。**注意（残留风险）**：一旦实例被不特定人访问到，「自用」在事实上即变成「面向公众」。**因此访问控制是合规前置条件，不是可选项。**

---

## 5. API 端点清单（锁定 — 开发唯一依据）

> 完整定义以 `docs/spec/openapi.yaml`（OpenAPI 3.0）为准：**37 path / 53 operation / 46 schema / 14 参数组件**。

| 分组 | Method + Path | 功能 |
|---|---|---|
| System | `GET /api/v1/system/info` · `GET /api/v1/system/selfcheck` | 版本信息、启动自检 |
| Auth | **公开端点**（不需令牌）：`POST /api/v1/auth/login` · `POST /api/v1/auth/logout` · `GET /api/v1/auth/session` | 访问控制：单用户口令登录（`{password}` → 200 + HttpOnly Cookie；401 `auth_failed`；5 次错口令 → 429 + `Retry-After`）/ 登出（清 Cookie）/ 会话校验（供前端路由守卫） |
| Cards | `GET|POST /api/v1/cards` · `GET|PATCH|DELETE /api/v1/cards/{cardId}` · `GET /api/v1/cards/{cardId}/assets` | 角色卡 CRUD + 该卡资产 |
| WorldBooks | `GET|POST /api/v1/worldbooks` · `GET|PATCH|DELETE /{worldBookId}` · `POST /{worldBookId}/test` | 世界书 CRUD + **触发自测** |
| Presets | `GET|POST /api/v1/presets` · `GET|PATCH|DELETE /{presetId}` | 预设 CRUD |
| Sessions | `GET|POST /api/v1/sessions` · `GET|PATCH|DELETE /{sessionId}` | 会话生命周期 |
| Sessions | `POST /{sessionId}/messages` · `POST /{sessionId}/stream` · `POST /{sessionId}/interrupt` · `POST /{sessionId}/regenerate` · `POST /{sessionId}/fork` · `GET /{sessionId}/last-context` | 对话（流式）、中止、重 roll、分支、**上下文检视** |
| Images | `POST /api/v1/images/jobs` · `GET /api/v1/images/jobs/{jobId}` | 出图任务（异步） |
| Assets | `POST /api/v1/assets` · `GET /api/v1/assets` · `GET|DELETE /{assetId}` · `GET /{assetId}/content` | 上传 / **列表（9 参数）** / 取用 / 删除 |
| Import/Export | `POST /api/v1/import/card` · `POST /api/v1/import/worldbook` · `POST /api/v1/export/bundle` · `GET /api/v1/export/card/{cardId}` | Tavern 兼容与可移植导出 |
| Onboarding | `POST /api/v1/onboarding/samples` | 内置示例卡（**现代日常向 3–5 张**） |
| Config | `GET|PUT /api/v1/config/llm` · `POST /api/v1/config/llm/test` · `GET|PUT /api/v1/config/moderation` · `POST /api/v1/config/comfyui/probe` | 后端 / 审核 / 出图配置 |
| Events/Diag | `POST /api/v1/events` · `GET /api/v1/diagnostics/export` | 匿名埋点、诊断包导出 |

**统一约定**：响应体统一信封 `Envelope`；错误体含 `error_class`（7 类枚举：`model_not_found` / `endpoint_invalid` / `auth_failed` / `quota_exhausted` / `network_unreachable` / `timeout` / `unknown`）+ 面向用户的中文 `message` + `model_seen`。列表端点统一支持 `Q` / `Tags` / `Sort` / `Order` / `Page` / `Limit`。

**公开面（免鉴权，对应 AC-02）**：仅 `GET /api/v1/system/info`、`GET /api/v1/system/selfcheck`、`/api/v1/auth/*` 三个面；其余 `/api/v1/**` 一律要求有效会话令牌，否则 401。健康检查必须公开，否则监控与容器 healthcheck 无法工作。

---

## 6. 数据库表清单（锁定）

> 字段级定义以 `docs/spec/schemas.md` 为准；此处锁定**表名、关键索引与关联**。

| 表名 | 核心字段 | 索引 | 关联 |
|---|---|---|---|
| `cards` | `id` · `owner_id`(默认`local`) · `name` · `spec` · `spec_version` · `data`(JSONB) · `extensions`(JSONB) · 时间戳 | `GIN(name gin_trgm_ops)` · `GIN(tags)` · `(owner_id, updated_at DESC)` | 1:N → `assets` |
| `worldbooks` | `id` · `owner_id` · `name` · `spec_version` · `data`(JSONB，含 entry 列表) | `GIN(name gin_trgm_ops)` | N:M ↔ `cards`（**一卡可绑多本**） |
| `presets` | `id` · `owner_id` · `name` · `data`(JSONB) | `GIN(name gin_trgm_ops)` | 1:N → `sessions` |
| `sessions` | `id` · `owner_id` · `card_id` · `preset_id` · `title` · `state_machine`(JSONB) · `scene`(JSONB) · `memory`(JSONB) · 时间戳 | `(owner_id, updated_at DESC)` · `(card_id)` | → `cards` / `presets`；1:N → `messages` |
| `messages` | `id` · `session_id` · `seq` · `role` · `content` · `meta`(JSONB，含命中的世界书条目 / 图资产 id) | `UNIQUE(session_id, seq)` | → `sessions` |
| `memory_snapshots` | `id` · `session_id` · `up_to_seq` · `summary` · `facts`(JSONB) | `(session_id, up_to_seq DESC)` | → `sessions` |
| `content_embeddings` | `id` · `entity_type` · `entity_id` · `chunk_idx` · `content` · `embedding vector` | HNSW（预留） | **v1 建表但不写入不查询** |
| `image_jobs` | `id` · `session_id` · `card_id` · `message_id` · `status` · `provider` · `prompt_id` · `asset_id` · `archived` · `error` | `(status)` · `(session_id)` | 完成后**服务端自动**产 `assets` 行 |
| `assets` | `id` · `owner_id` · `kind` · `filename` · `content_type` · `size_bytes` · `storage_key` · `card_id` · `session_id` · `message_id` · `tags` · `meta` | `(card_id, created_at DESC)` · `GIN(tags)` | → `cards` / `sessions` / `messages` |
| `app_config` | `key` · `value`(JSONB) · 时间戳 | PK(`key`) | 单用户配置（LLM / 审核 / 出图） |

**硬约束**：`ImageJob` 转为 `done` 时，**由服务端**创建 `kind=generated` 的 `assets` 行（回填 `card_id`/`session_id`/`message_id` + `meta`，置 `archived=true`），**前端禁止自行拼装归档逻辑**。

---

## 7. 页面清单（锁定）

| 页面 | 路由 | 核心组件 | 对应 API | 密度 |
|---|---|---|---|---|
| 首启向导 | `/setup` | 单后端接入表单 + 测试连接 + 错误分类 + 示例卡导入 | `/config/llm` `/config/llm/test` `/onboarding/samples` | studio |
| 工作台 / 内容库 | `/` | 左 rail（含实例与模型状态位）+ 内容区（继续上次 + 卡/世界书/预设分区）+ **搜索框 + 标签筛选 + 排序** | `/cards` `/worldbooks` `/presets` `/sessions` | studio |
| 角色卡编辑器 | `/cards/:cardId` | 三栏（字段导航 / 分组折叠表单 / 实时气泡预览）+ Quick/Advanced + Token 计数 | `/cards/{id}` `/import/card` `/export/card/{id}` | studio |
| 世界书编辑器 | `/worldbooks/:id` | 条目列表 + 触发条件 + 优先级 + 预算 + **命中测试面板（三态）** | `/worldbooks/{id}` `/worldbooks/{id}/test` | studio |
| 预设编辑器（P1） | `/presets/:id` | 系统提示 + 采样档位 | `/presets/{id}` | studio |
| 会话列表 | `/sessions` | 列表 + 状态筛选 + 搜索 | `/sessions` | studio |
| 会话运行时 | `/sessions/:id` | 68ch 单列阅读（Serif + 1.75 行高）+ 顶部细指示条 + 右侧抽屉（上下文检视 / 分支树）+ 沉浸模式 | `/sessions/{id}/stream` `/messages` `/regenerate` `/fork` `/interrupt` `/last-context` | session |
| 角色图集 | `/assets` | 以角色为中心的网格 + 搜索/筛选 + 出图归档入口 | `/assets` `/cards/{id}/assets` `/images/jobs` | studio |
| 设置 | `/settings` | 访问口令 · LLM 后端 · 审核层（4 控件 + 关闭风险确认）· 出图后端 · 诊断包导出 | `/config/*` `/diagnostics/export` | studio |

**空状态**：无角色 / 无会话 / 无图集 / 未连后端，一律给引导与示例，**不得出现空白页**。

---

## 8. 设计 Token（锁定）

- **唯一真源**：`design/design-tokens.json` → 导出 `design/design-tokens.css`（primitive → semantic → density 三层）
- **落地方式**：Tailwind CSS v4 `@theme` + shadcn/ui CSS 变量（映射见 `docs/03-uiux.md` §5.1）；Phase 2 必交 `globals.css` 主题预设文件，与 Token 同源，**前端禁止手抄变量**
- **主色**：琥珀暖光 Amber — 深色 `#E3AE3E` (on `#0A0B0D`) / 浅色 `#9C6F19`
- **表面**：深色 `bg #101215` · `surface #16181C` · `fg #E9EBEE`；浅色 `bg #F4F5F6` · `fg #1C1F24`
- **语义色**：success `#57BE84` · warn `#E2803A` · danger `#EC6A61`
- **字体**：`--font-sans: "Inter","Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui`；`--font-serif: "Noto Serif SC"`（仅会话叙事正文）；`--font-mono: "JetBrains Mono"`（仅 Token 计数/参数）
- **行高**：正文 1.6，会话叙事 1.75；字重仅 400 / 500 / 600
- **图标**：**Lucide 唯一**，24×24 网格 / `stroke-width: 2` / 尺寸仅 16·20·24px / `currentColor`
- **主题与密度**：深色默认 + 浅色完整可用；`studio`（创作端，高密度）/ `session`（运行端，沉浸）两档密度，**同一套主题派生，不做两套视觉系统**
- **对标品牌**：Linear + Obsidian + Raycast（辅 Cursor / VS Code）
- **明令禁止**：emoji 作功能图标 · 紫→粉渐变主视觉 · 发光边框 + 装饰性毛玻璃 · 硬编码颜色（除 `#fff`/`#000`）· 弹跳缓动

---

## 9. 验收标准（锁定 — EARS 格式，测试唯一依据）

| 编号 | 功能 | EARS 验收标准 | 优先级 |
|---|---|---|---|
| AC-01 | 部署 | When 在云服务器执行 `docker compose up -d`，系统**必须**在 90 秒内就绪；失败时**必须**给出中文原因与修复步骤 | P0 |
| AC-02 | 访问控制 | 除 `/api/v1/system/*` 与 `/api/v1/auth/*` 外，While 未持有有效会话令牌，任何 `/api/v1/**` 请求**必须**返回 401，**不得**泄露任何内容数据 | P0 |
| AC-03 | 访问控制 | When 提交正确口令，系统**必须**签发 HttpOnly 会话令牌；连续 5 次错误口令**必须**触发速率限制 | P0 |
| AC-04 | LLM 接入 | When 用户填一个可用端点并点「测试连接」，系统**必须**在 3 秒内返回成功并设为默认后端；If 失败，**必须**归类到 7 类 `error_class` 之一并回显 `model_seen` | P0 |
| AC-05 | 卡片导入 | When 导入一张 Tavern V2 PNG 卡，系统**必须**完整还原描述/人格/开场白/示例对话/头像 | P0 |
| AC-06 | 卡片导出 | When 导出角色，系统**必须**生成可移植文件包（卡 + 绑定世界书 + 预设），**可回导成 Tavern V2 格式** | P0 |
| AC-07 | 世界书触发 | When 会话中说中某条目关键词，该条目内容**必须**出现在注入上下文，且角色回复体现该设定 | P0 |
| AC-08 | 世界书可观测 | When 调用命中测试接口，系统**必须**逐条目返回 `matched` / `match_type` / `in_budget` / `token_count` / `final_position` | P0 |
| AC-09 | 记忆 | When 会话进行到 60 轮后询问第 3 轮提过的设定，角色**必须**能正确回忆（由摘要记忆召回） | P0 |
| AC-10 | 出图归档 | When 图像任务完成，服务端**必须**自动创建 `kind=generated` 资产并登记进该角色图集；**前端不得**参与拼装 | P0 |
| AC-11 | 审核层 | While 审核层开启，命中违规规则的输入**必须**被拦截并给中性提示、**不产生 LLM 调用**；When 关闭审核层，**必须**不再拦截 | P0 |
| AC-12 | 审核关闭 | When 用户关闭审核层，系统**必须**先展示风险确认，**不得**静默关闭 | P0 |
| AC-13 | 内容检索 | When 在内容库输入关键词/选择标签，系统**必须**返回过滤后的结果并保持排序一致 | P0 |
| AC-14 | 会话分支 | When 在某条消息上创建分支，系统**必须**保留原会话不变并生成可独立继续的新会话 | P0 |
| AC-15 | 流式对话 | When 发送消息，系统**必须**流式返回；When 用户点击中止，系统**必须**立即停止且**不得**留下半条脏消息 | P0 |
| AC-16 | 空状态 | While 无角色 / 无会话 / 未连后端，页面**必须**展示引导与示例，**不得**出现空白页 | P0 |

---

## 10. 边界与约束

- **浏览器**：Chrome / Safari / Firefox 最新两版；不支持 IE。桌面优先，响应式断点按 Token 定义。
- **性能目标**：首屏 < 3s；本地 API p95 < 500ms；流式首 token < 2s（云端模型首 token 依赖第三方，不计入）。
- **上下文预算**：默认 8K–16K，可配；超限**必须**给出截断提示，不得静默丢弃。
- **并发**：单实例支持多会话并存；出图与对话**互不阻塞**。
- **离线**：云端部署下无离线要求；LLM 为本地模型时才要求全离线可用（v1 不作为验收项）。
- **安全**：`.env` 管理密钥、不入库不进 git；API key 加密存储；输入校验；公网入口强制 HTTPS。
- **备份**：`pg_dump` 每日 + `assets` 增量；保留 ≥ 7 天；**恢复流程必须有文档且实际演练过一次**。
- **数据规模上限**：卡片/条目 < 10 万条（超出则引入 Meilisearch，见 ADR-005 升级路径）。
- **合规**：仅限自用，不面向公众 → 不适用备案/登记；**访问控制为合规前置条件**。运行时输出附「AI 生成内容」标识。
- **可访问性**：键盘可达 + 对比度达 WCAG 2.1 AA 基本合规。

---

## 11. 内嵌已知坑（从项目记忆拉取）

> 来源：`.workbuddy/memory/pitfalls.jsonl`

| 坑 | 技术栈指纹 | 根因 | 修法 |
|---|---|---|---|
| `No CUDA GPUs are available` | `pytorch` + `sm_120` | RTX 50 系为 sm_120，稳定版 PyTorch 可能未编译该内核 | 装 cu128+ 轮子；`pip install` 报 "already satisfied" 时用 `--force-reinstall --no-cache-dir`；驱动 ≥ 570 |
| `CUDA_VISIBLE_DEVICES=""` 导致 GPU 隐身 | `pytorch` | 空串 ≠ 未设置，PyTorch 会认为无可见设备而 `nvidia-smi` 正常 | 不要留空串；要么删除该变量，要么给合法索引 |
| 容器内访问宿主机服务失败 | `docker-compose` (Windows/macOS) | 容器内 `127.0.0.1` 指向容器自身 | 用 `host.docker.internal`；Linux 需显式 `extra_hosts` |
| `pgvector` 扩展缺失 | `postgres` 18 | 官方 `postgres` 镜像不含该扩展 | 必须用 `pgvector/pgvector:pg18`；启动后 `CREATE EXTENSION vector` |
| 中文子串搜不到 | `postgres` + FTS | 默认分词器把连续中文当整段一个 token | 用 `pg_trgm` GIN + `ILIKE`，不装分词器（ADR-005） |
| Alembic 与模型定义漂移 | `sqlalchemy` 2.0 | 手改表结构未生成迁移 | 禁止 `create_all` 上生产；改模型必须 `alembic revision --autogenerate` 并人工复核 |

---

## 12. 端到端验证步骤（Spec 锁定的最后一项）

```bash
# 1. 起服务（云服务器）
cp .env.example .env    # 填 DB_PASSWORD / ACCESS_PASSWORD / LLM_BASE_URL / LLM_API_KEY
docker compose up -d
docker compose ps       # 断言：caddy / api / db 三容器均 healthy

# 2. 健康检查
curl -s https://<domain>/api/v1/system/selfcheck
# 断言：200 + {"db":"ok","pgvector":"ok","llm":{"reachable":true}}

# 3. 访问控制（关键错误流）
curl -s -o /dev/null -w '%{http_code}' https://<domain>/api/v1/cards
# 断言：401（未带令牌必须被挡）

# 4. 登录取令牌
curl -s -c jar.txt -X POST https://<domain>/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"password":"<ACCESS_PASSWORD>"}'
# 断言：200 + Set-Cookie 含 HttpOnly 会话令牌

# 5. 核心成功流：导入示例卡 → 建会话 → 发一句话
curl -s -b jar.txt -X POST https://<domain>/api/v1/onboarding/samples
CARD=$(curl -s -b jar.txt https://<domain>/api/v1/cards | jq -r '.data.items[0].id')
SID=$(curl -s -b jar.txt -X POST https://<domain>/api/v1/sessions \
  -H 'Content-Type: application/json' -d "{\"card_id\":\"$CARD\"}" | jq -r '.data.id')
curl -s -b jar.txt -N -X POST https://<domain>/api/v1/sessions/$SID/stream \
  -H 'Content-Type: application/json' -d '{"content":"你好"}'
# 断言：SSE 流式返回 token，最终落库一条 assistant 消息

# 6. 世界书触发（关键成功流）
curl -s -b jar.txt -X POST https://<domain>/api/v1/worldbooks/<WB>/test \
  -H 'Content-Type: application/json' -d '{"text":"<含关键词的样例文本>"}' | jq '.data.entries[] | {matched,in_budget}'
# 断言：至少一条 matched=true；三态（命中且在预算内 / 命中被挤出 / 未命中）均可区分

# 7. 备份可恢复（演练一次）
docker compose exec db pg_dump -U postgres marionette > /tmp/bak.sql
# 断言：文件非空，且能在临时库中成功 restore
```

---

## 13. 变更记录

| 日期 | 变更内容 | 原因 | 影响范围 |
|---|---|---|---|
| 2026-10-09 | Spec v1.0 建档，锁定 §1–§12 | 用户确认三文档，进入开发契约阶段 | 全项目 |
| 2026-10-09 | **形态变更**：部署形态从「单机 Docker 一键起」→「云端私有单实例」 | 用户决定部署到云端（仅限自用） | §4.3、§5（新增 Auth 端点）、§6（`app_config`）、§9（AC-01~03）、§10、§12 |
| 2026-10-09 | **命名落地**：项目名定为「提线」(Marionette) | 用户拍板 OPEN-005 | 全文标题、镜像/包名前缀 `marionette-`、UI 文案 |
| 2026-10-09 | **切片题材锁定**：「现代日常向」通用角色卡 | 用户拍板 OPEN-003 | §2 F1/F2 字段权重、§5 `/onboarding/samples`、§7 编辑器中区字段顺序 |
| 2026-10-09 | **合规口径收敛**：不面向公众 → 备案/登记不适用；访问控制升级为合规前置 | 用户决定不对外开放 | §3、§4.3、§9 AC-02/03、§10 |
| 2026-10-09 | **出图方案定案**：云端图像 API（BYOK），`ImageProvider` = `CloudImageProvider`；本机 ComfyUI 适配器保留但默认关闭 | 用户拍板 OPEN-009 方案 C | §4.3 图像生成行 |
| 2026-10-09 | **部署载体定案**：腾讯云轻量应用服务器 · 2核4G · **境外（中国香港）地域** · Ubuntu 22.04 · 包年 | 免 ICP 备案即可用域名 + HTTPS（境内地域绑定域名须先备案）；深圳访问香港延迟低 | §4.3 部署形态表 · §12 端到端验证步骤 |
| 2026-10-09 | 待定项：云端形态下出图方案 | 云端无本机 ComfyUI 与 GPU | §4.3 图像生成行、OPEN-009 |
| 2026-10-09 | **契约补齐（小改）**：`openapi.yaml` 补 3 条 Auth 端点（login/logout/session）+ `LoginRequest`/`LoginResponse`/`SessionInfo` schema，并将 `ErrorEnvelope` 对齐为含 `error_class`+`model_seen`；AC-02 措辞精确化为「除 system/auth 公开面外一律 401」 | 后端已实现并实测通过，契约文件滞后（spec-as-contract 同步）；§12 健康检查需公开，与旧 AC-02 措辞矛盾 | §5（Auth 行 + 公开面说明 + 计数 34/50/43 → 37/53/46）、§9 AC-02、openapi.yaml |

---

## 变更流程（Spec 锁定后）

**小改**（同时满足：不新增 API 端点、不新增表、不影响 > 2 个页面、不改变核心流程）→ 更新 §13 变更记录 → 继续开发。

**大改**（满足任一：新增 ≥ 2 个端点、新增表、影响 > 2 个页面、改变核心用户流程）→ 回需求澄清 → 更新三文档 → 更新 Spec。
