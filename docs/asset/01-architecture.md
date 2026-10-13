# 01 · 架构与技术细节

> 配套总纲：[`README.md`](./README.md) · 生成日期：2026-10-12

---

## 1. 分层与依赖方向（铁律）

```
api/v1/          路由层 —— 只做编排：解析入参 → 调 service → 套统一信封
    ↓
services/        业务层 —— 全部业务逻辑在此。禁止 import 任何厂商 SDK
    ↓
adapters/        接缝层 —— Auth / LLM / Image / AssetStore / Moderation 五个可替换接口
    ↓
models/          数据层 —— SQLAlchemy 2.0 async ORM
```

**统一信封**：所有响应为 `{code, data, message?}`，由 `core/envelope.py` 提供。

---

## 2. 后端模块清单（30 个 service）

### 2.1 内容侧（第一波，已完成）

| 模块 | 职责 |
|---|---|
| `content.py` | 卡片/世界书/预设的通用 CRUD |
| `content_search.py` / `search.py` | 检索与分页（pg_trgm GIN + ILIKE） |
| `content_kinds.py` | 内容类型常量 |
| `st_compat.py` | SillyTavern V2 字段兼容层 |
| `st_book.py` / `wb_import.py` | 世界书导入 |
| `st_image.py` | PNG tEXt chunk 读写（卡片元数据嵌图） |
| `import_export.py` | 导入导出（含 RFC 5987 中文文件名） |
| `world_info.py` | 世界书引擎：三态判定 + 递归 + 优先级 |
| `builtin_cards.py` / `builtin_worldbooks.py` / `builtin_presets.py` / `builtin_content.py` | 内置示例内容 |
| `assets.py` | 资产查询 |
| `tokens.py` | token 估算（中文 3 汉字 ≈ 4 token，**不是**字符数） |
| `ids.py` / `text.py` | id 解析与文本工具 |

### 2.2 运行时侧（第二波，已完成）

| 模块 | 职责 | 关键实现 |
|---|---|---|
| `session.py` | 会话状态机 + fork | 显式迁移表 + version 乐观锁，冲突返回 409 |
| `chat.py` | SSE 编排 | 事件序 world_info→start→delta*→usage→done；中断置 incomplete **不留脏消息** |
| `context_assembler.py` | 上下文装配 | token 预算裁剪；**剧情模式新增 3 段** |
| `llm_router.py` | LLM 调度 | OpenAI 兼容流式薄层 + 7 类 error_class |
| `memory.py` | 记忆 | 滚动摘要 + 关键事实正则抽取 |
| `image_hook.py` | 出图钩子 | done 时**服务端**自动建 `kind=generated` 资产 |
| `moderation.py` | 审核 | 输入/输出双端，关闭需风险确认 |
| `config.py` | 配置 | LLM/审核/出图配置 + 连接测试 |
| `telemetry.py` | 埋点 | 事件记录 + 诊断包导出 |

### 2.3 剧情引擎（第三波，本轮新增）

| 模块 | 行数 | 职责 | 降级策略 |
|---|---|---|---|
| `director.py` | ~520 | AI 导演 | **三层**：L0 熔断（≥3 次失败）→ L1 `response_format` → L2 去掉重试 → L3 `fallback()` |
| `story_state.py` | ~470 | 剧情状态 | 纯状态读写，无 LLM/HTTP；getter 返回深拷贝，writer 增量 PATCH |
| `action_suggester.py` | ~360 | 行动建议 | 失败返回 `[]` 或规则兜底（观察/搭话/移动） |
| `opening.py` | ~380 | 序幕 | L1 模型 / L2 `world.opening` + `card.first_mes` / L3 纯模板 |
| `world.py` | ~180 | 世界观 CRUD | `_PATCHABLE` 白名单防脏写 |

---

## 3. 数据模型（11 张表）

| 表 | 说明 |
|---|---|
| `cards` | 角色卡（`spec=rpg_card`） |
| `worldbooks` | 世界书（`spec=rpg_worldbook`） |
| `presets` | 预设（`spec=rpg_preset`） |
| `sessions` | 会话（`spec=rpg_session` / `story_session`） |
| `messages` | 消息（含 `meta` JSONB） |
| `assets` | 资产（`kind=generated` 为出图归档） |
| `image_jobs` | 出图任务 |
| `memory_snapshots` | 记忆快照 |
| `embeddings` | 向量（pgvector） |
| `app_config` | 应用配置 |
| **`worlds`** | **世界观（本轮新增，`spec=rpg_world`）** |

### 3.1 `worlds` 表结构（0002_worlds 迁移）

字段**摊平**而非包在 `data` 里，因为导演需要按维度独立读写（例如只更新 `outline` 而不动 `cast`）：

| 列 | 类型 | 说明 |
|---|---|---|
| `title` | str | 世界名称 |
| `setting` | JSONB | `{era, locations[], rules[], tone, summary}` |
| `factions` | JSONB | 势力列表 |
| `cast` | JSONB | 角色群：`{id, name, role, voice, goals[], description, card_id?}` |
| `relations` | JSONB | 关系边：`{from, to, kind, tension∈[-1,1], note}` |
| `outline` | JSONB | `{main_goal, nodes[{id,title,brief,trigger}], endings[]}` |
| `opening` | str | 序幕底本 |
| `extensions` / `tags` | JSONB | 扩展与标签 |

> ⚠️ `relations[].from` 在 Python 里是关键字，schema 用 `from_` + `alias="from"` 映射。**JSON 里是 `from`**。

### 3.2 迁移链

```
0001_initial_schema  →  0002_worlds
```

---

## 4. 剧情模式的核心设计

### 4.1 模式分派（零迁移、零路由变更）

```python
# chat.py stream_reply 内，assembling 之后
if is_story_session(session_row):
    async for event in self._stream_story_round(...): yield event
    return
```

`session.spec` 是唯一开关。`is_story_session()` 容忍 `None`/缺失/空串。

### 4.2 状态机

```
idle → assembling → generating → {post_processing, interrupted, error}
```

**⚠️ `generating` 没有直达 `idle` 的边。** 收尾必须 `generating → post_processing → idle`。
容错路径用 `_force_idle()` 绕过迁移表（否则抛 `ConflictError`，会话**永久卡在 generating**——这是已修复的真实 bug）。

### 4.3 一轮剧情的完整流程

1. `world_info` 事件（与世界书触发结构相同，1v1 零改动）
2. 调导演 → `director` 事件（含降级标记）
3. 解析出场角色（空则退化为「在场首位」纯旁白）
4. `start` 事件（`message_id` 允许空串，真实 id 在循环里产生）
5. 旁白段（导演给的 `narration`，直接落库不走 LLM）→ `speaker_switch`
6. 逐角色：`speaker_switch`（首个除外，已在 start 后）→ 建占位行 → 流式 → `delta*`
7. 节点触发 → `node`
8. `usage`
9. `image`（沿用 1v1 钩子）
10. `actions`
11. `done`

**关键不变量：N 个说话者 = N 条消息**（不预建占位行，否则会多出一条空消息——已修复的真实 bug）。

### 4.4 上下文装配的 3 个新段

旧 9 段**字节级不变**，新 3 段仅在非空时追加：

| 段 | 预算 | 裁剪策略 |
|---|---|---|
| `story_state` | 8% | **永不因零预算丢弃**，硬截断 400 token |
| `relations` | 6% | 与当前说话者相关的子图，按 tension 降序截断 |
| `cast_roster` | 5% | 在场角色一行摘要 |

`budget` 字典新增 `story_tokens` / `relations_tokens` / `cast_tokens`。

---

## 5. 前端架构

### 5.1 类型契约层 `api/types/`

| 文件 | 内容 |
|---|---|
| `common.ts` | Envelope / ErrorClass（7 类）/ Paged\<T\> / SearchQuery |
| `content.ts` | Card / WorldBook / Preset |
| `session.ts` | Session / Message / **SseEventMap（11 事件）** / StoryState / Relation |
| `media.ts` | Asset / ImageJob |
| `system.ts` | SystemInfo / LlmConfig |
| `world.ts` | **World / WorldInput / emptyWorld() / nextEntityId()** |
| `index.ts` | 桶导出 + `Paged*` 别名 |

### 5.2 路由表（17 条）

```
/login  /setup                                  独立页
/                                               内容库
/cards/new  /cards/:cardId
/worldbooks/new  /worldbooks/:id
/presets/new  /presets/:id
/worlds  /worlds/new  /worlds/:worldId          ← 本轮新增
/sessions  /sessions/:id
/assets  /settings  *
```

**待加**：`/stories/:id`（S12）

### 5.3 全局导航

`components/layout/rail.tsx`（桌面左 rail）+ `app-layout.tsx`（移动端 TabBar），两处导航项需同步：

内容库 / 会话 / **剧情世界** / 素材 / 设置

### 5.4 前端自检工具链

| 脚本 | 作用 | 命令 |
|---|---|---|
| `check-sse-contract.mjs` | 三处白名单同构校验 | `npm run verify:sse` |
| `verify-icons.mjs` | 图标名存在性（108 个） | `npm run verify:icons` |
| `smoke.mjs` | jsdom 真实挂载 16 路由 | `npm run smoke` |
| `scan-p0.py` | emoji/硬编码色/渐变扫描 | `npm run scan:p0` |

---

## 6. 适配层五个接缝

| 接缝 | 默认实现 | 可替换为 |
|---|---|---|
| Auth | 单用户口令 + HttpOnly 签名令牌 + 5 次失败限流 | OAuth / 多用户 |
| LLM | OpenAI 兼容（httpx 流式） | 任何兼容端点 |
| Image | 云端 API / ComfyUI | BYOK |
| AssetStore | 本地文件系统 | S3 / 对象存储 |
| Moderation | 关键词 + 可选模型 | 任意审核服务 |

**7 类 error_class**：`model_not_found` / `endpoint_invalid` / `auth_failed` / `quota_exhausted` / `network_unreachable` / `timeout` / `unknown`

---

## 7. 设计系统

- 视觉隐喻：**后台工作台 + 舞台**
- Token 三层：primitive → semantic → density（`studio` 创作端高密度 / `session` 运行端沉浸）
- 主色：琥珀暖光（深色 `#E3AE3E` / 浅色 `#9C6F19`）
- 图标：Lucide 唯一，线宽 2px，尺寸仅 16/20/24px
- 源文件：`design/design-tokens.json` + `.css`，前端从 Token 同源映射
- `--color-meta` 对比度已修正至 WCAG AA（深 4.6:1 / 浅 4.7:1）
