# 「提线」(Marionette) 项目交接文档

> 生成日期：2026-10-10
> 仓库：https://github.com/ming-ni-we/Marionette
> 线上实例：http://101.33.117.223
> 形态：云端私有单实例 · 仅限自用

---

## 1. 项目是什么

一个 AI 角色扮演平台，双核形态：

- **创作工作室** —— 角色卡 / 世界书 / 预设 / 图集素材的编辑器，是重度创作工具
- **运行时引擎（核心）** —— 把创作产物 + 玩家输入编排成一场会话：会话状态机、世界书触发、记忆/摘要、LLM 调度、画面生成钩子

**目标用户**：当前仅单一用户（本人自用）。三个 persona（林澈 / 周雨桐 / 老张）作为设计参照而非法定用户。

**核心问题**：现有方案把「创作」和「运行」割裂了——能创作的工具门槛高到劝退（SillyTavern），开箱即用的工具又拿走了创作主权与记忆控制权。**没有人把「创作者级深度」和「15 分钟上手」合到同一个形态里。**

**MVP 一句话**：编辑一张「现代日常向」角色卡 → 挂一本世界书 → 一键开一场会话 → 世界书触发 + 记忆摘要生效 → 场景出图并存入角色图集。

---

## 2. 完成度总览

| 层 | 进度 | 状态说明 |
|---|---|---|
| 需求与设计文档 | **100%** | PRD / 架构 / UIUX / Spec v1.0 全部锁定 |
| 设计系统 | **100%** | Token 三层（primitive→semantic→density），已落地到代码 |
| 后端骨架 | **100%** | 10 张表 + 迁移 + 5 适配器 + 访问控制，已上线 |
| 后端 · 创作侧 | **约 98%** | 已实现；单元测试 80 passed，真实 PG 集成测试 106 passed / 0 failed 且生产库零写入。4 类缺陷已修复并复验，详见 §4.1 |
| 后端 · 运行时 | **0%** | 未开始（第二波） |
| 前端 | **约 95%** | 9 个页面 + 全部组件 + 设计系统，自检全绿 |
| 部署 | **100%** | 三容器已上线，公网可访问 |

---

## 3. 各部分进度明细

### 3.1 需求与设计文档（完成）

| 文档 | 路径 | 内容 |
|---|---|---|
| PRD | `docs/01-prd.md` | 定位、3 persona、F1~F16 功能带 RICE 评分、Out-of-Scope、成功指标、15 分钟链路 |
| 架构 | `docs/02-architecture.md` | 选型矩阵、分层与依赖方向、适配层接缝、风险 Top3 |
| UIUX | `docs/03-uiux.md` | 视觉隐喻「后台工作台 + 舞台」、双密度、Token 映射、Lucide 图标对照表 |
| Spec | `docs/spec/SPEC.md` | **唯一契约**（13 章）：MVP 范围 / 技术架构 / 34→37 path / 9 表 / 9 页面 / Token / **16 条 EARS 验收标准** |
| 内容 Schema | `docs/spec/schemas.md` | `rpg_card` / `rpg_worldbook` / `rpg_preset` / `rpg_session` 字段级定义 |
| API 契约 | `docs/spec/openapi.yaml` | 37 path / 53 operation / 46 schema / 14 参数组件 |
| 架构决策 | `docs/decisions/ADR-001~011.md` | MADR 格式，11 条选型决策 |
| 未决登记册 | `docs/decisions/OPEN-DECISIONS.md` | **0 未决 + 9 已决** |

**关键设计决策**：内容 Schema 统一信封 + 版本号，`data` 沿用 SillyTavern V2 同名字段，平台字段隔离在 `extensions.rpg` —— 保证与酒馆生态双向兼容、可回导。

### 3.2 设计系统（完成）

- `design/design-tokens.json` + `design-tokens.css` —— primitive → semantic → density 三层，明暗双套
- 主色：琥珀暖光（深色 `#E3AE3E` / 浅色 `#9C6F19`）
- 两档密度：`studio`（创作端，高密度）/ `session`（运行端，沉浸），**同一套主题派生**
- 图标：Lucide 唯一，线宽统一 2px，尺寸仅 16/20/24px
- 落地：`frontend/src/styles/globals.css` 从 Token 同源映射，前端不手抄变量

### 3.3 后端（骨架完成 + 创作侧已实现）

**技术栈**：FastAPI 0.141.1 / Python 3.12 / Pydantic 2.13.4 / SQLAlchemy 2.0 async + Alembic 1.18 / PostgreSQL 18 + pgvector 0.8.7 / Caddy 自动 HTTPS / Docker Compose

**已实现**：

| 模块 | 文件 | 状态 |
|---|---|---|
| 应用骨架 | `app/main.py`、`core/{config,db,envelope,errors,logging,security}.py` | 完成 |
| 数据模型 | `app/models/` 10 张表 + Alembic 初始迁移 | 完成 |
| 适配层 | `app/adapters/` 5 个接口（Auth/LLM/Image/AssetStore/Moderation）+ 默认实现 | 完成 |
| 访问控制 | 单用户口令 + HttpOnly 签名令牌 + 5 次失败限流 | 完成并验证 |
| 内容 CRUD | `services/content.py`（197 行） | 完成 |
| 检索 | `services/content_search.py`、`search.py`（pg_trgm + ILIKE） | 完成 |
| Tavern V2 兼容 | `services/st_compat.py`（250 行）、`st_book.py`、`st_image.py`（PNG tEXt chunk） | 完成 |
| 导入导出 | `services/import_export.py`（294 行）、`wb_import.py` | 完成 |
| 世界书引擎 | `services/world_info.py`（268 行）—— 三态判定 + 递归 + 优先级 | 完成 |
| 内置内容 | `services/builtin_cards.py` 等（现代日常向示例） | 完成 |
| 资产查询 | `services/assets.py`、`content_kinds.py`、`tokens.py`、`ids.py`、`text.py` | 完成 |

**未实现（仍是 501 / 空壳）**：

| 模块 | 状态 |
|---|---|
| `api/v1/sessions.py` 会话生命周期 + SSE 流式 | **501 占位** |
| `api/v1/config.py` LLM / 审核 / 出图配置 | **501 占位** |
| `api/v1/images.py` 出图任务 | **501 占位** |
| `api/v1/telemetry.py` 埋点 / 诊断包 | **501 占位** |
| `services/session.py` 会话状态机 | 空壳（23 行） |
| `services/memory.py` 记忆/摘要 | 空壳（22 行） |
| `services/llm_router.py` LLM 调度 | 空壳（22 行） |
| `services/context_assembler.py` 上下文装配 | 空壳（22 行） |
| `services/image_hook.py` 出图钩子 | 空壳（23 行） |

### 3.4 前端（约 95%）

**技术栈**：React 19.1 + Vite 7.3.7 + TypeScript 5.8 / Tailwind CSS 4.1（CSS-first `@theme`）/ shadcn/ui + Radix / Zustand 5 + TanStack Query 5 / react-router 7

**已交付**：108 个源文件、9 个页面 + 登录页 + 404 页、完整组件树（session / worldbook / cards / assets / settings / setup / workspace）

**自检证据（全部实测）**：

| 检查 | 结果 |
|---|---|
| `tsc --noEmit` | 零错误 |
| `vite build` | 成功，已代码分包（index 205KB / vendor-react 222KB / vendor 275KB） |
| P0 扫描（106 文件） | emoji **0** / 硬编码色 **0** / 紫粉渐变 **0** |
| 图标校验 | 107 个 Lucide 图标名全部存在 |
| 路由 smoke | **12 条路由全部渲染且非空白**，未捕获异常 0 |
| 差异化探针① | 三态命中判定 PASS（未命中 1 / 预算内 2 / 被挤出 2） |
| 差异化探针② | SSE 事件链路 PASS（world_info→start→delta×5→usage→done） |

**待办**：与后端真实 API 联调（当前页面用 mocks 数据跑通）。

### 3.5 部署（完成）

| 项 | 值 |
|---|---|
| 服务器 | 腾讯云轻量 · 中国香港（深水埗）· 2核 / 3.6G / 70G · Ubuntu 24.04.4 LTS |
| 环境 | Docker 29.6.1 + Compose v5.3.1（应用镜像预装） |
| 编排 | `caddy` + `api`（同时托管 SPA）+ `db`（`pgvector/pgvector:pg18`） |
| 代码位置 | 服务器 `/opt/marionette` |
| 入口 | http://101.33.117.223（暂无域名，走 HTTP） |
| 访问口令 | `DgX1yLVky0MOmDPpRGlh` |
| 到期 | 2026-11-09（按月，记得续费） |

**已验证**：三容器 healthy · selfcheck 全绿（db ok / pgvector 0.8.7 ok / **llm reachable=true，DeepSeek 真实连通**）· 无令牌 401 · 登录签发 HttpOnly 令牌 · 错误口令 5 次触发 429

---

## 4. 验收标准逐条状态（Spec §9 的 AC-01~16）

| 编号 | 功能 | 状态 | 证据 / 说明 |
|---|---|---|---|
| AC-01 | 部署 90 秒内就绪 | ✅ **已验证** | 启动到 healthy 约 35 秒 |
| AC-02 | 未持令牌返回 401 | ✅ **已验证** | 公网连测 3 次均 401 |
| AC-03 | 登录签发 HttpOnly + 5 次限流 | ✅ **已验证** | 200 + HttpOnly；错误口令 5 次 → 429 |
| AC-04 | LLM 接入 3s 内 + 7 类 error_class | ⚠️ **部分** | adapter 的 7 类归类已写好、selfcheck 真实调用；`/config/llm/test` 端点仍是 501 |
| AC-05 | 导入 Tavern V2 PNG 卡 | ✅ **已验证** | 真实 PG 集成测试通过：PNG 导入 201、头像自动登记为资产、二进制可取回 |
| AC-06 | 导出可回导的卡片包 | ✅ **已验证** | 导出 json/png/bundle zip 均 200 且可回导；中文名走 `filename*=UTF-8''` |
| AC-07 | 世界书触发注入上下文 | 🟡 **引擎完成，未接入会话** | `world_info.py` 完成；会话装配属第二波 |
| AC-08 | 命中测试三态可观测 | ✅ **已验证** | 真实 PG 集成测试通过：未命中 / 预算内 / 命中被挤出 三态断言全绿 |
| AC-09 | 60 轮后能回忆早期设定 | ❌ **未实现** | `memory.py` 空壳 |
| AC-10 | 出图完成自动归档进图集 | ❌ **未实现** | `image_hook.py` 空壳 + `images.py` 501 |
| AC-11 | 审核层开启时拦截违规输入 | ❌ **未实现** | moderation adapter 有骨架，未接 API |
| AC-12 | 关闭审核层需风险确认 | ❌ **未实现** | 前端 UI 已有，后端未接 |
| AC-13 | 内容检索与筛选 | ✅ **已验证** | 真实 PG 集成测试通过（分页稳定 / 多标签 AND / 中文子串）；线上实测 `q=日常` 命中 14 条 |
| AC-14 | 会话分支 | ❌ **未实现** | `session.py` 空壳 |
| AC-15 | 流式对话 + 中止不留脏消息 | ❌ **未实现** | `sessions.py` 501 |
| AC-16 | 空状态不出现空白页 | ✅ **已验证** | 前端 12 路由 smoke 全 PASS |

**汇总**：**8 条已验证** · 1 条部分（AC-04）· 1 条引擎完成待接入（AC-07）· 6 条未实现。

**集成测试最终状态**：真实 PostgreSQL 下 **`106 passed, 0 failed`**，且运行前后生产库 `public` 行数**完全不变**（74/9/4/3/0，零写入）。

---

### 4.1 集成测试首跑：4 类缺陷（**均已修复并在真实 PG 上复验通过**）

此前集成测试一直是 `26 skipped`，因为缺少 `MARIONETTE_INTEGRATION=1` 开关，**从未真正连过 PostgreSQL**。本轮打开开关后（真实 PG，首跑 `83 passed / 9 failed`），暴露出下面 4 类缺陷 —— 它们全部是**生产代码缺陷或测试基建缺陷**，不是环境问题。修复后复验：**`106 passed, 0 failed`**，且生产库零写入。

| # | 缺陷 | 影响面 | 根因 | 修法 |
|---|---|---|---|---|
| 1 | 导出/下载遇中文文件名必 **500** | `/export/card`（json/png）、`/assets/{id}/content` | `safe_filename` 刻意保留中文，却被塞进 `Content-Disposition` 响应头；Starlette 按 `latin-1` 编码头值 → `UnicodeEncodeError` | 新增 `content_disposition()`，按 RFC 6266/5987 输出 ASCII 回退名 + `filename*=UTF-8''…` |
| 2 | 集成测试**直接读写生产库** | 测试基建；已造成数据污染 | `create_all` 默认 `checkfirst=True`，靠 `pg_table_is_visible()` 判断表是否存在；`search_path` 里带 `public` 兜底 → `public.cards` 被判为"可见" → **跳过全部建表** → 临时 schema 空无一表 → 查询全部回落 `public` | 显式按 schema 建表（`Table.to_metadata(schema=…)`），并加"建表数量必须等于元数据表数，否则拒绝运行"的硬守卫 |
| 3 | 世界书导入 **500** | `POST /import/worldbook` | `wb_import` 返回 `st_worldbook`，但 `ImportResult` 的 `Literal` 与 `openapi.yaml` 枚举只有 `st_v1/v2/v3/native` → 字面量校验失败 | 契约与代码同步补齐 `st_worldbook` |
| 4 | 世界书条目自定义 id 被 **400/500** | `POST /worldbooks`、世界书导入响应序列化 | `WorldBookEntry.id` 声明为 `UUID`，但平台内部（`world_info.py`）本就把 entry id 当不透明字符串，且 ST 用 int id，UUID 化破坏无损兼容 | 放宽为 `str`，同步更新 `schemas.md` §4.2 |

**复验证据（服务器真实 PostgreSQL）**：

| 判据 | 结果 |
|---|---|
| 集成测试 | `1 failed → 106 passed, 0 failed` |
| 生产库零写入 | 跑前 `74/8/4/3/0`，跑后 `74/8/4/3/0`，**完全一致** |
| 临时 schema 无残留 | 跑后 `mtest_*` / `probe_*` 残留 = `(none)` |
| 中文名导出（缺陷 1） | 卡片「苏晚晴」`export json/png/bundle` 均 **200**；响应头 `attachment; filename="download.json"; filename*=UTF-8''%E8%8B%8F%E6%99%9A%E6%99%B4.json` |
| 世界书导入（缺陷 3） | `POST /import/worldbook` → **201**，`source_format=st_worldbook` |
| 条目自定义 id（缺陷 4） | 含 `"id":"c"` 的世界书创建/导入均通过 |

> 第 9 个失败（`test_export_png_is_reimportable`）经查是**测试断言写错**：它断言回导后卡片名不变，但 `on_conflict=rename` 的既定语义就是同名时追加「(导入副本)」（`ImportExportSvc._renamed`）。已修正断言，改为验证"除名字外正文逐字段无损"。这类问题此前因导出先 500 而始终没跑到。

**顺带澄清一个误报**：命令行里直接 `curl "...?q=日常"` 曾返回 400，一度以为是检索缺陷。实为 **Windows 侧 SSH 客户端把中文按 GBK 送出**导致远端收到非法 UTF-8；改用百分号编码后 `q=日常` → 200 / total=14，`q=林晚` → 200 / total=3，检索本身完全正常。

**数据污染善后**：生产库 `public` 被写入 21 张 `栖夜*`、9 张 `倒序*`、3 张 `双标签角色` 卡片，以及 2 本重复世界书（`worldbooks` 由 6 变 8）。清理方案待确认，见 §8 第 7 条。

---

## 5. 仓库与代码组织

```
marionette/
├── backend/                 FastAPI 应用（app/core, adapters, models, schemas, services, api/v1）
│   ├── alembic/             迁移（0001_initial_schema）
│   └── tests/               单元测试 + tests/integration/（需真实 PG）
├── frontend/                React SPA（src/{pages,components,api,hooks,mocks,stores,styles}）
├── deploy/Caddyfile         反代 + 自动 HTTPS
├── design/                  design-tokens.json / .css
├── docs/                    PRD / 架构 / UIUX / spec / decisions
├── docker-compose.yml       caddy + api + db
├── .env.example             环境变量样例（含中文注释）
└── .gitattributes           强制 Shell/Dockerfile/YAML 使用 LF
```

**分层约定**：`api/v1`（路由，只做编排）→ `services`（业务逻辑）→ `adapters`（可替换接缝）→ `models`（数据）。业务层禁止 import 任何厂商 SDK。

**提交历史**：

| SHA | 说明 |
|---|---|
| `1ef5d36` | 项目初始化（Phase 1–3 产出） |
| `cab4617` | 添加 `.gitattributes` 统一换行符 |
| `98d718a` | Phase 3 第一波 —— 创作侧实现 |

---

## 6. 未完成工作清单（第二波）

按依赖顺序：

1. **配置层**（`config.py`）—— LLM / 审核 / 出图配置 + `POST /config/llm/test`（打通 AC-04）
2. **会话状态机**（`services/session.py`）—— 显式迁移表 + version 乐观锁，并发冲突返回 409
3. **上下文装配 + LLM 调度**（`context_assembler.py` / `llm_router.py`）—— 把世界书注入接进会话（打通 AC-07）
4. **SSE 流式对话**（`api/v1/sessions.py`）—— 7 类事件：`world_info` / `start` / `delta` / `usage` / `image` / `done` / `error`；中止不留脏消息（打通 AC-15）
5. **会话分支**（frok）—— 保留原会话、生成可独立继续的新会话（打通 AC-14）
6. **记忆/摘要**（`memory.py`）—— 自动摘要 + 关键事实落库 + 会话内召回（打通 AC-09）
7. **出图钩子**（`image_hook.py` + `images.py`）—— **铁律：ImageJob 转 done 时由服务端自动创建 `kind=generated` 资产，前端禁止拼装归档逻辑**（打通 AC-10）
8. **审核层接线**（`moderation`）—— 输入/输出双端，可整体关闭且关闭需风险确认（打通 AC-11/12）
9. **埋点与诊断包**（`telemetry.py`）
10. **前后端联调** —— 前端从 mocks 切到真实 API

---

## 7. 已知坑与经验（项目级）

| 坑 | 根因 | 修法 |
|---|---|---|
| 中文子串搜不到 | PG 默认分词器把连续中文当整段 token | 用 `pg_trgm` GIN + `ILIKE`，不装分词器 |
| `pgvector` 扩展缺失 | 官方 `postgres` 镜像不含该扩展 | 必须用 `pgvector/pgvector:pg18` |
| Alembic 与模型漂移 | 手改表结构未生成迁移 | 禁止 `create_all` 上生产，必须 `alembic revision --autogenerate` 并复核 |
| `alembic.ini` 在 Windows 崩溃 | Alembic 以 `locale` 编码读取，GBK 解不了中文注释 | 配置文件保持纯 ASCII |
| Windows 生成的 lock 在 Linux 构建失败 | lock 不含 Linux 原生可选依赖，`npm ci` 静默漏装 | 容器内 `rm -f package-lock.json && npm install` |
| Git Bash 改写 SSH 路径参数 | MSYS2 把 `/home/x` 转成 Windows 路径，症状像网络故障 | 调用前设 `MSYS2_ARG_CONV_EXCL='*'` |
| **HTTP 响应头塞中文 → 500** | HTTP 头必须是 `latin-1`，Starlette 编码时抛 `UnicodeEncodeError` | 文件名一律走 RFC 5987：ASCII 回退名 + `filename*=UTF-8''` 百分号编码 |
| **`create_all` 在临时 schema 里"静默不建表"** | `checkfirst=True` 用 `pg_table_is_visible()` 判存在性，而 `search_path` 带 `public` 兜底 → 误判已存在 → 跳过建表 → 查询回落生产库 | 显式按 schema 建表，并断言"实建表数 == 元数据表数"，不符即拒绝运行 |
| **Windows SSH 传中文参数变乱码** | Windows 侧 Python 按 GBK 解析 argv，再以 UTF-8 发出 → 远端拿到非法字节 → FastAPI 400 | 需要中文时用百分号编码，或把命令写成脚本文件按字节上传 |
| **`Literal` 枚举漏值 → 500 而非 400** | Pydantic 字面量校验失败会以 `ValidationError` 冒到通用异常处理器（500），不易定位 | 契约枚举与代码 `Literal` 必须同步维护，并配单测防漂移 |

---

## 8. 交接注意事项

1. **密钥**：DeepSeek API key 曾在对话中明文出现，**建议作废并重新生成**；新 key 只需改服务器 `/opt/marionette/.env` 的 `LLM_API_KEY` 后 `docker compose up -d` 即可热替换。`.env` 权限 600，不进 git。
2. **访问控制是合规前置条件**：形态为「仅限自用」，一旦实例被不特定人访问到，事实上就变成「面向公众」，会触发生成式 AI 的备案/登记义务。**不要关闭口令、不要裸奔到公网。**
3. **域名与 HTTPS 待补**：当前走 HTTP 明文。买域名解析到该 IP 后，改 `.env` 的 `DOMAIN` + `SESSION_COOKIE_SECURE=true`，Caddy 会自动签证书。
4. **服务器密码** `WBAccess@1` 偏短，建议改强密码或改用密钥登录。
5. **备份**：Spec 要求 `pg_dump` 每日 + assets 增量，保留 ≥7 天，且恢复流程需演练一次 —— **当前尚未配置 cron，属待办**。
6. **服务器到期** 2026-11-09，记得续费。
7. **生产库存在测试脏数据（待清理）**：因为 §4.1 缺陷 2，集成测试曾把数据写进生产库。当前 `public` 计数 = `cards 74 / worldbooks 9 / presets 4 / assets 3 / sessions 0`，其中非你本人内容的待清理项：
   - **卡片**：`栖夜书店`·`栖夜咖啡馆`·`栖夜车站`·`栖夜天台`·`栖夜码头`·`栖夜小巷`·`栖夜公园`（各 3 份）、`倒序甲/乙/丙`（各 3 份）、`双标签角色`（3 份）、`单标签角色`、`空资产角色`、`描述检索角色`、`图集角色`、`格式校验角色`、`打包角色`、`PNG导出角色`、`PNG导出角色 (导入副本)`、`HTTP往返角色`、`HTTP往返角色 (导入副本)`、`PROBE_ISOLATION_CARD`
   - **世界书**：重复的 `城南街区` / `日常向对话基调`（每个名字本应只有 1 本，多出的都该删）、`三态验证世界书`、`公交线路世界书`、`验证用世界书`
   - **清理建议**：先 `pg_dump` 备份，再按名精确删除；或鉴于目前还没有真实内容，直接清空这几张表重跑一次 `POST /api/v1/onboarding/samples`（更干净）。
8. **集成测试运行纪律**：`conftest.py` 现已内置两道硬守卫（建表后核对 `current_schema()` 与实建表数），隔离一旦失效会 `pytest.exit(returncode=2)` 中止，不会再静默写进生产库。仍需注意：跑集成测试会真实读写数据库，**务必先确认守卫生效**。

---

## 9. 一句话总结

**创作侧已经能用了**（文档、设计、后端创作侧、前端页面、云端部署全部就位），**运行时会话是最后一块拼图** —— 打通它，MVP 的「创作 → 运行」闭环就完整了。
