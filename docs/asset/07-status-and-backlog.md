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
| **S13** | **会话列表集成** | ✅ | `session-list.tsx` 区分 + 跳转分派、新建对话框补选卡/预设；新增 `check-story-create.mjs` 守卫；smoke 新增第 4 项探针 |
| **S14** | **联调 + 回归 + 部署** | ✅ | 真 PG 端到端 + 全量 446 passed + **服务器已部署并线上验收**（见 §3.2–§3.3.2、§5.6） |

**进度：14/14（100%）** —— S1–S14 全部完成。剧情引擎 MVP 闭环。
剩余未完成项只有**非代码**事项：GitHub 推送（缺 PAT，见 §4 P0）与 COS 异地容灾密钥。

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

> 🔴 **本表已并入 [`09-project-plan.md`](./09-project-plan.md)**（唯一权威路线图，2026-10-13 复核）。
> 下面保留简要摘要，**细节与执行顺序以 09 卡为准**。

### P0 · 阻塞 MVP 闭环

| # | 事项 | 状态 | 卡 |
|---|---|---|---|
| 1 | ~~**S12 剧情演出页**~~ | ✅ 已完成并上线 | [`task-S12-story-runtime.md`](./task-S12-story-runtime.md) |
| 2 | **S13 会话列表集成** | ⬜ **未开始**（`session-list.tsx` 无剧情逻辑） | [`task-S13-session-list.md`](./task-S13-session-list.md) |
| 3 | **S14 联调回归** | 🟡 部署已做，联调待 S13 | [`09-project-plan.md`](./09-project-plan.md) §2 |

### P1 · 风险控制

| # | 事项 | 状态 | 卡 |
|---|---|---|---|
| 4 | ~~配置每日备份 cron + 演练恢复~~ | ✅ **已完成**（cron 已触发、演练通过） | [`task-INFRA-ops.md`](./task-INFRA-ops.md) |
| 5 | **代码推到 GitHub** | ⬜ **就绪待推，只差 PAT**（已预提交 `df97c19`） | [`task-GIT-push.md`](./task-GIT-push.md) |
| 6 | 异地备份（COS） | ⬜ 脚本就绪，**缺密钥** | [`09-project-plan.md`](./09-project-plan.md) §3 |
| 7 | 域名 + HTTPS | ⬜ 仍 HTTP 明文 | [`09-project-plan.md`](./09-project-plan.md) §3 |

### P2 · 清理与加固

| # | 事项 | 状态 | 卡 |
|---|---|---|---|
| 8 | 改强服务器口令 | ⬜ | [`task-INFRA-ops.md`](./task-INFRA-ops.md) |
| 9 | 换 DeepSeek key | ⬜（key 曾明文泄露） | 同上 |
| 10 | 清理生产库脏数据 | 🟡 **大部分已清**（现存 `cards=5/worldbooks=2/presets=1/sessions=5/worlds=1`） | 同上 |
| 11 | 服务器续费 | ⬜（到期 2026-11-09） | 同上 |

---

## 5. S14 联调部署清单（S12+S13 完成后执行）

> **执行状态（2026-10-13）：全部完成 ✅** —— 详见 §5.6 实测记录。

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

### 5.6 S14 实测记录（2026-10-13）

#### 清单完成情况

| # | 清单项 | 结果 |
|---|---|---|
| 1 | 真 PG 上跑集成测试 | ✅ **44 passed, 0 skipped** |
| 2 | 全量（单元 + 集成） | ✅ **446 passed, 0 skipped** |
| 3 | ruff | ✅ All checks passed |
| 4 | 前端 typecheck / verify:sse / verify:story-create / smoke | ✅ 全绿 |
| 5 | 端到端走完剧情链路（含 SSE 推进） | ✅ 见下 |
| 6 | `degraded=false`（LLM 真实连通） | ✅ 导演与行动建议均为 `degraded=false` |

> 清单第 2 项「浏览器里手动走完」以**离线可复现的方式**替代：
> 起真实 PG + 真实 FastAPI + OpenAI 兼容 mock 上游，用 curl 驱动完整链路，
> 并把闸门**固化进 `smoke.mjs` 的第 4 项探针**（见下），
> 这样每次 `npm run smoke` 都会重跑，不会随人工验收一起漂走。

#### 环境搭法（本地，无需服务器）

```bash
# 1) 真实 PG 18 + pgvector
docker run -d --name mtest-pg -e POSTGRES_USER=marionette -e POSTGRES_PASSWORD=mtest \
  -e POSTGRES_DB=marionette_test -p 55432:5432 pgvector/pgvector:pg18
docker exec mtest-pg psql -U marionette -d marionette_test \
  -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# 2) 迁移（需 Python ≥ 3.12：schemas 里用了 PEP 695 泛型 `class Envelope[T]`）
cd backend && DATABASE_URL=postgresql+asyncpg://marionette:mtest@127.0.0.1:55432/marionette_test \
  python3.12 -m alembic upgrade head      # → 0002_worlds (head)

# 3) 集成测试
MARIONETTE_INTEGRATION=1 ASSETS_DIR=/tmp/mtest-assets \
  DATABASE_URL=... python3.12 -m pytest tests/integration -q
```

> ⚠️ **两个坑**（都已踩过）：
> 1. 设置项**没有 env 前缀**，是 `DATABASE_URL` 而非 `MARIONETTE_DATABASE_URL`；
> 2. 测试库必须预装 `vector` **和** `pg_trgm`（后者用于 `gin_trgm_ops` 索引，
>    缺了会在建表阶段报 `operator class "gin_trgm_ops" does not exist`）。

#### 端到端断言（真 PG + 真 FastAPI + mock 上游）

事件序列（2 角色 + 旁白 + 节点触发 + 关系更新）：

```
world_info → director → start → speaker_switch → delta×4 → speaker_switch → delta×5
           → node → usage → actions → done
```

| 验证点 | 实测 |
|---|---|
| 剧情会话创建（真实 card + preset + world） | ✅ `spec=story_session`，序幕由 LLM 生成 |
| 导演裁决 `degraded` | ✅ `false`；`speakers=['su','zhou']` |
| **多角色独立气泡** | ✅ 苏晚与老周各自成泡，台词不串 |
| **旁白不落进角色气泡** | ✅ 独立旁白块，`is_narration=true` 且不发 delta |
| **行动建议走 LLM**（非兜底 `f*`） | ✅ id 为 `a0/a1/a2`，tone 覆盖 act/speak/observe |
| **节点推进** | ✅ `node` 事件 → `/story` 的 `node_id=n1` 已持久化，`beat_index` 递增 |
| **关系图增量更新** | ✅ 新增「猜忌」边，原「旧识」边完整保留 |
| 刷新恢复（`/story`） | ✅ `scene.present` / `cast` / `relations` 全部回填 |
| `/actions` 兜底补拉 | ✅ 拿到同一批 LLM 建议 |
| 消息落库 `N 说话者 = N 条` | ✅ 旁白 1 + 角色 2 = 3 条，无空占位 |

#### 新增回归闸门

`smoke.mjs` 第 4 项探针 **`probeSessionList`**（驱动真实 `/sessions` 页面）：

```
PASS  会话列表剧情集成  条目=4 剧情标识=3 世界观名=true 跳转=/stories//sessions
```

检查：剧情与 1v1 条目共存、剧情条目带「剧情」标识、标题位显示世界观名
（不是裸 UUID）、跳转分派正确（含 `spec` 缺失但 `world_id` 存在的兜底分支）。

> 已做**故障注入验证**：把 `sessionHref` 的剧情分支改回 `/sessions` 后，
> 探针准确报 `FAIL 跳转=✗/✗`；恢复即 PASS —— 证明这条闸门真的有效。

### 5.7 线上反馈修复：「世界编辑页开演失败」（2026-10-13）

#### 现象

用户在世界编辑页点「用这个世界开演」，弹红色 toast：

> 无法开演 —— 创建剧情会话失败。请确认后端已配置模型，并且这个世界至少有一个角色。

截图里世界已保存（2 角色 · 1 关系 · 1 节点），节点 `n1 雨夜的第一封信` 存在。
**toast 的文案具有误导性**：它把用户引向「配模型 / 加角色」，而真实原因与这两者无关。

#### 根因：**第二个创建入口漏改**

S13 已经判定「创建剧情会话必须传真实 card / preset」并修掉了
`new-session-dialog.tsx`。但创建剧情会话有**两个**入口，世界编辑页的
`play.mutationFn` 是第二个，写法与修掉的完全一样：

```ts
// world-editor.tsx（修复前）
const lead = draft.cast[0];
return sessionsApi.create({
  character_card_id: lead?.card_id ?? '',
  preset_id: '',            // ← 后端必填 UUID，这里必然失败
  world_id: worldId,
});
```

后端 `SessionCreateRequest` 的 `character_card_id` / `preset_id` 均为**非 Optional** UUID。
真实后端实测三条失败路径：

| 入参 | 结果 |
|---|---|
| `preset_id: ''` | `400 endpoint_invalid`「preset_id Input should be a valid UUID…found 0」 |
| `character_card_id: ''` | `400 endpoint_invalid`「character_card_id Input should be a valid UUID…found 0」 |
| `preset_id: <不存在的 UUID>` | `404 model_not_found`「预设不存在，无法开启剧情。」 |

即便绕过 pydantic 校验，`parse_uuid('')` 也会抛 `BadRequestError` → 400；
`create_story_session()` 还会再查一次 card/preset，查不到即 404。**三道关卡**都过不去。

#### 为什么没被拦住

守卫脚本 `check-story-create.mjs` **只扫 `new-session-dialog.tsx` 一个文件**。
修完那个文件后闸门全绿，第二个入口从未被扫过 —— 这是典型的
「修了症状所在的入口，没修同类入口」的遗漏。

#### 修复

`world-editor.tsx`：
- 拉取 `cardsApi.list` / `presetsApi.list` 全量清单
- 新增 `linkedCardId`，与对话框**同一套**三级优先：
  成员 `card_id` 精确命中 → 按 `name` 匹配 → 清单首张
- 新增 `defaultPresetId`（清单首份预设）
- `play.mutationFn` 改传真实 id
- 新增 `canPlay` / `playBlockReason`：缺卡或缺预设时**按钮直接禁用**，
  并把原因写进 `title`，不让用户对着灰按钮猜

`editor-header.tsx`：顶栏「开演」同步接入 `playDisabled` / `playBlockReason`。

#### 守卫加固（防同类回归）

`check-story-create.mjs` 从「只扫一个文件」改为
**递归扫描 `src/` 下所有 `sessionsApi.create(` 调用点**，
对传了 `world_id` 的（即剧情路径）逐个校验 card / preset 是否为真实变量，
并覆盖 `?? ''` 这种可选链兜底变体：

```
=== 剧情会话创建守卫（S13）===
  · src/components/session/new-session-dialog.tsx：剧情创建传真实 card + preset + world
  · src/pages/world-editor.tsx：剧情创建传真实 card + preset + world
  · 后端 SessionCreateRequest：character_card_id / preset_id 均为必填 UUID
  · 演示世界观 1 个关联卡均指向真实卡片
[结论] PASS
```

**故障注入验证**：把 `world-editor.tsx` 改回空串 → `FAIL（2 项）` exit=1；
恢复 → PASS。

#### 端到端复验（真实后端）

修复前 / 修复后入参对照：

| | 入参 | 结果 |
|---|---|---|
| 修复前 | `preset_id: ''` | **400** endpoint_invalid |
| 修复后 | `card_id + preset_id + world_id`（真实 UUID） | **201**，`spec=story_session` |

修复后建出的会话，完整链路实测：

- **序幕**：`opening_parts=1`，走 L1（LLM）生成，落库为第 1 条 assistant 消息
- **SSE 演出**（11 个事件）：
  `world_info → director → start → speaker_switch(旁白) → delta×3 → node → usage → actions → done`
- **气泡独立**：旁白气泡 + 林砚台词气泡分开，未串
- **节点推进**：`node_id=n1 雨夜的第一封信` 落库
- **关系增量**：`c1→c1 旧识` 更新为 tension 0.7
- **刷新恢复**：`GET /sessions/{id}/story` 返回 `is_story=true` + cast + relations
- **`degraded=false`**

#### 教训（已同步进 §6 风险表）

> **修一类契约错误时，必须枚举「所有具备该契约的调用点」，而不是只修报错的那一个。**
> 守卫脚本的扫描范围要覆盖全仓，不能只盯住症状出现的文件 ——
> 否则闸门会在「第二个入口」上给出虚假的安全感。

### 5.8 线上反馈修复第二轮：气泡顺序 + 部署缺口（2026-10-13）

用户第二次线上反馈，两个问题：

#### 问题 ① 剧情多轮对话，回复跑到用户消息上方

**现象**：连续游玩两轮。第二轮回答提交后，角色回复与剧情推演**没有出现在
本轮用户气泡下方**，而是被追加进**第一轮**的历史气泡（位置上在用户消息**上方**）。

**根因**：`delta` 只带 `speaker_id`，前端 `appendDelta` 靠它**反向查找**该写进哪条气泡。
但**同一角色每轮的 `speaker_id` 完全相同**，第二轮就命中了第一轮留下的旧气泡。
旁白分支（`is_narration`）有同一缺陷。

**修复**：引入轮次边界 `_turnKey`（详见 §4 坑位 D11）：

- `session.ts`：`MessageMeta` 加 `_turnKey?: string`（纯前端本地字段）
- `use-chat-stream.ts`：`turnKeyRef` 在 **`startStream`** 里换新值（不是 `send`，
  这样 `regenerate` / `retry` 也覆盖）；`tagTurn()` 给本轮气泡打标记；
  `appendDelta` **两处**反查都加边界条件

**回归防护**：新增 `probeStoryMultiTurn`（`smoke.mjs` 第 6 项探针），连发两轮断言
「第二轮用户气泡 → 本轮回复气泡」顺序，且第一轮气泡未被改写。
**已做故障注入验证**：移除两处 `_turnKey` 条件后探针正确报 FAIL。

修复后：

```
PASS  剧情多轮气泡顺序  第二轮用户@3 回复@4 首轮气泡误膨胀=false
[结论] PASS
```

#### 问题 ② 线上依然无法开演 —— **修复从未部署**

D9 修完并提交 `2872bc5` 之后，用户反馈线上「依然无法开演」。
实测对照线上 JS 与本地新构建产物：

| 特征 | 线上 `index-DAZGvsr6.js` | 本地 `index-DCcJtofX.js` |
|---|---|---|
| `playBlockReason` | 0 | **2** |
| `_turnKey` | 0 | **3** |
| `preset_id:""`（旧空串写法） | **1** | 0 |

**结论：线上跑的是有 bug 的旧版，`2872bc5` 从未部署。**

**部署方式（关键约束）**：前端产物被**烤进 api 镜像**
（`backend/Dockerfile` → `COPY --from=web /src/frontend/dist /app/static`），
所以更新前端 = **重新构建 api 镜像 + 重启容器**，不能只替换静态文件。

**阻塞**：沙箱无 SSH 凭据（`Permission denied (publickey,password)`，
`~/.ssh` 只有 `known_hosts`），服务器仅开放 22/80，无其他上传入口。
已产出 `deploy-frontend-fix.sh`（含镜像备份 + 回滚提示 + 产物校验），
待用户提供 SSH 通道后执行。

#### 教训

> **「修好了」和「上线了」是两件事。**
> 提交 + 校验全绿只能证明**仓库里的代码对了**，不能证明**用户看到的东西变了**。
> 声明修复完成前，必须在**用户实际访问的地址**上验证；
> 做不到时必须明确写「未部署」，不能让用户误以为已经生效。

> **探针必须做故障注入验证。** 本次 `probeStoryMultiTurn` 第一版
> 因为 `ok` 判定漏项，在注入故障后**仍然 PASS**（漏报）——
> 修正后才成功报 FAIL。一个从不失败的探针等于没有探针。

---

## 6. 已知风险与限制

| 风险 | 影响 | 缓解 |
|---|---|---|
| 剧情模式 LLM 成本 **2x** | 一轮 = 导演 1 次 + 各角色各 1 次 | 已接受（产品决策）；`MAX_SPEAKERS=3` 限制上限 |
| 导演降级时不透明 | 用户只看到质量波动 | `director` 事件带 `degraded` 标记，S12 需展示 |
| 无域名走 HTTP | Cookie 明文传输 | 见运维卡待办 2 |
| 备份未配置 | 数据丢失不可恢复 | 见运维卡待办 1（最高优先） |
| 服务器代码落后 | 剧情功能线上不可用 | **已确认为当前最高优先缺口**：线上前端是旧版（`preset_id:""` 仍在），`2872bc5`（开演修复）与 `e3c0a33`（气泡修复）均未部署。见 §5.8 问题② |
| 代码未推 GitHub | 单点存放，无异地备份 | 见 Git 卡 |
| 集成测试需真实 PG | 本地只能 skip | 服务器上跑 |
| **同一契约有多个调用点** | 修一个漏一个（已发生过：S13 漏 world-editor） | 守卫脚本改为**全仓扫描**；修契约时先枚举全部调用点 |

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
