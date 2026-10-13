# 02 · 构建、测试与自检

> 配套总纲：[`README.md`](./README.md) · 生成日期：2026-10-12

---

## 0. 环境准备（沙箱内）

```bash
# 后端：Python 虚拟环境。两个位置任选其一，都已装好依赖：
#   - /workspace/marionette/backend/.venv   ← 随仓库走，推荐（可复现）
#   - /tmp/venv                             ← 沙箱预置（重建沙箱后可能消失）
cd /workspace/marionette/backend
source .venv/bin/activate                 # 或直接用 ./.venv/bin/python

# 前端：依赖已装（node_modules 存在）
cd /workspace/marionette/frontend && ls node_modules >/dev/null && echo "deps OK"
```

> 若两个 venv 都不存在（全新沙箱），重建：
> `cd backend && /usr/bin/python3.12 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"`

---

## 1. 后端

### 1.1 跑测试 ⚠️ 必须在 backend/ 目录

```bash
cd /workspace/marionette/backend
./.venv/bin/python -m pytest -q
```

**基线（无 PG 的沙箱）**：`402 passed, 44 skipped`（共收集 **446** 条）

> ⚠️ **两个数字都要认**：446 是**用例总数**，402 是本地**实际执行**的条数，
> 差的 44 条是集成测试（无 PG 时 skip）。在**有真 PG** 的环境（服务器 / e2e 容器）里，
> 结果是 **`446 passed, 0 skipped`** —— 见 §1.2。
>
> ⚠️ **绝不能在仓库根目录跑**。`conftest.py` 依赖相对路径，在仓库根会报 **22 个 collection error**
> （`ModuleNotFoundError`），看着像代码坏了，其实只是工作目录不对。这是本项目最容易踩的
> 「假故障」之一。

### 1.2 那 44 个 skipped 是什么 —— 别被它骗了

全部是 `tests/integration/` 下的**真实 PostgreSQL 集成测试**，跳过原因统一为：

```
需要真实 PostgreSQL；设 MARIONETTE_INTEGRATION=1 并在 api 容器内运行
```

本地沙箱没有 PG（`Errno 111` 连不上 5432）时自动 skip。

> 🔴 **教训（已经真出过事）**：这批集成测试**长期从未被执行**，
> 因此它们内部**藏着两处写错的断言**（分页信封写成了嵌套 `meta`、校验错误码写成 422），
> 同时还**掩盖了一个线上 500 缺陷**（`create_story_session` 的 `MissingGreenlet`）。
> 本地 `402 passed` 全绿 ≠ 线上没问题。
> **动过 `services/` 或 `api/` 后，必须找有 PG 的环境把这 44 条真跑一遍。** 详见 [`04-pitfalls.md`](./04-pitfalls.md) D8。

**在有真 PG 的环境里跑**（二选一）：

```bash
# A. 服务器上（那里有真实 PG，且代码是权威版）
ssh ubuntu@101.33.117.223 'cd /opt/marionette && docker compose exec api python -m pytest tests/integration -q'

# B. 沙箱内自起一个 PG 容器
docker run -d --name marionette-e2e-db -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=marionette -p 55432:5432 pgvector/pgvector:pg18
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/marionette \
  MARIONETTE_INTEGRATION=1 ./.venv/bin/python -m pytest tests/integration -q
```

> ⚠️ 集成测试会真实读写数据库。`conftest.py` 已内置两道硬守卫（建表后核对
> `current_schema()` 与实建表数，不符则 `pytest.exit(returncode=2)` 中止）。
> 仍建议**先备份再跑**。

### 1.3 Lint

```bash
cd /workspace/marionette/backend
ruff check app/ tests/
# 期望：All checks passed!
```

自动修复导入排序：`ruff check --fix app/ tests/`

### 1.4 测试文件清单（31 个）

| 分组 | 文件 |
|---|---|
| **剧情引擎（本轮新增 8 个）** | `test_story_state.py`(55) / `test_director.py`(52) / `test_action_suggester.py`(44) / `test_opening.py`(39) / `test_story_chat.py`(27) / `test_context_story_segments.py`(25) / `test_world_service.py`(24, sqlite) / `test_llm_complete.py`(7) |
| 运行时 | `test_runtime_chat.py` / `test_runtime_db.py` / `test_runtime_m1.py` / `test_runtime_m2.py` / `test_runtime_m2_api.py` |
| 内容侧 | `test_builtin_content.py` / `test_search.py` / `test_world_info.py` / `test_worldbook_entry_id.py` / `test_st_compat.py` / `test_import_helpers.py` / `test_export_headers.py` |
| 基建 | `test_api_access_control.py` / `test_security.py` / `test_logging_extra_keys.py` / `test_tokens.py` |
| 集成（skip） | `integration/test_content_crud.py` / `test_import_export_api.py` / `test_worldbook_onboarding.py` / **`test_story_api.py`(16)** |

---

## 2. 前端

### 2.1 类型检查

```bash
cd /workspace/marionette/frontend
npx tsc --noEmit          # 期望：0 错误
```

### 2.2 构建

```bash
npm run build             # = tsc --noEmit && vite build
```

**当前产物**：

```
dist/assets/index-*.css      56.55 kB │ gzip 11.52 kB
dist/assets/index-*.js      233.75 kB │ gzip 68.36 kB
dist/assets/vendor-react-*  222.25 kB │ gzip 69.19 kB
dist/assets/vendor-*.js     275.78 kB │ gzip 89.52 kB
```

### 2.3 四项自检（提交前必跑）

```bash
cd /workspace/marionette/frontend
npx tsc --noEmit                    # ① 类型
npm run verify:sse                  # ② SSE 三处白名单同构
node scripts/smoke.mjs              # ③ 16 路由真实挂载
node scripts/verify-icons.mjs       # ④ 图标存在性
```

### 2.4 SSE 契约校验（本项目的关键守卫）

```bash
npm run verify:sse
```

**期望输出**：

```
=== SSE 契约一致性检查 ===
SseEventMap (11):  world_info, start, delta, usage, image, done, error, director, speaker_switch, node, actions
KNOWN_EVENTS (11): 同上
后端 EVT_*  (11):  同上

[结论] PASS —— 双白名单同构，共 11 个事件（含 4 个剧情事件）
```

**为什么需要它**：SSE 事件名分散在三处，漏改任何一处，前端都会在 `dispatchFrame` 里
**静默丢弃事件**（不报错、不告警），表现为「页面卡住」——极难定位。这个脚本把漏改变成
**构建前就能发现的失败**。

脚本会读 `../backend/app/services/chat.py` 提取 `EVT_*` 常量做交叉验证。后端目录不在预期位置时会
打印 warn 并跳过后端比对。

### 2.5 冒烟测试

```bash
node scripts/smoke.mjs
```

原理：用 esbuild 把 `scripts/smoke-entry.tsx` 打成 Node 可加载的 ESM，在 jsdom 里**真实挂载**
`<App />`，逐路由断言「非空白 + 出现引导关键词 + 无未捕获异常」。

所有 `fetch` 被 stub 成 reject → 逼出各页面的离线兜底路径（正好验证 AC-16「空状态不出现空白页」）。

**当前 17 条路由 + 3 个探针全 PASS**。新增页面时记得往 `ROUTES` 数组加一条：

```js
{ path: '/stories/xxx', expect: /剧情|导演|旁白/ },
```

### 2.6 P0 扫描

```bash
npm run scan:p0      # emoji / 硬编码色 / 紫粉渐变 三者均须为 0
```

---

## 3. 一键全量验证（推荐流程）

```bash
# 后端（注意：在 backend/ 目录下跑，用 ./.venv/bin/python）
cd /workspace/marionette/backend && \
  ./.venv/bin/python -m pytest -q && \
  ruff check app/ tests/ && \
# 前端
cd /workspace/marionette/frontend && \
  npx tsc --noEmit && \
  npm run verify:sse && \
  node scripts/smoke.mjs && \
  npm run build
```

**期望全绿**：`402 passed, 44 skipped`（本地）/ ruff All checks passed / tsc 0 错误 /
SSE 11 事件三处同构 PASS / smoke 17+3 PASS / build 成功（`index.js ≈ 263 kB`）。

---

## 4. 常见「假故障」对照表

| 现象 | 真实原因 | 处理 |
|---|---|---|
| 测试报 22 个 collection error | 在仓库根而非 `backend/` 跑 pytest | `cd backend` 再跑 |
| `No module named pytest` | 用了系统 python 而非 venv | 用 `./.venv/bin/python`（或 `/tmp/venv/bin/python`） |
| `No module named aiosqlite` | 依赖没装全（曾是 `pyproject.toml` 漏声明） | `./.venv/bin/pip install -e ".[dev]"` |
| **44 skipped**（不是 42） | 本地无 PG，集成测试正常跳过 | 属预期；**但务必在有 PG 处真跑一遍**，别当没事 |
| `python: command not found` | PATH 未含 python | 直接调 `./.venv/bin/python` |
| 前端 `ERR_MODULE_NOT_FOUND` | 在错误目录跑脚本 | `cd frontend` |

> ⚠️ 表中「44 skipped」这一行是本项目**代价最高**的一条：它曾长期掩盖线上 500。
> 看到 skipped 不要放过，见 §1.2 与 [`04-pitfalls.md`](./04-pitfalls.md) D8。

---

## 5. 依赖安装（如需）

```bash
# 后端
./.venv/bin/pip install <package>          # 或 /tmp/venv/bin/pip install <package>

# 前端
cd /workspace/marionette/frontend && npm install
```

> ⚠️ **Windows 生成的 `package-lock.json` 在 Linux 构建会失败**——lock 不含 Linux 原生可选依赖，
> `npm ci` 会静默漏装（esbuild/rollup 的 `@esbuild/linux-x64`、`@rollup/rollup-linux-x64-gnu`）。
> 容器内解决：`rm -f package-lock.json && npm install`。
