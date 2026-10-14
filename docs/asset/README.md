# 提线 (Marionette) · 项目资产总纲

> **这是并行任务的唯一入口。** 任何新开的任务，先读这一页定位自己，再读对应任务卡。
> 生成日期：2026-10-12 · 仓库：https://github.com/ming-ni-we/Marionette
> 线上实例：http://101.33.117.223 · 服务器目录 `/opt/marionette` · 形态：云端私有单实例，仅限自用

---

## ⚠️ 第 0 步：先把代码拿到手（**跳过这步会浪费一整个任务**）

**新沙箱里默认没有任何项目代码。** 它只会挂载空的 `/workspace`，不会自动同步源码。

**动手前必须确认：**

| 问题 | 答案 |
|---|---|
| 代码在哪？ | **服务器 `ubuntu@101.33.117.223:/opt/marionette` ＝ 权威运行版** |
| GitHub 上是新版吗？ | ✅ **是（2026-10-14 起）**。`ming-ni-we/Marionette` 远端 `main` = `5d989ed`… 现已含 S1–S14 全部代码 + 火影剧情资产，与本地一致 |
| 怎么拿？ | **`git clone https://github.com/ming-ni-we/Marionette.git`**（已是完整最新版）；或 `rsync` 从服务器拉 |

```bash
# 取代码（会排除 .env / data / backups 等敏感与运行时目录）
rsync -az --exclude='.env' --exclude='data/' --exclude='backups/' \
      --exclude='.backup-env' --exclude='node_modules/' --exclude='.venv/' \
      ubuntu@101.33.117.223:/opt/marionette/  ./marionette/

# 自检：这些 S12 文件必须存在，缺任一说明你拿的是旧版
ls marionette/backend/app/models/world.py \
   marionette/backend/app/services/director.py \
   marionette/backend/alembic/versions/0002_worlds.py \
   marionette/frontend/src/pages/story-runtime.tsx
```

> **完整说明见 [`task-GET-CODE.md`](./task-GET-CODE.md)**（含凭据、备选路径、开工自检清单、
> 以及「联调还需要 DB / LLM / 服务」的依赖清单）。
>
> **不要**用 `find / -name SPEC.md` 搜不到就断言「项目不存在」——
> 在干净沙箱里那个结果**必然为空**，证明不了任何事情。

---

## 0. 30 秒速览

**这是什么**：一个 AI 角色扮演平台，双核形态 —— **创作工作室**（角色卡/世界书/预设/图集编辑器）+ **运行时引擎**（把创作产物编排成一场会话：状态机、世界书触发、长期记忆、LLM 调度、出图钩子）。

**当前在做什么**：把平台从「单角色 1v1 对话」升级为「**AI 导演驱动的多角色剧情引擎**」。这是 14 步改造计划（S1–S14），目前 **12/14 完成**。

**一句话进度**：后端剧情引擎（S1–S9）**全量完成**、前端类型与世界观管理页（S10–S11）**全量完成**、**剧情演出页（S12）全量完成**；只剩**会话列表集成（S13）→ 上线部署（S14，真库联调已提前跑通）**。

```
S1  ✅ worlds 表 + 迁移          S8  ✅ action_suggester.py
S2  ✅ complete_chat 非流式      S9  ✅ API 端点 + worlds 路由
S3  ✅ story_state.py            S10 ✅ 前端类型 + 双白名单
S4  ✅ director.py（三层降级）    S11 ✅ 世界观创建页
S5  ✅ context_assembler +3 段    S12 ✅ 剧情演出页      ← 刚完成
S6  ✅ chat.py 剧情分支            S13 ⬜ 会话列表集成    ← 当前
S6  ✅ chat.py 剧情分支           S13 ⬜ 会话列表集成
S7  ✅ opening.py                S14 ⬜ 联调 + 回归 + 部署
```

---

## 1. 目录导航（按你要做的事找）

| 你要做的事 | 读哪个文件 |
|---|---|
| **⚠️ 先把代码拿到手（开工第一步）** | [`task-GET-CODE.md`](./task-GET-CODE.md) |
| **接手任意开发任务** | 本文 → 对应 `task-*.md` |
| 了解已完成部分的技术细节 | [`01-architecture.md`](./01-architecture.md) |
| 跑测试 / 构建 / 提交前自检 | [`02-build-and-test.md`](./02-build-and-test.md) |
| 部署到服务器 | [`03-deployment.md`](./03-deployment.md) |
| 踩过的坑（**动手前必读**） | [`04-pitfalls.md`](./04-pitfalls.md) |
| 并行任务拆分与边界 | [`05-parallel-tasks.md`](./05-parallel-tasks.md) |
| 剧情引擎完整设计 | [`06-story-engine-spec.md`](./06-story-engine-spec.md) |
| 现状清单 / 待办 / 风险 | [`07-status-and-backlog.md`](./07-status-and-backlog.md) |
| **改完代码怎么发布（推 GitHub）** | [`08-release-discipline.md`](./08-release-discipline.md) |
| **接下来要做什么（唯一权威路线图）** | [`09-project-plan.md`](./09-project-plan.md) |
| **玩家体验优化（S15，7 项）** | [`09-project-plan.md`](./09-project-plan.md) §4.5 |
| **对话配图 / 火山方舟出图（S16）** | [`task-S16-image-generation.md`](./task-S16-image-generation.md) |
| 玩家体验诊断原始报告（含核实批注） | [`11-player-experience-report.md`](./11-player-experience-report.md) |
| 文生图选型评估（含完整对比表） | [`12-image-api-selection.html`](./12-image-api-selection.html) |
| 剧情成品说明（雾隐町 / 木叶） | [`10-story-naruto.md`](./10-story-naruto.md) |

**任务卡**（每张卡都可独立领取）：

| 卡片 | 内容 | 可并行？ |
|---|---|---|
| [`task-GET-CODE.md`](./task-GET-CODE.md) | **代码在哪 / 怎么拿（新任务第一张）** | ✅ 前置必读 |
| [`task-S12-story-runtime.md`](./task-S12-story-runtime.md) | 剧情演出页（前端） | ✅ **已完成**（含交接记录） |
| [`task-S13-session-list.md`](./task-S13-session-list.md) | 会话列表集成（前端） | ⚠️ 依赖 S12 的路由约定，但可先写 |
| [`task-INFRA-ops.md`](./task-INFRA-ops.md) | 运维待办（备份/HTTPS/密码/脏数据） | ✅ 完全独立，不与代码冲突 |
| [`task-GIT-push.md`](./task-GIT-push.md) | 推送代码到 GitHub | ✅ 完全独立 |
| [`task-S16-image-generation.md`](./task-S16-image-generation.md) | 对话配图（火山方舟出图） | 🟡 链路已通，剩触发钩子 |

> 🗺️ **想知道「接下来做什么」？直接看 [`09-project-plan.md`](./09-project-plan.md)** —— 项目计划唯一权威清单。
>
> 📌 **发布纪律（所有任务适用）**：一个功能阶段做完 + 五项校验全绿 → 立刻同步到 GitHub。
> 一条命令：`cd /workspace/marionette && ./scripts/push-to-github.sh "feat(xxx): 说明"`。
> 详见 [`08-release-discipline.md`](./08-release-discipline.md)。

---

## 2. 技术栈（锁定版本，不得替换）

| 层 | 技术 |
|---|---|
| 后端 | FastAPI 0.141.1 + Uvicorn 0.48 · Python 3.12 · Pydantic 2.13.4 |
| 数据 | PostgreSQL 18 + pgvector 0.8.6（镜像 `pgvector/pgvector:pg18`） |
| ORM/迁移 | SQLAlchemy 2.0 async + Alembic 1.18 |
| 检索 | `pg_trgm` GIN + `ILIKE`（中文免分词，见 ADR-005） |
| 前端 | React 19.1 + Vite 7.3.7 + TypeScript 5.8 + Tailwind CSS 4.1 |
| 前端状态 | Zustand 5 + TanStack Query 5 + react-router 7 |
| UI | shadcn/ui + Radix + Lucide（唯一图标库） |
| 编排 | Docker Compose（`caddy` + `api` + `db`）· Caddy 2.x |

**规模**：后端 `app/` 12011 行 / 前端 `src/` 13110 行 / 前端 120 个源文件。

---

## 3. 项目铁律（违反即返工）

1. **分层单向**：`api/v1`（只做编排）→ `services`（业务逻辑）→ `adapters`（可替换接缝）→ `models`（数据）。业务层禁止 import 任何厂商 SDK。
2. **契约优先**：任何接口变更先改 `docs/spec/openapi.yaml`，再改实现。`docs/spec/SPEC.md` 是唯一契约。
3. **内容无损**：所有内容 schema 用 `extra="allow"`，未知字段不得销毁。平台字段隔离在 `extensions`。
4. **图标唯一**：只用 `@/components/icons` 导出的 Lucide 图标；禁 emoji 作功能图标、禁硬编码色值。
5. **迁移必须 Alembic**：禁止在生产用 `create_all`。改模型必须 `alembic revision --autogenerate` 并人工复核。
6. **出图归档铁律**：`ImageJob` 转 `done` 时由**服务端**自动创建 `kind=generated` 资产，前端禁止拼装归档逻辑。
7. **访问控制是合规前置条件**：形态为「仅限自用」，一旦被不特定人访问即变成「面向公众」，触发备案义务。**不要关闭口令、不要裸奔到公网**。
8. **SSE 三处白名单必须同构**：见 §6，漏一处前端静默丢事件。

---

## 4. 分层与关键文件地图

### 后端 `backend/app/`

```
api/v1/          13 个路由模块（cards, worldbooks, presets, sessions, worlds, images, assets,
                 config, system, auth, telemetry, import_export, onboarding）
services/        30 个业务模块
adapters/        Auth / LLM / Image / AssetStore / Moderation 五个可替换接缝
models/          11 张表（含 world）
schemas/         Pydantic 契约（extra="allow" 无损扩展）
core/            config, db, envelope, errors, ids, logging, security, text
alembic/versions 0001_initial_schema → 0002_worlds
```

**剧情引擎核心模块**（本轮新增）：

| 文件 | 行数 | 职责 |
|---|---|---|
| `services/director.py` | ~520 | AI 导演：决定本轮谁说话、写旁白、改状态。**三层降级，永不抛异常** |
| `services/story_state.py` | ~470 | 剧情状态读写（幕/拍点/旗标/关系图/cast）。纯状态，无 LLM/HTTP |
| `services/action_suggester.py` | ~360 | 行动建议生成，失败返回 `[]` 或规则兜底 |
| `services/opening.py` | ~380 | 序幕生成，L1 模型 / L2 卡片兜底 / L3 纯模板 |
| `services/world.py` | ~180 | 世界观 CRUD + 中文子串检索 |

### 前端 `frontend/src/`

```
api/types/       契约层（common, content, session, media, system, world）
api/client/      客户端（core, resources, stream, index）
pages/           14 个页面（含 worlds, world-editor）
components/      cards, world, worldbook, session, workspace, settings, setup, ui, common, layout
hooks/           use-auth, use-chat-stream, use-library
mocks/           离线演示数据（samples/, fixtures.ts）
stores/          ui.ts（Zustand）
```

---

## 5. 当前真实状态（已被验证）

| 项 | 结果 | 如何复现 |
|---|---|---|
| 后端测试 | **402 passed / 44 skipped**（共收集 446；有 PG 时 **446 passed / 0 skipped**） | `cd backend && ./.venv/bin/python -m pytest -q` |
| 后端 lint | ruff 全绿 | `cd backend && ruff check app/ tests/` |
| 前端类型 | 0 错误 | `cd frontend && npx tsc --noEmit` |
| 前端构建 | 成功 | `cd frontend && npm run build` |
| 前端冒烟 | **17/17 路由 + 3 探针 PASS**，未捕获异常 0 | `cd frontend && node scripts/smoke.mjs` |
| SSE 契约 | 三处白名单同构，11 事件 | `cd frontend && node scripts/check-sse-contract.mjs` |
| 图标校验 | 108 个全部存在 | `cd frontend && node scripts/verify-icons.mjs` |

> ⚠️ **测试必须在 `backend/` 目录下运行**。在仓库根跑会 22 个 collection error（`conftest.py` 依赖相对路径）。

---

## 6. SSE 事件契约（改造的核心接口）

**1v1 是子集，剧情模式是超集**。旧前端白名单不含后 4 个事件，收到即静默丢弃 → 对既有会话零影响。

```
1v1 :  world_info → start → delta* → usage → (image?) → done
剧情:  world_info → director → start → (delta* | speaker_switch → delta*) → node? → usage → (image?) → actions → done
```

| 事件 | 触发时机 | 关键载荷 |
|---|---|---|
| `director` | 每轮开头 | `speakers[]`, `narration`, `scene_patch`, `node_triggered`, `relation_updates`, `flags`, `reason`, `degraded` |
| `speaker_switch` | 切换说话者 | `speaker_id`, `speaker_name`, `is_narration`, `message_id` |
| `node` | 剧情节点触发 | `id`, `title`, `brief` |
| `actions` | 每轮结束 | `actions: [{id, label, hint, tone}]` |

### ⚠️ 三处白名单必须同时改（漏一处 = 前端静默卡住）

1. `frontend/src/api/types/session.ts` → `SseEventMap` 的键
2. `frontend/src/api/client/stream.ts` → `KNOWN_EVENTS` 数组
3. `backend/app/services/chat.py` → `EVT_*` 常量

**已配自动化守卫**：`npm run verify:sse` 会把三处拉到一起比对，不一致直接退出码 1。

---

## 7. 数据模型速查（剧情相关）

**模式切换零迁移**：`session.spec` 从 `"rpg_session"` → `"story_session"`，靠这个字段分派，路由不变。

| 位置 | 内容 |
|---|---|
| `state_machine.story` | 幕/节点/flags/导演失败计数 |
| `scene.{present, last_speaker_id, beat}` | 在场角色、上一说话者、拍点 |
| `message.meta.{speaker_id, speaker_name, beat_role, is_narration, turn, direction, intent}` | 每条消息的说话者归属 |
| `session.world_id` | 外键指向 `worlds`（ON DELETE SET NULL） |
| `extensions.story.{world_id, cast, relations, relations_version}` | 固化快照 |

**状态机**：`idle → assembling → generating → {post_processing, interrupted, error}`。
⚠️ `generating` **没有直达 `idle` 的边**，收尾必须走 `post_processing`；容错路径用 `_force_idle()` 绕过迁移表。

---

## 8. 并行工作守则

多任务同时跑时，遵守以下边界可避免互相覆盖：

| 任务类型 | 独占文件 | 说明 |
|---|---|---|
| S12 剧情演出页 | `pages/story-runtime.tsx`, `components/story/*`, `hooks/use-speakers.ts` | ✅ 已交付，S13 可放心消费 |
| S13 会话列表 | `pages/session-list.tsx` | 只改这一个页面 |
| 后端改动 | `backend/app/services/*` | 改完**必须**跑全量测试 |
| 运维 | 服务器 `/opt/marionette` | 不碰仓库代码 |
| Git 推送 | 无 | 只操作 git |

**三条硬约束**：

1. **改前端共享文件（`api/types/`、`api/client/`、`App.tsx`、`components/icons.ts`）前先声明**，这些是冲突热点。
2. **改后端 services 后必跑** `cd backend && ./.venv/bin/python -m pytest -q`，基线是 402 passed（44 skipped）。
   动过 `services/`/`api/` 的，还必须**在有真 PG 的环境跑一遍集成测试**（那 44 条），别被 skip 骗过去。
3. **提交前四项自检**：`tsc --noEmit` + `verify:sse` + `smoke` + `ruff check`。

---

## 9. 遗留问题（非阻塞，但需知道）

| 问题 | 影响 | 处理 |
|---|---|---|
| **代码未推到 GitHub；且 GitHub 上是旧版** | 新任务 `git clone` 会拿到**缺剧情引擎**的版本，误判「项目没代码」 | 见 `task-GET-CODE.md` §2 + `task-GIT-push.md` |
| 无域名 / 走 HTTP 明文 | 会话 Cookie 有被截获风险 | 见 `task-INFRA-ops.md` |
| 服务器口令 `WBAccess@1` 偏短 | 安全风险 | 见 `task-INFRA-ops.md` |
| 服务器到期 **2026-11-09** | 到期停机 | 记得续费 |
| 生产库有测试脏数据 | 卡片 74 / 世界书 9 中含测试数据 | 见 `task-INFRA-ops.md` |
| 备份 cron 未配置 | 无自动备份 | 见 `task-INFRA-ops.md` |
| DeepSeek key 曾明文出现 | 建议作废重发 | 见 `task-INFRA-ops.md` |
