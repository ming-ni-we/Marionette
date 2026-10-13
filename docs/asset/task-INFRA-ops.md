# task-INFRA-ops · 运维待办

> 配套总纲：[`README.md`](./README.md) · **完全独立**，不与代码任务冲突 ✅
> 详细环境信息：[`03-deployment.md`](./03-deployment.md)

---

## 背景

线上实例（腾讯云轻量 · 中国香港 · `101.33.117.223`）已能跑，但有若干**运维缺口**，
不影响功能，但都是真实风险。本卡把它们逐条列清、给出可直接执行的命令。

**这些事都不碰仓库代码**，可与任意开发任务并行。

---

## 待办 1 · ~~配置每日备份 cron~~ ✅ 已完成（2026-10-13）

**状态**：**已上线**。脚本 `/opt/marionette/backup.sh` + `/opt/marionette/restore.sh`，
root crontab 每日 03:20 备份、每周日 04:40 自动恢复演练，本地保留 7 天。

**与本卡原始草稿的差异**（原草稿有 4 处会出问题，已修正）：

| 原草稿 | 问题 | 实际实现 |
|---|---|---|
| `backend/data/assets` | **路径错误**——实际是 `/opt/marionette/data/assets`（Docker bind-mount） | 用 `-C /opt/marionette data/assets config` |
| 无 `sudo` | `data/` 与 `.env` 属主是 **root**，`ubuntu` 读不到 | 脚本要求以 root 运行（`ubuntu` sudo 免密） |
| `pg_dump \| gzip` 无校验 | 管道下 `pg_dump` 失败会被 gzip 成功掩盖 | 改用 `--format=custom` + `pg_restore -l` 结构校验 + 体积阈值 |
| `find -mtime +7 -delete` | 无差别删除，易误伤 | 按 `db_*` / `assets_*` / `env_*` 前缀各自清理 |

**另加了原草稿没有的**：`flock` 并发保护、`pg_isready` 前置检查、
失败可见的结构化日志（`SUMMARY` 行供告警）、`.env` 归档 600 权限、
每周自动恢复演练、可选 COS 异地同步（配置密钥即生效）。

**验证证据**：

- 恢复演练通过：临时库 `cards=5 / worldbooks=2 / presets=1 / sessions=5 / worlds=1` 全部可查
- cron 真实触发已实测（排 2 分钟后的探针任务，到点自动跑出产物，验后移除）
- 故障注入通过：填入假 COS 密钥，本地备份照常完成、退出码 0

**详见**：`07-status-and-backlog.md` §3.5。

**遗留**：COS 异地同步的密钥需你提供（见该节「待填密钥」）——
在此之前**只有本地备份**，能防误删/坏数据，但**防不了整机或磁盘故障**。

---

## 待办 2 · 域名 + HTTPS ⭐ 高优先

**现状**：走 **HTTP 明文**，会话 Cookie 在公网明文传输。

**为什么重要**：`ACCESS_PASSWORD` 与 HttpOnly 会话令牌都靠这个通道。明文 = 可被中途截获。

```bash
# 1. 买域名，A 记录指向 101.33.117.223
# 2. 改 .env
DOMAIN=your.domain.com
SESSION_COOKIE_SECURE=true      # ⚠️ 关键，否则浏览器不回传 Cookie

# 3. 重启（Caddy 自动签证书）
cd /opt/marionette && docker compose up -d

# 4. 验证
curl -sI https://your.domain.com/api/v1/system/selfcheck | head -3
```

---

## 待办 3 · 改强服务器口令

**现状**：`WBAccess@1` 偏短。

```bash
# 方案 A：改强密码
passwd

# 方案 B（推荐）：改用密钥登录
# 本机
ssh-keygen -t ed25519 -C "marionette"
ssh-copy-id root@101.33.117.223
# 验证能免密登录后，关闭密码登录
# 服务器 /etc/ssh/sshd_config:  PasswordAuthentication no
systemctl restart sshd
```

---

## 待办 4 · 换 DeepSeek API key

**背景**：key 曾在对话中明文出现。

```bash
# 在 DeepSeek 控制台作废旧 key、生成新 key
cd /opt/marionette
# 编辑 .env 的 LLM_API_KEY
docker compose up -d          # 热替换，无需重建镜像
curl -s https://<域名>/api/v1/system/selfcheck   # 确认 llm.reachable=true
```

---

## 待办 5 · 清理生产库脏数据

**背景**：历史上集成测试因隔离缺陷写进过生产库（缺陷已修复，守卫已加）。

**当前计数**：`cards 74 / worldbooks 9 / presets 4 / assets 3 / sessions 0`

**待清理项**（非本人内容）：

- **卡片**：`栖夜书店`/`栖夜咖啡馆`/`栖夜车站`/`栖夜天台`/`栖夜码头`/`栖夜小巷`/`栖夜公园`（各 3 份）、
  `倒序甲/乙/丙`（各 3 份）、`双标签角色`（3 份）、`单标签角色`、`空资产角色`、`描述检索角色`、
  `图集角色`、`格式校验角色`、`打包角色`、`PNG导出角色`、`PNG导出角色 (导入副本)`、
  `HTTP往返角色`、`HTTP往返角色 (导入副本)`、`PROBE_ISOLATION_CARD`
- **世界书**：重复的 `城南街区` / `日常向对话基调`（每个名字本应只有 1 本）、
  `三态验证世界书`、`公交线路世界书`、`验证用世界书`

**清理步骤**：

```bash
# ① 先备份（见待办 1）
bash /opt/marionette/backup.sh

# ② 看清现状
docker compose exec -T db psql -U postgres -d marionette -c \
  "select id,title from cards order by created_at;"

# ③ 逐个删除（先跑 select 确认，再删）
docker compose exec -T db psql -U postgres -d marionette -c \
  "delete from cards where title like '栖夜%' or title like '倒序%';"
```

> **更干净的方案**：既然目前还没有真实内容，可考虑直接清空这几张表，
> 再跑一次 `POST /api/v1/onboarding/samples` 重新灌内置示例。
> **但务必先备份，且确认你确实不需要现有数据。**

---

## 待办 6 · 服务器续费

**到期日：2026-11-09**（按月）。到期即停机。

---

## 验收标准

- [x] `backup.sh` 存在且可执行，crontab 已装，手工跑一次有产物
- [x] 恢复演练成功（临时库能查到数据），临时库已清理
- [ ] COS 异地同步生效（**待提供密钥**）
- [ ] 域名解析生效，HTTPS 可访问，Cookie 正常回传
- [ ] 密钥登录可用（或口令已改强）
- [ ] 新 LLM key 生效，`selfcheck` 的 `llm.reachable=true`
- [ ] 生产库计数下降至只剩真实内容
- [ ] （日历提醒）2026-11-09 前续费

---

## 交接记录

> 完成后填这里

**状态**：待办 1 已完成 ✅（2026-10-13）；待办 2–6 待领取。

**待办 1 交付物**：

| 路径 | 说明 |
|---|---|
| `/opt/marionette/backup.sh` | 备份脚本（700 root） |
| `/opt/marionette/restore.sh` | 恢复工具（700 root），默认演练、`--to-prod` 才动生产库 |
| `/opt/marionette/backup-env.example` | COS 配置模板（复制为 `.backup-env` 填密钥） |
| `/opt/marionette/backups/` | 产物目录（700 root） |
| `/var/log/marionette-backup.log` | 运行日志 |

**root crontab 现有条目**（`sudo crontab -l`）：

```
20 3 * * * /usr/bin/flock -n /tmp/marionette-backup.lock /opt/marionette/backup.sh >> /var/log/marionette-backup.log 2>&1
40 4 * * 0 /usr/bin/flock -n /tmp/marionette-restore.lock /opt/marionette/restore.sh >> /var/log/marionette-backup.log 2>&1
```

**下次接手须知**：

1. 部署时的 rsync **必须排除 `backups/` 与 `.backup-env`**，否则 `--delete` 会删掉备份。
2. 备份脚本要求 **root** 运行（`data/` 与 `.env` 属主是 root）；`ubuntu` 有 sudo 免密。
3. 想看备份是否正常：`sudo tail -20 /var/log/marionette-backup.log`，末行 `SUMMARY` 有体积与文件数。
4. 要恢复：先 `sudo /opt/marionette/restore.sh`（演练，安全），确认无误再 `--to-prod`。

---

## 待办 X · 线上前端补部署（2026-10-13 已完成 ✅）

**背景**：`2872bc5`（开演修复）与 `e3c0a33`（气泡修复）两个提交都**从未部署**，
线上跑的是旧版前端。详见 `04-pitfalls.md` D10。

**服务器访问凭据**（用户 2026-10-13 提供）：

```
主机：101.33.117.223
账号：ubuntu
口令：WBAccess@1
```

沙箱侧用 `sshpass` 免交互登录：

```bash
export SSHPASS='WBAccess@1'
sshpass -e ssh -o StrictHostKeyChecking=no ubuntu@101.33.117.223 '<命令>'
sshpass -e scp -o StrictHostKeyChecking=no <本地文件> ubuntu@101.33.117.223:<远端路径>
```

**执行记录**：

| 步骤 | 命令要点 | 结果 |
|---|---|---|
| 1 | `git bundle` → `md5sum` → `scp` 上传 | 1.9 MB，MD5 `64abf05a…` 两端一致 |
| 2 | 服务器 `git clone marionette-fix2.bundle marionette-new` | HEAD `1954a4d`，修复特征齐全 |
| 3 | 备份当前镜像 | `marionette-api:pre-bubblefix-20261013-145629` |
| 4 | `sudo docker build -f backend/Dockerfile -t marionette-api:newfix .` | 成功，产物 `index-CD95XgpK.js` |
| 5 | 镜像内特征校验 | `playBlockReason=2` / `_turnKey=3` / `preset_id:""=0` |
| 6 | **原目录**替换重启（`--no-deps --force-recreate api`） | healthy，镜像 ID `9caf9806` → `9757102c` |
| 7 | 线上验收 | 首页 JS 变 `index-CD95XgpK.js`；特征与镜像一致 |

**线上业务验收**（真实 deepseek-chat）：

- 开演：`POST /sessions` → **201**，`spec=story_session`，序幕 2 段旁白真实生成
- 第 1 轮 SSE：旁白 `speaker_switch`（`is_narration=true`）→ `c2` 白发 delta（首个说话人不发 switch）→ `node n1`
- 第 2 轮 SSE：**`delta` 说话人仍是 `c2`** —— 正是 bug 的触发条件
- 落库顺序验证：8 条消息，`白鸟 澪` 在两轮**各有一条独立消息**
  （`[4]` turn0 / `[7]` turn1），未被合并 —— 证明 `_turnKey` 边界生效

**遗留清理**：`/home/ubuntu/marionette-new`（构建用源码目录）与
`/home/ubuntu/marionette-fix2.bundle` 可保留作下次部署的代码来源。

**下次更新代码时的推荐流程**：见 `03-deployment.md` §1.1–§1.4。

---

