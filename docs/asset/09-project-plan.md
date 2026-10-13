# 09 · 项目计划（唯一权威路线图）

> 配套总纲：[`README.md`](./README.md) · 建立日期：**2026-10-13** · 复核依据：线上实测 + 本地实跑
> 本卡是**接下来要做什么**的唯一权威清单。其他卡提到待办时，以本卡为准。

---

## 0. 一句话现状

**核心功能（S1–S12 剧情引擎）已完成并上线运行**，线上端到端验收通过。
**当前卡在两件"接入"上的事**：① 代码还没推到 GitHub（缺凭据）；
② 前端还进不去剧情页（S13 会话列表未接入）。基础设施的备份已就位，但**没有异地容灾**。

```
已完成 ████████████████░░░░  12/14 步（86%）
        ├─ S1–S12 ✅ 已上线
        ├─ S13    ⬜ 未开始（P0）
        └─ S14    🟡 部分完成（部署已做，联调待 S13）
```

---

## 1. 里程碑总览

| 阶段 | 内容 | 状态 | 阻塞于 |
|---|---|---|---|
| **M1** | 剧情引擎后端 + 前端（S1–S12） | ✅ **已完成并上线** | — |
| **M2** | 会话列表接入剧情（S13） | ⬜ **未开始** | — |
| **M3** | 全链路联调 + 回归（S14） | 🟡 一半 | S13 |
| **M4** | 代码同步 GitHub | 🟡 **就绪待推**（代码全在本地 git，从未上远端） | **PAT**（连接器已证无效） |
| **M5** | 基础设施加固 | 🟡 部分 | 密钥 / 域名 |

---

## 2. P0 · 打通用户可用闭环

### P0-1 ⬜ S13 · 会话列表集成（前端）

**为什么是 P0**：现在剧情会话**建得出来、跑得通，但用户在界面上进不去**。
`/stories/:id` 路由已存在且可用，缺的是**入口**。

**实测依据**（2026-10-13 复核）：
- `frontend/src/pages/session-list.tsx`（292 行）**完全没有**剧情会话相关逻辑 —— 全文无 `story_session` / `world` 字样
- `components/session/new-session-dialog.tsx` 只处理 cards / presets / worldbooks，**不能选世界观建剧情会话**
- 但 `App.tsx` 里 `/stories/:id` → `StoryRuntimePage` **已接好**

**要做的事**：
1. `session-list.tsx`：剧情会话显示「剧情」标签；点击跳 `/stories/:id`（而非 `/sessions/:id`）
2. `new-session-dialog.tsx`：新增「剧情模式」选项，可选世界观 → `POST /sessions` 带 `world_id`
3. 复用已有 `worldsApi.list()` 拉世界观下拉

**验收标准**：
- [ ] 剧情会话在列表中可见且有「剧情」标签
- [ ] 点击跳转到 `/stories/:id` 并正常渲染
- [ ] 能从列表新建剧情会话（选世界观）
- [ ] `tsc` 0 错误 / `verify:sse` PASS / smoke 从 17 增到 18 条且全 PASS

**卡**：[`task-S13-session-list.md`](./task-S13-session-list.md)

---

### P0-2 🟡 S14 · 全链路联调 + 回归

**为什么是 P0**：这是**唯一能验证真实 SSE 链路**的环节。

**已完成的一半**（2026-10-13）：
- ✅ 代码已部署到服务器，容器 healthy，迁移到 `0002_worlds (head)`
- ✅ 线上端到端已验收过一次：真 SSE **109 事件**跑通，`speaker_switch=2` 与后端行为一致
- ✅ 本地全量回归全绿（402 passed / ruff / tsc / SSE / smoke）

**还差的一半**（依赖 S13）：
- [ ] S13 完成后**重新**部署一次
- [ ] 在**真实 PG** 上跑集成测试：`446 passed, 0 skipped`（本地因无 PG 会 skip 44 条）
- [ ] 浏览器里**手动**走完：登录 → 新建剧情会话 → 演出页多角色气泡 → 行动建议点击 → 节点推进
- [ ] 确认 `degraded=false`（LLM 真实连通）

**卡**：本文 §5 + [`07-status-and-backlog.md`](./07-status-and-backlog.md) §3.4

---

## 3. P1 · 代码资产与风险控制

### P1-1 ⬜ 推送代码到 GitHub 🔴 **只差一个 Token**

**为什么是 P1 最高**：GitHub 现在**仍是旧版**（`c9f6da5`，S11 之前）。
任何新任务 `git clone` 都会拿到缺剧情引擎的代码，进而误判「项目没有代码」——
这个坑**真实发生过一次**，浪费了一整个任务。

**当前状态**（2026-10-13 复核）：

| 项 | 状态 |
|---|---|
| S1–S12 + 资产文档同步进 git 仓库 | ✅ 已完成（本地已提交，见 `task-GIT-push.md` 提交链） |
| 代码规模核对 | ✅ 90 个 backend `.py` / 126 个前端 `.ts/.tsx` |
| 五项校验 | ✅ 全绿（402 passed, 44 skipped / ruff / tsc / SSE / smoke） |
| 敏感文件防线 | ✅ 通过（无 `.env` / `.backup-env` / 私钥） |
| MCP GitHub connector | ❌ **实测只读**（`push_files` → 403 `Resource not accessible by integration`） |
| GitHub 连接器 OAuth token | ❌ **实测无 `repo` scope**（`x-oauth-scopes` 为空 → `git push` 403 `denied to ming-ni-we`） |
| 与远端的关系 | 本地领先若干提交（`c9f6da5` 起）、落后 0，可 fast-forward；**数量以 `git rev-list --left-right --count origin/main...HEAD` 实测为准** |
| **`GITHUB_TOKEN`（PAT）** | ⏳ **缺 —— 唯一阻塞项** |

**一条命令完成**：
```bash
cd /workspace/marionette
export GITHUB_TOKEN=<fine-grained PAT，Contents: Read and write>
./scripts/push-to-github.sh --dry-run "feat(story): S1–S12"   # 先试推
./scripts/push-to-github.sh "feat(story): S1–S12"             # 正式推
```

> ⚠️ **已穷尽本环境所有通道**（2026-10-13 实测）：MCP 只读、连接器 OAuth token 无
> `repo` scope、`gh` 未登录、credential helper 返回空。**不要再花时间重试这些**，
> 直接要 PAT 是唯一路径。详见 [`task-GIT-push.md`](./task-GIT-push.md)。

**完成后**：本项关闭，且 [`task-GET-CODE.md`](./task-GET-CODE.md) §2 的「GitHub 落后」高危坑**自动消失**。

> 🔴 **这是全项目最高性价比的一件事**：一条命令，消除一个已经发生过的高危坑。

**卡**：[`task-GIT-push.md`](./task-GIT-push.md) · 纪律：[`08-release-discipline.md`](./08-release-discipline.md)

---

### P1-2 ⬜ 异地备份（COS）

**当前风险**：备份**只在本机**（`/opt/marionette/backups/`）。
能防误删、防损坏，**但防不了机器或磁盘故障** —— 服务器一挂，数据全没。

**现状**（2026-10-13 复核）：
- ✅ 本机备份正常：cron `20 3 * * *`，实测已触发，保留 7 天
- ✅ 恢复演练正常：cron `40 4 * * 0`，演练通过（`cards=5/worldbooks=2/presets=1/sessions=5/worlds=1`）
- ✅ 上传脚本已写好（`backup.sh` 内置，**仅上传不镜像删除**）
- ❌ **`/opt/marionette/.backup-env` 不存在** → 上传通道未启用

**要做的事**：提供腾讯云 COS 凭据，写入 `/opt/marionette/.backup-env`（600）：
```bash
COS_SECRET_ID=...
COS_SECRET_KEY=...
COS_BUCKET=...
COS_REGION=ap-hongkong
```
然后跑一次 `sudo /opt/marionette/backup.sh` 验证上传成功。

**卡**：[`task-INFRA-ops.md`](./task-INFRA-ops.md)

---

### P1-3 ⬜ 域名 + HTTPS

**当前风险**：`DOMAIN=:80` + `SESSION_COOKIE_SECURE=false` → **Cookie 走 HTTP 明文**，
会话令牌有被截获风险。

**实测依据**：服务器 `.env` 仍是 `DOMAIN=:80` / `SESSION_COOKIE_SECURE=false`。

**要做的事**：
1. 买域名，解析 A 记录到 `101.33.117.223`
2. 改 `.env`：`DOMAIN=你的域名` + `SESSION_COOKIE_SECURE=true`
3. `docker compose up -d caddy` → Caddy 自动签 Let's Encrypt 证书

**卡**：[`task-INFRA-ops.md`](./task-INFRA-ops.md)

---

## 4. P2 · 安全加固与清理

| # | 事项 | 现状（2026-10-13 复核） | 动作 |
|---|---|---|---|
| P2-1 | **换 DeepSeek key** | key 曾明文出现在对话中 | 作废重生成 → 改服务器 `.env` 的 `LLM_API_KEY` → `compose up -d` 热替换 |
| P2-2 | **改强服务器口令 / 换密钥登录** | `WBAccess@1` 偏短 | 用 `ubuntu` 用户改强密码，或改为 SSH key 登录 |
| P2-3 | **清理生产库测试数据** | 🟡 **大部分已清**：`cards=5`（含 1 张 `测试角色A`）、`worldbooks=2`、`presets=1`、`sessions=5`（含 `部署验证会话`、2 条 `部署验收 · 雨夜旧城`） | 删掉明显的验收/测试残留（`测试角色A`、`部署验证会话`） |
| P2-4 | **服务器续费** | 到期 2026-11-09 | 记得续费，否则停机 |

---

## 5. 建议执行顺序

```
① 推 GitHub（P1-1）           ← 一条命令，消除高危坑，性价比最高
       ↓
② S13 会话列表（P0-1）        ← 打通用户可用闭环
       ↓
③ 重新部署 + S14 联调（P0-2）  ← 在真 PG 上跑集成测试 + 浏览器手验
       ↓
④ 异地备份 COS（P1-2）        ← 需你提供密钥
       ↓
⑤ 域名 + HTTPS（P1-3）        ← 需你买域名
       ↓
⑥ P2 加固与清理
```

> **①和②互不阻塞，可并行。** 若你希望尽快让项目"能正常用"，先做②；
> 若更怕代码丢失/他人接手踩坑，先做①。

---

## 6. 需要你提供的（外部依赖）

| 需要什么 | 用来做什么 | 阻塞哪项 |
|---|---|---|
| **GitHub PAT**（fine-grained，Contents: Read and write） | 推送代码到 GitHub | P1-1 |
| **腾讯云 COS 密钥**（SecretId / SecretKey / Bucket） | 异地备份 | P1-2 |
| **域名** | HTTPS + 安全 Cookie | P1-3 |
| **新的 DeepSeek key** | 替换泄露的 key | P2-1 |
| （可选）服务器 SSH 公钥 | 改用密钥登录 | P2-2 |

---

## 7. 诚实标注：未验证 / 不确定的

- **`snapshot.scene.present` 语义**：我按「在场角色」使用；若后端意指「本回合说话者」，S13/S14 联调时需对齐。
- **集成测试在真 PG 上的结果**：`446 passed, 0 skipped` 是**推断值**（本地 402 + 44 skipped = 446 收集数）。
  真 PG 上是否 446 全过，**需 S14 实测确认**。
- **COS 上传通道**：脚本已写好，但**从未用真实密钥跑通过**（只用假密钥测过失败路径）。
- **备份 cron 长期稳定性**：只验证了单次触发，未观察多日连续运行。
