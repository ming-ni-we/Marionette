# 06 · 剧情引擎设计规范

> 配套总纲：[`README.md`](./README.md) · 生成日期：2026-10-12 · 状态：**S1–S12 已实现并上线（2026-10-13），S13–S14 待做**

---

## 1. 产品意图

把平台从「**单角色 1v1 对话**」升级为「**AI 导演驱动的多角色剧情引擎**」。

玩家不再是「和一个人聊天」，而是**进入一个世界**：有多个角色、有彼此的关系、有正在推进的情节。
每次玩家输入后，**AI 导演**先裁决「这一幕该谁出场、说什么基调、要不要推进剧情」，再由各角色分别演出。

**已确认的产品决策**：

| 决策项 | 结论 |
|---|---|
| 与 1v1 的关系 | **并存**（不是替换） |
| LLM 成本 | 接受 **2x**（导演一次 + 各角色各一次） |
| 起点 | 从第二期开始（不回溯改造历史会话） |
| 导演权限 | **强控制 · 世界模拟器** |
| 世界观创建 | 手工表单（AI 生成留到第三期） |
| 台词呈现 | 群聊式 + 角色卡头 |
| 行动引导 | AI 生成多选项 + 自由输入 |
| 交付范围 | 一次性做到**可游玩** |
| 剧情入口 | 复用会话列表 |

---

## 2. 核心架构决策

### 2.1 模式切换：零迁移、零路由变更

```python
# 唯一开关：session.spec
RPG_SPEC   = "rpg_session"     # 既有 1v1
STORY_SPEC = "story_session"   # 剧情模式
```

`ChatSvc.stream_reply` 在 `assembling` 之后分派：

```python
if is_story_session(session_row):
    async for event in self._stream_story_round(...): yield event
    return
# 否则走原 1v1 路径（代码字节级不变）
```

**收益**：无需数据迁移、无需新路由、旧会话无感。

### 2.2 SSE 事件：超集设计

**1v1 是子集，剧情是超集。** 旧前端 `KNOWN_EVENTS` 不含新事件，收到即静默丢弃 → **零破坏**。

```
1v1 :  world_info → start → delta* → usage → (image?) → done
剧情:  world_info → director → start → (delta* | speaker_switch → delta*) → node? → usage → (image?) → actions → done
```

### 2.3 三处白名单必须同构

| # | 位置 | 内容 |
|---|---|---|
| 1 | `frontend/src/api/types/session.ts` | `SseEventMap` 的键（类型层） |
| 2 | `frontend/src/api/client/stream.ts` | `KNOWN_EVENTS` 数组（运行时层） |
| 3 | `backend/app/services/chat.py` | `EVT_*` 常量（发送方） |

**守卫**：`npm run verify:sse` 三者交叉比对，不一致退出码 1。

---

## 3. 状态模型

### 3.1 状态存放位置

| 位置 | 内容 |
|---|---|
| `state_machine.story` | `{node_id, pending_node, flags, director_failures, turn}` |
| `scene.present` | 在场角色 id 数组 |
| `scene.last_speaker_id` | 上一说话者 |
| `scene.beat` | 当前拍点计数 |
| `scene.{location,time,mood,summary}` | 从 world 播种 |
| `message.meta` | `{speaker_id, speaker_name, is_narration, beat_role, turn, story_node_id, direction, intent}` |
| `session.world_id` | 外键 → `worlds` |
| `extensions.story` | `{world_id, cast, relations, relations_version}` 固化快照 |

### 3.2 `StoryStateSvc` 契约

**纯状态读写，无 LLM、无 HTTP。**

- 所有 **getter 返回深拷贝**（调用方改不脏库）
- 所有 **writer 做增量合并**（PATCH 语义，不整体覆盖）
- **不 commit / flush**（事务归调用方）

关键方法：

| 方法 | 语义 |
|---|---|
| `is_story_session(row)` | 容忍 `None` / 缺 `spec` / 空串 |
| `get_story` / `get_relations` / `get_cast` / `get_scene_story` / `get_present` | 读 |
| `set_story` / `set_story_many` / `bump_turn` / `apply_flags` | 写 |
| `mark_director_success` / `mark_director_failure` / `is_director_circuit_open` / `reset_director_circuit` | 熔断 |
| `apply_relation_updates` | 按 `(from,to)` 增量 PATCH 关系图；边不存在则追加；`tension` 夹到 `[-1,1]` |
| `apply_scene_update` / `set_present` / `next_speaker_after` | 场景 |
| `bind_world` | 新建会话时固 cast/relations |

---

## 4. AI 导演 `director.py`

### 4.1 决策结构

```python
@dataclass(frozen=True)
class DirectorDecision:
    speakers: list[dict]          # 本轮出场角色
    narration: str                # 旁白（景/环境）
    scene_patch: dict             # 场景增量
    node_triggered: dict | None   # 触发的节点
    relation_updates: list[dict]  # 关系变化
    flags: dict                   # 剧情旗标
    reason: str                   # 为什么这样安排（透明性）
    degraded: bool                # 是否走了降级
```

### 4.2 ⚠️ 三层降级（永不抛异常）

```
L0  熔断检查：连续失败 ≥ 3 次 → 直接 fallback()，不再尝试
    ↓ 未熔断
L1  带 response_format={"type":"json_object"} 调用
    ↓ 解析失败（注意：是 parsed is None，不只是 raw is None）
L2  去掉 response_format 重试
    ↓ 仍失败
L3  fallback()：规则兜底，保证本轮一定有角色说话
```

**关键实现细节**：L1→L2 的触发条件是 **`parsed is None`**，而不是 `raw is None`。
因为最常见的失败不是端点报错，而是**端点接受了参数但返回散文而非 JSON**。
详见 [`04-pitfalls.md`](./04-pitfalls.md) D3。

### 4.3 JSON 提取（`_extract_json`）三级策略

1. 直接 `json.loads`
2. 剥掉 markdown 围栏 ` ```json ... ``` `
3. 切片找 `{`…`}`

### 4.4 常量

```python
_DIRECTOR_PARAMS = {"temperature": 0.4, "max_tokens": 512}
MAX_SPEAKERS = 3
DIRECTOR_FAILURE_THRESHOLD = 3
```

---

## 5. 行动建议 `action_suggester.py`

```python
TONES = frozenset({"observe", "speak", "act", "move"})
DEFAULT_COUNT = 3
MAX_COUNT = 4
_SUGGEST_PARAMS = {"temperature": 0.8, "max_tokens": 200}
```

**返回结构**：`[{id, label, hint, tone}]`
**契约**：**绝不抛异常**；失败返回 `[]`（`use_fallback=False`）或规则兜底（默认）。

**规则兜底**（`fallback_suggestions`）：不顾场景语义，只保证玩家**不会面对空的输入框**——
「仔细观察{地点}」/「开口问一句」/「说出你此刻的想法」/「离开{地点}」。

---

## 6. 序幕 `opening.py`

```
L1  模型生成（temperature 0.7, max_tokens 700）
    ↓ 失败
L2  fallback_from_card()：world.opening + card.first_mes
    ↓ 都为空
L3  fallback_template()：纯模板
```

**注意**：`OpeningSvc.generate()` **不写数据库**。它返回 drafts `[{role, content, meta}]`，
由 `SessionSvc.create_story_session()` 负责落库。

---

## 7. 上下文装配的 3 个新段

旧 9 段**字节级不变**（有专门测试 `TestOneVsOneInvariance` 断言，含 prompt 文本指纹）。

| 段 | 预算占比 | 裁剪策略 |
|---|---|---|
| `story_state` | 8% | **永不因零预算丢弃**，硬截断 400 token |
| `relations` | 6% | 与当前说话者相关的子图，按 tension 降序截断 |
| `cast_roster` | 5% | 在场角色一行摘要 |

新段**仅在非空时追加**。`budget` 新增 `story_tokens` / `relations_tokens` / `cast_tokens`。

### ⚠️ 前端耦合

新增段名必须同步 `context-inspection.tsx` 的 `SEGMENT_LABEL`（`Record<ContextSegmentName, string>`），
否则 **TS 编译失败**。

---

## 8. 一轮剧情的完整时序

```
玩家输入
  │
  ├─ 1. assembling 状态
  ├─ 2. 载入 world / cast / relations / history
  ├─ 3. 调导演（含降级）
  ├─ 4. 应用 decision：scene_patch / flags / relation_updates / node
  ├─ 5. emit world_info          （与 1v1 同结构）
  ├─ 6. emit director            （含 degraded 标记）
  ├─ 7. 解析 speakers（空 → 退化为「在场首位」纯旁白）
  ├─ 8. emit start（message_id=""，允许空）
  ├─ 9. generating 状态
  ├─ 10. 若有 narration → 落旁白消息 → emit speaker_switch(is_narration=true)
  ├─ 11. 对每个 speaker：
  │       ├─ emit speaker_switch（首个除外）
  │       ├─ 建占位消息行
  │       ├─ 流式生成 → emit delta*
  │       └─ 更新消息为 complete
  ├─ 12. 若节点触发 → emit node
  ├─ 13. post_processing → idle；turn+1
  ├─ 14. emit usage
  ├─ 15. 出图钩子 → emit image?
  ├─ 16. 生成行动建议 → emit actions?
  └─ 17. emit done

异常路径 → _finalize_incomplete()
             ├─ 扫掉所有 streaming 残留（置 incomplete）
             └─ _force_idle()（绕过迁移表！）
```

### 关键不变量

| 不变量 | 说明 |
|---|---|
| **N 个说话者 = N 条消息** | 不预建占位行（否则多一条空消息） |
| **无 streaming 残留** | 中断/异常后库里不得留下 `status="streaming"` |
| **1v1 路径不碰剧情代码** | 测试用「炸弹」`_FakeDirectorSvc` 证明 |

---

## 9. 世界观数据模型

`worlds` 表字段**摊平**（不包 `data`），因为导演需按维度独立读写：

```jsonc
{
  "title": "旧城区 · 拆迁前三十天",
  "setting": {
    "era": "近未来的沿海旧城区，雨季",
    "tone": "潮湿、压抑，但偶尔有微光",
    "summary": "一句话总览（同时是新建会话的场景摘要）",
    "locations": ["未名书店", "旧码头"],
    "rules": ["没有超自然力量", "拆迁公告具有法律效力"]
  },
  "factions": [{ "id": "f1", "name": "拆迁办", "stance": "中立" }],
  "cast": [{
    "id": "c1",              // ⚠️ 剧情内主键：speaker_id / 关系图都引用它
    "name": "苏晚",
    "role": "主角",
    "voice": "话少，句子短",   // 说话风格（供导演写台词对齐语气）
    "goals": ["找到账本"],
    "description": "书店掌柜",
    "card_id": null          // 可选：关联已有角色卡
  }],
  "relations": [{
    "from": "c1",            // ⚠️ JSON 里是 from，Python 里是 from_
    "to": "c2",
    "kind": "旧识",
    "tension": 0.5,          // [-1,1]，负=敌意，正=亲密
    "note": "老周看着苏晚长大"
  }],
  "outline": {
    "main_goal": "在动工前查清父亲失踪那晚发生了什么",
    "nodes": [{
      "id": "n1",
      "title": "雨夜的第一封信",
      "brief": "触发时该发生什么",
      "trigger": "玩家主动翻找书店的旧物"   // 自然语言，由导演判断
    }],
    "endings": ["真相被揭开，但代价是失去这间书店"]
  },
  "opening": "序幕文本（模型不可用时的兜底底本）",
  "tags": ["悬疑", "现代", "群像"]
}
```

**`cast[].id` 是整个引擎的主键**：`meta.speaker_id`、关系图两端、`scene.present` 全部引用它。
前端用 `nextEntityId('c', existing)` 分配 `c1`/`c2`…。

---

## 10. API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/worlds` | 列表（支持 `q` / `tags` / 分页） |
| POST | `/worlds` | 创建（201） |
| GET | `/worlds/{worldId}` | 详情 |
| PATCH | `/worlds/{worldId}` | 部分更新 |
| DELETE | `/worlds/{worldId}` | 删除（sessions.world_id 走 SET NULL） |
| GET | `/sessions/{sessionId}/story` | 剧情快照 `{spec, is_story, world_id, story, scene, cast, relations}` |
| GET | `/sessions/{sessionId}/actions` | 行动建议（1v1 返回 `[]`） |

**创建剧情会话**：`POST /sessions` 带 `world_id` → 后端分派 `create_story_session()`。

---

## 11. S12 需要注意的接口细节

前端剧情演出页要用到的：

| 事件 | 前端应做什么 |
|---|---|
| `director` | 清空上轮残留（`nodes`/`suggestions`/`activeSpeaker`）；存 `speakers` 与 `lastDecision` |
| `speaker_switch` | `message_id` **有值** → 后端已建行，前端直接用；**无值** → 前端补一条空占位，否则随后 `delta` 无处可落 |
| `delta` | 带 `speaker_id` → **按 speaker_id 反查目标气泡**（不能只往最后一条追加，见 D7） |
| `node` | 累加进 `nodes`，弹横幅 |
| `actions` | 替换 `suggestions` |
| `done` | 把**所有仍为 streaming 的消息**收口（不只最后一条） |

`start.message_id` 在剧情模式**允许为空串**，这是合法契约。

### 状态机标签

`use-chat-stream.ts` 已暴露：`speakers` / `activeSpeaker` / `nodes` / `suggestions` / `lastDecision`
/ `setSuggestions` / `setActiveSpeaker` / `setStorySnapshot`。

**S12 可直接复用 `useChatStream`**，不必重写流式逻辑。
