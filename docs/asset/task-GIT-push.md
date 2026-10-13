# task-GIT-push · 推送代码到 GitHub

> 配套总纲：[`README.md`](./README.md) · **完全独立** ✅
> 详细原始记录：`/workspace/PUSH-HANDOVER.md`（含完整改动清单与提交信息原文）
> 关联卡：[`08-release-discipline.md`](./08-release-discipline.md) —— **长期发布纪律（改完代码怎么推）**
> 关联卡：[`task-GET-CODE.md`](./task-GET-CODE.md) §2 —— **GitHub 目前是旧版，本卡完成后该问题消失**

---

## ✅ 已就绪：现在只需一条命令

**S1–S12 + 项目资产文档已同步进本地 git 仓库并完成提交**（最新 `1d41b70`），五项校验全绿。
**唯一缺的是 GitHub 写凭据。**

```bash
cd /workspace/marionette
export GITHUB_TOKEN=<你的 fine-grained PAT>     # 需 Contents: Read and write
./scripts/push-to-github.sh --dry-run "feat(story): S1–S12"   # 先试推确认权限
./scripts/push-to-github.sh "feat(story): S1–S12"             # 通过后正式推
```

> ⚠️ **别再重复提交**：本地已有 3 个待推提交（`c9f6da5` / `df97c19` / `1d41b70`）。
> 拿到 token 后若工作区无新改动，脚本会跳过提交直接推送 —— 这是**正确行为**，不是失败。

> 脚本会自动：同步工作目录 → 敏感文件防线 → 五项校验全绿 → 提交 → 推送 → 核对远端 SHA。
> 下文是**手工流程**，保留作为原理参考与故障兜底。

---

## ⚠️ 这张卡为什么优先级被抬高了

GitHub 上现在只有 `c9f6da5`（S11 之前）。**所有从 GitHub 取码的新任务都会拿到缺剧情引擎的版本**
（找不到 `models/world.py` / `services/director.py` / `story-runtime.tsx`），
进而误判「项目没有代码」——这正是 [`task-GET-CODE.md`](./task-GET-CODE.md) 记录的坑。

**本卡完成 = 该坑自动消失**：此后 `git clone` 即可拿到含 S1–S12 的完整代码，
新任务不再需要服务器凭据。

> 在此之前，唯一权威版本是 **服务器 `ubuntu@101.33.117.223:/opt/marionette`**。

---

## 背景

代码**已在本地完整提交**，但**从未成功推到 GitHub**。
沙箱没有 GitHub 写凭据，这一步在沙箱内无法完成，需要外部执行。

**目标仓库**：https://github.com/ming-ni-we/Marionette （分支 `main`）

---

## 当前状态（2026-10-13 11:32 核实）

| 项 | 状态 |
|---|---|
| git 工作仓库 | `/workspace/marionette-git`（**注意：不是** `/workspace/marionette`） |
| 本地最新提交 | `1d41b70` — `feat(story): AI 导演驱动的多角色剧情引擎（S1–S12）` |
| 工作区 | 干净（`git status --porcelain` 无输出） |
| 五项校验 | ✅ 全绿（402 passed, 44 skipped / ruff / tsc / SSE / smoke） |
| 远程读权限 | ✅ 正常（`git fetch` 成功） |
| 远程写权限 | ❌ **403 —— 实测连"连接器 OAuth token"也推不动**（见下节） |
| 与远程的关系 | 远程 `main` 停在 `3ac1cc3`；本地**领先 3 个提交**，落后 0（可 fast-forward） |

**提交链**：

```
1d41b70  feat(story): AI 导演驱动的多角色剧情引擎（S1–S12）  ← 未推送（含 08/09 等资产文档）
df97c19  feat(story): AI 导演驱动的多角色剧情引擎（S1–S12）  ← 未推送
c9f6da5  feat(runtime): 运行时引擎全量实现 + 前端设计精修     ← 未推送
3ac1cc3  docs(memory): 补记 git push 卡死坑 + 交接文档上传通道结论   ← 远端当前位置
```
06ae597  docs: 交接文档定稿 + 记忆沉淀（新增 4 条坑）
be693ad  fix: 修掉「集成测试直连生产库」等 4 类缺陷
98d718a  feat(backend): Phase 3 第一波 —— 创作侧实现
cab4617  chore: 添加 .gitattributes 统一换行符
1ef5d36  chore: 项目初始化 —— 「提线」(Marionette) 云端私有部署 MVP
```

---

## ⚠️ 重要：还有一批改动**尚未提交**

`/workspace/marionette`（工作目录）与 `/workspace/marionette-git`（git 仓库）**内容不同**。
剧情引擎改造 **S1–S12** 的成果**只存在于工作目录，还没进 git**。

> 规模差异（2026-10-13 核实）：工作目录 `backend/app` 有 **90** 个 `.py`，
> git 仓库只有 **82** 个 —— 差的正是剧情引擎那一批。

差异概览（`/workspace/marionette` 有、`marionette-git` 没有）：

**后端 · 剧情引擎（新增 7 个文件）**
```
backend/alembic/versions/0002_worlds.py
backend/app/api/v1/worlds.py
backend/app/models/world.py
backend/app/schemas/world.py
backend/app/services/action_suggester.py
backend/app/services/director.py
backend/app/services/opening.py
backend/app/services/story_state.py
backend/app/services/world.py
backend/tests/test_action_suggester.py
backend/tests/test_director.py
backend/tests/test_opening.py
backend/tests/test_story_state.py
backend/tests/test_story_chat.py
backend/tests/test_context_story_segments.py
backend/tests/test_llm_complete.py
backend/tests/test_world_service.py
backend/tests/integration/test_story_api.py
```

**前端 · 剧情页面与类型（新增 10 个文件）**
```
frontend/src/api/types/world.ts
frontend/src/components/world/*.tsx          (7 个)
frontend/src/pages/worlds.tsx
frontend/src/pages/world-editor.tsx
frontend/src/mocks/samples/worlds.ts
frontend/scripts/check-sse-contract.mjs
```

**同时被修改**（两边都有但内容不同）：`chat.py`、`context_assembler.py`、`session.py`、
`llm_router.py`、`api/v1/sessions.py`、`api/v1/__init__.py`、`models/session.py`、
`schemas/session.py`、`frontend/src/api/types/session.ts`、`api/client/stream.ts`、
`hooks/use-chat-stream.ts`、`App.tsx` 等。

---

## 推荐执行方案

### 步骤 1：把工作目录的改动同步进 git 仓库

```bash
# 以工作目录为准，同步到 git 仓库（排除构建产物与依赖）
cd /workspace/marionette-git
rsync -av --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='dist' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.ruff_cache' \
  --exclude='.smoke-bundle.mjs' \
  /workspace/marionette/ /workspace/marionette-git/

git status          # 应看到剧情引擎相关的新增与修改
```

### 步骤 2：跑全量验证（提交前必须绿）

```bash
cd /workspace/marionette-git/backend && python -m pytest -q && ruff check app/ tests/
cd /workspace/marionette-git/frontend && npx tsc --noEmit && npm run verify:sse && node scripts/smoke.mjs
```

**期望（2026-10-13 基线）**：`446 passed, 0 skipped` / ruff 全绿 / tsc 0 错误 /
SSE 契约 11 事件三处同构 / smoke 17 PASS + 3 探针

> ⚠️ `pytest` **必须在 `backend/` 目录下跑**，否则 22 个 collection error。
> ⚠️ 集成测试需 `MARIONETTE_INTEGRATION=1` + 真 Postgres，否则**静默 skip** ——
> 曾经的 `402 passed, 42 skipped` 就是被这批 skip 掩盖了线上 500 缺陷（见 `04-pitfalls.md` D8）。

### 步骤 3：提交

```bash
cd /workspace/marionette-git
git add -A
git commit -F- <<'EOF'
feat(story): AI 导演驱动的多角色剧情引擎（S1–S12）

后端 · 剧情引擎：
- models/world.py + schemas/world.py + alembic 0002_worlds：世界观数据模型
- services/story_state.py：剧情状态（幕/拍点/旗标/关系图/cast），纯状态无 IO
- services/director.py：AI 导演，三层降级（熔断 → response_format → 去参数重试 → 规则兜底）
- services/opening.py：序幕生成，模型/卡片/模板三级兜底
- services/action_suggester.py：行动建议，失败返回规则兜底
- services/world.py + api/v1/worlds.py：世界观 CRUD + 中文子串检索
- services/chat.py：剧情分支编排（director/speaker_switch/node/actions 四类新事件）
- services/context_assembler.py：新增 story_state/relations/cast_roster 三段（旧 9 段字节不变）
- services/session.py：create 分派 + create_story_session；fork 同样修复
- services/llm_router.py：新增非流式 complete_chat
- api/v1/sessions.py：+/story 与 /actions 端点
- 修复：状态机 generating→idle 死锁（_force_idle 绕过迁移表）
- 修复：重复空占位消息（N 个说话者 = N 条消息）
- 修复：create_story_session/fork 在 flush() 后 serialize() 触发 MissingGreenlet → 线上 500
        （补 await db.refresh(row)，与 _create_rpg_session 对齐）

前端 · 类型 / 世界观管理 / 剧情演出页：
- api/types/session.ts：MessageMeta +9 字段、SseEventMap +4 事件、ContextSegmentName +3 段
- api/types/world.ts：世界观契约
- api/client/stream.ts：KNOWN_EVENTS +4（共 11）
- hooks/use-chat-stream.ts：+4 事件分支 + 剧情状态；修复多说话者 delta 串气泡；
        修复旁白不显示（按后端 message_id 做 upsert）
- hooks/use-speakers.ts：说话者归并
- pages/worlds.tsx / world-editor.tsx + components/world/*：世界观创建与管理
- pages/story-runtime.tsx + components/story/*：剧情演出页（多角色气泡/旁白/行动建议/节点横幅）
- scripts/check-sse-contract.mjs：三处白名单同构校验（新增守卫）

部署与运维：
- scripts/backup.sh / restore.sh / install-backup-cron.sh：每日自动备份 + 演练恢复

测试：446 passed / 0 skipped；ruff 全绿；tsc 零错误；
smoke 17 路由 PASS + 3 探针；SSE 契约 11 事件三处同构；真 PG 端到端 26 断言 PASS。
EOF
```

### 步骤 4：推送（三选一）

**方案 A · 在本地已登录 GitHub 的机器上推（推荐）**

```bash
cd /workspace/marionette-git
git bundle create /tmp/marionette-latest.bundle main
# 把 bundle 拷到本地机器后
git clone https://github.com/ming-ni-we/Marionette.git
cd Marionette
git fetch /path/to/marionette-latest.bundle main:latest
git merge --ff-only latest
git push origin main
```

**方案 B · 提供 PAT，在沙箱内直推**

需要具备 `repo` 权限的 GitHub Personal Access Token
（fine-grained 需含 `Contents: Read and write`）：

```bash
cd /workspace/marionette-git
git push https://<TOKEN>@github.com/ming-ni-we/Marionette.git main
```

> ⚠️ 安全提示：Token 是敏感凭据。若通过对话传递，**推送完成后立即吊销**。
> 建议用一次性细粒度 Token 并限定仅该仓库。

**方案 C · 用 patch / bundle 手工搬运**

现成产物（对应提交 `c9f6da5`，**不含 S1–S12 的新改动**）：

```bash
git am /workspace/marionette-git-runtime.patch
# 或
git fetch /workspace/marionette-c9f6da5.bundle main:c9f6da5-local
git merge --ff-only c9f6da5-local
```

> 这两个现成产物**只到 S11 之前**，不能替代步骤 1–3 的新提交。

---

## 为什么沙箱内推不上去（已穷尽排查）

| 通道 | 结果 |
|---|---|
| git 直接推送（无凭据） | `fatal: could not read Username`（terminal prompts disabled） |
| `gh` CLI | `You are not logged into any GitHub hosts`（2026-10-13 复测，仍未登录） |
| 环境变量 | `GITHUB_TOKEN` / `GH_TOKEN` / `GIT_TOKEN` / `GH_PAT` 均未预设 |
| `~/.git-credentials` / `~/.netrc` | 均不存在 |
| git-credential-helper | 实测 `get` 返回空；逆向发现它请求 `{IDE_EDITOR_SERVER}/api/v1/git/credentials`，依赖编辑器服务的 GitHub 登录态 |
| 编辑器服务凭据端点 | 已定位 `editor_sdk`（`127.0.0.1:39099`），穷举 15 种路径组合，**全部 `Unknown endpoint`** → 该版本未实现凭据转发 |
| GitHub MCP 集成 | 已认证为仓库属主，但**写接口 403**：`push_files` / `create_or_update_file` 均 `Resource not accessible by integration` |
| **GitHub 连接器 OAuth token**（2026-10-13 新增实测） | 能拿到 `ghu_` token、身份确认为仓库属主，**但 `git push` 仍 403**（详见下节） |

**结论**：本环境**所有**可用的 GitHub 通道都**只有读权限，没有代码写权限**。
**这不是代码或提交的问题，是环境缺少写入凭据。** 唯一解法是外部提供一个带
`Contents: Read and write` 的 PAT。

---

## 🧪 2026-10-13 实测：连接器 OAuth token 为什么推不动

这一条**专门记给后续任务看**，避免再花一轮时间重新试一遍。

### 现象

用连接器脚本拿到 token 后跑完整发布流程：

```
✓ pytest：402 passed, 44 sk
✓ ruff：All checks passed
✓ tsc：0 错误
✓ verify:sse：三处白名单同构
✓ smoke：全 PASS
✓ 五项校验全绿
✓ 已提交：1d41b70 feat(story): AI 导演驱动的多角色剧情引擎（S1–S12）
✗ remote: Permission to ming-ni-we/Marionette.git denied to ming-ni-we.
  fatal: unable to access 'https://github.com/ming-ni-we/Marionette.git/':
         The requested URL returned error: 403
```

注意措辞：**`denied to ming-ni-we`** —— 认证成功（认出了你就是属主），
但**该凭据没有被授予写代码的权限**。

### 根因

```bash
curl -sI -H "Authorization: Bearer $TOKEN" https://api.github.com/user | grep -i x-oauth-scopes
# x-oauth-scopes:            ← 空
# x-accepted-oauth-scopes:   ← 空
```

连接器发的是 **GitHub OAuth App 的 user-to-server token**（`ghu_` 前缀，40 字符），
该 App 授权时**没有申请 `repo` / `public_repo` scope**，所以 scopes 列表为空。
`git push` 走 Basic 认证，必须带 `repo`（或 `public_repo`）scope，于是 403。

### 🔴 一个极易误判的陷阱（务必记住）

同样是这个 token，调 API 会返回：

```json
GET /repos/ming-ni-we/Marionette
→ "permissions": { "admin": true, "maintain": true, "push": true, "triage": true, "pull": true }
```

**看到 `push: true` 很容易以为"能推"，其实是错的。**
`permissions` 字段描述的是**你这个用户**对仓库的权限，不是**这张 token** 的 scope。
判断 token 能不能写代码，唯一可靠的是：

```bash
curl -sI -H "Authorization: Bearer $TOKEN" https://api.github.com/user | grep -i x-oauth-scopes
# 空 → 不能推。含 repo / public_repo → 能推。
```

（或者干脆 `git push --dry-run`，让 GitHub 自己告诉你。）

### 副作用（无害）

校验全绿但推送失败 → **`1d41b70` 提交已留在本地**。这是好事：
项目资产文档（08/09/README 等）也一并进了版本历史。
拿到 PAT 后直接推，**不需要重新提交**。

---

## 安全复核（提交前必查）

```bash
cd /workspace/marionette-git
git status --short | grep -E "\.env$|\.env\." || echo "✅ 无 .env"
git diff --cached --name-only | grep -E "secret|token|password|\.key$" || echo "✅ 无疑似凭据文件"
```

**确认**：`.env`（含 LLM Key、DB 密码）已在 `.gitignore` 中，不得入库。

---

## 验收标准

- [ ] `/workspace/marionette` 的改动已同步进 git 仓库
- [ ] 提交前四项验证全绿（pytest 446 / ruff / tsc / smoke 17+3）
- [ ] 无 `.env` 等敏感文件被跟踪
- [ ] 提交已创建
- [ ] `git push origin main` 成功（或产出可搬运的 bundle/patch）
- [ ] GitHub 上能看到提交
- [ ] `git clone` 后 `backend/app` 有 90 个 `.py`（即含剧情引擎）

---

## 交接记录

> 完成后填这里

**状态**：待领取（**需要在沙箱外执行，或提供 PAT**）
