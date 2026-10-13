# task-S13 · 会话列表集成（前端）

> 配套总纲：[`README.md`](./README.md) · 可独立领取 ⚠️（建议 S12 定下路由后再做）
> 独占文件：`frontend/src/pages/session-list.tsx`

---

## 目标

让**剧情会话**与 1v1 会话在同一个列表里共存且可区分，并给出一条**新建剧情**的入口。

产品决策是「**剧情入口复用会话列表**」——不新开导航层级。

---

## 交付物

| 文件 | 类型 | 说明 |
|---|---|---|
| `frontend/src/pages/session-list.tsx` | 修改 | **只改这一个页面** |
| `frontend/src/components/session/new-session-dialog.tsx` | 可能改 | 加「剧情模式」分支（选世界观） |
| `frontend/src/mocks/samples/sessions.ts` | 可能改 | 加一条剧情会话演示数据 |

> ⚠️ 若需改 `App.tsx`（加路由），**先与 S12 协调**，避免同文件冲突。

---

## 关键实现要点

### 1. 用 `spec` 区分两类会话

```ts
// api/types/session.ts 已导出
import { RPG_SPEC, STORY_SPEC } from '@/api/types';

const isStory = (s: Session) => s.spec === STORY_SPEC;
```

| spec | 标签 | 跳转 |
|---|---|---|
| `rpg_session` | 单人对话 | `/sessions/:id` |
| `story_session` | **剧情** | `/stories/:id`（S12 提供） |

### 2. 列表项展示

- 剧情会话加一枚 `Badge`（建议 `variant="accent"`，文字「剧情」）
- `session.world_id` 有值时，可显示世界观名（需查 `worldsApi`，或后端序列化时带上）
- 视觉上不要让两类会话割裂成两段——它们是同一种东西的两个模式

### 3. 新建入口

现有 `NewSessionDialog` 是「选角色卡 + 预设」。需要加一条**剧情分支**：

```
新建会话
  ├─ 单人对话   （现有逻辑：选卡 + 预设）
  └─ 剧情世界   （选世界观 → POST /sessions { world_id }）
```

**关键**：创建剧情会话时**必须传 `world_id`**，后端据此分派 `create_story_session()`：

```ts
sessionsApi.create({
  character_card_id: '',   // 剧情模式下由世界观的 cast 定义角色
  preset_id: '',           // 后端有默认
  world_id: selectedWorldId,
});
```

> ⚠️ 后端目前要求 `character_card_id` / `preset_id` 字段存在（沿用 1v1 表约束）。
> 若后端接受空串则直接可用；若校验失败，需同步放宽后端 schema（**改后端就要跑 pytest**）。

### 4. 筛选

可在现有 `status` 筛选旁加一个 `spec` 筛选：全部 / 单人 / 剧情。
若嫌重，可先只做**标签区分 + 跳转分派**，筛选留到后续迭代。

---

## 验收标准

- [ ] 剧情会话在列表中显示「剧情」标签
- [ ] 点击剧情会话跳 `/stories/:id`，1v1 跳 `/sessions/:id`
- [ ] 能从列表新建剧情会话（选世界观）
- [ ] 空状态不出现空白页
- [ ] `tsc --noEmit` 0 错误
- [ ] `node scripts/smoke.mjs` 全 PASS
- [ ] `npm run build` 成功

---

## 阻塞项

**轻度依赖 S12**：`/stories/:id` 路由由 S12 注册。若 S12 未完成，跳转目标会 404。

**处理方式**：
- 若 S12 已完成 → 直接做
- 若 S12 未完成 → 可以先做「标签区分 + 新建入口」，跳转先指向 `/stories/:id`（S12 完成后自然生效）
- **或**等 S12 完成后再开，避免在同一轮里改两次 `App.tsx`

---

## 交接记录

> 完成后填这里

**状态**：待领取（建议等 S12）
