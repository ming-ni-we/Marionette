# 08 · 发布纪律：代码同步到 GitHub

> 配套总纲：[`README.md`](./README.md)
> 适用：**所有**改动本项目的任务。
> 一句话：**一个功能阶段做完 + 五项校验全绿 → 立刻同步到 GitHub。**

---

## 1. 为什么要有这条纪律

本项目踩过一次代价很真实的坑：

> 有任务在干净沙箱里开工，用 `git clone` 拿代码，结果**拿不到剧情引擎**
> （`models/world.py`、`services/director.py`、`story-runtime.tsx` 全都不存在），
> 于是得出「本项目没有代码」的错误结论，白白浪费一个任务。

根因就是 **GitHub 停在 `c9f6da5`（S11 之前）**，而 S1–S12 只存在于服务器。
**代码不同步，下一个接手的人就会重踩。** 这条纪律就是为此而立。

---

## 2. 触发时机：一个功能阶段一次

不要每改一行就推，也不要攒一整个月。**按「功能阶段」推**：

| 该推 | 不该推 |
|---|---|
| ✅ 一个 S 阶段（如 S13 会话列表）做完并通过验收 | ❌ 改到一半、编译都不过的中间状态 |
| ✅ 一次线上缺陷修复 | ❌ 纯本地试验性改动（随时可能丢弃的） |
| ✅ 一次部署完成后（代码即线上版本） | ❌ 只改了注释/格式化且无其他变化 |

**判断标准**：*"现在把代码交给另一个人，他能直接开工吗？"* —— 能，就推。

---

## 3. 怎么推：一条命令

```bash
cd /workspace/marionette
export GITHUB_TOKEN=ghp_xxxxxxxx        # 见第 4 节，只需设一次
./scripts/push-to-github.sh "feat(story): S13 会话列表集成"
```

脚本会按顺序做四件事，**任一步失败即中止**：

| 步 | 动作 | 失败后果 |
|---|---|---|
| 1 | 把 `/workspace/marionette` 同步进 git 仓库（排除 `.env`/`data/`/依赖） | 中止 |
| 1.5 | **敏感文件防线**：检查将要提交的文件里有无 `.env` / 私钥 | 中止并撤销暂存 |
| 2 | **五项校验**：pytest / ruff / tsc / verify:sse / smoke | 中止，**不产生提交** |
| 3 | 提交 | 中止 |
| 4 | 推送 + 远端 SHA 核对 | 报告失败原因 |

### 其他模式

```bash
./scripts/push-to-github.sh --check-only          # 只跑校验，不同步不推（改完先自检）
./scripts/push-to-github.sh --dry-run "msg"       # 跑完整流程但试推，不真正写入远端
./scripts/push-to-github.sh --skip-verify "msg"   # 跳过校验（应急，不推荐）
```

> **`--check-only` 是改完代码后的第一件事**。它 30 秒内告诉你是否达到可推标准，
> 不动仓库、不动远端。

---

## 4. 凭据：怎么配 GITHUB_TOKEN

沙箱内**没有** GitHub 写凭据（实测 `git push` → `could not read Username`）。
需要你提供 Personal Access Token：

1. 打开 https://github.com/settings/tokens?type=beta （fine-grained token）
2. **Repository access**：Only select repositories → `ming-ni-we/Marionette`
3. **Permissions** → Repository permissions → **Contents: Read and write**
4. 生成后设置环境变量：

```bash
export GITHUB_TOKEN=github_pat_xxxxxxxx
# 建议写进 shell profile，省得每次重设
```

> 🔴 **安全**：Token 等价于仓库写权限。
> - 优先用**细粒度** token 且**限定单仓库**
> - 传过对话的 token，**用完立即吊销**
> - 绝不把 token 写进任何入库文件

---

## 5. 「全绿」的标准是什么

脚本会逐项跑，**五项全过**才提交：

| 校验 | 命令 | 期望 |
|---|---|---|
| 后端测试 | `cd backend && ./.venv/bin/python -m pytest -q` | `402 passed, 44 skipped` |
| 后端 lint | `cd backend && ruff check app/ tests/` | All checks passed |
| 前端类型 | `cd frontend && npx tsc --noEmit` | 0 错误 |
| SSE 契约 | `cd frontend && npm run verify:sse` | 三处白名单同构 |
| 前端冒烟 | `cd frontend && node scripts/smoke.mjs` | 全 PASS，0 未捕获异常 |

> ⚠️ **那 44 个 skipped 别放过**：它们是集成测试，无 PG 时跳过。
> 若动过 `services/` 或 `api/`，**推之前必须在有 PG 的环境补跑一遍**（见 `02-build-and-test.md` §1.2）。
> 历史上这批测试长期没跑，藏了两个错断言 + 掩盖了一个线上 500。

---

## 6. 推送之后

```bash
# 脚本会自动核对远端 SHA；也可手动确认
git -C /workspace/marionette-git ls-remote origin refs/heads/main
```

推送成功后，**GitHub 就成为可靠的取码来源**，可以顺带做两件事：

1. 更新 [`task-GET-CODE.md`](./task-GET-CODE.md) §2 的表格：把 GitHub 从「旧版」改为「已同步」
2. 在 [`tasks.json`](./tasks.json) 里把 `GIT` 任务标记完成

> 这样下一个任务直接 `git clone` 即可，**不再需要服务器凭据**。

---

## 7. 与部署的关系

**代码同步 ≠ 线上更新。** 两条独立通道：

| | 同步 GitHub | 部署到线上 |
|---|---|---|
| 命令 | `push-to-github.sh` | `rsync` + `docker compose build/up` |
| 目的 | 备份代码、供协作取码、留版本历史 | 让用户用上新版 |
| 见 | 本卡 | [`03-deployment.md`](./03-deployment.md) |

**推荐顺序**：先在本地全绿 → 部署上线并验收 → **再推 GitHub**（这样 GitHub 上永远是"已验证版本"）。

---

## 8. 交接记录

**状态**：已建立（2026-10-13）。

**当前进度**：

| 项 | 状态 |
|---|---|
| `scripts/push-to-github.sh` | ✅ 已写好并通过故障注入测试 |
| S1–S12 同步进 git 仓库 | ✅ 已提交 `df97c19`（90 个 backend `.py`） |
| 五项校验 | ✅ 全绿（402 passed / ruff / tsc / SSE / smoke） |
| 推送凭据 | ⏳ **待提供 GITHUB_TOKEN** |
| 实际推送 | ⏳ 待凭据到位后一条命令完成 |

**下一步**：拿到 token 后执行

```bash
cd /workspace/marionette && export GITHUB_TOKEN=<token> \
  && ./scripts/push-to-github.sh --dry-run "feat(story): S1–S12"   # 先试推确认权限
```

试推通过即去掉 `--dry-run` 正式推送。
