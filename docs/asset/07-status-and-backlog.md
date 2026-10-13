# 07 · 现状清单与待办

> 配套总纲：[`README.md`](./README.md) · 核实日期：2026-10-12

---

## 1. 改造计划进度（14 步）

| 步 | 内容 | 状态 | 证据 |
|---|---|---|---|
| S1 | `worlds` 表 + 迁移 + schema | ✅ | `0002_worlds.py` |
| S2 | `complete_chat` 非流式调用 | ✅ | `test_llm_complete.py`(7) |
| S3 | `services/story_state.py` | ✅ | `test_story_state.py`(55) |
| S4 | `services/director.py` 三层降级 | ✅ | `test_director.py`(52) |
| S5 | `context_assembler` +3 段 | ✅ | `test_context_story_segments.py`(25) |
| S6 | `chat.py` 剧情分支 + 收尾修复 | ✅ | `test_story_chat.py`(27) |
| S7 | `services/opening.py` | ✅ | `test_opening.py`(39) |
| S8 | `services/action_suggester.py` | ✅ | `test_action_suggester.py`(44) |
| S9 | API 端点 + `worlds` 路由 | ✅ | `test_world_service.py`(24) + 集成(16) |
| S10 | 前端类型 + 双白名单 | ✅ | `check-sse-contract.mjs` PASS |
| S11 | 世界观创建页 | ✅ | 10 个新文件，smoke 16/16 |
| **S12** | **剧情演出页** | ✅ | 6 组件 + 1 hook，smoke 17/17 + 3 探针；详见 [`task-S12-story-runtime.md`](./task-S12-story-runtime.md) |
| **S13** | **会话列表集成** | ⬜ | 见 [`task-S13-session-list.md`](./task-S13-session-list.md) |
| **S14** | **联调 + 回归 + 部署** | ✅ | 真 PG 端到端 + **服务器已部署并线上验收**（见 §3.2–§3.3.2） |

**进度：12/14（86%）** —— 14 步中 S1–S12 全部完成；S13/S14 是收尾集成，
且 **S14 的主要风险（真库联调 + 部署上线）已经超前完成**。

---

## 2. 当前被验证的状态（2026-10-12 实测）

### 后端

| 项 | 结果 |
|---|---|
| `pytest -q`（在 `backend/` 下） | **446 passed, 0 skipped**（含集成测试；此前 402 + 42 skipped） |
| `ruff check .` | All checks passed |
| `app/` 代码量 | 12011 行 |
| 模块数 | 30 个 service / 13 个路由 / 11 个 model |
| 迁移链 | `0001_initial_schema → 0002_worlds` |

> 集成测试（`MARIONETTE_INTEGRATION=1` + 真 Postgres）本轮**首次真正执行**。
> 执行它们立刻揪出了 D8 的 `MissingGreenlet` 500——此前 42 个 skipped 一直在掩盖它。

### 前端

| 项 | 结果 |
|---|---|
| `tsc --noEmit` | 0 错误 |
| `npm run build` | 成功（index.js 263.56 kB / gzip 76.64 kB） |
| `smoke.mjs` | **17/17 路由 PASS + 3 探针 PASS**，未捕获异常 0 |
| `verify:sse` | PASS，11 事件三处同构 |
| `verify:icons` | 108 个全部存在 |
| `src/` 代码量 | 13110 行 / 120 个文件 |
| 页面数 | 15（含 worlds / world-editor / story-runtime） |

**测试增长轨迹**：128（基线）→ 402（本轮 +274）

### 2.3 剧情链路真库端到端（2026-10-13 新增，S12 期间完成）

在 **真 Postgres 18 + pgvector 0.8.7** 上跑通完整剧情轮次 —— 这是 S14 联调里最关键的
一项，提前完成。脚本：`backend/tests/integration/e2e_story_pg.py`（人工执行，不被 pytest 收集）。

```bash
docker run -d --name marionette-e2e-db -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=marionette -p 55432:5432 pgvector/pgvector:pg18
cd backend && DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/marionette \
  ./.venv/bin/alembic upgrade head
DATABASE_URL=... ./.venv/bin/python tests/integration/e2e_story_pg.py
```

**结果：26 项断言全 PASS。**

真实事件序列（2 角色 + 旁白 + 节点触发）：

```
world_info → director → start → speaker_switch → delta → speaker_switch → delta
           → node → usage → actions → done
```

关键验证点（都是**只在真实多角色轮次才成立**的）：

| 验证点 | 实测 |
|---|---|
| 迁移链 `0001 → 0002_worlds` 在真 PG 上可执行 | ✅ |
| `start.message_id` 为空串（剧情模式放宽） | `''` |
| 每个 `delta` 都带 `speaker_id` | `['c1', 'c2']` |
| 旁白 `speaker_switch` 恰好 1 条且带 `message_id` | ✅ |
| **角色 `speaker_switch` 只有 1 条** —— 首个说话者后端**刻意不发** | ✅（仅 `c2`） |
| N 个说话者 = N 条 reply 消息 | 2 → 2 |
| reply 正文各自独立、未串行 | `['你来晚了。','我早就来了。']` |
| **旁白正文未被角色台词污染** | `['雨下了三天，墙皮泡得发胀。']` |
| 无残留 `streaming` | ✅ |
| 状态机回 `idle` + 轮次推进 | `idle` / turn=1 |
| `story.node_id` / `flags` / `scene.mood` 落库 | ✅ |

> ⚠️ 其中「角色 `speaker_switch` 只有 1 条」是**最容易踩的坑**：
> 后端对第一个说话者不发该事件，只发 `delta + speaker_id`。
> 前端若在匹配不到 `speaker_id` 时退回「最后一条 assistant」，
> 首个说话者的台词就会串进旁白气泡。S12 已修复并加回归探针（见 `04-pitfalls.md` G1/G2）。


---

## 3. 服务器状态

| 项 | 值 |
|---|---|
| 实例 | 腾讯云轻量 · 中国香港 · `101.33.117.223` |
| 代码位置 | `/opt/marionette` |
| SSH | **`ubuntu@101.33.117.223`**（口令见 `docs/HANDOVER.md`；属 docker+sudo 组，sudo 免密） |
| 访问 | http://101.33.117.223（HTTP 明文，无域名） |
| 容器 | `caddy` + `api` + `db` 三容器 healthy |
| selfcheck | db ok / pgvector 0.8.7 ok / **llm reachable=true（DeepSeek 真实连通）** |
| 部署版本 | **含剧情引擎 S1–S12 + D8 修复**（`alembic current` = `0002_worlds (head)`） |
| 生产库计数 | `cards 74 / worldbooks 9 / presets 4 / assets 3 / sessions 0`（部署验收另建了 1 条剧情会话） |
| 到期 | **2026-11-09** |

### 3.2 线上探针实测（2026-10-13 部署后）

**部署已完成，剧情引擎上线。**

| 探测 | 部署前 | **部署后** | 读法 |
|---|---|---|---|
| `GET /api/v1/worlds` | `404` | **`401`** | ✅ **端点已存在**，鉴权生效（关键指标） |
| `GET /stories/xxx` | — | **`200`** | ✅ 前端新路由已达线上 |
| `GET /assets/index-ofP2eCdf.js` | — | **`200`** | ✅ 新构建产物已挂载（哈希与本地 build 一致） |
| `GET /api/v1/system/info` | 4 类 schema | 4 类 schema | 正常：`SCHEMA_VERSIONS` 是**静态常量**，与表无关（见下方注） |
| `docker compose exec api alembic current` | — | **`0002_worlds (head)`** | ✅ 迁移已推进 |
| `psql \dt` | — | 出现 **`worlds`** 表 | ✅ 建表成功 |
| `psql \d sessions` | — | 出现 **`world_id`** + FK + 索引 | ✅ 绑定列已加 |
| `GET /healthz` | `200` | `200` | 服务健康 |

> **注意 `schema_versions` 的读法**：它来自 `app/core/config.py` 的 `SCHEMA_VERSIONS`
> 常量（card/worldbook/preset/session 四项），**不对 world 做声明**，因此它**不能**
> 用来判断剧情引擎是否上线。判断依据应看 `alembic current` / `\dt` / `GET /worlds` 状态码。
> （此前把它的"4 类"当作"没有剧情引擎"的证据之一，是**误读**，已更正。）

### 3.3 部署过程记录（2026-10-13，已完成）

**凭据**：`ubuntu@101.33.117.223`（**不是 root**），口令见 `docs/HANDOVER.md`。
该用户属于 `docker` + `sudo` 组且 **sudo 免密**。

> 教训：此前一直用 `root@` 尝试并失败，误判为「口令被改」。
> 实际是**用户名不对**。`ubuntu` 用户才是运维账号。

**步骤**（全部已执行）：

```bash
# 1) 备份（代码 + 数据库 dump）
ssh ubuntu@... 'tar czf ~/backups/marionette-code-$(date +%F-%H%M%S).tar.gz -C /opt marionette'
ssh ubuntu@... 'docker exec marionette-db pg_dump -U postgres -d marionette --clean --if-exists > ~/backups/db.sql'

# 2) 增量同步（--delete，但保护 .env / data/）
rsync -az --delete --exclude='.git/' --exclude='node_modules/' --exclude='.venv/' \
  --exclude='dist/' --exclude='__pycache__/' --exclude='*.pyc' \
  --exclude='.env' --exclude='data/' \
  ./ ubuntu@101.33.117.223:/opt/marionette/
#   结果：317 更新 / 61 新建 / 0 删除；.env 与 data/pgdata 未被触碰

# 3) 重建 + 重启（entrypoint.sh 自动 alembic upgrade head）
ssh ubuntu@... 'cd /opt/marionette && docker compose build api && docker compose up -d --no-deps api'
```

启动日志确认迁移执行：

```
[marionette] 执行数据库迁移（alembic upgrade head）...
INFO  [alembic.runtime.migration] Running upgrade 0001_initial_schema -> 0002_worlds, worlds table + sessions.world_id (剧情引擎)
[marionette] 迁移完成，启动 API（uvicorn）...
```

### 3.3.1 部署后揪出的线上 bug（已修 + 已重新部署）

首次部署后做真实链路验收，`POST /api/v1/sessions`（带 `world_id`）**必现 500**
（`MissingGreenlet`）。根因与修法详见 [`04-pitfalls.md`](./04-pitfalls.md) **D8**。

这个 bug **只有真实服务器才暴露**：单元测试用内存夹具不走 async 会话生命周期；
集成测试虽已写好但从未执行（需 `MARIONETTE_INTEGRATION=1`）；前端 mock 完全不碰后端。

已修复并**二次部署**，同时补了 2 个必须跑真库的回归测试。

### 3.3.2 线上端到端验收（2026-10-13，全部通过）

| # | 验收项 | 结果 |
|---|---|---|
| 1 | 登录（应用口令） | `200` |
| 2 | 创建世界观（含 cast/relations/outline/opening） | `201`，中文无损，`relations.from` alias 正确 |
| 3 | 读取世界观 | `200` |
| 4 | **创建剧情会话**（此前 500） | **`201`** —— `spec=story_session`、`world_id` 绑定、`scene.mood=阴郁`、`scene.present=[c1,c2]` |
| 5 | 序幕生成 | **2 条**，真实 DeepSeek 产出（非降级文案），中文贴合设定 |
| 6 | `GET /sessions/{id}/story` | `200` —— `is_story=true`、`story{arc_id:act1,beat_index,flags}`、`cast` 完整固化 |
| 7 | `GET /sessions/{id}/actions` | `200` —— 3 条 LLM 行动建议（`act`/`speak`/`observe` 三种 tone） |
| 8 | **真实 SSE 流式一轮** | **109 个事件**，序列与设计规格完全一致（见下） |

**线上真实事件序列**（DeepSeek 生成，2 角色 + 旁白 + 节点触发）：

```
world_info → director → start
  → speaker_switch(旁白: speaker_id=null, is_narration=true, 带 message_id)
  → delta ×85 (c2 老周)
  → speaker_switch(c1 苏晚)
  → delta ×20 (c1)
  → node(n1 雨夜的第一封信) → usage → actions(3) → done(status=complete, turn=1)
```

关键设计点在线上全部成立：

| 验证点 | 线上实测 |
|---|---|
| 导演未降级 | `degraded: false`，`reason` 完整，每个 speaker 带 `intent`/`direction` |
| 旁白通道语义 | `speaker_id=null` + `is_narration=true` + **有** `message_id`、**无** `delta` |
| **首个说话者不发 `speaker_switch`** | `speaker_switch` 仅 **2 次**（旁白 + c1），**c2 老周只有 delta** —— 这正是坑 G1 的根因，线上实证 |
| 角色区分 | 老周 `c2`（沙哑短句）、苏晚 `c1`（克制）—— `cast.voice` 生效 |
| 节点判定 | `node = n1`「雨夜的第一封信」 |
| 状态收尾 | 无残留 `streaming`，`turn: 1` |

### 3.4 重建/回滚速查（留作运维参考）

```bash
ssh ubuntu@101.33.117.223
cd /opt/marionette

# 查看状态
docker compose ps
docker compose exec api alembic current          # 期望 0002_worlds (head)
docker compose logs api --tail=50

# 重建（改了 backend/frontend 之后）
docker compose build api && docker compose up -d --no-deps api

# 备份 / 恢复
sudo /opt/marionette/backup.sh                    # 手工触发一次备份
sudo /opt/marionette/restore.sh                   # 恢复演练（临时库，安全）
sudo /opt/marionette/restore.sh --to-prod <file>  # 真恢复到生产库（危险，需二次确认）
sudo tail -50 /var/log/marionette-backup.log      # 看备份日志

# 回滚代码
ls ~/backups/
tar xzf ~/backups/marionette-code-<TS>.tar.gz -C /opt
# 回滚数据库（谨慎）
docker compose exec -T db psql -U postgres -d marionette < ~/backups/marionette-db-<TS>.sql
```

> ⚠️ **rsync 部署时必须排除 `backups/` 与 `.backup-env`**，否则 `--delete` 会把备份删掉：
> ```bash
> rsync -az --delete --exclude='.env' --exclude='data/' \
>       --exclude='backups/' --exclude='.backup-env' \
>       ./ ubuntu@101.33.117.223:/opt/marionette/
> ```
> 这两个路径已加入 `.gitignore`，但 rsync 不看 `.gitignore`，必须显式排除。

> ⚠️ `.env` 在服务器上（`-rw------- ubuntu`），`SESSION_COOKIE_SECURE=false`（走 `:80` 纯 HTTP 必须如此）。
> rsync 时务必排除它。

---

## 3.5 自动备份（2026-10-13 已上线）

| 项 | 值 |
|---|---|
| 脚本 | `/opt/marionette/backup.sh`（700 root） |
| 恢复工具 | `/opt/marionette/restore.sh`（700 root） |
| 产物目录 | `/opt/marionette/backups/`（700 root） |
| 日志 | `/var/log/marionette-backup.log` |
| 调度 | **每日 03:20** 备份；**每周日 04:40** 自动恢复演练 |
| 保留 | 本地 7 天（`db_` / `assets_` / `env_` 各自独立清理） |
| 并发保护 | `flock`，上一轮未结束则跳过 |

**备份三件套**（恢复一个实例的最小完备集合）：

| 产物 | 内容 | 说明 |
|---|---|---|
| `db_<时间>.dump` | PostgreSQL 全库 | `pg_dump --format=custom --no-owner`，可 `pg_restore` |
| `assets_<时间>.tar.gz` | `data/assets` + `data/config` | 用户上传的图片与素材 |
| `env_<时间>.tar.gz` | `.env` | 密钥与配置（600 权限） |

**每个产物都做完整性校验**：`pg_restore -l` 能列目录 / `gzip -t` 通过 / 非空且超过阈值。
**宁可不生成，也不留一个坏的备份**。

**恢复演练已验证**（2026-10-13）：从备份恢复到临时库，断言
`cards=5 / worldbooks=2 / presets=1 / sessions=5 / worlds=1` 全部可查，临时库随后清理。

**cron 触发已实测**：临时排一条 2 分钟后的任务，确认到点自动执行并产出文件，
之后移除探针 —— 不是「只写了配置没验证」。

### 异地容灾（COS）：待填密钥

脚本已内置 COS 上传段，**配置好密钥即自动生效**，无需改代码：

```bash
sudo cp /opt/marionette/backup-env.example /opt/marionette/.backup-env
sudo vim /opt/marionette/.backup-env      # 填 COS_SECRET_ID / COS_SECRET_KEY / COS_BUCKET
sudo chmod 600 /opt/marionette/.backup-env
sudo /opt/marionette/backup.sh            # 手工验证一次
```

- `coscmd 1.9.0.6` 已装在 `/opt/marionette-tools/venv`，并软链到 `/usr/local/bin/coscmd`
- **只上传、不同步删除**：本地留 7 天、云端靠存储桶生命周期规则留更久（建议 90/180 天）
- 云端建议用**子账号最小权限密钥**（仅该桶读写），别用主账号密钥
- **故障隔离已实测**：填入假密钥后，COS 上传失败但**本地备份照常完成、退出码 0**

---

## 4. 待办清单（按优先级）

### P0 · 阻塞 MVP 闭环

| # | 事项 | 卡 |
|---|---|---|
| 1 | ~~**S12 剧情演出页**~~ ✅ 已完成 | [`task-S12-story-runtime.md`](./task-S12-story-runtime.md) |
| 2 | S13 会话列表集成 | [`task-S13-session-list.md`](./task-S13-session-list.md) |
| 3 | S14 部署上线（真库联调已过，只差把代码弄上服务器） | 本文 §3.4 |

### P1 · 风险控制

| # | 事项 | 卡 |
|---|---|---|
| 4 | 配置每日备份 cron + 演练恢复 | [`task-INFRA-ops.md`](./task-INFRA-ops.md) 待办 1 |
| 5 | 域名 + HTTPS | 同上 待办 2 |
| 6 | 代码推到 GitHub | [`task-GIT-push.md`](./task-GIT-push.md) |

### P2 · 清理与加固

| # | 事项 | 卡 |
|---|---|---|
| 7 | 改强服务器口令 | [`task-INFRA-ops.md`](./task-INFRA-ops.md) 待办 3 |
| 8 | 换 DeepSeek key | 同上 待办 4 |
| 9 | 清理生产库脏数据 | 同上 待办 5 |
| 10 | 服务器续费 | 同上 待办 6 |

---

## 5. S14 联调部署清单（S12+S13 完成后执行）

### 5.1 本地全量回归

```bash
# 后端
cd /workspace/marionette/backend
./.venv/bin/python -m pytest -q           # 期望 ≥ 402 passed（44 skipped）
ruff check app/ tests/

# 前端
cd /workspace/marionette/frontend
npx tsc --noEmit
npm run verify:sse
node scripts/smoke.mjs                     # 期望 18/18（新增 2 条路由）
npm run build
```

### 5.2 服务器部署

```bash
# 同步代码到服务器 /opt/marionette
cd /opt/marionette
docker compose up -d --build
docker compose logs api --tail=80

# 迁移会自动执行（0002_worlds）
docker compose exec api alembic current    # 应显示 0002
```

### 5.3 真实 PG 集成测试

```bash
docker compose exec api python -m pytest tests/integration -q
```

**期望**：含 `test_story_api.py` 的 16 条剧情 API 测试全绿。
> ⚠️ 会真实读写数据库，**先备份**。

### 5.4 端到端手动验证（关键：这是唯一能验证真实 SSE 链路的方式）

1. 登录 → 新建世界观（填角色 + 一条关系）→ 保存
2. 用该世界观开一局 → 进入 `/stories/:id`
3. 观察首屏：序幕是否正确渲染
4. 发一句输入，**逐项核对**：
   - [ ] 导演裁决出现（`director` 事件到达）
   - [ ] 多个角色**依次**说话，各自独立气泡（不是拼成一坨）
   - [ ] 旁白居中显示
   - [ ] 行动建议出现在底部
   - [ ] 一轮结束后无 `streaming` 残留（刷新后消息状态正确）
5. 中途点「停止」→ 确认消息置 `incomplete` 且**能继续下一轮**
   （这一步专门验证 `_force_idle` 修复是否生效——历史 bug 是会话永久卡死）
6. 打开上下文检视 → 确认 `story_state` / `relations` / `cast_roster` 三段出现

### 5.5 验收判定

全部通过 → 剧情引擎 MVP 闭环完成。
任一项失败 → 按 [`04-pitfalls.md`](./04-pitfalls.md) 对照排查，**在卡里记录现象与复现步骤**。

---

## 6. 已知风险与限制

| 风险 | 影响 | 缓解 |
|---|---|---|
| 剧情模式 LLM 成本 **2x** | 一轮 = 导演 1 次 + 各角色各 1 次 | 已接受（产品决策）；`MAX_SPEAKERS=3` 限制上限 |
| 导演降级时不透明 | 用户只看到质量波动 | `director` 事件带 `degraded` 标记，S12 需展示 |
| 无域名走 HTTP | Cookie 明文传输 | 见运维卡待办 2 |
| 备份未配置 | 数据丢失不可恢复 | 见运维卡待办 1（最高优先） |
| 服务器代码落后 | 剧情功能线上不可用 | S14 部署 |
| 代码未推 GitHub | 单点存放，无异地备份 | 见 Git 卡 |
| 集成测试需真实 PG | 本地只能 skip | 服务器上跑 |

---

## 7. 未验证项（诚实标注）

以下事项**尚未在真实环境验证**，不要当成已完成：

| 项 | 原因 |
|---|---|
| 剧情模式真实 SSE 链路 | 需连后端；本地沙箱无 PG 且未连线上实例 |
| `test_story_api.py`（18 条集成测试） | 本地 skip，需在有 PG 处跑；**曾长期未跑，掩盖线上 500** |
| 剧情会话真实创建与序幕生成 | 需真实 LLM 调用 |
| 世界观 CRUD 的真实 PG 持久化 | 本地只在 sqlite 上验证过 `WorldSvc` |
| 多角色渲染的实际视觉效果 | 需 S12 完成后才能看 |
| 行动建议的真实生成质量 | 需真实 LLM |

> **诚实原则**：本地单测覆盖了逻辑正确性，但**端到端链路必须在服务器上跑一遍**才算数。
> 见 §5.4。
