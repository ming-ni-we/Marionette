# task-GET-CODE · 代码在哪、怎么拿到（**新任务开工前必读**）

> 配套总纲：[`README.md`](./README.md)
> 创建原因：2026-10-13 有任务在**干净的沙箱**里开工，因资产未写「代码位置」而全盘搜不到源码，
> 得出「本项目没有代码」的错误结论。本卡专治该问题。

---

## 1. 一句话结论

**代码真实存在且线上在跑，但它不会自动出现在你的沙箱里。**
你必须**先按本卡第 3 节把代码取到本地**，才能做任何开发/联调。

---

## 2. 代码的四个真实位置

| # | 位置 | 内容 | 说明 |
|---|---|---|---|
| 1 | **服务器** `ubuntu@101.33.117.223:/opt/marionette` | **完整、最新、正在运行** | 90 个 `backend/app/*.py`；Docker 三容器 healthy |
| 2 | GitHub `https://github.com/ming-ni-we/Marionette` | ⏳ **正在补齐** | 当前远端停在 `c9f6da5`（S11 之前），**不含 S1–S12**；本地已备好提交 `df97c19`，**只差一次 `git push`**（缺凭据）。见 [`08-release-discipline.md`](./08-release-discipline.md) |
| 3 | 本地工作副本 `/workspace/marionette` | 完整、最新 | **不是 git 仓库**（无 `.git`），是 rsync 出来的工作目录 |
| 4 | 离线包 `/workspace/marionette-c9f6da5.bundle` + `.patch` | 历史快照 | 与 GitHub 同代，同样不含 S1–S12 |

> ⚠️ **最重要的认知**：**GitHub 上的代码目前是旧的。**
> S1–S12（剧情引擎改造）**从未被 git 推送过**，只存在于「服务器 `/opt/marionette`」。
> 所以 `git clone` 拿到的是 S11 之前的版本 —— 拿它去做剧情相关任务会一直找不到文件。
>
> ✅ **正在修复**：S1–S12 已提交进本地 git 仓库（`df97c19`），一旦补充 `GITHUB_TOKEN`
> 并执行 `./scripts/push-to-github.sh`，GitHub 即成为完整可用的取码来源。
> 此后本卡第 2 节的「GitHub 落后」问题即消失，**新任务可优先用 `git clone`**。

---

## 3. 怎么拿到代码（按场景选）

### 场景 A：能 SSH 到服务器（**最可靠，推荐**）

服务器上是**权威版本**，且带生产 `.env` 与 `data/`。凭据见 `docs/HANDOVER.md`。

```bash
# 账号是 ubuntu，不是 root（这一点踩过坑）
ssh ubuntu@101.33.117.223 'ls /opt/marionette'

# 拉到自己沙箱（务必排除密钥与数据）
rsync -az --exclude='.env' --exclude='data/' --exclude='backups/' \
      --exclude='.backup-env' --exclude='node_modules/' --exclude='.venv/' \
      ubuntu@101.33.117.223:/opt/marionette/  ./marionette/
```

> `ubuntu` 用户密码见 `docs/HANDOVER.md`；它属于 `docker` + `sudo` 组且 **sudo 免密**。
> 沙箱内若装了 `sshpass` 可非交互使用：`sshpass -p '<口令>' ssh ubuntu@...`。

### 场景 B：拿不到服务器凭据，但有 GitHub 读权限

```bash
git clone https://github.com/ming-ni-we/Marionette.git
cd Marionette && git log --oneline -1    # 预期 c9f6da5
```

> ⚠️ 这样拿到的是 **S11 之前的版本**。若任务涉及 `worlds` / 剧情引擎 / `story-runtime`，
> 你会找不到 `backend/app/models/world.py`、`services/director.py` 等文件 ——
> **这不是"项目没有代码"，而是"你没拿到最新那版"**。此时必须回到场景 A。

### 场景 C：只想看某一小段代码

不必拉全量。直接在服务器上读：

```bash
ssh ubuntu@101.33.117.223 'cat /opt/marionette/backend/app/services/session.py'
ssh ubuntu@101.33.117.223 'ls /opt/marionette/frontend/src/hooks/'
```

---

## 4. 开工前的自检清单

取到代码后，**逐条确认**，全绿才算就绪：

```bash
cd marionette

# 1) 是不是最新版？（判据：这些 S12 文件必须存在）
ls backend/app/models/world.py \
   backend/app/services/director.py \
   backend/app/services/story_state.py \
   backend/alembic/versions/0002_worlds.py \
   frontend/src/pages/story-runtime.tsx
# 缺任何一个 → 你拿的是旧版（GitHub 快照），回场景 A

# 2) 后端规模自检（最新版约 90 个 py）
find backend/app -name '*.py' | wc -l

# 3) 前端规模自检（最新版约 126 个 ts/tsx）
find frontend/src -name '*.ts' -o -name '*.tsx' | wc -l

# 4) 跑一遍后端测试（必须在 backend/ 目录下跑，否则 22 个 collection error）
cd backend && python -m pytest -q
#   期望：446 passed

# 5) 前端校验
cd ../frontend && npx tsc --noEmit && npm run verify:sse
```

---

## 5. 「联调」需要什么（缺一不可）

做端到端联调（如 M3/S14）时，只有代码是不够的。真实依赖如下：

| 依赖 | 怎么满足 |
|---|---|
| 源码 | 见第 3 节 |
| **PostgreSQL + pgvector** | `docker run -d -p 55432:5432 -e POSTGRES_PASSWORD=... pgvector/pgvector:pg18`，再 `alembic upgrade head` |
| **LLM 后端** | 需要 DeepSeek key（在服务器 `.env` 的 `LLM_API_KEY`）。无 key 时剧情只会走降级文案 |
| 后端服务 | 沙箱内可自起：`uvicorn app.main:app --port 8000`（无需 docker） |
| 前端 dev server | `cd frontend && npm install && npm run dev` |

**若这些依赖一个都没有**，那么正确地判断是：
> 「本环境缺少源码 / DB / LLM，联调无法执行」——
> 而不是「本项目没有代码」。前者是环境问题，后者是事实错误。

---

## 6. 为什么会出现「沙箱里什么都没有」

这类任务通常在**隔离沙箱**里启动：一台全新机器，只挂载 `/workspace`（初始为空）
与 `/root/uploads`（空）。它**不会**自动同步任何项目的代码、数据库或服务。

因此**任何任务的第一个动作**，都应该是：
1. 读本卡，确认代码在哪；
2. 按第 3 节把代码取来；
3. 按第 4 节自检。

**不要**因为 `find / -name SPEC.md` 没命中就断言项目不存在 ——
在一台干净的沙箱里，那个结果**必然为空**，它证明不了任何事。

---

## 7. 交接记录

**状态**：已创建（2026-10-13），用于补齐「代码位置」这一缺失的资产信息。

**相关卡**：
- [`08-release-discipline.md`](./08-release-discipline.md) —— 发布纪律：改完代码怎么同步到 GitHub
- [`task-GIT-push.md`](./task-GIT-push.md) —— 把本地新版推到 GitHub（**已预提交，只差凭据**；完成后本卡第 2 节的"GitHub 落后"问题即消失）
- [`03-deployment.md`](./03-deployment.md) —— 服务器部署细节
- [`02-build-and-test.md`](./02-build-and-test.md) —— 构建与测试怎么跑
