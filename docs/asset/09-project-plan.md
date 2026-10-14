# 09 · 项目计划（唯一权威路线图）

> 配套总纲：[`README.md`](./README.md) · 建立日期：**2026-10-13** · 复核依据：线上实测 + 本地实跑
> 本卡是**接下来要做什么**的唯一权威清单。其他卡提到待办时，以本卡为准。

---

## 0. 一句话现状

**核心功能（S1–S12 剧情引擎）已完成并上线运行**，线上端到端验收通过。
**S13 会话列表、S14 联调部署、GitHub 推送（25 提交）均已完成** —— 用户可用闭环已打通。
**当前新阶段是 S15 玩家体验优化**：导演每轮生成的行动建议**没递到玩家手边**（刷新即丢、点击即直发），
这是当前最大的体验浪费。基础设施的备份已就位，但**没有异地容灾**。

```
已完成 ████████████████░░░░  S1–S14 全部完成（含 GitHub 推送）
       ├─ S1–S12 ✅ 剧情引擎已上线
       ├─ S13    ✅ 会话列表集成
       ├─ S14    ✅ 联调 + 部署 + 验收
       └─ S15    ⬜ 玩家体验优化（新增，7 项）
```

---

## 1. 里程碑总览

| 阶段 | 内容 | 状态 | 阻塞于 |
|---|---|---|---|
| **M1** | 剧情引擎后端 + 前端（S1–S12） | ✅ **已完成并上线** | — |
| **M2** | 会话列表接入剧情（S13） | ✅ **已完成** | — |
| **M3** | 全链路联调 + 回归（S14） | ✅ **已完成** | — |
| **M4** | 代码同步 GitHub | ✅ **已完成（2026-10-14）**，25 提交已推，远端 `main`=`5d989ed` | — |
| **M5** | **玩家体验优化（S15）** | ⬜ **未开始** | — |
| **M6** | **对话配图 · 文生图接入（S16）** | 🟡 **出图链路已跑通**（2026-10-14），待「触发钩子 + 前端展示」 | 火山账户余额（4.0 可用） |
| **M7** | 基础设施加固 | 🟡 部分 | 密钥 / 域名 |

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

## 4.5 🆕 S15 · 玩家体验优化（2026-10-14 新增）

> **依据**：《提线 · Marionette 玩家体验优化方案》（两场 20 轮实玩复盘 + 前端代码逆向）。
> **本节的成本与假设已全部经代码核实**（2026-10-14），与原始报告的估算有出入的地方已标注。

### 4.5.0 一句话诊断（核实后成立）

> **平台最大的浪费不是缺功能，而是"导演系统"的产出只喂给了叙事，没喂给玩家。**

**证据**（报告数据，与代码现状一致）：

| 指标 | 雾隐町 | 木叶·火影 | 说明 |
|---|---|---|---|
| 玩家平均输入 | 76 字 | 103 字 | 必须写「动作+台词+意图」复合长句 |
| AI 平均输出 | 135 字 | 244 字 | AI:玩家 = 5.1:1 / 7.6:1 |
| 复合型输入占比 | 19/20 | 20/20 | 几乎每条都要写 2 个以上意图 |
| 每轮建议 | 3 条 | 3 条 | **服务端每轮都在生成，但玩家看不到** |

### 4.5.1 代码核实结论（关键，决定成本）

| 报告假设 | 代码现实（含证据） | 对成本的影响 |
|---|---|---|
| actions 需新增持久化 | ✅ 确为纯 SSE 瞬态。`action_suggester.py` docstring 明写「不落库」；`chat.py:506-511` 是唯一下发点，无 DB 写入 | 成立 |
| 持久化要改表结构 | ❌ **不必**。`models/session.py:48-61` 已有 6 个 JSONB 字段（`extensions`/`context` 可直接用） | **原估偏高**，纯接线 |
| 前端刷新能恢复建议 | ✅ `use-chat-stream.ts:402-408` 只回填 `cast`；`story-runtime.tsx:99` `suggestions` 初值 `[]` 且从不恢复 | 成立 |
| 有 `/actions` 端点可读缓存 | ⚠️ **该端点每次实时重跑 LLM**（`sessions.py:246-278`），**且前端零调用**（`resources.ts` 无 `getActions`） | **原估偏低**：要么改成读库，要么新增前端调用 |
| tone 四分类需新建 | ❌ **已完整实现**。后端 `action_suggester.py:30` `TONES`；前端 `action-dock.tsx:24-29` `TONE_META` | **原估偏高**，可省 |
| 改 preset 即可调导演 | ⚠️ **仅 `system` 生效且截断 1200 字**；`instruction` 对导演**完全无效**（`director.py:399-400` 只取 `system`）；输出格式/JSON 结构硬编码在 `_DIRECTOR_SYSTEM` | **原估偏低**：格式类改动**必须改代码** |

**另一个关键发现**：芯片 UI 已存在（`components/story/action-dock.tsx`，标题「导演给了几个方向」），
但 `action-dock.tsx:83-86` 的 `pick()` 是 **`onSend(s.label)` —— 点击即直接发送**，不是预填。

### 4.5.2 七项改造（按优先级）

#### S15-1 · 建议动作持久化 + 会话恢复 🔴 P0

| 项 | 内容 |
|---|---|
| **为什么 P0** | 成本最低、收益最大。后端每轮都生成高质量建议，但**刷新即丢**，玩家永远看不到 |
| **后端** | 把每轮 `actions` 写进会话的 JSONB（复用 `extensions`，**不改表结构**）；`GET /sessions/{id}` 或 `/story` 一并返回 |
| **前端** | `setStorySnapshot` 补上 `setSuggestions(...)`（现在只回填 `cast`）；首屏从接口恢复 |
| **注意** | 顺带修 `director` 事件到达时 `setSuggestions([])` 的清空行为（`story-runtime.tsx:241`），勿把恢复的建议又清掉 |
| **验收** | [ ] 重开已有会话，必现 3 条芯片 <br> [ ] 刷新页面建议区不空 <br> [ ] 首轮（仅序幕）也有建议 |

#### S15-2 · 芯片点击改为「预填」而非直发 🔴 P0

| 项 | 内容 |
|---|---|
| **现状** | `action-dock.tsx:83-86` `pick()` 直接 `onSend(s.label)` |
| **改法** | 单击 → 填入输入框（label 预填，hint 作 placeholder）；双击/长按或「⚡」→ 直接发送（保留快捷路径） |
| **验收** | [ ] 单击预填可编辑 <br> [ ] 双击直发 <br> [ ] 探针：三种交互各自断言 |

#### S15-3 · 意图四键输入条 🟡 P1

- 把已有 `tone` 四分类（`observe`/`speak`/`act`/`move`）升级为**输入模式开关**
- 选「发言」→ placeholder 变「你说什么？（一句话就够，语气导演来配）」
- 选「行动」→「你要做什么？（写动词+对象即可，如：查脚印）」
- 提交时 `tone` 作为**结构化字段**随 `input` 发给导演
- **成本订正**：前端 1 天；**但 tone 要真正影响导演，还需 S15-4 配合改代码**（只改 preset 无效）
- **验收**：[ ] 选 tone 后 placeholder 变化 [ ] payload 带 tone [ ] 导演按意图配戏

#### S15-4 · 导演侧「短输入增补」🟡 P1 ⚠️ 成本订正

| 项 | 内容 |
|---|---|
| **报告说** | 「改 prompt 不改代码」 |
| **实际是** | ❌ **不成立**。`instruction` 对导演无效；`system` 被截断至 1200 字且塞在「仅供理解世界」块里，语义上不该承载行为规则 |
| **正确做法** | 在 `director.py` 的 `_DIRECTOR_SYSTEM` **加一条规则**（改代码）：<br>「玩家输入按三层解读：① 有明确动作/台词 → 照演；② 输入过短（<15字）→ 由最近一轮 scene.beat、present 角色与未决张力自动补全合理细节，**不反问、不暂停**；③ 禁止要求玩家复述上一轮环境细节，环境由旁白承担。」 |
| **顺带** | 若要做「输入风格」开关（详细/简短），需在 preset schema 增加可控字段并让 `build_decision_prompt` 读取 |
| **验收** | [ ] 「查脚印」3 字输入也能推进一拍且不反问 <br> [ ] 加单测覆盖短输入判定 |

#### S15-5 · 叙事瘦身 + 消息聚合 🟡 P1

- **聚合渲染**：同一导演拍的 4~6 条消息合并为「演出块」，台词用对话气泡、旁白用衬底（从「日志流」变「漫画格」）
- **导演 prompt 加约束**（同样要改 `_DIRECTOR_SYSTEM`）：单条发言 ≤120 字、每轮台词角色 ≤2 人、旁白 ≤2 段
- **背景**：实测单条最长 564 字、一轮 6 条消息
- **验收**：[ ] 单轮 AI 总输出 ≤400 字 <br> [ ] 台词角色 ≤2 <br> [ ] 聚合块视觉正确（含 reduced-motion）

#### S15-6 · 新手引导三件套 🟢 P2

1. **开场即建议**：会话首轮（序幕之后）强制生成一次 `actions` —— 现在要等玩家先输一轮才有，**冷启动最懵的一步反而没扶手**
2. **卡壳检测**：输入框聚焦 15 秒无输入且无点击 → 轻提示「卡住了？点上面的方向，或按 💡 让导演换个问法」
3. **一键推进**：「继续」按钮（发送固定指令 `.`），导演按 `pending_node` / `beat` 推进下一拍

- **验收**：[ ] 首轮即有建议 <br> [ ] 卡壳提示出现且不打扰 <br> [ ] 「继续」可推进

#### S15-7 · 剧情状态可视化 🟢 P2

- 导演维护着 `flags`/`tension`/`scene.beat`（SSE 里都有），但界面只有一行地点时间
- 加可折叠「剧情状态条」：`当前节拍：灭灯后的僵持 ｜ 张力：卡卡西↔佐助 0.2 ｜ 已获线索：绳结·纸角·第七个`
- **验收**：[ ] flags/tension/beat 可折叠展示 <br> [ ] 刷新后仍可见（**依赖 S15-1 的持久化**）

### 4.5.3 北极星指标

| 指标 | 现状 | 目标 |
|---|---|---|
| 单轮输入字数中位数 | 103 字 | **≤20 字** |
| 首 5 轮流失率 | 未测 | 下降 |
| 建议芯片点击率 | 未测（因 UI 常空） | **≥60%** |

### 4.5.4 落地顺序建议

```
① S15-1 建议持久化（P0）      ← 纯接线，先做，立刻见效
② S15-2 芯片预填（P0）        ← 前端小改，与 ① 同批上线
③ S15-4 短输入增补（P1）      ← 改 _DIRECTOR_SYSTEM，治「必须写很长」的病根
④ S15-3 意图四键（P1）        ← 依赖 ③ 才能真正生效
⑤ S15-5 叙事瘦身（P1）        ← 与 ③ 同属 prompt 层，可合并
⑥ S15-6 / S15-7（P2）         ← 打磨
```

> **报告结论采纳**：优化主轴**不是加新 AI 能力**，而是把导演**已经想好的答案**递到玩家手边。
> ①+②+③ 做完，「必须写很长才能推动」的问题解决八成。
> **但要注意**：③ 必须改代码（报告说的「改 preset」不成立）。

---

## 4.6 🆕 S16 · 对话配图（文生图接入）（2026-10-14 新增）

> **需求**：在剧情对话中「不时插入图片」——不是每轮出图，而是**关键节点自动配一张**。
> **评估结论见** `/workspace/文生图API选型评估.html`（含完整对比表）。

### 4.6.0 先决条件（已核实）

项目**已有完整出图链路**，且架构是厂商无关的：

| 组件 | 位置 | 状态 |
|---|---|---|
| `ImageHook`（任务编排 + 自动归档） | `services/image_hook.py`（319 行） | ✅ 已实现 |
| `CloudImageProvider`（走 OpenAI images 协议） | `adapters/image.py:21-105` | ✅ 已实现 |
| `image_jobs` 表 + `assets` 归档 | 迁移已就位 | ✅ 已实现 |
| SSE `image` 事件 | `chat.py` 已接 | ✅ 已实现 |
| 配置项 | `core/config.py:68-71`（`image_base_url` / `image_api_key` / `image_model`） | ✅ 已实现 |

**关键**：`image_hook.py` 顶部明确「**绝不 import 任何厂商 SDK**」，只依赖 `ImageProvider` 接口。
`adapters/image.py:61` 拼的 URL 是 `{base_url}/images/generations` ——
**换平台 = 改两个环境变量，零改代码**。

### 4.6.1 选型结论

| 方案 | 单张价 | 兼容 | 国内直连 | 结论 |
|---|---|---|---|---|
| **火山引擎方舟 · Seedream** | ¥0.22 / ¥0.30 | ✅ 原生 | ✅ | ⭐ **首选（已实测落地）** |
| 阿里云百炼 · 通义万相 / 千问图像 | ≈¥0.25 | ✅ 兼容模式 | ✅ | 次选 |
| Google · Nano Banana 2 / Pro | ¥0.48 / ¥0.97 | ⚠️ 非标准协议 | ❌ | 有域名后再考虑 |
| OpenAI · GPT Image 2.5 | $0.005–0.21 | ✅ 原生 | ❌ | 合规风险，排除 |
| Midjourney V8.2 | 月度订阅 | ❌ 无公开 API | ❌ | 不可用 |

**首选理由**（火山引擎）：
1. 接口 `POST /api/v3/images/generations` 与现有适配器**完全对齐**
2. 国内直连、免备案（服务器 `101.33.117.223` 无域名）
3. 中文提示词强 + **支持最多 10~14 张参考图** → 角色跨图一致性有解

### 4.6.2 接入参数（2026-10-14 实测落定）

```bash
IMAGE_PROVIDER=cloud
IMAGE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
IMAGE_API_KEY=<你的 ARK_API_KEY>
IMAGE_MODEL=doubao-seedream-4-0-20260415
# IMAGE_MODEL=doubao-seedream-5-0-pro-260628   # 质量更好，但需账户有余额/额度
```

**账号 `2132988262` 的 Seedream 实测状态**（2026-10-14）：

| 模型 ID | 开通状态 | 出图实测 |
|---|---|---|
| `doubao-seedream-4-0-20260415` | ✅ 已开通 | ✅ **成功**（免费额度尚存） |
| `doubao-seedream-5-0-pro-260628` | ✅ 已开通 | ⚠️ 曾被 `AccountOverdueError` 拦截 |
| `doubao-seedream-5-0-flash-260915` | ❌ 未开通 | ❌ `ModelNotOpen` |
| `doubao-seedream-5-0-lite-260128` | ❌ 不在可用列表 | — |
| `doubao-seedream-5-0-260128` / `4-5-251128` / `4-0-250828` | Retiring（下架中） | — |
| `doubao-seedream-3-0-t2i-250415` | Shutdown | — |

**协议验证结论（全部通过，零改代码即可用）**：

| 项 | 结果 |
|---|---|
| `size: "1024x1024"` | ✅ 直接接受（项目默认值，无需改） |
| `size: "2K"` / `"2048x2048"` | ✅ 也接受 |
| `response_format: "b64_json"` / `"url"` | ✅ 两者都支持 |
| 接口路径 | ✅ `/api/v3/images/generations` 与适配器拼接规则一致 |

### 4.6.2b 实测踩到的三个坑（已在代码中修复）

**坑 1 · `ModelNotOpen` ≠ 没充钱**
```
{"error":{"code":"ModelNotOpen","message":"...has not activated the model ... Please activate the model service in the Ark Console."}}
```
火山方舟的每个模型都要在控制台「**开通管理**」里**逐个手动开通**，与账户余额无关。
未开通时连免费额度都用不了，直接在网关被拦。

**坑 2 · `AccountOverdueError` 是账户级拦截，但按额度粒度放行**
```
{"error":{"code":"AccountOverdueError","message":"The request failed because your account has an overdue balance."}}
```
**同一个 Key、同一个容器、同一份代码**下：免费额度耗尽的模型（5.0-pro）返回 403，
而仍有额度的模型（4.0）**正常出图**。→ 排查出图失败时，**必须分模型实测**，
不能用「某模型失败」推断「配置错了」。

**坑 3 · 默认水印 + MIME 标错（代码缺陷，已修）**

| 缺陷 | 位置 | 现象 | 修法 |
|---|---|---|---|
| 水印未关闭 | `adapters/image.py` 请求体 | 图右下角有「AI 生成」角标 | 显式加 `"watermark": False` |
| MIME 硬编码 PNG | `adapters/image.py:103` | 火山回 **JPEG**，却被标成 `image/png`、存成 `.png` 后缀 | 按字节流嗅探（JPEG/PNG/GIF/WebP） |

**回归守卫**：`backend/tests/test_image_adapter.py`（13 条，含 `test_jpeg_does_not_get_png_label` 点名守卫）。

### 4.6.3 出图触发时机（核心设计，2026-10-14 定稿）

> **决策已定**：触发策略 = **节点 + 新角色**；提示词 = **额外调一次 LLM 扩写**；
> 本轮交付 = **后端触发 + 单测**（前端展示下一轮）。

#### 4.6.3.1 为什么不能「每轮出图」

| 方案 | 一局 20 轮成本 | 体验 |
|---|---|---|
| 每轮出图 | 20 × ¥0.30 = **¥6.0** | 打断阅读节奏，且多数图无信息量 |
| **本设计（节点+新角色）** | 约 3 张 = **¥0.9** | 只在「值得画」的时刻配图 |

#### 4.6.3.2 触发信号源（全部是现成的，无需新计算）

| 信号 | 代码位置 | 说明 |
|---|---|---|
| `decision.node_triggered` | `director.py:106`（`DirectorDecision`） | 导演判定的剧情节点，**最强信号** |
| `story.cast` | `story_state.py:105` `get_cast()` | 角色表，长度变化 = 新角色加入 |
| `story.triggered_entries` | `story_state.py` | 已触发过的节点 id（用于「同一节点不重复出图」） |
| `scene.present` | `story_state.py:137` | 在场角色 |
| `scene.location` / `beat` | `story_state.py:125` | 提示词素材 |
| `assistant_rows[-1].id` | `chat.py:501` | 出图关联的消息 id（归档用） |

#### 4.6.3.3 触发规则（优先级从高到低）

```
① 节点触发（node_triggered 非空）
   → 必出图。这是「剧情转折点」，最值得配图。
   → 去重：同一 node_id 只出一次（记在 story.image_nodes）

② 新角色首次登场（cast 长度增加，或首次成为 speaker）
   → 出图。用于建立「这个人长什么样」的视觉锚点。
   → 去重：每个角色 id 只出一次（记在 story.image_cast）

③ 玩家手动请求（overrides.image）
   → 出图。保留现有行为不变（优先级最高，可直接覆盖开关）

④ 其余情况
   → 不出图。
```

#### 4.6.3.4 节流与配额（防跑飞）

| 机制 | 值 | 理由 |
|---|---|---|
| **每局总配额** | 8 张 | 20 轮最多 8 张，硬性成本上限 ¥2.4 |
| **最小间隔** | 2 轮 | 防止「刚画完又画」的重复感 |
| **单轮最多** | 1 张 | 一轮多张既贵又乱 |
| **配置开关** | `story_image_enabled` | 默认 `false`，**需显式开启**（避免默默烧钱） |

> ⚠️ **默认关闭**是刻意的：出图是**花钱**的功能，
> 不能让「用户没开过但每轮都在扣费」发生。开启方式：设置页开关 或 `.env`。

#### 4.6.3.5 提示词构造（调一次 LLM 扩写）

**输入**（复用 `action_suggester` 的低 token 模式）：

```
场景：location / time / mood / beat
在场角色：name + voice（形象描述）
本轮已发生：speaker 台词摘要（最近 3 条）
触发原因：节点标题 / 「新角色登场」
```

**输出契约**（严格 JSON，便于解析失败时降级）：

```json
{
  "prompt": "中文画面描述，60-120 字",
  "negative_prompt": "不要出现的元素",
  "aspect": "landscape|portrait|square"
}
```

**提示词设计要点**（写进 `_IMAGE_PROMPT_SYSTEM`）：
- 描述**画面**而非**情节**（「雨夜的青石板巷，灯笼在风里晃」而非「他走进巷子」）
- 中文提示词，但**不出现角色名**（模型不认识「沈砚」）→ 用外观特征代替
- 固定画风关键词，保证一局内视觉一致（如「写实电影感、冷色调、胶片颗粒」）
- 禁止文字/水印类元素（避免模型在画面里写字）

**降级**：LLM 扩写失败 → 用**模板拼接**兜底（`scene.location + beat + mood`），
保证「不出图」永远不会因为扩写失败而发生（只降质量，不降可用性）。

#### 4.6.3.6 失败处理

| 失败点 | 处理 | 依据 |
|---|---|---|
| LLM 扩写失败 | 退回模板拼接 | 与 `action_suggester` 同策略 |
| 出图 API 失败 | 记 warning，**不发 image 事件**，对话正常 done | `chat.py:808-810` 已有此设计 |
| 配额耗尽 | 静默跳过 | 不报错，不打断 |

> **铁律**：出图是**锦上添花**。任何环节失败都不能影响对话主流 —— 这条已在
> `_maybe_image_events` 里实现（`except Exception → warning → return`），新逻辑必须沿用。

#### 4.6.3.7 实现位置

| 新增/改动 | 文件 | 说明 |
|---|---|---|
| **新增** `services/image_trigger.py` | 新文件 | 纯函数 `decide_image()` + `build_image_prompt()` + `ImageTriggerSvc` |
| 改动 | `services/chat.py:496-504` | 把 `overrides.image` 判定换成 `trigger.should_generate()` |
| 改动 | `core/config.py` | 加 `story_image_enabled` / `story_image_quota` / `story_image_min_gap` |
| 改动 | `services/story_state.py` | `story` 加 `image_nodes` / `image_cast` / `image_count` / `last_image_turn` |
| **新增** `tests/test_image_trigger.py` | 新文件 | 覆盖全部触发规则 + 去重 + 节流 + 降级 |

**分层铁律**：`image_trigger.py` 只依赖 `LLMRouter` 与纯数据，
**绝不 import 出图 SDK**（沿用 `image_hook.py` 的架构约束）。

#### 4.6.3.8 成本复核

| 项 | 单价 | 一局用量 | 小计 |
|---|---|---|---|
| 出图 | ¥0.30 | ≤ 8 张 | ≤ ¥2.4 |
| 扩写 LLM | ≈¥0.002 | ≤ 8 次 | ≤ ¥0.02 |
| **合计** | | | **≤ ¥2.42 / 局** |

对比：一局 20 轮的 LLM 对话成本本身远高于此 —— **出图不是成本瓶颈**。

### 4.6.4 实施步骤

| 步骤 | 内容 | 状态 |
|---|---|---|
| 1 | 开通火山方舟账号，拿 API Key | ✅ 已完成 |
| 2 | 控制台开通 Seedream 模型服务 | ✅ **已完成**（充值后三个模型全部可用） |
| 3 | 配置 3 个 `IMAGE_*` 变量 | ✅ 已完成 |
| 4 | **端到端跑通出图 → 归档 → 取回** | ✅ **已完成（2026-10-14）** |
| 5 | 修复水印 + MIME 两处缺陷 | ✅ 已完成（含 13 条回归守卫） |
| 6 | **触发时机设计定稿** | ✅ **已完成（见 §4.6.3）** |
| 7 | 实现 `image_trigger.py` + 接入 `chat.py` + 单测 | ✅ **已完成（2026-10-14，520 行 + 39 条单测，全量 458 passed）** |
| 8 | 前端图片展示（插入消息流） | ⬜ 未开始 |
| 9 | 角色一致性：用参考图固定角色长相 | ⬜ 未开始 |

**验收标准**：
- [x] 手动出图能拿到图并归档（`asset_id` 非空）—— 已实测
- [x] 出图失败不阻塞对话主流 —— `image_hook` + `_maybe_image_events` 已有此设计
- [x] 节点触发时自动出图，SSE 有 `image` 事件 —— 单测覆盖 `REASON_NODE`
- [x] 新角色登场自动出图，且同一角色不重复 —— 单测覆盖 `REASON_CAST` + `image_cast` 去重
- [x] 配额 / 最小间隔 / 开关 三项节流生效 —— 单测覆盖三种 `SKIP_*`
- [x] LLM 扩写失败时能退回模板拼接 —— `render_prompt` 返回 `source="template"`，单测覆盖
- [ ] 同一角色跨 3 张图长相一致（步骤 9）
- [ ] 真实剧情会话端到端触发验证（下一步）

**卡**：`/workspace/文生图API选型评估.html`（完整对比）

---

## 5. 执行顺序

### 5.1 已完成的原计划（S13 → S14 → GitHub）

用户 2026-10-13 拍板：**先做 S13，代码连同 GitHub 推送一起做**。现已全部完成：

```
① S13 会话列表（P0-1）        ✅ 已完成
② 五项校验全绿 + 重新部署 + S14 联调  ✅ 已完成
③ 推 GitHub（P1-1）           ✅ 已完成（2026-10-14，25 提交，远端 main=5d989ed）
```

### 5.2 当前顺序（S15 玩家体验优化）

```
① S15-1 建议持久化 + S15-2 芯片预填   ← 同批做，纯接线 + 前端小改，立刻见效
       ↓
② S15-4 短输入增补（改 _DIRECTOR_SYSTEM）  ← 治「必须写很长」的病根
       ↓
③ S15-3 意图四键 + S15-5 叙事瘦身      ← 同属 prompt 层，依赖 ②
       ↓
④ S15-6 新手三件套 + S15-7 状态条      ← 打磨
       ↓
⑤ S16 对话配图（文生图接入）           ← ✅ 出图链路已实测跑通，剩「触发钩子」
       ↓
⑥ 异地备份 COS（P1-2）                 ← 需你提供密钥
       ↓
⑦ 域名 + HTTPS（P1-3）                 ← 需你买域名
       ↓
⑧ P2 加固与清理
```

> 💡 **S16 可提前**：它与 S15 无依赖，且**改动极小**（配置 + 一个触发钩子）。
> 如果想要「先看到效果」，S16 是见效最快的一项。
> **2026-10-14 更新**：出图链路（配置 → 出图 → 服务端自动归档 → 取回）**已端到端实测跑通**，
> 零改代码接入成功。顺带修复了适配器的两个真实缺陷（水印未关、MIME 硬编码 PNG）。
> 剩余工作只有「触发时机设计」+ 前端展示，**成本大幅下降**。

> ⚠️ **S15-4 的关键提醒**：报告说「改 preset 就能改导演行为」——**代码核实为不成立**。
> 导演 prompt 的 `instruction` 字段从未被使用，`system` 又被截断到 1200 字且定位是
> 「仅供理解世界」。**行为规则必须写进 `director.py` 的 `_DIRECTOR_SYSTEM`**。
> 这项是治本的一步，别按「改配置」估工时。

---

## 6. 需要你提供的（外部依赖）

| 需要什么 | 用来做什么 | 阻塞哪项 |
|---|---|---|
| ~~GitHub PAT~~ | ~~推送代码到 GitHub~~ | ✅ **已提供并完成推送** |
| **腾讯云 COS 密钥**（SecretId / SecretKey / Bucket） | 异地备份 | P1-2 |
| **域名** | HTTPS + 安全 Cookie | P1-3 |
| **新的 DeepSeek key** | 替换泄露的 key | P2-1 |
| （可选）服务器 SSH 公钥 | 改用密钥登录 | P2-2 |

---

## 7. 诚实标注：未验证 / 不确定的

- **S15 的收益数字未验证**：「输入字数 103 → ≤20」是**目标**，非实测；芯片点击率、流失率均**未埋点**。
  建议 S15-1 上线时顺带加最简埋点，否则无法验证北极星指标。
- **`snapshot.scene.present` 语义**：我按「在场角色」使用；若后端意指「本回合说话者」，联调时需对齐。
- **`/actions` 端点的定位**：目前是「实时重跑 LLM 的兜底」，前端零调用。
  S15-1 落地后需决定它的去留（改造成读缓存 / 直接废弃），否则会留下两套语义。
- **COS 上传通道**：脚本已写好，但**从未用真实密钥跑通过**（只用假密钥测过失败路径）。
- **备份 cron 长期稳定性**：只验证了单次触发，未观察多日连续运行。
