# 03 · 部署与运维

> 配套总纲：[`README.md`](./README.md) · 生成日期：2026-10-12

---

## 1. 线上环境

| 项 | 值 |
|---|---|
| 服务器 | 腾讯云轻量 · 中国香港（深水埗）· 2 核 / 3.6 G / 70 G · Ubuntu 24.04.4 LTS |
| 公网 IP | `101.33.117.223` |
| 代码位置 | `/opt/marionette` |
| 入口 | http://101.33.117.223（**暂无域名，走 HTTP 明文**） |
| 环境 | Docker 29.6.1 + Compose v5.3.1 |
| 到期 | **2026-11-09**（按月，记得续费） |
| 访问口令 | 已设置（见 `.env`，不进 git） |
| 服务器登录口令 | 偏短，**建议改强或改密钥登录**（见 §5） |

---

## 2. 编排结构

`docker-compose.yml` 三个服务：

| 服务 | 镜像 | 说明 |
|---|---|---|
| `db` | `pgvector/pgvector:pg18` | **不能用官方 `postgres` 镜像**——不含 pgvector 扩展 |
| `api` | 本地多阶段构建 | FastAPI + 同时托管前端 SPA；启动时自动跑 Alembic 迁移 |
| `caddy` | `caddy:2` | 反代 + 自动 HTTPS + **SSE 免缓冲**（`flush_interval -1`） |

### ⚠️ 构建上下文必须在仓库根

`docker-compose.yml` 里 `api.build.context` 是**仓库根目录**，`dockerfile` 指向 `backend/Dockerfile`。
原因：该 Dockerfile 是多阶段的，第一段要构建 `frontend/`、第二段跑 Python，而 Docker 无法 COPY
构建上下文之外的目录。**这是刻意的，不是笔误。**

---

## 3. 部署流程

```bash
# 1. 准备配置
cp .env.example .env
# 至少填：DOMAIN / ACCESS_PASSWORD / SECRET_KEY / DB_PASSWORD
#        LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
#        IMAGE_BASE_URL / IMAGE_API_KEY / IMAGE_MODEL

# 2. 起服务
docker compose up -d
docker compose ps
```

**启动顺序断言**：`db` healthy → `api` 启动（自动迁移）→ `caddy` 就绪。
整体应在 **90 秒内**完成（AC-01，实测约 35 秒）。

```bash
# 3. 健康检查
curl -s https://<域名>/api/v1/system/selfcheck
# 期望：{"code":0,"data":{"db":"ok","pgvector":"ok","llm":{"reachable":<bool>}}}

# 4. 访问控制生效
curl -s -o /dev/null -w '%{http_code}\n' https://<域名>/api/v1/cards
# 期望：401

# 5. 登录取令牌
curl -s -c jar.txt -X POST https://<域名>/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"<ACCESS_PASSWORD>\"}"
# 期望：200 + Set-Cookie 含 HttpOnly
# 连续 5 次错误口令 → 429
```

### 热更新（改配置/代码后）

```bash
cd /opt/marionette
git pull                     # 或上传改动
docker compose up -d --build
docker compose logs api --tail=80
```

---

## 4. `.env` 关键变量

| 变量 | 说明 |
|---|---|
| `DOMAIN` | 有域名填域名；无域名填 `:80` 走纯 HTTP |
| `ACCESS_PASSWORD` | 访问口令，**合规前置条件**，不可留默认值 |
| `SECRET_KEY` | 令牌签名密钥，`openssl rand -hex 32` |
| `DB_PASSWORD` | 数据库密码 |
| `SESSION_COOKIE_SECURE` | ⚠️ 走 `:80` 纯 HTTP 时**必须设 `false`**，否则浏览器不回传 Cookie |
| `ACCESS_MAX_FAILED` | 登录失败限流阈值（默认 5） |
| `ACCESS_LOCK_WINDOW_SECONDS` | 限流窗口（默认 900） |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | OpenAI 兼容后端 |
| `IMAGE_BASE_URL` / `IMAGE_API_KEY` / `IMAGE_MODEL` | 出图后端（BYOK） |
| `CORS_ORIGINS` | 跨域白名单（同源部署留空） |
| `TZ` | `Asia/Shanghai` |

> `.env` 权限应为 600，**不进 git**。

---

## 5. 运维待办（见 `task-INFRA-ops.md`）

| # | 事项 | 优先级 |
|---|---|---|
| 1 | 配置每日 `pg_dump` + assets 增量备份 cron（保留 ≥7 天），并演练一次恢复 | 高 |
| 2 | 买域名 + 解析 + 改 `DOMAIN` + `SESSION_COOKIE_SECURE=true`，启用 HTTPS | 高 |
| 3 | 改强服务器 root 口令或改密钥登录 | 中 |
| 4 | 作废并重新生成 DeepSeek API key（曾明文出现） | 中 |
| 5 | 清理生产库测试脏数据 | 中 |
| 6 | 服务器续费（2026-11-09 到期） | ⏰ |

---

## 6. 备份与恢复

### 备份（当前需手工，cron 待配）

```bash
cd /opt/marionette
docker compose exec db pg_dump -U postgres marionette > /tmp/marionette-$(date +%F).sql
```

### 恢复演练（务必先在临时库验证）

```bash
docker compose exec -T db createdb -U postgres marionette_restore_test
docker compose exec -T db psql -U postgres -d marionette_restore_test < /tmp/marionette-*.sql
docker compose exec -T db dropdb -U postgres marionette_restore_test
```

Spec 要求：每日 `pg_dump` + assets 增量，保留 ≥7 天，且**恢复流程需演练一次**。

---

## 7. 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `api` 反复重启，日志报连不上数据库 | `DB_PASSWORD` 与 `db` 服务不一致；或 `db` 未 healthy |
| 浏览器登录后立刻失效 | 走 HTTPS 时 `SESSION_COOKIE_SECURE=true` 正确；若用 `:80` 调试须设 `false` |
| 前端流式输出「憋住」不出字 | 确认经 Caddy 转发（`flush_interval -1`）；不要直连 api 端口并叠加别的代理缓冲 |
| 中文搜不到 | 走 `pg_trgm` GIN + `ILIKE`，属**预期方案**（ADR-005）；确认迁移已 `CREATE EXTENSION pg_trgm` |
| `extension "vector" is not available` | 镜像必须是 `pgvector/pgvector:pg18` |
| `alembic.ini` 崩溃 | Alembic 以 `locale` 编码读取，GBK 解不了中文注释 → 配置文件保持**纯 ASCII** |

### 看日志

```bash
docker compose logs api --tail=80
docker compose logs db --tail=40
docker compose logs caddy --tail=40
```

---

## 8. 生产库当前计数（2026-10-12 参考）

```
cards 74 / worldbooks 9 / presets 4 / assets 3 / sessions 0
```

⚠️ 其中含**集成测试遗留的脏数据**（历史缺陷已修复，守卫已加）。清理方案见 `task-INFRA-ops.md`。

---

## 9. Caddyfile 要点

`deploy/Caddyfile` 负责反代 + 自动 HTTPS + SSE 免缓冲。

**SSE 必须免缓冲**，否则流式输出会被代理攒成一大块后才吐出，体验上等同于「没有流式」：

```
reverse_proxy api:8000 {
    flush_interval -1
}
```
