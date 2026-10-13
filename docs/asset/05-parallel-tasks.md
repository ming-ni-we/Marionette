# 05 · 并行任务拆分与协作守则

> 配套总纲：[`README.md`](./README.md) · 生成日期：2026-10-12
> 目的：让多个任务**同时跑而不互相覆盖**。

---

## 0. 开工前置：先把代码拿到手

> ⚠️ **这一步不做，下面所有编排都是空谈。**
> 并行任务通常在**干净沙箱**里启动，`/workspace` 初始为空，**不会**自动带上本项目代码。
> 因此第一步永远是：看 [`task-GET-CODE.md`](./task-GET-CODE.md) → 取码 → 自检。

```bash
# 权威版本在服务器（不是 GitHub！GitHub 只有 S11 之前的旧快照）
rsync -az --exclude='.env' --exclude='data/' --exclude='backups/' \
      --exclude='.backup-env' --exclude='node_modules/' --exclude='.venv/' \
      ubuntu@101.33.117.223:/opt/marionette/  ./marionette/
```

自检判据（缺任一即说明你拿的是旧版）：`models/world.py`、`services/director.py`、
`services/story_state.py`、`alembic/versions/0002_worlds.py`、`pages/story-runtime.tsx` 全部存在，
且 `find backend/app -name '*.py' | wc -l` ≈ **90**。

> **不要**因为 `find / -name SPEC.md` 全无命中，就断言「本项目没有代码」——
> 在干净沙箱里那个结果必然为空，它**证明不了任何事**。

---

## 1. 可并行的任务分组

```
                     ┌─────────────────────────────┐
                     │  共享契约层（冲突热点，慎改）  │
                     │  api/types/  api/client/     │
                     │  App.tsx     icons.ts        │
                     └──────────┬──────────────────┘
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │ A. 剧情演出页 │  │ B. 会话列表   │  │ C. 运维+推送  │
      │ (S12)        │  │ 集成 (S13)    │  │ (INFRA/GIT)  │
      │              │  │              │  │              │
      │ 独占：        │  │ 独占：        │  │ 不碰仓库代码  │
      │ pages/story- │  │ pages/       │  │ 只操作服务器  │
      │  runtime.tsx │  │  session-    │  │ 与 git       │
      │ components/  │  │  list.tsx    │  │              │
      │  story/*    │  │              │  │              │
      │ hooks/use-   │  │              │  │              │
      │  speakers.ts │  │              │  │              │
      └──────────────┘  └──────────────┘  └──────────────┘
```

**A / B / C 三组可以完全同时开跑。**

---

## 2. 文件占用表

| 文件 | A（S12） | B（S13） | C（运维/推送） |
|---|---|---|---|
| `pages/story-runtime.tsx` | 🟢 新建/独占 | — | — |
| `components/story/*.tsx` | 🟢 新建/独占 | — | — |
| `hooks/use-speakers.ts` | 🟢 新建/独占 | — | — |
| `pages/session-list.tsx` | — | 🟢 独占 | — |
| `App.tsx` | 🔴 **改**（加路由） | 🔴 **改**（加按钮跳转） | — |
| `api/types/session.ts` | 🟡 可能改 | 🟡 可能改 | — |
| `api/client/resources.ts` | 🟡 可能改 | 🟡 可能改 | — |
| `components/icons.ts` | 🟡 可能改 | 🟡 可能改 | — |
| 服务器 `/opt/marionette` | — | — | 🟢 独占 |
| git 仓库 | — | — | 🟢 独占 |

🔴 = 双方都要改，**必冲突**
🟡 = 可能改，**可能冲突**
🟢 = 独占，**安全**

---

## 3. 防冲突三条规则

### 规则 1：改共享文件前先声明

`App.tsx`、`api/types/`、`api/client/`、`components/icons.ts` 是**冲突热点**。改动前先说一句
「我要改 `App.tsx` 加 X 路由」，避免两个任务同时写导致互相覆盖。

**降低冲突的实操技巧**：这些文件都是**追加式**修改（加一个 import、加一个路由行、加一个导出）。
只要双方都**在末尾追加**而非重排，Git 能自动合并。

### 规则 2：把共享改动集中做一次

如果 A 和 B 都需要新图标 / 新类型，**先由一方一次性加完并跑通 `tsc`**，另一方直接复用。
不要各加一份。

### 规则 3：改后端必跑全量测试

任何 `backend/app/services/*` 的改动，提交前必须：

```bash
cd /workspace/marionette/backend && ./.venv/bin/python -m pytest -q
# 基线：402 passed, 44 skipped（共收集 446）—— 本地跑的条数只能涨，不能掉
# ⚠️ 445→446 之外的 skipped 若变化，说明集成测试被漏跑，务必查
```

---

## 4. 领取任务的标准动作

```bash
# ① 读总纲定位
cat /workspace/marionette/docs/asset/README.md

# ② 读任务卡
cat /workspace/marionette/docs/asset/task-<你的任务>.md

# ③ 建立基线（确认接手前是绿的）
cd /workspace/marionette/backend && ./.venv/bin/python -m pytest -q        # 402 passed, 44 skipped
cd /workspace/marionette/frontend && npx tsc --noEmit && npm run verify:sse  # 0 错误 / PASS
node scripts/smoke.mjs                                                       # 16/16 PASS

# ④ 干活

# ⑤ 收官自检（四项）
cd /workspace/marionette/frontend && \
  npx tsc --noEmit && npm run verify:sse && node scripts/smoke.mjs && npm run build
```

---

## 5. 任务完成定义（DoD）

一个任务只有同时满足以下条件才算完成：

- [ ] 功能按任务卡的验收标准实现
- [ ] `tsc --noEmit` 0 错误
- [ ] `npm run verify:sse` PASS（若动过 SSE 相关）
- [ ] `node scripts/smoke.mjs` 全 PASS（**新页面必须加进 `ROUTES`**）
- [ ] `npm run build` 成功
- [ ] 若动过后端：`pytest` ≥ 402 passed（44 skipped）且 `ruff check` 全绿；
      动过 `services/`/`api/` 的还必须**在有 PG 处跑集成测试**（见 02 §1.2）
- [ ] 无 emoji 功能图标、无硬编码色值（`npm run scan:p0`）
- [ ] 更新对应任务卡的状态标记

---

## 6. 交接格式（任务收尾时写）

```markdown
## 交接记录

**任务**：S12 剧情演出页
**状态**：完成 / 部分完成 / 阻塞

**改动的文件**：
- 新增：pages/story-runtime.tsx（xxx 行）
- 修改：App.tsx（+2 行路由）

**验收证据**：
- tsc --noEmit：0 错误
- smoke：18/18 PASS（新增 2 条路由）
- build：成功，index.js xxx kB

**遗留 / 已知问题**：
- xxx

**给下一个任务的注意事项**：
- xxx
```

---

## 7. 当前并行机会（2026-10-12）

| 可立即开跑 | 卡 | 阻塞关系 |
|---|---|---|
| ✅ | `task-S12-story-runtime.md` | 无依赖，**优先级最高**（是 MVP 闭环的最后一环） |
| ✅ | `task-INFRA-ops.md` | 完全独立（服务器侧） |
| ✅ | `task-GIT-push.md` | 完全独立（git 侧） |
| ⚠️ | `task-S13-session-list.md` | 建议等 S12 定下 `/stories/:id` 路由后再做，避免改两次 `App.tsx` |
| ⏸️ | S14 联调部署 | 必须等 S12 + S13 都完成 |

**推荐并行方案**：
- 任务 1 → S12 剧情演出页（主线，最重）
- 任务 2 → 运维待办（备份 cron / HTTPS / 密码 / 清脏数据）
- 任务 3 → Git 推送（把本地提交推上去）

S12 完成后，再开 S13，最后 S14。
