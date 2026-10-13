# task-S12 · 剧情演出页（前端）

> 配套总纲：[`README.md`](./README.md) · 可独立领取 ✅ · 优先级 **最高**
> 前置背景：[`06-story-engine-spec.md`](./06-story-engine-spec.md) §11

---

## 目标

做出玩家实际游玩的剧情页面：**进入一个世界，看到 AI 导演安排的多个角色轮流说话，结束后拿到行动建议**。

这是整个「多角色剧情引擎」改造的**用户可见核心**——S1–S11 的后端与类型工作全部为它铺路。

---

## 交付物

| 文件 | 类型 | 说明 |
|---|---|---|
| `frontend/src/pages/story-runtime.tsx` | 新建 | 页面主体，路由 `/stories/:id` |
| `frontend/src/components/story/action-dock.tsx` | 新建 | 底部行动建议 Dock（选项 + 自由输入） |
| `frontend/src/components/story/opening-card.tsx` | 新建 | 序幕卡片（居中，区别于角色气泡） |
| `frontend/src/components/story/node-banner.tsx` | 新建 | 剧情节点触发横幅 |
| `frontend/src/hooks/use-speakers.ts` | 新建 | 角色头色/头像映射等派生逻辑 |
| `frontend/src/App.tsx` | 修改 | 加路由 `stories/:id` |

> ⚠️ **改 `App.tsx` 前先声明**（见 [`05-parallel-tasks.md`](./05-parallel-tasks.md) §3）。

---

## 关键实现要点

### 1. 复用 `useChatStream`，不要重写流式逻辑

S10 已经把它改造完毕，新增的剧情状态直接可用：

```ts
const chat = useChatStream({ sessionId: id, offline: false });
// chat.speakers       本轮出场角色（来自 director 事件）
// chat.activeSpeaker  当前说话者
// chat.nodes          本轮触发的节点
// chat.suggestions    行动建议
// chat.lastDecision   导演裁决原文（可做「导演在想什么」调试面板）
// chat.messages       全部消息（含 meta.speaker_id / is_narration / beat_role）
```

`delta` 已按 `speaker_id` 精确落到对应气泡（多角色不会串），`done` 已收口所有 streaming 残留。
**这些坑已经填好了，别再自己实现一遍。**

### 2. 三类消息的渲染区分

按 `message.meta` 分派：

| 条件 | 渲染 |
|---|---|
| `meta.is_narration === true` 或 `beat_role === 'narration'` | **旁白**：居中、斜体、无角色头 |
| `beat_role === 'opening'` | **序幕卡片**（`opening-card.tsx`） |
| 其他 assistant | **角色气泡**：左对齐，上方角色头（名字 + 头像占位色） |
| `role === 'user'` | 玩家气泡（右对齐，复用既有配色） |

复用 `components/session/message-bubble.tsx` 的视觉语言，保持与 1v1 一致。

### 3. 多角色消息不应共用「最后一条」假设

一轮里可能连续出现 3 条 assistant 消息（旁白 + 2 个角色）。渲染时**逐条按自己的 meta 渲染**，
不要做「把最后 N 条合成一块」的假设。

### 4. 行动建议 Dock

```tsx
// suggestions: [{id, label, hint, tone}]
// tone ∈ 'observe' | 'speak' | 'act' | 'move'
```

- 每个选项是一个按钮，点击 → `chat.send(suggestion.label)`
- 保留**自由输入框**（用户可自己写）
- `chat.generating` 时禁用
- 无建议时降级为纯输入框（不能出现空的死区）

### 5. 导演透明性面板（差异化亮点）

`chat.lastDecision` 含 `reason` 与 `degraded`：

- 展示「导演为什么这样安排」——这把 AI 的编排从黑盒变成可解释
- `degraded === true` 时明确标注「本轮走了降级链路」，避免用户困惑于质量波动

建议做成可折叠的侧栏或抽屉，默认收起，不干扰沉浸。

### 6. 首屏拉取剧情快照

进入页面时调 `GET /sessions/{id}/story` 拿 `{story, scene, cast, relations}`，
用于：

- 顶部展示当前场景（`scene.location` / `mood`）
- 角色头配色按 `cast` 稳定映射
- 若 `messages` 为空但有序幕消息，正常渲染

拉到后调 `chat.setStorySnapshot(snap)` 回填。

---

## 依赖的既有资产

| 用途 | 现成的东西 |
|---|---|
| 流式状态机 | `hooks/use-chat-stream.ts`（已改造完） |
| 类型 | `api/types/session.ts` 的 `StoryState` / `CastMember` / `Relation` / `ActionSuggestion` / `SseEventMap` |
| 消息渲染参考 | `components/session/message-bubble.tsx` |
| 场景条参考 | `components/session/scene-bar.tsx` |
| 输入框参考 | `components/session/composer.tsx` |
| 上下文检视 | `components/session/context-inspection.tsx` |
| 离线兜底 | `components/common/offline-banner.tsx`（需 children） |
| 演示数据 | `mocks/samples/worlds.ts` 的 `SAMPLE_WORLDS` |
| API | `sessionsApi.get` / `api/types` 的 story 快照 |

---

## 验收标准

- [ ] `/stories/:id` 可渲染，非空白
- [ ] 多角色一轮渲染为**多条独立气泡**，各有角色头
- [ ] 旁白渲染为居中样式，无角色头
- [ ] 行动建议可点击并发出输入
- [ ] 自由输入始终可用
- [ ] `chat.generating` 时输入与建议均禁用
- [ ] 导演 `degraded=true` 有明确标识
- [ ] `tsc --noEmit` 0 错误
- [ ] `node scripts/smoke.mjs` 全 PASS（**须在 `ROUTES` 加一条 `/stories/xxx`**）
- [ ] `npm run verify:sse` PASS
- [ ] `npm run build` 成功
- [ ] 无 emoji 功能图标、无硬编码色值

---

## 需要同步更新

1. **`scripts/smoke.mjs`** 的 `ROUTES` 数组加：
   ```js
   { path: '/stories/s1f0a1e2-0001-4d01-9c01-000000000001', expect: /导演|旁白|行动/ },
   ```

2. **`components/icons.ts`**：如需新图标，先加进注册表，再跑 `npm run verify:icons`。

3. **`App.tsx`** 加路由：
   ```tsx
   <Route path="stories/:id" element={<StoryRuntimePage />} />
   ```

---

## 阻塞项

**无。** 后端（S1–S9）与前端类型（S10）全部就绪，可以立即开工。

唯一注意：后端返回的**真实事件流**只能在连上后端时验证。本地无后端时，
可先用 `mocks/` 造一段剧情事件序列跑通渲染，再在服务器上验证真实链路。

---

## 交接记录

> 完成后填这里（格式见 [`05-parallel-tasks.md`](./05-parallel-tasks.md) §6）

**状态**：✅ 已完成（2026-10-13）

### 交付物（实际）

| 文件 | 类型 | 说明 |
|---|---|---|
| `frontend/src/pages/story-runtime.tsx` | 新建 | 页面主体 `/stories/:id` |
| `frontend/src/components/story/action-dock.tsx` | 新建 | 行动建议 Dock + 自由输入 + 就地错误条 |
| `frontend/src/components/story/opening-card.tsx` | 新建 | 序幕卡片（居中 + 书挡线 + 56ch 窄版心） |
| `frontend/src/components/story/node-banner.tsx` | 新建 | 剧情节点触发横幅 |
| `frontend/src/components/story/director-panel.tsx` | **新建（超出计划）** | 导演透明性抽屉，含 `degraded` 显著告警 |
| `frontend/src/components/story/cast-strip.tsx` | **新建（超出计划）** | 在场角色条（当前说话者高亮） |
| `frontend/src/components/story/story-reading-column.tsx` | **新建（超出计划）** | 四路消息分派渲染 |
| `frontend/src/hooks/use-speakers.ts` | 新建 | 角色色位/首字稳定映射 + `relationBetween` / `tensionLabel` |
| `frontend/src/hooks/use-chat-stream.ts` | **修改（修 2 处真实 bug）** | 见下「发现并修复的真实缺陷」 |
| `frontend/src/api/client/resources.ts` | 修改 | 新增 `sessionsApi.getStory` + `StorySnapshot` import |
| `frontend/src/mocks/stream.ts` | 修改 | 新增 `mockStoryStream`（与后端事件形态同构） |
| `frontend/src/mocks/fixtures.ts` | 修改 | 导出 `mockStoryStream` |
| `frontend/src/App.tsx` | 修改 | 加路由 `stories/:id` |
| `frontend/scripts/smoke-entry.tsx` | 修改 | 新增 `probeStoryRuntime` 回归探针 |
| `frontend/scripts/smoke.mjs` | 修改 | 加 `/stories/xxx` 路由 + 第 3 项探针 |

### ⚠️ 发现并修复的真实缺陷（2 个，均非本任务引入）

这两个都是**离线路径与单角色路径都测不出来**的缺陷——只有「真实后端 + 多角色一轮」才触发。
已加回归探针，验证过「注入回归后探针确实 FAIL」。

#### 缺陷 1：首个说话者的正文被串进旁白气泡（严重）

**根因**：后端对**第一个**说话者**不发** `speaker_switch`（`chat.py` 的 `if index > 0:`），
只发 `delta + speaker_id`。而前端 `appendDelta` 匹配不到 `speaker_id` 时**退回「最后一条 assistant」**——
那条通常是导演的旁白。结果旁白气泡里长出角色台词，该角色没有自己的气泡。

实测污染文本：`雨下了三天。旧城区的墙皮泡得发胀，像随时会掉她没抬头，把账本往阴影里推了半寸。下来一层。`

**修复**：`appendDelta` 在匹配不到 `speaker_id` 时**就地新建气泡**（不再退回最后一条）；
仅 `speaker_id === undefined`（1v1）才走「最后一条」分支。

#### 缺陷 2：旁白在本轮内完全不显示

**根因**：旁白的 `speaker_switch` **带 `message_id`**，前端据此假设「后端已建行 → 本地已有」。
但该行是**本轮**才落库的，而本地 `messages` 是首屏 `GET /sessions/{id}` 播种的旧快照——里面没有它。
于是旁白整轮不渲染。

**修复**：`speaker_switch` 改为**按后端 id 做 upsert**（本地没有就补一条带真实 id 的占位），
旁白行直接标 `complete`（后端落库时正文已完整）。

### 顺带修正的行为

- `useChatStream` 新增 `storyMode` 参数：剧情模式**不预建空占位**（消息行由后端建，
  否则多出一条填不满的空气泡），并在 `done` 时清掉仍为空的非旁白占位。
- 离线链路：剧情模式改用 `mockStoryStream`（含 `director`/`speaker_switch`/`node`/`actions`），
  否则演示页永远看不到导演裁决与行动建议。

### 验收结果

| 项 | 结果 |
|---|---|
| `/stories/:id` 可渲染，非空白 | PASS（smoke 412 字符，命中 `导演|旁白|行动`） |
| 多角色一轮渲染为多条独立气泡 | **PASS**（探针：气泡=2，名字=[苏晚、老周]） |
| 旁白渲染为居中样式，无角色头 | **PASS**（探针：`旁白未被串=true`） |
| 行动建议可点击并发出输入 | PASS（探针：行动建议=4） |
| 自由输入始终可用 | PASS（无建议时降级为纯输入框 + 明示文案） |
| `chat.generating` 时输入与建议均禁用 | PASS（`blocked` 同时约束两者） |
| 导演 `degraded=true` 有明确标识 | PASS（顶栏 Badge + 抽屉内显著告警块） |
| `tsc --noEmit` | **0 错误** |
| `node scripts/smoke.mjs` | **17 路由 + 3 探针全 PASS** |
| `npm run verify:sse` | PASS（11 事件三方同构） |
| `npm run verify:icons` | PASS（108 个） |
| `npm run build` | 成功（index 263.56 kB / gzip 76.64 kB） |
| 后端回归 | **402 passed, 44 skipped**（共收集 446；有 PG 时 446 passed, 0 skipped） · ruff All checks passed |
| 无 emoji 功能图标、无硬编码色值 | PASS（色位走 accent/info/success/warn 语义类） |

### 遗留 / 未验证

- **真实后端链路仍未跑过**：探针验证的是与后端同构的事件序列，
  真实 `POST /sessions/{id}/chat` 的 SSE 需要连上后端才能确认（属 S14 联调范围）。
- `GET /sessions/{id}/story` 的 `snapshot.scene.present` 语义按「在场角色」使用；
  若后端实际返回的 `present` 是「说话者」而非「在场者」，需在 S14 校正。

