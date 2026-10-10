# 提线 (Marionette)

在自己云上的一台服务器里，15 分钟从零开始一场带世界书触发与长期记忆的角色扮演。
角色卡、世界书、图集全程以可移植文件进出——随时完整带走，换模型不换档。

> 形态：**云端私有单实例 · 仅限自用**。产品定义以 `docs/spec/SPEC.md` 为唯一契约。

---

## 技术栈（锁定版本，不得替换）

| 层 | 技术 |
|---|---|
| 后端 | FastAPI 0.141.1 + Uvicorn 0.48 · Python 3.12 · Pydantic 2.13.4 |
| 数据 | PostgreSQL 18 + pgvector 0.8.6（镜像 `pgvector/pgvector:pg18`） |
| ORM/迁移 | SQLAlchemy 2.0 async + Alembic 1.18 |
| 检索 | `pg_trgm` GIN + `ILIKE`（中文免分词） |
| 编排 | Docker Compose（`caddy` + `api` + `db`） · Caddy 2.x 自动 HTTPS |

---

## 前置条件

- 一台云服务器：2 vCPU / 4 GB 起，Ubuntu 22.04 LTS
- Docker Engine 28.x + Compose v2（`docker compose version` 能跑通）
- 一个域名并已把 A 记录指向服务器公网 IP（要用 HTTPS 时必需）
- 开放入方向 80 / 443

---

## 部署（对应 SPEC §12 端到端验证）

### 1. 准备配置

```bash
cp .env.example .env
```

至少填写：

| 变量 | 说明 |
|---|---|
| `DOMAIN` | 有域名填域名（如 `play.example.com`）；无域名填 `:80` 走纯 HTTP |
| `ACCESS_PASSWORD` | 访问口令，**合规前置条件**，不可留默认值 |
| `SECRET_KEY` | 令牌签名密钥，`openssl rand -hex 32` 生成 |
| `DB_PASSWORD` | 数据库密码 |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 你要接入的 OpenAI 兼容后端 |
| `IMAGE_BASE_URL` / `IMAGE_API_KEY` / `IMAGE_MODEL` | 出图后端（BYOK） |

> 走 `:80` 纯 HTTP 调试时，务必同时设 `SESSION_COOKIE_SECURE=false`，否则浏览器不会回传会话 Cookie。

### 2. 起服务

```bash
docker compose up -d
docker compose ps
```

**断言**：`db` 先 healthy -> `api` 启动（自动执行 Alembic 迁移）-> `caddy` 就绪。
整体应在 90 秒内完成（AC-01）。若 `api` 起不来，看它的日志——迁移失败会打印中文原因与排查方向：

```bash
docker compose logs api --tail=80
```

### 3. 健康检查

```bash
curl -s https://<你的域名>/api/v1/system/selfcheck
```

**断言**：HTTP 200，返回
`{"code":0,"data":{"db":"ok","pgvector":"ok","llm":{"reachable":<bool>}}, ...}`。
`llm.reachable` 为 `false` 表示还没配 LLM 或网络不通——不影响本步通过。

### 4. 访问控制（未带令牌必须被挡）

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://<你的域名>/api/v1/cards
```

**断言**：`401`（AC-02）。

### 5. 登录取令牌

```bash
curl -s -c jar.txt -X POST https://<你的域名>/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"<你的 ACCESS_PASSWORD>\"}"
```

**断言**：HTTP 200，且响应头 `Set-Cookie` 含 `HttpOnly` 会话令牌（AC-03）。

连续提交 5 次错误口令会触发限流（HTTP 429），冷却后自动恢复。

### 6. 备份可恢复（建议演练一次）

```bash
docker compose exec db pg_dump -U postgres marionette > /tmp/marionette-$(date +%F).sql
# 恢复演练（先用临时库验证）
docker compose exec -T db createdb -U postgres marionette_restore_test
docker compose exec -T db psql -U postgres -d marionette_restore_test < /tmp/marionette-*.sql
docker compose exec -T db dropdb -U postgres marionette_restore_test
```

---

## 本轮交付范围

本轮交付：**可部署最小闭环** —— `docker compose up -d` 起来 -> 健康检查通过 -> 访问控制生效。

- 已真正实现：`GET /api/v1/system/info`、`GET /api/v1/system/selfcheck`、
  `POST /api/v1/auth/login`、`POST /api/v1/auth/logout`、`GET /api/v1/auth/session`
- 其余端点已按 `docs/spec/openapi.yaml` 建出路由并挂上鉴权依赖，统一返回 **501**
  （路径 / 方法 / 参数 / 响应 schema 已对齐，业务逻辑留待下一轮）。

下一轮：世界书引擎、会话状态机、记忆摘要、上下文组装、出图钩子。

---

## 目录结构

```
.
├── docker-compose.yml        # caddy + api + db
├── deploy/Caddyfile          # 反代 + 自动 HTTPS + SSE 免缓冲
├── .env.example              # 环境变量样例（逐项中文注释）
├── no-push 说明：.env 不入 git
├── backend/                  # FastAPI 应用（分层：api -> services -> adapters -> models）
└── frontend/                 # React SPA（由 api 容器多阶段构建后托管）
```

> **构建上下文说明**：`docker-compose.yml` 里 `api.build.context` 是**仓库根目录**，
> `dockerfile` 指向 `backend/Dockerfile`。因为该 Dockerfile 是多阶段的，
> 第一段要构建 `frontend/`、第二段跑 Python，Docker 无法 COPY 构建上下文之外的目录，
> 所以上下文必须落在仓库根。这是刻意的，不是笔误。

---

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `api` 反复重启，日志报连不上数据库 | `DB_PASSWORD` 与 `db` 服务不一致；或 `db` 未 healthy |
| 浏览器登录后立刻失效 | 走 HTTPS 时 `SESSION_COOKIE_SECURE=true` 正确；若用 `:80` 调试须设 `false` |
| 前端流式输出“憋住”不出字 | 确认经 Caddy 转发（`flush_interval -1`）；不要直连 api 端口并叠加别的代理缓冲 |
| 中文搜不到 | 走 `pg_trgm` GIN + `ILIKE`，属预期方案（见 ADR-005）；确认迁移已 `CREATE EXTENSION pg_trgm` |
| `extension "vector" is not available` | 镜像必须是 `pgvector/pgvector:pg18`，不能用官方 `postgres` 镜像 |
